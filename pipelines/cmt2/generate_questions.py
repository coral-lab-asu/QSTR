import os
import re
import json
import glob
import uuid
import math
import random
import argparse
import importlib.util
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import duckdb


# -----------------------------
# Query analysis + row index extraction (for downstream analysis)
# -----------------------------

def compress_indices_to_ranges(idxs: List[int]) -> str:
    if not idxs:
        return ""
    s = sorted(idxs)
    out = []
    start = prev = s[0]
    for v in s[1:]:
        if v == prev + 1:
            prev = v
            continue
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = v
    out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(out)


def _strip_qualifiers(name: str) -> str:
    return name.split(".")[-1].strip().strip('"').strip('`').strip('[').strip(']')


def _normalize_positions(df: pd.DataFrame, idx_list: List[Any]) -> List[float]:
    """Return normalized positions in [0,1] using positional index (0..N-1)/(N-1)."""
    N = len(df)
    if N <= 1:
        return [0.0 for _ in idx_list]
    pos = df.index.get_indexer(idx_list)
    pos = [int(p) for p in pos if p >= 0]
    denom = float(N - 1)
    return [p / denom for p in pos]


def analyze_query(query: str, allowed_columns: Optional[set] = None) -> Dict[str, Any]:
    """Lightweight SQL analysis for downstream metrics.

    Extracts:
      - where_text
      - arithmetic_functions
      - hop_count / is_multihop
      - entity_target (batsman/bowler/both/unknown)
      - columns_targeted (restricted to allowed_columns if provided)
    """
    analysis: Dict[str, Any] = {}

    # WHERE text (for debugging)
    m = re.search(r"\bWHERE\b\s+(.+?)(\bGROUP BY\b|\bHAVING\b|\bORDER BY\b|;|$)", query, flags=re.I | re.S)
    analysis["where_text"] = m.group(1).strip() if m else None

    # functions (scan whole query)
    funcs = re.findall(r"\b(SUM|AVG|COUNT|MIN|MAX|ROUND|ABS|COALESCE|CAST)\b", query, flags=re.I)
    analysis["arithmetic_functions"] = sorted(set(f.upper() for f in funcs)) if funcs else []

    # hop count: nested SELECTs (except the outermost) + JOINs
    num_selects = len(re.findall(r"\bSELECT\b", query, flags=re.I))
    analysis["hop_count"] = max(0, num_selects - 1) + len(re.findall(r"\bJOIN\b", query, flags=re.I))
    analysis["is_multihop"] = bool(analysis["hop_count"] > 0)

    # entity
    has_batsman = re.search(r"\bbatsman\b", query, flags=re.I) is not None
    has_bowler = re.search(r"\bbowler\b", query, flags=re.I) is not None
    analysis["entity_target"] = "both" if (has_batsman and has_bowler) else (
        "batsman" if has_batsman else ("bowler" if has_bowler else "unknown")
    )

    # columns targeted: scan SELECT/WHERE/GROUP BY/HAVING/ORDER BY
    frags: List[str] = []
    for pat in [
        r"\bSELECT\b\s+(.+?)\s+\bFROM\b",
        r"\bWHERE\b\s+(.+?)(?=\bGROUP BY\b|\bHAVING\b|\bORDER BY\b|;|$)",
        r"\bGROUP BY\b\s+(.+?)(?=\bHAVING\b|\bORDER BY\b|;|$)",
        r"\bHAVING\b\s+(.+?)(?=\bORDER BY\b|;|$)",
        r"\bORDER BY\b\s+(.+?)(?=;|$)",
    ]:
        for mm in re.finditer(pat, query, flags=re.I | re.S):
            frags.append(mm.group(1))

    cols: List[str] = []
    drop = set(x.lower() for x in [
        "sum", "avg", "count", "min", "max", "round", "abs", "coalesce", "cast", "as", "distinct"
    ])
    for frag in frags:
        for n in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", frag):
            base = _strip_qualifiers(n)
            if base.lower() in drop or base.isnumeric():
                continue
            if allowed_columns is None:
                cols.append(base)
            else:
                if base in allowed_columns:
                    cols.append(base)

    analysis["columns_targeted"] = sorted(set(cols))
    return analysis


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _to_number_if_possible(s: str):
    try:
        return float(s)
    except Exception:
        return s


def _parse_list_items(s: str) -> List[Any]:
    items = [i.strip() for i in s.split(",")]
    out: List[Any] = []
    for it in items:
        it = _strip_quotes(it)
        it = _to_number_if_possible(it)
        out.append(it)
    return out


def _safe_col(df: pd.DataFrame, col: str) -> Optional[str]:
    base = col.split(".")[-1].strip()
    return base if base in df.columns else None


def _like_to_regex(pat: str) -> str:
    return "^" + pat.replace("%", ".*").replace("_", ".") + "$"


def _atom_mask(df: pd.DataFrame, atom: str) -> pd.Series:
    atom = atom.strip()

    m = re.match(r"^([\w\.]+)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)$", atom, flags=re.I)
    if m:
        col, a, b = m.groups()
        col = _safe_col(df, col)
        if not col:
            return pd.Series(True, index=df.index)
        a = _to_number_if_possible(_strip_quotes(a))
        b = _to_number_if_possible(_strip_quotes(b))
        return (df[col] >= a) & (df[col] <= b)

    m = re.match(r"^([\w\.]+)\s+IN\s*\((.+)\)$", atom, flags=re.I)
    if m:
        col, items = m.groups()
        col = _safe_col(df, col)
        if not col:
            return pd.Series(True, index=df.index)
        values = _parse_list_items(items)
        return df[col].isin(values)

    m = re.match(r"^([\w\.]+)\s+LIKE\s+('.*'|\".*\")$", atom, flags=re.I)
    if m:
        col, pat = m.groups()
        col = _safe_col(df, col)
        if not col:
            return pd.Series(True, index=df.index)
        pat = _strip_quotes(pat)
        regex = _like_to_regex(pat)
        return df[col].astype(str).str.contains(regex, regex=True, na=False)

    m = re.match(r"^([\w\.]+)\s*(=|!=|<>|<=|<|>=|>)\s*(.+)$", atom)
    if m:
        col, op, rhs = m.groups()
        col = _safe_col(df, col)
        if not col:
            return pd.Series(True, index=df.index)
        rhs_v = _to_number_if_possible(_strip_quotes(rhs))
        s = df[col]
        if op == "=":
            return s == rhs_v
        if op in ("!=", "<>"):
            return s != rhs_v
        if op == "<":
            return s < rhs_v
        if op == "<=":
            return s <= rhs_v
        if op == ">":
            return s > rhs_v
        if op == ">=":
            return s >= rhs_v

    return pd.Series(True, index=df.index)


def _where_to_mask(df: pd.DataFrame, where: str) -> pd.Series:
    # Very lightweight parsing: split OR then AND
    where_norm = re.sub(r"\s+", " ", where.strip())
    or_parts = re.split(r"\s+OR\s+", where_norm, flags=re.I)
    masks: List[pd.Series] = []
    for part in or_parts:
        and_parts = re.split(r"\s+AND\s+", part, flags=re.I)
        m = pd.Series(True, index=df.index)
        for atom in and_parts:
            m = m & _atom_mask(df, atom)
        masks.append(m)
    out = masks[0].copy() if masks else pd.Series(True, index=df.index)
    for mm in masks[1:]:
        out = out | mm
    return out


def _extract_outer_block(query: str, table_name: str):
    q = query.strip()
    from_pat = re.compile(r"\bFROM\b\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+[A-Za-z_][A-Za-z0-9_]*)?", flags=re.I)
    matches = list(from_pat.finditer(q))

    outer_from = None
    for m in reversed(matches):
        base = m.group(1)
        if base.lower() == table_name.lower():
            outer_from = m
            break
    if not outer_from:
        outer_from = matches[-1] if matches else None
    if not outer_from:
        return None, None, []

    tail = q[outer_from.start():]

    wm = re.search(r"\bWHERE\b\s+(.+?)(\bGROUP BY\b|\bHAVING\b|\bORDER BY\b|;|$)", tail, flags=re.I | re.S)
    where_sql = wm.group(1).strip() if wm else None

    gm = re.search(r"\bGROUP BY\b\s+(.+?)(\bHAVING\b|\bORDER BY\b|;|$)", tail, flags=re.I | re.S)
    groupby_cols: List[str] = []
    if gm:
        raw = gm.group(1).strip()
        groupby_cols = [_strip_qualifiers(x.strip()) for x in raw.split(",")]

    return tail, where_sql, groupby_cols


def extract_row_indices_from_query(
    query: str,
    df: pd.DataFrame,
    result_df: Optional[pd.DataFrame],
    table_name: str = "df",
) -> Dict[str, Any]:
    """Approximate scanned/contributing row indices based on outer WHERE/GROUP BY."""
    _, where_sql, groupby_cols = _extract_outer_block(query, table_name)

    # scanned rows
    if where_sql:
        mask_scanned = _where_to_mask(df, where_sql)
    else:
        mask_scanned = pd.Series(True, index=df.index)
    scanned_idx = df.index[mask_scanned].tolist()

    # contributing rows: for GROUP BY queries, approximate by keeping rows whose group keys survive
    if groupby_cols and result_df is not None and not result_df.empty:
        gcols_df = [c for c in groupby_cols if c in df.columns]
        gcols_res = [c for c in groupby_cols if c in result_df.columns]
        gcols = [c for c in gcols_df if c in gcols_res]
        if gcols:
            df_scanned = df.loc[mask_scanned, gcols]
            surviving = result_df[gcols].drop_duplicates()
            scanned_keys = list(map(tuple, df_scanned[gcols].itertuples(index=False, name=None)))
            surviving_set = set(map(tuple, surviving[gcols].itertuples(index=False, name=None)))
            contrib_mask = pd.Series([k in surviving_set for k in scanned_keys], index=df_scanned.index)
            contributing_idx = contrib_mask[contrib_mask].index.tolist()
        else:
            contributing_idx = scanned_idx
    else:
        contributing_idx = scanned_idx

    return {
        "row_indices_scanned": scanned_idx,
        "row_indices_contributing": contributing_idx,
        "row_indices_scanned_normalized": _normalize_positions(df, scanned_idx),
        "row_indices_contributing_normalized": _normalize_positions(df, contributing_idx),
        "row_indices_scanned_ranges": compress_indices_to_ranges(scanned_idx),
        "row_indices_contributing_ranges": compress_indices_to_ranges(contributing_idx),
    }


# -----------------------------
# Helpers: IO
# -----------------------------
def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# -----------------------------
# Helpers: formatting / normalization
# -----------------------------
def truncate_text(s: str, max_chars: int) -> str:
    if max_chars is None or max_chars <= 0:
        return s
    return s if len(s) <= max_chars else s[:max_chars] + " ..."

def normalize_cell(x):
    if x is None:
        return None
    if isinstance(x, (np.floating, float)):
        if np.isnan(x):
            return None
        return float(x)
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (pd.Timestamp,)):
        return x.isoformat()
    return x

def df_to_answer_json(df: pd.DataFrame, max_rows: Optional[int] = None) -> Dict[str, Any]:
    out = df.copy()
    if max_rows is not None and max_rows > 0 and len(out) > max_rows:
        out = out.head(max_rows)
    cols = [str(c) for c in out.columns.tolist()]
    rows = [[normalize_cell(v) for v in row] for row in out.to_numpy().tolist()]
    return {"columns": cols, "rows": rows}

def is_zeroish_result(df: pd.DataFrame) -> bool:
    """Empty OR all numeric columns are 0/NaN and non-numeric columns are empty/NaN."""
    if df is None or df.shape[0] == 0:
        return True
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            s2 = s.replace([np.inf, -np.inf], np.nan)
            if (s2.fillna(0) != 0).any():
                return False
        else:
            if s.dropna().astype(str).str.strip().ne("").any():
                return False
    return True

def sql_literal(v: Any) -> str:
    """
    Convert a python value into a SQL literal safely for DuckDB.
    Strings get single-quoted and escaped.
    None -> NULL
    """
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        if np.isnan(v):
            return "NULL"
        # keep decimal representation
        return str(float(v))
    if isinstance(v, (pd.Timestamp,)):
        s = v.isoformat()
        s = s.replace("'", "''")
        return f"'{s}'"
    # default: string-like
    s = str(v)
    s = s.replace("'", "''")
    return f"'{s}'"

# -----------------------------
# SQL param formatting helpers
# -----------------------------
def _escape_sql_string(s: str) -> str:
    """Escape single quotes for SQL string literals."""
    return str(s).replace("'", "''")


def build_params_sql(sql_template: str, params_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Build params for formatting SQL.

    This pipeline standardizes SQL templates to use unquoted placeholders like {bowler}/{batsman}.
    Therefore we always provide proper SQL literals (quoted/escaped) for non-snippet params.

    - temporal_predicate is a SQL snippet and is passed through as-is.
    - table_name is passed through as-is.
    """
    out = dict(params_raw)

    for k, v in list(out.items()):
        if k == "table_name":
            continue
        if k == "temporal_predicate":
            continue
        out[k] = sql_literal(v)

    return out


def normalize_sql_template_placeholders(sql_template: str) -> str:
    """Convert quoted placeholders like '{batsman}' or "{batsman}" into unquoted {batsman}.

    The runtime formatting/parameter injection expects unquoted placeholders, and we provide SQL literals
    (already quoted/escaped) via `sql_literal`. Therefore, any placeholders that are already wrapped
    in single/double quotes would lead to double-quoting like ''Kohli''.

    We normalize *all* quoted placeholders except for special snippet params.

    Notes:
      - `table_name` is an identifier/snippet and is intentionally left untouched.
      - `temporal_predicate` is a SQL snippet and is intentionally left untouched.
    """
    if not isinstance(sql_template, str):
        return sql_template

    # Unquote any single-quoted placeholder e.g. '{batsman}' -> {batsman}
    # Skip special snippet params.
    sql_template = re.sub(
        r"'\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*'",
        lambda m: m.group(0) if m.group(1) in {"table_name", "temporal_predicate"} else "{" + m.group(1) + "}",
        sql_template,
    )

    # Unquote any double-quoted placeholder e.g. "{batsman}" -> {batsman}
    sql_template = re.sub(
        r"\"\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*\"",
        lambda m: m.group(0) if m.group(1) in {"table_name", "temporal_predicate"} else "{" + m.group(1) + "}",
        sql_template,
    )

    return sql_template

def safe_format(template: str, params: Dict[str, Any]) -> str:
    """template.format(**params) with clear error."""
    try:
        return template.format(**params)
    except KeyError as e:
        raise KeyError(f"Missing placeholder {e} for template: {template[:200]} ...")


# -----------------------------
# Commentary context builder
# -----------------------------
def build_context_from_df(
    df: pd.DataFrame,
    commentary_col: str = "commentary",
    overs_col: str = "overs",
    include_overs: bool = False,
    max_chars: int = 6000,
) -> str:
    """Build a text context from commentary.

    If include_overs=True and `overs_col` exists, prefix each commentary line with its over value.
    Example line: "12.3 | Some commentary..."

    Truncation is applied after joining.
    """
    if commentary_col not in df.columns:
        return ""

    if include_overs and overs_col in df.columns:
        # Keep alignment between overs and commentary by iterating rows.
        lines: List[str] = []
        for _, row in df[[overs_col, commentary_col]].iterrows():
            comm = row.get(commentary_col)
            if pd.isna(comm):
                continue
            over_val = row.get(overs_col)
            if pd.isna(over_val):
                lines.append(str(comm))
            else:
                lines.append(f"{over_val} | {comm}")
        ctx = "\n".join(lines)
        return truncate_text(ctx, max_chars=max_chars)

    # Default: commentary only
    lines = df[commentary_col].dropna().astype(str).tolist()
    ctx = "\n".join(lines)
    return truncate_text(ctx, max_chars=max_chars)


# -----------------------------
# Context builder for a subset of rows (e.g., rows_scanned)
# -----------------------------
def build_context_from_df_rows(
    df: pd.DataFrame,
    row_indices: List[Any],
    commentary_col: str = "commentary",
    overs_col: str = "overs",
    include_overs: bool = False,
    max_chars: int = 6000,
) -> str:
    """Build context text from only the specified row indices.

    This is useful to create a context focused on `rows_scanned` (or contributing rows).

    - If include_overs=True and overs_col exists, each line becomes: "<overs> | <commentary>".
    - Truncation is applied after joining.
    """
    if not row_indices:
        return ""
    if commentary_col not in df.columns:
        return ""

    # Keep only valid indices that exist in df.index
    try:
        # df.index can be RangeIndex or other; intersection keeps order if we sort.
        valid = [i for i in row_indices if i in df.index]
    except Exception:
        valid = row_indices

    if not valid:
        return ""

    sub = df.loc[valid]
    # Ensure deterministic order by row position
    try:
        sub = sub.sort_index()
    except Exception:
        pass

    if include_overs and overs_col in sub.columns:
        lines: List[str] = []
        for _, row in sub[[overs_col, commentary_col]].iterrows():
            comm = row.get(commentary_col)
            if pd.isna(comm):
                continue
            over_val = row.get(overs_col)
            if pd.isna(over_val):
                lines.append(str(comm))
            else:
                lines.append(f"{over_val} | {comm}")
        ctx = "\n".join(lines)
        return truncate_text(ctx, max_chars=max_chars)

    lines = sub[commentary_col].dropna().astype(str).tolist()
    ctx = "\n".join(lines)
    return truncate_text(ctx, max_chars=max_chars)

# -----------------------------
# ROI bucket helpers (overs-based regions of interest)
# -----------------------------
ROI_BUCKETS = ["entire", "first_half", "middle", "second_half"]

def _safe_float_series(s: pd.Series) -> pd.Series:
    """Convert overs to float when possible; drop NaNs."""
    try:
        return pd.to_numeric(s, errors="coerce")
    except Exception:
        return s.astype(float)

def compute_entity_roi_buckets(
    df: pd.DataFrame,
    entity_col: str,
    overs_col: str = "overs",
    *,
    entire_min_thresh: float = 0.10,
    entire_max_thresh: float = 0.90,
    middle_lo: float = 0.25,
    middle_hi: float = 0.75,
) -> Dict[str, List[str]]:
    """
    Bucket entities by where they appear across the match overs timeline using normalized overs:
      o_norm = (over - min_over) / (max_over - min_over)

    Buckets:
      - entire: spans near the whole match (min_norm <= 0.10 and max_norm >= 0.90)
      - first_half: appears only early (max_norm <= 0.5)
      - second_half: appears only late  (min_norm >= 0.5)
      - middle: confined to middle window (min_norm>=0.25 and max_norm<=0.75)
    """
    out: Dict[str, List[str]] = {b: [] for b in ROI_BUCKETS}
    if entity_col not in df.columns or overs_col not in df.columns:
        return out

    overs = _safe_float_series(df[overs_col]).dropna()
    if overs.empty:
        return out

    o_min = float(overs.min())
    o_max = float(overs.max())
    denom = (o_max - o_min)
    if denom <= 1e-9:
        return out

    work = df[[entity_col, overs_col]].copy()
    work[overs_col] = _safe_float_series(work[overs_col])
    work = work.dropna(subset=[entity_col, overs_col])
    if work.empty:
        return out

    work["_o_norm"] = (work[overs_col] - o_min) / denom
    g = work.groupby(entity_col)["_o_norm"].agg(["min", "max"]).reset_index()

    for _, row in g.iterrows():
        ent = str(row[entity_col])
        mn = float(row["min"])
        mx = float(row["max"])

        if mn <= entire_min_thresh and mx >= entire_max_thresh:
            out["entire"].append(ent)
        if mx <= 0.5:
            out["first_half"].append(ent)
        if mn >= 0.5:
            out["second_half"].append(ent)
        if mn >= middle_lo and mx <= middle_hi:
            out["middle"].append(ent)

    # de-dup preserve order
    for k in list(out.keys()):
        seen = set()
        dedup: List[str] = []
        for v in out[k]:
            if v in seen:
                continue
            seen.add(v)
            dedup.append(v)
        out[k] = dedup

    return out

def pick_roi_bucket(rng: random.Random, mode: str, rr_state: Dict[str, int], key: str) -> str:
    """Pick an ROI bucket via random or round-robin (per key)."""
    if mode == "round_robin":
        i = rr_state.get(key, 0)
        rr_state[key] = i + 1
        return ROI_BUCKETS[i % len(ROI_BUCKETS)]
    return rng.choice(ROI_BUCKETS)


# -----------------------------
# Temporal predicate sampling (optional)
# -----------------------------
def snap_over_ball(x: float, one_to_six: bool = True) -> float:
    O = math.floor(x)
    ball = int(math.floor((x - O) * 10 + 1e-9))
    if one_to_six:
        if ball < 1:
            ball = 1
        if ball > 6:
            O += 1
            ball = 1
    else:
        if ball < 0:
            ball = 0
        if ball > 5:
            O += 1
            ball = 0
    return float(f"{O}.{ball}")

def pick_relation(rng: random.Random) -> str:
    return rng.choice(["before", "after", "before_or_at", "after_or_at", "between", "overlaps"])

def build_temporal_with_phrase(
    relation: Optional[str],
    x1: Optional[float],
    x2: Optional[float],
    field: str = "overs",
    rng: Optional[random.Random] = None,
    one_to_six: bool = True,
    distinct: bool = True,
) -> Tuple[str, str, Optional[str]]:
    """
    Returns: (sql_predicate, nl_phrase, relation_used)
    If relation is None -> returns (1=1, 'the entire match', None)
    """
    if rng is None:
        rng = random.Random()

    if not relation or str(relation).lower() == "none" or x1 is None or x2 is None:
        return "(1=1)", "the entire match", None

    lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)

    p1 = snap_over_ball(rng.uniform(lo, hi), one_to_six=one_to_six)
    p2 = snap_over_ball(rng.uniform(lo, hi), one_to_six=one_to_six)
    if distinct and p1 == p2:
        p2 = snap_over_ball(rng.uniform(lo, hi), one_to_six=one_to_six)
    b1, b2 = tuple(sorted((p1, p2)))

    a = field
    r = str(relation).lower()

    sql_map = {
        "before":        f"({a} < {b1})",
        "after":         f"({a} > {b2})",
        "before_or_at":  f"({a} <= {b1})",
        "after_or_at":   f"({a} >= {b2})",
        "between":       f"({a} BETWEEN {b1} AND {b2})",
        "overlaps":      f"({a} <= {b2} AND {b1} <= {a})",
    }
    nl_map = {
        "before":        f"when over is before {b1}",
        "after":         f"when over is after {b2}",
        "before_or_at":  f"when over is at or before {b1}",
        "after_or_at":   f"when over is at or after {b2}",
        "between":       f"when over is between {b1} and {b2}",
        "overlaps":      f"when over falls between {b1} and {b2}",
    }
    if r not in sql_map:
        return "(1=1)", "the entire match", None

    return sql_map[r], nl_map[r], r


# -----------------------------
# SQL execution
# -----------------------------
def execute_sql_on_df(df: pd.DataFrame, sql: str, table_name: str = "df") -> pd.DataFrame:
    con = duckdb.connect(database=":memory:")
    con.register(table_name, df)
    try:
        return con.execute(sql).fetchdf()
    finally:
        try:
            con.close()
        except Exception:
            pass


# -----------------------------
# Param sampling based on template variables
# -----------------------------
def sample_params_for_template(
    df: pd.DataFrame,
    variables: List[str],
    rng: random.Random,
    *,
    roi_stratify: bool = False,
    roi_bucket_mode: str = "random",
    roi_rr_state: Optional[Dict[str, int]] = None,
    roi_buckets_cache: Optional[Dict[str, Dict[str, List[str]]]] = None,
) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any] = {"table_name": "df"}

    batsmen = df["batsman"].dropna().unique().tolist() if "batsman" in df.columns else []
    bowlers = df["bowler"].dropna().unique().tolist() if "bowler" in df.columns else []
    overs = df["overs"].dropna().tolist() if "overs" in df.columns else []

    if roi_rr_state is None:
        roi_rr_state = {}
    if roi_buckets_cache is None:
        roi_buckets_cache = {}

    def _get_buckets(col: str) -> Dict[str, List[str]]:
        if col in roi_buckets_cache:
            return roi_buckets_cache[col]
        roi_buckets_cache[col] = compute_entity_roi_buckets(df, col, overs_col="overs")
        return roi_buckets_cache[col]

    def _pick_from_bucket(col: str, fallback_list: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Return (chosen_value, bucket_label)."""
        if not roi_stratify:
            return (rng.choice(fallback_list) if fallback_list else None), None

        buckets = _get_buckets(col)
        bucket = pick_roi_bucket(rng, roi_bucket_mode, roi_rr_state, key=col)
        cands = buckets.get(bucket) or []
        if cands:
            return rng.choice(cands), bucket

        # fallback: any bucket that has candidates
        for b in ROI_BUCKETS:
            if buckets.get(b):
                return rng.choice(buckets[b]), b

        return (rng.choice(fallback_list) if fallback_list else None), None

    # batsman
    if "batsman" in variables:
        if not batsmen:
            return None
        b, b_bucket = _pick_from_bucket("batsman", batsmen)
        if b is None:
            return None
        params["batsman"] = b
        params["roi_bucket_batsman"] = b_bucket

    # bowler
    if "bowler" in variables:
        if not bowlers:
            return None

        # prefer bowlers that the selected batsman faced
        if "batsman" in params and "batsman" in df.columns and "bowler" in df.columns:
            sub = df[df["batsman"] == params["batsman"]]
            faced = sub["bowler"].dropna().unique().tolist()
            faced = [str(x) for x in faced]

            if faced:
                if roi_stratify and "overs" in sub.columns:
                    tmp = sub[["bowler", "overs"]].copy()
                    tmp["bowler"] = tmp["bowler"].astype(str)
                    buckets = compute_entity_roi_buckets(tmp, "bowler", overs_col="overs")
                    bucket = pick_roi_bucket(rng, roi_bucket_mode, roi_rr_state, key="bowler")
                    cands = buckets.get(bucket) or []
                    if cands:
                        params["bowler"] = rng.choice(cands)
                        params["roi_bucket_bowler"] = bucket
                    else:
                        params["bowler"] = rng.choice(faced)
                        params["roi_bucket_bowler"] = None
                else:
                    params["bowler"] = rng.choice(faced)
                    params["roi_bucket_bowler"] = None
            else:
                w, w_bucket = _pick_from_bucket("bowler", bowlers)
                if w is None:
                    return None
                params["bowler"] = w
                params["roi_bucket_bowler"] = w_bucket
        else:
            w, w_bucket = _pick_from_bucket("bowler", bowlers)
            if w is None:
                return None
            params["bowler"] = w
            params["roi_bucket_bowler"] = w_bucket

    # bowler1 / bowler2
    if "bowler1" in variables or "bowler2" in variables:
        if not bowlers:
            return None
        if len(bowlers) == 1:
            b1 = bowlers[0]
            b2 = bowlers[0]
        else:
            b1, b2 = rng.sample(bowlers, 2)
        if "bowler1" in variables:
            params["bowler1"] = b1
            params["roi_bucket_bowler1"] = None
        if "bowler2" in variables:
            params["bowler2"] = b2
            params["roi_bucket_bowler2"] = None

    # temporal_predicate
    if "temporal_predicate" in variables:
        if len(overs) < 2:
            params["temporal_predicate"] = "(1=1)"
            params["temporal_phrase"] = "the entire match"
            params["temporal_relation"] = None
        else:
            sub = df
            if "batsman" in params and "batsman" in df.columns:
                sub = sub[sub["batsman"] == params["batsman"]]
            if "bowler" in params and "bowler" in df.columns:
                sub = sub[sub["bowler"] == params["bowler"]]

            sub_overs = sub["overs"].dropna().tolist() if "overs" in sub.columns else []
            if len(sub_overs) >= 2:
                x1, x2 = min(sub_overs), max(sub_overs)
            else:
                x1, x2 = tuple(sorted(rng.sample(overs, 2)))

            rel = pick_relation(rng)
            pred, phrase, rel_used = build_temporal_with_phrase(rel, x1, x2, field="overs", rng=rng)
            params["temporal_predicate"] = pred
            params["temporal_phrase"] = phrase
            params["temporal_relation"] = rel_used

    return params



# -----------------------------
# Template loader
# -----------------------------
def _load_templates_one(path: str) -> List[Dict[str, Any]]:
    """Load templates from a single file path (.json/.py)."""
    p = Path(path)

    if p.suffix.lower() == ".py":
        spec = importlib.util.spec_from_file_location(p.stem, str(p))
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not import template module from: {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]

        if not hasattr(mod, "question_templates"):
            raise ValueError(f"Python template file must define `question_templates` list: {path}")

        raw = getattr(mod, "question_templates")
        if not isinstance(raw, list):
            raise ValueError(f"`question_templates` must be a list in: {path}")

        mapped: List[Dict[str, Any]] = []
        for t in raw:
            if not isinstance(t, dict):
                continue
            mapped.append({
                "template_id": t.get("template_id", t.get("id")),
                "item_id": t.get("item_id", t.get("id")),
                "question": t.get("question", ""),
                "paraphrases": t.get("paraphrases") or [],
                # In the python file the field is `query`
                "sql": t.get("sql") or t.get("query"),
                "original_sql": t.get("original_sql"),
                "description": t.get("description") or t.get("exp"),
                "variables": t.get("variables") or [],
                "primary_key": t.get("primary_key"),
                "intent": t.get("intent"),
                "structure": t.get("structure"),
            })
        return mapped

    # Default: JSON
    data = read_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "final" in data and isinstance(data["final"], list):
        return data["final"]
    raise ValueError(f"Template JSON must be a list, or a dict with key 'final' as a list. Got: {type(data)} in {path}")


def load_templates(paths: Any) -> List[Dict[str, Any]]:
    """Load and merge templates from one or more files.

    Supports:
      - a single string path
      - a comma-separated string of paths
      - a list/tuple of paths (recommended; used by CLI nargs='+')

    Returns a single merged list.
    """
    # Normalize input -> list[str]
    if isinstance(paths, (list, tuple)):
        path_list = [str(x).strip() for x in paths if str(x).strip()]
    elif isinstance(paths, str):
        # allow comma-separated
        path_list = [p.strip() for p in paths.split(",") if p.strip()]
    else:
        raise TypeError(f"templates paths must be str or list[str], got: {type(paths)}")

    merged: List[Dict[str, Any]] = []
    for path in path_list:
        merged.extend(_load_templates_one(path))

    if not merged:
        raise ValueError(f"No templates loaded from: {path_list}")

    return merged


 # -----------------------------
# Analysis slicing helpers
# -----------------------------

def _has_temporality(rec: Dict[str, Any]) -> bool:
    """True if this record uses an actual temporal predicate (not (1=1))."""
    pred = rec.get("temporal_predicate")
    rel = rec.get("temporal_relation")
    if pred is None:
        return False
    # Treat explicit no-op predicate as non-temporal
    if isinstance(pred, str) and pred.replace(" ", "") == "(1=1)":
        return False
    # If relation is None but predicate exists and is not (1=1), still count as temporal
    return True if pred is not None else bool(rel)


def _init_group_from_variables(variables: Any) -> str:
    """Map template variables -> init group label for analysis."""
    if not isinstance(variables, list):
        try:
            variables = list(variables)
        except Exception:
            variables = []

    core = set([v for v in variables if v not in {"table_name", "temporal_predicate", "temporal_phrase", "temporal_relation"}])

    has_batsman = "batsman" in core or "batsman1" in core or "batsman2" in core
    has_bowler = "bowler" in core or "bowler1" in core or "bowler2" in core

    if has_batsman and has_bowler:
        return "both"
    if has_batsman:
        return "batsman_only"
    if has_bowler:
        return "bowler_only"
    return "none"


def _write_slice_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    write_jsonl(path, rows)

# -----------------------------
# Pipeline config
# -----------------------------
@dataclass
class PipelineConfig:
    templates_paths: List[str]
    matches_glob: str
    output_dir: str
    max_matches: int
    total_examples: int
    samples_per_template_per_match: int
    seed: int
    context_max_chars: int
    answer_max_rows: int
    drop_zeroish: bool
    write_analysis_jsonls: bool
    roi_stratify: bool
    roi_bucket_mode: str


# -----------------------------
# Main generator
# -----------------------------
def generate_dataset(cfg: PipelineConfig) -> Dict[str, Any]:
    rng = random.Random(cfg.seed)
    ensure_dir(cfg.output_dir)

    templates = load_templates(cfg.templates_paths)

    match_paths = sorted(glob.glob(cfg.matches_glob))
    if not match_paths:
        raise FileNotFoundError(f"No match CSV files found for glob: {cfg.matches_glob}")

    if cfg.max_matches > 0 and len(match_paths) > cfg.max_matches:
        match_paths = rng.sample(match_paths, cfg.max_matches)

    out_rows_no_overs: List[Dict[str, Any]] = []
    out_rows_with_overs: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    roi_rr_state: Dict[str, int] = {}

    def stop() -> bool:
        return cfg.total_examples > 0 and len(out_rows_no_overs) >= cfg.total_examples

    for match_idx, match_path in enumerate(match_paths):
        if stop():
            break

        try:
            df = pd.read_csv(match_path)
        except Exception as e:
            errors.append({"match_path": match_path, "error": f"read_csv failed: {e}"})
            continue

        full_context_no_overs = build_context_from_df(df, commentary_col="commentary", overs_col="overs", include_overs=False, max_chars=cfg.context_max_chars)
        full_context_with_overs = build_context_from_df(df, commentary_col="commentary", overs_col="overs", include_overs=True, max_chars=cfg.context_max_chars)
        roi_buckets_cache_match: Dict[str, Dict[str, List[str]]] = {}

        tmpl_order = templates[:]
        rng.shuffle(tmpl_order)

        for t in tmpl_order:
            if stop():
                break

            # Choose SQL template: original_sql if present else sql
            sql_template = t.get("original_sql") if t.get("original_sql") else t.get("sql")
            sql_template = normalize_sql_template_placeholders(sql_template)
            if not sql_template:
                # skip broken template
                continue

            question_template = t.get("question", "")
            variables = t.get("variables") or []
            if not isinstance(variables, list):
                variables = list(variables)

            template_id = t.get("template_id")
            item_id = t.get("item_id")

            # samples for this template for this match
            K = max(1, cfg.samples_per_template_per_match)
            if len(variables) == 0:
                K = 1

            for _ in range(K):
                if stop():
                    break

                try:
                    # sample params if needed
                    params_raw = {"table_name": "df"}
                    if variables:
                        p = sample_params_for_template(
                            df,
                            variables,
                            rng,
                            roi_stratify=cfg.roi_stratify,
                            roi_bucket_mode=cfg.roi_bucket_mode,
                            roi_rr_state=roi_rr_state,
                            roi_buckets_cache=roi_buckets_cache_match,
                        )
                        if p is None:
                            continue
                        params_raw.update(p)

                    # Build params_sql for SQL formatting.
                    # Supports templates using {batsman}/{bowler} (unquoted) and also templates that already have '{batsman}'/'{bowler}'.
                    params_sql = build_params_sql(sql_template, params_raw)

                    # Choose a question variant: base question + paraphrases (if present)
                    q_variants: List[str] = []
                    base_q = (t.get("question") or "").strip()
                    if base_q:
                        q_variants.append(base_q)
                    for pq in (t.get("paraphrases") or []):
                        if isinstance(pq, str) and pq.strip():
                            q_variants.append(pq.strip())

                    chosen_q_template = rng.choice(q_variants) if q_variants else ""
                    question_text = safe_format(chosen_q_template, params_raw) if chosen_q_template else ""

                    # format SQL with SQL literals (safe + handles missing quotes in template)
                    sql_text = safe_format(sql_template, params_sql)

                    # execute
                    ans_df = execute_sql_on_df(df, sql_text, table_name=params_raw.get("table_name", "df"))

                    # analysis for downstream use
                    row_info = extract_row_indices_from_query(
                        query=sql_text,
                        df=df,
                        result_df=ans_df,
                        table_name=params_raw.get("table_name", "df"),
                    )
                    query_analysis = analyze_query(sql_text, allowed_columns=set(df.columns))
                    # attach row targeting info
                    query_analysis.update(row_info)

                    # Build a *focused* context from rows_contributing (match output-driving rows)
                    contrib_idxs = row_info.get("row_indices_contributing") or []
                    context_contrib_no_overs = build_context_from_df_rows(
                        df,
                        contrib_idxs,
                        commentary_col="commentary",
                        overs_col="overs",
                        include_overs=False,
                        max_chars=cfg.context_max_chars,
                    )
                    context_contrib_with_overs = build_context_from_df_rows(
                        df,
                        contrib_idxs,
                        commentary_col="commentary",
                        overs_col="overs",
                        include_overs=True,
                        max_chars=cfg.context_max_chars,
                    )

                    zeroish = is_zeroish_result(ans_df)
                    if cfg.drop_zeroish and zeroish:
                        continue

                    rid_base = f"{match_idx:02d}-{uuid.uuid4().hex[:8]}"

                    base_record = {
                        "match_idx": match_idx,
                        "match_path": match_path,

                        "template_id": template_id,
                        "item_id": item_id,

                        "intent": t.get("intent"),
                        "description": t.get("description"),
                        "structure": t.get("structure"),
                        "primary_key": t.get("primary_key"),
                        "variables": variables,

                        "question": question_text,
                        "sql": sql_text,

                        # both raw + sql params are useful for debugging
                        "params_raw": params_raw,
                        "params_sql": params_sql,

                        "answer": df_to_answer_json(ans_df, max_rows=cfg.answer_max_rows),
                        "answer_rows": int(ans_df.shape[0]),
                        "answer_cols": int(ans_df.shape[1]),
                        "is_zeroish": bool(zeroish),

                        # temporal metadata if present
                        "temporal_relation": params_raw.get("temporal_relation"),
                        "temporal_phrase": params_raw.get("temporal_phrase"),
                        "temporal_predicate": params_raw.get("temporal_predicate"),

                        "roi_bucket_batsman": params_raw.get("roi_bucket_batsman"),
                        "roi_bucket_bowler": params_raw.get("roi_bucket_bowler"),
                        "roi_bucket_bowler1": params_raw.get("roi_bucket_bowler1"),
                        "roi_bucket_bowler2": params_raw.get("roi_bucket_bowler2"),

                        "analysis": query_analysis,
                    }

                    rec_no_overs = dict(base_record)
                    rec_no_overs["record_id"] = f"{rid_base}-no_overs"
                    # Primary context: only contributing rows
                    rec_no_overs["context"] = context_contrib_no_overs
                    # Keep full match context for debugging/ablation
                    rec_no_overs["context_full"] = full_context_no_overs

                    rec_with_overs = dict(base_record)
                    rec_with_overs["record_id"] = f"{rid_base}-with_overs"
                    # Primary context: only contributing rows
                    rec_with_overs["context"] = context_contrib_with_overs
                    # Keep full match context for debugging/ablation
                    rec_with_overs["context_full"] = full_context_with_overs

                    out_rows_no_overs.append(rec_no_overs)
                    out_rows_with_overs.append(rec_with_overs)

                except Exception as e:
                    errors.append({
                        "match_path": match_path,
                        "template_id": template_id,
                        "item_id": item_id,
                        "params_raw": params_raw if "params_raw" in locals() else None,
                        "error": str(e),
                        "sql_template_preview": (sql_template[:250] if isinstance(sql_template, str) else None),
                    })
                    continue

    # save outputs
    dataset_path_no_overs = os.path.join(cfg.output_dir, "dataset.no_overs.jsonl")
    dataset_path_with_overs = os.path.join(cfg.output_dir, "dataset.with_overs.jsonl")
    summary_path_no_overs = os.path.join(cfg.output_dir, "summary.no_overs.json")
    summary_path_with_overs = os.path.join(cfg.output_dir, "summary.with_overs.json")
    errors_path = os.path.join(cfg.output_dir, "errors.json")

    write_jsonl(dataset_path_no_overs, out_rows_no_overs)
    write_jsonl(dataset_path_with_overs, out_rows_with_overs)

    # Optional: write additional analysis-focused JSONLs
    analysis_paths: Dict[str, str] = {}
    if cfg.write_analysis_jsonls:
        def add_labels(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for r in rows:
                rr = dict(r)
                rr["has_temporality"] = _has_temporality(rr)
                rr["init_group"] = _init_group_from_variables(rr.get("variables"))
                out.append(rr)
            return out

        rows_no = add_labels(out_rows_no_overs)
        rows_with = add_labels(out_rows_with_overs)

        # --- temporal slices ---
        no_temporal = [r for r in rows_no if r.get("has_temporality")]
        no_nontemp = [r for r in rows_no if not r.get("has_temporality")]
        with_temporal = [r for r in rows_with if r.get("has_temporality")]
        with_nontemp = [r for r in rows_with if not r.get("has_temporality")]

        p_no_temporal = os.path.join(cfg.output_dir, "dataset.no_overs.temporal_only.jsonl")
        p_no_nontemp = os.path.join(cfg.output_dir, "dataset.no_overs.non_temporal.jsonl")
        p_with_temporal = os.path.join(cfg.output_dir, "dataset.with_overs.temporal_only.jsonl")
        p_with_nontemp = os.path.join(cfg.output_dir, "dataset.with_overs.non_temporal.jsonl")

        _write_slice_jsonl(p_no_temporal, no_temporal)
        _write_slice_jsonl(p_no_nontemp, no_nontemp)
        _write_slice_jsonl(p_with_temporal, with_temporal)
        _write_slice_jsonl(p_with_nontemp, with_nontemp)

        analysis_paths.update({
            "no_overs_temporal_only": p_no_temporal,
            "no_overs_non_temporal": p_no_nontemp,
            "with_overs_temporal_only": p_with_temporal,
            "with_overs_non_temporal": p_with_nontemp,
        })

        # --- init-group slices ---
        for grp in ["batsman_only", "bowler_only", "both", "none"]:
            p_no = os.path.join(cfg.output_dir, f"dataset.no_overs.init_{grp}.jsonl")
            p_with = os.path.join(cfg.output_dir, f"dataset.with_overs.init_{grp}.jsonl")
            _write_slice_jsonl(p_no, [r for r in rows_no if r.get("init_group") == grp])
            _write_slice_jsonl(p_with, [r for r in rows_with if r.get("init_group") == grp])
            analysis_paths[f"no_overs_init_{grp}"] = p_no
            analysis_paths[f"with_overs_init_{grp}"] = p_with

        # --- combined slices (optional but useful) ---
        # Example: temporal-only within init=both
        for grp in ["batsman_only", "bowler_only", "both"]:
            p_no = os.path.join(cfg.output_dir, f"dataset.no_overs.temporal_only.init_{grp}.jsonl")
            p_with = os.path.join(cfg.output_dir, f"dataset.with_overs.temporal_only.init_{grp}.jsonl")
            _write_slice_jsonl(p_no, [r for r in rows_no if r.get("has_temporality") and r.get("init_group") == grp])
            _write_slice_jsonl(p_with, [r for r in rows_with if r.get("has_temporality") and r.get("init_group") == grp])
            analysis_paths[f"no_overs_temporal_only_init_{grp}"] = p_no
            analysis_paths[f"with_overs_temporal_only_init_{grp}"] = p_with

    base_summary = {
        "seed": cfg.seed,
        "max_matches": cfg.max_matches,
        "total_examples": cfg.total_examples,
        "samples_per_template_per_match": cfg.samples_per_template_per_match,
        "context_max_chars": cfg.context_max_chars,
        "answer_max_rows": cfg.answer_max_rows,
        "drop_zeroish": cfg.drop_zeroish,
        "write_analysis_jsonls": cfg.write_analysis_jsonls,
        "templates_paths": cfg.templates_paths,
        "matches_glob": cfg.matches_glob,
        "num_errors": len(errors),
    }

    write_json(summary_path_no_overs, {
        **base_summary,
        "dataset_path": dataset_path_no_overs,
        "num_examples": len(out_rows_no_overs),
        "context_mode": "no_overs",
    })

    write_json(summary_path_with_overs, {
        **base_summary,
        "dataset_path": dataset_path_with_overs,
        "num_examples": len(out_rows_with_overs),
        "context_mode": "with_overs",
    })

    if errors:
        write_json(errors_path, errors)

    return {
        "dataset_path_no_overs": dataset_path_no_overs,
        "dataset_path_with_overs": dataset_path_with_overs,
        "summary_path_no_overs": summary_path_no_overs,
        "summary_path_with_overs": summary_path_with_overs,
        "errors_path": errors_path if errors else None,
        "num_examples": len(out_rows_no_overs),
        "num_errors": len(errors),
        "analysis_paths": analysis_paths,
    }


# -----------------------------
# CLI
# -----------------------------
def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--templates",
        nargs="+",
        default=["output/converted_params/test_generated_sql_nl_progress_5k_4_removed_fixed.json"],
        help="One or more template files (.json and/or .py). You can pass multiple: --templates a.json b.py",
    )
    ap.add_argument("--matches_glob", default="Cricket_tables/*.csv")
    ap.add_argument("--out_dir", default="output_dataset_v1")
    ap.add_argument("--max_matches", type=int, default=10, help="0 = all matches")
    ap.add_argument("--total_examples", type=int, default=5000, help="0 = unlimited")
    ap.add_argument("--samples_per_template_per_match", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--context_max_chars", type=int, default=0)
    ap.add_argument("--answer_max_rows", type=int, default=0)
    ap.add_argument("--drop_zeroish", action="store_true")
    ap.add_argument(
        "--write_analysis_jsonls",
        action="store_true",
        help="If set, also write analysis slices (temporal/non-temporal and init-group) as separate JSONL files for both context modes.",
    )
    ap.add_argument(
        "--roi_stratify",
        action="store_true",
        help="If set, initialize batsman/bowler from overs-based ROI buckets (entire/first_half/middle/second_half) when possible.",
    )
    ap.add_argument(
        "--roi_bucket_mode",
        type=str,
        default="random",
        choices=["random", "round_robin"],
        help="How to choose ROI bucket per sample when roi_stratify is enabled.",
    )
    return ap.parse_args()

def main():
    args = parse_args()
    cfg = PipelineConfig(
        templates_paths=args.templates,
        matches_glob=args.matches_glob,
        output_dir=args.out_dir,
        max_matches=args.max_matches,
        total_examples=args.total_examples,
        samples_per_template_per_match=args.samples_per_template_per_match,
        seed=args.seed,
        context_max_chars=args.context_max_chars,
        answer_max_rows=args.answer_max_rows,
        drop_zeroish=args.drop_zeroish,
        write_analysis_jsonls=args.write_analysis_jsonls,
        roi_stratify=args.roi_stratify,
        roi_bucket_mode=args.roi_bucket_mode,
    )
    res = generate_dataset(cfg)
    print("✅ Done")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()


# python generate_questions.py \
#   --templates output/converted_params/test_generated_sql_nl_progress_5k_4_removed_fixed.json template_q_param_cricket_pk.py \
#   --matches_glob "Cricket_tables/*.csv" \
#   --out_dir output/dataset_runs/roi_test \
#   --max_matches 5 \
#   --total_examples 200 \
#   --samples_per_template_per_match 2 \
#   --seed 7 \
#   --drop_zeroish \
#   --write_analysis_jsonls \
#   --roi_stratify \
#   --roi_bucket_mode round_robin
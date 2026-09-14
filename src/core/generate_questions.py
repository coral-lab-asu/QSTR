"""Question generation core + coverage dataset builder.

This module provides the canonical helper functions used across QSG question generation
(SQL formatting/execution, parameter sampling, context building, split labeling, etc.)

It also includes a **coverage-mode generator** that ensures:
  - every template is used at least N times (default 2)
  - every match is used at least M times (default 1)
  - zeroish results are capped at max_zeroish_frac of the produced dataset (default 2%)

Outputs (coverage mode):
  - <out_dir>/dataset.coverage.json
  - <out_dir>/exclude_keys.coverage.json
  - <out_dir>/errors.coverage.json (if any)

Disjointness key format:
  match_path|template_index|init_id|temporal_relation
"""

from __future__ import annotations

import os
import re
import json
import glob
import math
import random
import hashlib
import argparse
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import duckdb


# -----------------------------------------------------------------------------
# IO helpers
# -----------------------------------------------------------------------------

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)





# -----------------------------------------------------------------------------
# Disjointness key
# -----------------------------------------------------------------------------

def record_key(match_path: str, template_index: Any, init_id: Any, temporal_relation: Any) -> str:
    return "|".join([
        str(match_path),
        str(template_index),
        str(init_id),
        "" if temporal_relation is None else str(temporal_relation),
    ])


# -----------------------------------------------------------------------------
# SQL + dataframe helpers
# -----------------------------------------------------------------------------

def normalize_cell(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (np.floating, float)):
        try:
            if np.isnan(x):
                return None
        except Exception:
            pass
        return float(x)
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return x


def df_to_answer_json(df: pd.DataFrame, max_rows: int = 0) -> Dict[str, Any]:
    out = df.copy()
    if max_rows and max_rows > 0 and len(out) > max_rows:
        out = out.head(max_rows)
    cols = [str(c) for c in out.columns.tolist()]
    rows = [[normalize_cell(v) for v in row] for row in out.to_numpy().tolist()]
    return {"columns": cols, "rows": rows}


def is_zeroish_result(df: pd.DataFrame) -> bool:
    """Treat empty result or all-zeros/all-empty as zeroish."""
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


def sql_literal(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        try:
            if np.isnan(v):
                return "NULL"
        except Exception:
            pass
        return str(float(v))
    if isinstance(v, pd.Timestamp):
        s = v.isoformat().replace("'", "''")
        return f"'{s}'"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def build_params_sql(sql_template: str, params_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw params into SQL-safe substitutions.

    Important: `temporal_predicate` is expected to be a raw SQL fragment and must NOT be quoted.
    """
    out = dict(params_raw)
    for k, v in list(out.items()):
        if k in {"table_name", "temporal_predicate"}:
            continue
        out[k] = sql_literal(v)
    return out


def safe_format(template: str, params: Dict[str, Any]) -> str:
    return template.format(**params)


def normalize_sql_template_placeholders(sql_template: str) -> str:
    """Undo common failure mode: templates containing '{x}' wrapped in quotes."""
    if not isinstance(sql_template, str):
        return sql_template

    sql_template = re.sub(
        r"'\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*'",
        lambda m: m.group(0)
        if m.group(1) in {"table_name", "temporal_predicate"}
        else "{" + m.group(1) + "}",
        sql_template,
    )

    sql_template = re.sub(
        r"\"\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*\"",
        lambda m: m.group(0)
        if m.group(1) in {"table_name", "temporal_predicate"}
        else "{" + m.group(1) + "}",
        sql_template,
    )

    return sql_template


# -----------------------------------------------------------------------------
# Context helpers
# -----------------------------------------------------------------------------

def _truncate_text(s: str, max_chars: int) -> str:
    if not max_chars or max_chars <= 0:
        return s
    return s if len(s) <= max_chars else s[:max_chars] + " ..."


def build_context_from_df(
    df: pd.DataFrame,
    commentary_col: str = "commentary",
    overs_col: str = "overs",
    include_overs: bool = False,
    max_chars: int = 0,
) -> str:
    if commentary_col not in df.columns:
        return ""

    if include_overs and overs_col in df.columns:
        lines: List[str] = []
        for _, row in df[[overs_col, commentary_col]].iterrows():
            comm = row.get(commentary_col)
            if pd.isna(comm):
                continue
            ov = row.get(overs_col)
            lines.append(f"{ov} | {comm}" if not pd.isna(ov) else str(comm))
        return _truncate_text("\n".join(lines), max_chars)

    lines = df[commentary_col].dropna().astype(str).tolist()
    return _truncate_text("\n".join(lines), max_chars)


def build_context_from_df_rows(
    df: pd.DataFrame,
    row_indices: List[Any],
    commentary_col: str = "commentary",
    overs_col: str = "overs",
    include_overs: bool = False,
    max_chars: int = 0,
) -> str:
    if not row_indices or commentary_col not in df.columns:
        return ""

    valid = [i for i in row_indices if i in df.index]
    if not valid:
        return ""

    sub = df.loc[valid]
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
            ov = row.get(overs_col)
            lines.append(f"{ov} | {comm}" if not pd.isna(ov) else str(comm))
        return _truncate_text("\n".join(lines), max_chars)

    lines = sub[commentary_col].dropna().astype(str).tolist()
    return _truncate_text("\n".join(lines), max_chars)


# -----------------------------------------------------------------------------
# Row-index extraction
# -----------------------------------------------------------------------------

def extract_row_indices_from_query(
    query: str,
    df: pd.DataFrame,
    result_df: Optional[pd.DataFrame],
    table_name: str = "df",
) -> Dict[str, Any]:
    """Minimal implementation.

    If you have a more precise implementation elsewhere, replace this.
    This function is kept for compatibility with split-analysis generation.
    """
    idxs = df.index.tolist()
    return {"row_indices_scanned": idxs, "row_indices_contributing": idxs}


# -----------------------------------------------------------------------------
# Template loading
# -----------------------------------------------------------------------------

def _load_templates_one(path: str) -> List[Dict[str, Any]]:
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
        return [t for t in raw if isinstance(t, dict)]

    data = read_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("final"), list):
        return data["final"]
    raise ValueError(f"Template JSON must be a list or dict with key 'final' list. Got {type(data)}")


def load_templates(paths: Any) -> List[Dict[str, Any]]:
    if isinstance(paths, (list, tuple)):
        path_list = [str(x).strip() for x in paths if str(x).strip()]
    elif isinstance(paths, str):
        path_list = [p.strip() for p in paths.split(",") if p.strip()]
    else:
        raise TypeError(f"templates paths must be str or list[str], got: {type(paths)}")

    merged: List[Dict[str, Any]] = []
    for path in path_list:
        merged.extend(_load_templates_one(path))

    if not merged:
        raise ValueError(f"No templates loaded from: {path_list}")

    # Normalize a few keys so downstream code can rely on them
    for t in merged:
        # tolerate different schema names
        if "template_id" not in t and "id" in t:
            t["template_id"] = t.get("id")
        if "item_id" not in t and "id" in t:
            t["item_id"] = t.get("id")
        if "sql" not in t and "query" in t:
            t["sql"] = t.get("query")

    return merged


# -----------------------------------------------------------------------------
# Temporality + split labeling
# -----------------------------------------------------------------------------

def _init_group_from_variables(variables: Any) -> str:
    if not isinstance(variables, list):
        try:
            variables = list(variables)
        except Exception:
            variables = []

    core = set(
        v
        for v in variables
        if v not in {"table_name", "temporal_predicate", "temporal_phrase", "temporal_relation"}
    )

    has_batsman = any(v.startswith("batsman") for v in core)
    has_bowler = any(v.startswith("bowler") for v in core)

    if has_batsman and has_bowler:
        return "both"
    if has_batsman:
        return "batsman_only"
    if has_bowler:
        return "bowler_only"
    return "none"


def _has_temporality(rec: Dict[str, Any]) -> bool:
    pred = rec.get("temporal_predicate")
    rel = rec.get("temporal_relation")

    if pred is None:
        return False

    if isinstance(pred, str) and pred.replace(" ", "") == "(1=1)":
        return False

    return True if pred is not None else bool(rel)


def _compute_splits(rec: Dict[str, Any]) -> List[str]:
    init_grp = _init_group_from_variables(rec.get("variables"))
    has_tmp = _has_temporality(rec)

    if init_grp == "none" and not has_tmp:
        return []

    tmp = "temporal" if has_tmp else "non_temporal"
    splits: List[str] = [tmp]

    if has_tmp:
        splits.append("temporal_init")

    if init_grp == "batsman_only":
        splits.append("batsman_init")
    elif init_grp == "bowler_only":
        splits.append("bowler_init")
    elif init_grp == "both":
        splits.append("batsman_init")
        splits.append("bowler_init")

    splits.append(f"init_{init_grp}")
    splits.append(f"{tmp}__init_{init_grp}")

    return sorted(set(splits))


def pick_relation(rng: random.Random) -> str:
    return rng.choice(["before", "after", "before_or_at", "after_or_at", "between", "overlaps"])


def _snap_over_ball(x: float) -> float:
    O = math.floor(x)
    ball = int(math.floor((x - O) * 10 + 1e-9))
    if ball < 1:
        ball = 1
    if ball > 6:
        O += 1
        ball = 1
    return float(f"{O}.{ball}")


def build_temporal_with_phrase(
    relation: Optional[str],
    x1: Optional[float],
    x2: Optional[float],
    field: str = "overs",
    rng: Optional[random.Random] = None,
) -> Tuple[str, str, Optional[str]]:
    if rng is None:
        rng = random.Random()

    if not relation or x1 is None or x2 is None:
        return "(1=1)", "the entire match", None

    lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)

    b1 = _snap_over_ball(rng.uniform(lo, hi))
    b2 = _snap_over_ball(rng.uniform(lo, hi))
    if b1 == b2:
        b2 = _snap_over_ball(rng.uniform(lo, hi))
    a, b = tuple(sorted((b1, b2)))

    r = str(relation).lower()

    sql_map = {
        "before": f"({field} < {a})",
        "after": f"({field} > {b})",
        "before_or_at": f"({field} <= {a})",
        "after_or_at": f"({field} >= {b})",
        "between": f"({field} BETWEEN {a} AND {b})",
        "overlaps": f"({field} <= {b} AND {a} <= {field})",
    }

    nl_map = {
        "before": f"when over is before {a}",
        "after": f"when over is after {b}",
        "before_or_at": f"when over is at or before {a}",
        "after_or_at": f"when over is at or after {b}",
        "between": f"when over is between {a} and {b}",
        "overlaps": f"when over falls between {a} and {b}",
    }

    if r not in sql_map:
        return "(1=1)", "the entire match", None

    return sql_map[r], nl_map[r], r


# -----------------------------------------------------------------------------
# Parameter sampling
# -----------------------------------------------------------------------------

def sample_params_for_template(
    df: pd.DataFrame,
    variables: List[str],
    rng: random.Random,
    roi_stratify: bool = False,
    roi_bucket_mode: str = "",
    roi_rr_state: Optional[Dict[str, int]] = None,
    roi_buckets_cache: Optional[Dict[str, Dict[str, List[str]]]] = None,
) -> Optional[Dict[str, Any]]:
    """Best-effort sampler for common placeholders.

    This keeps the same function signature used by the split-analysis script.
    Extend this if your templates include additional variables.
    """

    params: Dict[str, Any] = {}

    # Common entity pools
    batsmen = df["batsman"].dropna().unique().tolist() if "batsman" in df.columns else []
    bowlers = df["bowler"].dropna().unique().tolist() if "bowler" in df.columns else []

    if "batsman" in variables:
        if not batsmen:
            return None
        params["batsman"] = rng.choice(batsmen)

    if "bowler" in variables:
        if not bowlers:
            return None
        params["bowler"] = rng.choice(bowlers)

    if "bowler1" in variables:
        if not bowlers:
            return None
        params["bowler1"] = rng.choice(bowlers)

    if "bowler2" in variables:
        if not bowlers:
            return None
        params["bowler2"] = rng.choice(bowlers)

    if "batsman1" in variables:
        if not batsmen:
            return None
        params["batsman1"] = rng.choice(batsmen)

    if "batsman2" in variables:
        if not batsmen:
            return None
        params["batsman2"] = rng.choice(batsmen)

    return params


# -----------------------------------------------------------------------------
# Coverage generator
# -----------------------------------------------------------------------------

@dataclass
class CoverageConfig:
    templates_paths: List[str]
    matches_glob: str
    output_dir: str

    seed: int = 42

    # If >0, stop after producing this many records.
    total_examples: int = 0

    # Output sizing
    context_max_chars: int = 0
    answer_max_rows: int = 0
    num_shards: int = 1

    # Zeroish controls
    drop_zeroish: bool = False
    max_zeroish_frac: float = 0.02

    # Coverage requirements
    require_each_template_uses: int = 2
    require_each_match_uses: int = 1


def _chunk_list(items: List[Any], num_chunks: int) -> List[List[Any]]:
    """Split a list into `num_chunks` chunks as evenly as possible."""
    if num_chunks <= 1:
        return [items]
    n = len(items)
    if n == 0:
        return [[] for _ in range(num_chunks)]
    k, r = divmod(n, num_chunks)
    chunks: List[List[Any]] = []
    start = 0
    for i in range(num_chunks):
        size = k + (1 if i < r else 0)
        chunks.append(items[start:start + size])
        start += size
    return chunks


_ENRICH_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _preferred_template_sql(item: Dict[str, Any]) -> str:
    sql = item.get("original_sql")
    if isinstance(sql, str) and sql.strip():
        return sql
    sql = item.get("sql")
    return sql if isinstance(sql, str) else ""


def _preferred_executed_sql(item: Dict[str, Any]) -> str:
    sql = item.get("sql")
    return sql if isinstance(sql, str) else ""


def _strip_sql_literal_wrapping(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
        return v[1:-1]
    return v


def _extract_placeholder_values_for_enrich(item: Dict[str, Any]) -> Dict[str, str]:
    params = item.get("params_raw")
    if isinstance(params, dict):
        out = {}
        for k, v in params.items():
            if isinstance(v, (str, int, float)):
                out[str(k)] = str(v)
        if out:
            return out

    template_sql = _preferred_template_sql(item)
    concrete_sql = _preferred_executed_sql(item)
    if not template_sql or not concrete_sql or template_sql == concrete_sql:
        return {}

    names: List[str] = []
    parts: List[str] = []
    last = 0
    for m in _ENRICH_PLACEHOLDER_RE.finditer(template_sql):
        parts.append(re.escape(template_sql[last:m.start()]))
        names.append(m.group(1))
        parts.append(r"(.+?)")
        last = m.end()
    parts.append(re.escape(template_sql[last:]))

    try:
        match = re.fullmatch("".join(parts), concrete_sql, flags=re.DOTALL)
    except re.error:
        match = None
    if not match:
        return {}

    values: Dict[str, str] = {}
    for name, captured in zip(names, match.groups()):
        values[name] = _strip_sql_literal_wrapping(captured)
    return values


def _materialize_question_for_enrich(item: Dict[str, Any]) -> str:
    question = item.get("question")
    if not isinstance(question, str) or not question.strip():
        return ""
    if "{" not in question or "}" not in question:
        return question

    values = _extract_placeholder_values_for_enrich(item)
    if not values:
        return question

    class SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    try:
        return question.format_map(SafeDict(values))
    except Exception:
        return question


def enrich_dataset_with_ground_truth(
    input_path: str,
    matches_glob: str,
    output_path: str,
    manual_review_path: str,
    *,
    answer_max_rows: int = 0,
) -> Dict[str, Any]:
    """Attach a compatible match path and executed table to each existing item."""
    items = read_json(input_path)
    if not isinstance(items, list):
        raise ValueError(f"Expected a JSON list at {input_path}, got {type(items)}")

    match_paths = sorted(glob.glob(matches_glob))
    if not match_paths:
        raise FileNotFoundError(f"No match CSV files found for glob: {matches_glob}")

    ensure_dir(str(Path(output_path).parent))
    ensure_dir(str(Path(manual_review_path).parent))

    match_dfs: Dict[str, pd.DataFrame] = {}
    enriched_rows: List[Dict[str, Any]] = []
    manual_review: List[Dict[str, Any]] = []

    for item in items:
        rec = dict(item)
        item_id = rec.get("item_id")
        if "index_id" not in rec:
            rec["index_id"] = len(enriched_rows)
        if "record_id" not in rec:
            rec["record_id"] = str(item_id) if item_id is not None else f"r{rec['index_id']}"
        had_original_sql = isinstance(rec.get("original_sql"), str) and bool(str(rec.get("original_sql")).strip())
        template_sql = _preferred_template_sql(rec)
        question_template = rec.get("question") if isinstance(rec.get("question"), str) else ""
        variables = rec.get("variables") or []
        if not isinstance(variables, list):
            try:
                variables = list(variables)
            except Exception:
                variables = []

        rec["match_path"] = None
        rec["ground_truth_table"] = None
        rec["params_raw"] = None

        if not isinstance(template_sql, str) or not template_sql.strip():
            manual_review.append({
                "item_id": item_id,
                "reason": "missing_sql",
            })
            enriched_rows.append(rec)
            continue

        sql_template = normalize_sql_template_placeholders(template_sql)

        found_match = False
        last_error: Optional[str] = None
        item_seed = int(hashlib.md5(str(item_id).encode("utf-8")).hexdigest()[:8], 16) if item_id is not None else 0

        for match_i, match_path in enumerate(match_paths):
            try:
                df = match_dfs.get(match_path)
                if df is None:
                    df = pd.read_csv(match_path)
                    match_dfs[match_path] = df
            except Exception as e:
                last_error = str(e)
                continue

            max_attempts = 5 if variables else 1
            for attempt in range(max_attempts):
                try:
                    rng_local = random.Random(item_seed + 1009 * (match_i + 1) + 97 * (attempt + 1))
                    params_raw: Dict[str, Any] = {"table_name": "df"}
                    if variables:
                        sampled = sample_params_for_template(df, variables, rng_local)
                        if sampled is None:
                            continue
                        params_raw.update(sampled)

                    params_sql = build_params_sql(sql_template, params_raw)
                    sql_text = safe_format(sql_template, params_sql)
                    question_text = safe_format(question_template, params_raw) if question_template else ""

                    ans_df = execute_sql_on_df(df, sql_text, table_name="df")
                    if is_zeroish_result(ans_df):
                        continue

                    rec["sql"] = sql_text
                    if had_original_sql:
                        rec["original_sql_template"] = sql_template
                        rec["original_sql"] = sql_text
                    elif sql_template != sql_text:
                        rec["original_sql"] = sql_template
                    elif "original_sql" in rec:
                        rec.pop("original_sql", None)
                    rec["question"] = question_text
                    rec["match_path"] = match_path
                    rec["ground_truth_table"] = df_to_answer_json(ans_df, max_rows=answer_max_rows)
                    rec["params_raw"] = params_raw
                    found_match = True
                    break
                except Exception as e:
                    last_error = str(e)
                    continue

            if found_match:
                break

        if not found_match:
            manual_review.append({
                "item_id": item_id,
                "reason": "no_compatible_match_found",
                "last_error": last_error,
            })

        enriched_rows.append(rec)

    write_json(output_path, enriched_rows)
    write_json(manual_review_path, manual_review)

    return {
        "output_path": output_path,
        "manual_review_path": manual_review_path,
        "num_records": len(enriched_rows),
        "num_manual_review": len(manual_review),
    }

def generate_coverage_dataset(cfg: CoverageConfig) -> Dict[str, Any]:
    rng = random.Random(cfg.seed)
    ensure_dir(cfg.output_dir)

    templates = load_templates(cfg.templates_paths)
    for i, t in enumerate(templates):
        t["template_index"] = i

    match_paths = sorted(glob.glob(cfg.matches_glob))
    if not match_paths:
        raise FileNotFoundError(f"No match CSV files found for glob: {cfg.matches_glob}")

    T = len(templates)
    M = len(match_paths)

    # 1) Build forced schedule ensuring template coverage first.
    schedule: List[Tuple[int, int]] = []
    for ti in range(T):
        for u in range(max(1, int(cfg.require_each_template_uses))):
            mi = (ti + u) % M
            schedule.append((ti, mi))

    # 2) Top up match coverage.
    match_use: Dict[int, int] = {i: 0 for i in range(M)}
    for _, mi in schedule:
        match_use[mi] += 1

    for mi in range(M):
        while match_use[mi] < max(1, int(cfg.require_each_match_uses)):
            schedule.append((rng.randrange(T), mi))
            match_use[mi] += 1

    rng.shuffle(schedule)

    out_rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    exclude_keys: set = set()

    # (revert: keep context fields in records, don't split into separate files)

    kept = 0
    kept_zeroish = 0

    def zeroish_ok(is_zeroish: bool) -> bool:
        nonlocal kept, kept_zeroish
        if not is_zeroish:
            return True
        if cfg.max_zeroish_frac <= 0:
            return False
        return (kept_zeroish + 1) / max(1, kept + 1) <= cfg.max_zeroish_frac

    for sched_i, (ti, mi) in enumerate(schedule):
        if cfg.total_examples and cfg.total_examples > 0 and len(out_rows) >= cfg.total_examples:
            break

        match_path = match_paths[mi]
        tt = templates[ti]

        try:
            df = pd.read_csv(match_path)
        except Exception as e:
            errors.append({"match_path": match_path, "template_index": ti, "error": f"read_csv failed: {e}"})
            continue

        # Full contexts once per match
        full_context_no_overs = build_context_from_df(
            df,
            commentary_col="commentary",
            overs_col="overs",
            include_overs=False,
            max_chars=cfg.context_max_chars,
        )
        full_context_with_overs = build_context_from_df(
            df,
            commentary_col="commentary",
            overs_col="overs",
            include_overs=True,
            max_chars=cfg.context_max_chars,
        )


        sql_template = tt.get("original_sql") if tt.get("original_sql") else tt.get("sql")
        sql_template = normalize_sql_template_placeholders(sql_template)
        if not sql_template:
            errors.append({"match_path": match_path, "template_index": ti, "error": "empty sql template"})
            continue

        variables = tt.get("variables") or []
        if not isinstance(variables, list):
            try:
                variables = list(variables)
            except Exception:
                variables = []

        # overs bounds (for temporal)
        overs_series = pd.to_numeric(df["overs"], errors="coerce") if "overs" in df.columns else pd.Series([], dtype=float)
        overs_series = overs_series.dropna()
        o_min = float(overs_series.min()) if not overs_series.empty else None
        o_max = float(overs_series.max()) if not overs_series.empty else None

        # Question pool
        q_variants: List[str] = []
        base_q = ((tt.get("question") or "") if isinstance(tt.get("question"), str) else "").strip()
        if base_q:
            q_variants.append(base_q)
        for pq in (tt.get("paraphrases") or []):
            if isinstance(pq, str) and pq.strip():
                q_variants.append(pq.strip())

        made = False
        last_err: Optional[str] = None

        # Retry loop to avoid exceeding zeroish cap and to handle sampling failures.
        for attempt in range(20):
            rng_local = random.Random(cfg.seed + 100000 * (sched_i + 1) + 1000 * (attempt + 1))

            params_raw: Dict[str, Any] = {"table_name": "df"}

            # sample entity placeholders
            if variables:
                p = sample_params_for_template(df, variables, rng_local)
                if p is None:
                    continue
                params_raw.update(p)

            # temporal predicate if required
            if "temporal_predicate" in variables:
                rel = pick_relation(rng_local)
                if o_min is None or o_max is None or o_min == o_max:
                    params_raw["temporal_predicate"] = "(1=1)"
                    params_raw["temporal_phrase"] = "the entire match"
                    params_raw["temporal_relation"] = None
                else:
                    pred, phrase, rel_used = build_temporal_with_phrase(rel, o_min, o_max, field="overs", rng=rng_local)
                    params_raw["temporal_predicate"] = pred
                    params_raw["temporal_phrase"] = phrase
                    params_raw["temporal_relation"] = rel_used
            else:
                params_raw["temporal_relation"] = None

            # init_id excludes temporal fields
            init_params: Dict[str, Any] = {}
            for k in ["batsman", "batsman1", "batsman2", "bowler", "bowler1", "bowler2"]:
                if k in params_raw:
                    init_params[k] = params_raw.get(k)

            init_id = hashlib.md5(json.dumps(init_params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:8]

            params_sql = build_params_sql(sql_template, params_raw)

            chosen_q = rng_local.choice(q_variants) if q_variants else ""
            try:
                question_text = safe_format(chosen_q, params_raw) if chosen_q else ""
            except Exception:
                question_text = chosen_q

            try:
                sql_text = safe_format(sql_template, params_sql)
                ans_df = execute_sql_on_df(df, sql_text, table_name=params_raw.get("table_name", "df"))

                zeroish = is_zeroish_result(ans_df)
                if cfg.drop_zeroish and zeroish:
                    continue
                if not zeroish_ok(zeroish):
                    continue

                row_info = extract_row_indices_from_query(
                    query=sql_text,
                    df=df,
                    result_df=ans_df,
                    table_name=params_raw.get("table_name", "df"),
                )
                contrib_idxs = row_info.get("row_indices_contributing") or []
                scanned_idxs = row_info.get("row_indices_scanned") or []
                num_rows_scanned = len(scanned_idxs)
                num_rows_contributing = len(contrib_idxs)
                total_rows = int(df.shape[0])
                frac_rows_scanned = (num_rows_scanned / total_rows) if total_rows > 0 else 0.0
                frac_rows_contributing = (num_rows_contributing / total_rows) if total_rows > 0 else 0.0

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


                rec: Dict[str, Any] = {
                    "index_id": len(out_rows),
                    "record_id": str(tt.get("item_id")) if tt.get("item_id") is not None else f"r{len(out_rows)}",
                    "match_idx": mi,
                    "match_path": match_path,
                    "template_index": ti,
                    "template_id": tt.get("template_id"),
                    "item_id": tt.get("item_id"),
                    "intent": tt.get("intent"),
                    "description": tt.get("description"),
                    "structure": tt.get("structure"),
                    "primary_key": tt.get("primary_key"),
                    "variables": variables,
                    "question": question_text,
                    "sql": sql_text,
                    "params_raw": params_raw,
                    "params_sql": params_sql,
                    "answer": df_to_answer_json(ans_df, max_rows=cfg.answer_max_rows),
                    "answer_rows": int(ans_df.shape[0]),
                    "answer_cols": int(ans_df.shape[1]),
                    #"row_indices_scanned": scanned_idxs,
                    #"row_indices_contributing": contrib_idxs,
                    "num_rows_scanned": int(num_rows_scanned),
                    "num_rows_contributing": int(num_rows_contributing),
                    "total_rows": int(total_rows),
                    "frac_rows_scanned": float(frac_rows_scanned),
                    "frac_rows_contributing": float(frac_rows_contributing),
                    "is_zeroish": bool(zeroish),
                    "temporal_relation": params_raw.get("temporal_relation"),
                    "temporal_phrase": params_raw.get("temporal_phrase"),
                    "temporal_predicate": params_raw.get("temporal_predicate"),
                    "init_params": init_params,
                    "init_id": init_id,
                    # Restore context fields in record (revert splitting)
                    "context": context_contrib_no_overs,
                    "context_with_overs": context_contrib_with_overs,
                    "context_full": full_context_no_overs,
                    "context_full_with_overs": full_context_with_overs,
                }

                # splits
                rec["splits"] = _compute_splits(rec)

                out_rows.append(rec)
                kept += 1
                if zeroish:
                    kept_zeroish += 1

                exclude_keys.add(record_key(match_path, ti, init_id, rec.get("temporal_relation")))

                made = True
                break

            except Exception as e:
                last_err = str(e)
                continue

        if not made:
            errors.append({
                "match_path": match_path,
                "template_index": ti,
                "template_id": tt.get("template_id"),
                "error": "failed_to_generate_after_retries" if last_err is None else f"failed_to_generate_after_retries: {last_err}",
            })

    metadata = {
        "seed": cfg.seed,
        "matches_glob": cfg.matches_glob,
        "templates_paths": cfg.templates_paths,
        "require_each_template_uses": cfg.require_each_template_uses,
        "require_each_match_uses": cfg.require_each_match_uses,
        "max_zeroish_frac": cfg.max_zeroish_frac,
        "drop_zeroish": cfg.drop_zeroish,
        "total_examples": cfg.total_examples,
        "num_records": len(out_rows),
        "num_errors": len(errors),
    }

    num_shards = int(cfg.num_shards) if cfg.num_shards and int(cfg.num_shards) > 0 else 1

    if num_shards <= 1:
        out_path = os.path.join(cfg.output_dir, "dataset.coverage.json")
        write_json(out_path, {
            "metadata": metadata,
            "records": out_rows,
        })
        dataset_paths = [out_path]
        manifest_path = ""
    else:
        parts = _chunk_list(out_rows, num_shards)
        dataset_paths: List[str] = []
        for si, part_rows in enumerate(parts):
            part_path = os.path.join(cfg.output_dir, f"dataset.coverage.part-{si:03d}.json")
            write_json(part_path, {
                "metadata": {**metadata, "shard_index": si, "num_shards": num_shards, "num_records_in_shard": len(part_rows)},
                "records": part_rows,
            })
            dataset_paths.append(part_path)

        manifest_path = os.path.join(cfg.output_dir, "dataset.coverage.manifest.json")
        write_json(manifest_path, {
            "metadata": {**metadata, "num_shards": num_shards},
            "parts": dataset_paths,
        })
        # Keep a stable pointer name for downstream scripts.
        out_path = manifest_path

    write_json(os.path.join(cfg.output_dir, "exclude_keys.coverage.json"), {"keys": sorted(exclude_keys)})

    if errors:
        write_json(os.path.join(cfg.output_dir, "errors.coverage.json"), errors)

    return {
        "dataset_path": out_path,
        "dataset_parts": dataset_paths,
        "dataset_manifest_path": manifest_path,
        "exclude_keys_path": os.path.join(cfg.output_dir, "exclude_keys.coverage.json"),
        "num_records": len(out_rows),
        "num_errors": len(errors),
    }


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate coverage dataset (all templates + all matches)")

    ap.add_argument(
        "--templates",
        nargs="+",
        help="One or more template files (.json or .py).",
    )
    ap.add_argument(
        "--enrich_existing_dataset",
        type=str,
        default="",
        help="Existing JSON list to enrich with `match_path` and `ground_truth_table`.",
    )
    ap.add_argument(
        "--matches_glob",
        type=str,
        default="Cricket_tables/*.csv",
        help="Glob for match CSV files.",
    )
    ap.add_argument(
        "--out_dir",
        type=str,
        default="output_dataset_coverage",
        help="Output directory.",
    )

    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--total_examples", type=int, default=0)

    ap.add_argument("--context_max_chars", type=int, default=0)
    ap.add_argument("--answer_max_rows", type=int, default=0)
    ap.add_argument(
        "--enrich_output_path",
        type=str,
        default="",
        help="Output path for the enriched existing dataset JSON.",
    )
    ap.add_argument(
        "--manual_review_path",
        type=str,
        default="",
        help="Output path for the manual review JSON.",
    )

    ap.add_argument(
        "--num_shards",
        type=int,
        default=1,
        help="Split dataset.coverage.json into N parts (writes dataset.coverage.part-XXX.json plus a manifest when N>1).",
    )

    ap.add_argument("--drop_zeroish", action="store_true")
    ap.add_argument("--max_zeroish_frac", type=float, default=0.02)

    ap.add_argument("--require_each_template_uses", type=int, default=2)
    ap.add_argument("--require_each_match_uses", type=int, default=1)

    return ap.parse_args()


def main() -> None:
    args = parse_args()

    if args.enrich_existing_dataset:
        input_path = args.enrich_existing_dataset
        output_path = args.enrich_output_path or str(
            Path(input_path).with_name(Path(input_path).stem + ".ground_truth.json")
        )
        manual_review_path = args.manual_review_path or str(
            Path(input_path).with_name(Path(input_path).stem + ".manual_review.json")
        )
        enrich_dataset_with_ground_truth(
            input_path=input_path,
            matches_glob=args.matches_glob,
            output_path=output_path,
            manual_review_path=manual_review_path,
            answer_max_rows=args.answer_max_rows,
        )
        return

    if not args.templates:
        raise ValueError("--templates is required unless --enrich_existing_dataset is provided.")

    cfg = CoverageConfig(
        templates_paths=args.templates,
        matches_glob=args.matches_glob,
        output_dir=args.out_dir,
        seed=args.seed,
        total_examples=args.total_examples,
        context_max_chars=args.context_max_chars,
        answer_max_rows=args.answer_max_rows,
        num_shards=args.num_shards,
        drop_zeroish=args.drop_zeroish,
        max_zeroish_frac=args.max_zeroish_frac,
        require_each_template_uses=args.require_each_template_uses,
        require_each_match_uses=args.require_each_match_uses,
    )

    generate_coverage_dataset(cfg)


if __name__ == "__main__":
    main()


# python -m src.core.generate_questions \
#   --templates data/data_final/test_generated_sql_nl.json data/data_manual_template/template_q_param_cricket_pk.py \
#   --matches_glob "data/Cricket_tables/*.csv" \
#   --out_dir data/output_dataset_coverage_v1 \
#   --seed 42 \
#   --require_each_template_uses 2 \
#   --require_each_match_uses 1 \
#   --max_zeroish_frac 0.02
#   --num_shards 10

# python -m src.core.generate_questions \
#   --enrich_existing_dataset data/data_final/test_generated_sql_nl.json \
#   --matches_glob "data/Cricket_tables/*.csv" \
#   --enrich_output_path data/data_final/test_generated_sql_nl.ground_truth.json \
#   --manual_review_path data/data_final/test_generated_sql_nl.manual_review.json

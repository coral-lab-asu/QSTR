import os
import re
import json
import glob
import uuid
import hashlib
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
import sqlglot
from sqlglot import exp


# -----------------------------
# Small shared helpers (copied from generate_questions.py)
# -----------------------------

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

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

def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s

def sql_literal(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        if np.isnan(v):
            return "NULL"
        return str(float(v))
    if isinstance(v, (pd.Timestamp,)):
        s = v.isoformat().replace("'", "''")
        return f"'{s}'"
    s = str(v).replace("'", "''")
    return f"'{s}'"

def build_params_sql(sql_template: str, params_raw: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(params_raw)
    for k, v in list(out.items()):
        if k in {"table_name", "temporal_predicate"}:
            continue
        out[k] = sql_literal(v)
    return out

def safe_format(template: str, params: Dict[str, Any]) -> str:
    try:
        return template.format(**params)
    except KeyError as e:
        raise KeyError(f"Missing placeholder {e} for template: {template[:200]} ...")

def normalize_sql_template_placeholders(sql_template: str) -> str:
    if not isinstance(sql_template, str):
        return sql_template
    sql_template = re.sub(
        r"'\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*'",
        lambda m: m.group(0) if m.group(1) in {"table_name", "temporal_predicate"} else "{" + m.group(1) + "}",
        sql_template,
    )
    sql_template = re.sub(
        r"\"\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*\"",
        lambda m: m.group(0) if m.group(1) in {"table_name", "temporal_predicate"} else "{" + m.group(1) + "}",
        sql_template,
    )
    return sql_template

def build_context_from_df(df: pd.DataFrame, commentary_col="commentary", overs_col="overs", include_overs=False, max_chars=6000) -> str:
    if commentary_col not in df.columns:
        return ""
    if include_overs and overs_col in df.columns:
        lines = []
        for _, row in df[[overs_col, commentary_col]].iterrows():
            comm = row.get(commentary_col)
            if pd.isna(comm):
                continue
            ov = row.get(overs_col)
            lines.append(f"{ov} | {comm}" if not pd.isna(ov) else str(comm))
        return truncate_text("\n".join(lines), max_chars)
    lines = df[commentary_col].dropna().astype(str).tolist()
    return truncate_text("\n".join(lines), max_chars)

def build_context_from_df_rows(df: pd.DataFrame, row_indices: List[Any], commentary_col="commentary", overs_col="overs", include_overs=False, max_chars=6000) -> str:
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
        lines = []
        for _, row in sub[[overs_col, commentary_col]].iterrows():
            comm = row.get(commentary_col)
            if pd.isna(comm):
                continue
            ov = row.get(overs_col)
            lines.append(f"{ov} | {comm}" if not pd.isna(ov) else str(comm))
        return truncate_text("\n".join(lines), max_chars)
    lines = sub[commentary_col].dropna().astype(str).tolist()
    return truncate_text("\n".join(lines), max_chars)

def _normalize_trace_idx_list(v: Any) -> List[int]:
    def _to_int_if_valid(x: Any) -> Optional[int]:
        if x is None:
            return None
        try:
            if pd.isna(x):
                return None
        except Exception:
            pass
        try:
            return int(x)
        except Exception:
            return None

    if v is None:
        return []
    if isinstance(v, np.ndarray):
        out = []
        for x in v.tolist():
            val = _to_int_if_valid(x)
            if val is not None:
                out.append(val)
        return out
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            val = _to_int_if_valid(x)
            if val is not None:
                out.append(val)
        return out
    val = _to_int_if_valid(v)
    return [val] if val is not None else []


def _unique_preserve(items: List[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _sorted_unique(items: List[int]) -> List[int]:
    out = set()
    for x in items:
        try:
            if pd.isna(x):
                continue
        except Exception:
            pass
        out.add(int(x))
    return sorted(out)


def _flatten_base_row_ids(trace_df: pd.DataFrame, trace_ids: List[int]) -> List[int]:
    if trace_df.empty or not trace_ids:
        return []
    idx_map = trace_df.set_index("__trace_row_idx")["__source_row_ids"].to_dict()
    out: List[int] = []
    for tid in trace_ids:
        try:
            if pd.isna(tid):
                continue
        except Exception:
            pass
        vals = idx_map.get(int(tid), [])
        if isinstance(vals, list):
            for x in vals:
                try:
                    if pd.isna(x):
                        continue
                except Exception:
                    pass
                out.append(int(x))
    return _unique_preserve(out)


def _union_all_base_row_ids(trace_df: pd.DataFrame) -> List[int]:
    if trace_df.empty or "__source_row_ids" not in trace_df.columns:
        return []
    out: List[int] = []
    for vals in trace_df["__source_row_ids"].tolist():
        if isinstance(vals, list):
            for x in vals:
                try:
                    if pd.isna(x):
                        continue
                except Exception:
                    pass
                out.append(int(x))
    return _unique_preserve(out)


def _make_base_trace_df(df: pd.DataFrame) -> pd.DataFrame:
    tdf = df.copy()
    tdf["__trace_row_idx"] = list(range(len(tdf)))
    tdf["__source_row_ids"] = [[int(i)] for i in range(len(tdf))]
    return tdf


def _make_trace_df_from_output(actual_df: pd.DataFrame, output_row_provenance: List[List[int]]) -> pd.DataFrame:
    tdf = actual_df.copy()
    tdf["__trace_row_idx"] = list(range(len(tdf)))
    clean_ids: List[List[int]] = []
    for ids in output_row_provenance:
        row_ids: List[int] = []
        for x in ids:
            try:
                if pd.isna(x):
                    continue
            except Exception:
                pass
            row_ids.append(int(x))
        clean_ids.append(row_ids)
    tdf["__source_row_ids"] = clean_ids
    return tdf


def _run_sql_on_env(env: Dict[str, pd.DataFrame], sql_text: str) -> pd.DataFrame:
    con = duckdb.connect(database=":memory:")
    try:
        for name, table_df in env.items():
            con.register(name, table_df)
        return con.execute(sql_text).fetchdf()
    finally:
        try:
            con.close()
        except Exception:
            pass


def _has_aggregate(select_expr: exp.Expression) -> bool:
    if not isinstance(select_expr, exp.Select):
        return False

    def _is_inside_window(node: exp.Expression) -> bool:
        cur = getattr(node, "parent", None)
        while cur is not None and not isinstance(cur, exp.Select):
            if isinstance(cur, exp.Window):
                return True
            cur = getattr(cur, "parent", None)
        return False

    def _contains_nonwindow_aggregate(expr_root: Optional[exp.Expression]) -> bool:
        if expr_root is None:
            return False
        for node in expr_root.walk(prune=lambda n: isinstance(n, exp.Select)):
            if isinstance(node, exp.AggFunc) and not _is_inside_window(node):
                return True
        return False

    for proj in select_expr.expressions or []:
        if _contains_nonwindow_aggregate(proj):
            return True

    where_expr = select_expr.args.get("where")
    if _contains_nonwindow_aggregate(where_expr):
        return True

    having_expr = select_expr.args.get("having")
    if _contains_nonwindow_aggregate(having_expr):
        return True

    order_expr = select_expr.args.get("order")
    if _contains_nonwindow_aggregate(order_expr):
        return True

    return False


def _from_items(select_expr: exp.Select) -> List[exp.Expression]:
    from_clause = select_expr.args.get("from_")
    if not from_clause:
        return []
    from_items = list(from_clause.expressions or [])
    if not from_items and getattr(from_clause, "this", None) is not None:
        from_items = [from_clause.this]
    return from_items


def _alias_or_name(expr: exp.Expression) -> Optional[str]:
    alias = getattr(expr, "alias", None)
    if alias is not None:
        alias_name = getattr(alias, "name", None)
        if alias_name:
            return str(alias_name)
    alias_or_name = getattr(expr, "alias_or_name", None)
    if alias_or_name:
        return str(alias_or_name)
    name = getattr(expr, "name", None)
    if name:
        return str(name)
    return None


def _select_alias_map(select_expr: exp.Select) -> Dict[str, exp.Expression]:
    alias_map: Dict[str, exp.Expression] = {}
    for proj in select_expr.expressions or []:
        if isinstance(proj, exp.Alias):
            alias_name = proj.alias
            if alias_name:
                alias_map[str(alias_name)] = proj.this.copy()
    return alias_map

def _rewrite_alias_references(expr_root: Optional[exp.Expression], alias_map: Dict[str, exp.Expression]) -> Optional[exp.Expression]:
    if expr_root is None or not alias_map:
        return expr_root

    def _rewrite(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Column) and not node.table:
            col_name = node.name
            repl = alias_map.get(str(col_name))
            if repl is not None:
                return repl.copy()
        return node

    return expr_root.transform(_rewrite)


def _expand_select_aliases_in_clauses(select_expr: exp.Select) -> exp.Select:
    alias_map = _select_alias_map(select_expr)
    if not alias_map:
        return select_expr

    group_expr = select_expr.args.get("group")
    if group_expr is not None:
        new_group_exprs = []
        for grp_item in list(group_expr.expressions or []):
            new_group_exprs.append(_rewrite_alias_references(grp_item, alias_map))
        group_expr.set("expressions", new_group_exprs)

    having_expr = select_expr.args.get("having")
    if having_expr is not None:
        target = having_expr.this if isinstance(having_expr, exp.Having) else having_expr
        rewritten = _rewrite_alias_references(target, alias_map)
        if isinstance(having_expr, exp.Having):
            having_expr.set("this", rewritten)
        else:
            select_expr.set("having", rewritten)

    order_expr = select_expr.args.get("order")
    if order_expr is not None:
        for ordered in order_expr.expressions or []:
            if isinstance(ordered, exp.Ordered):
                ordered.set("this", _rewrite_alias_references(ordered.this, alias_map))
            else:
                rewritten = _rewrite_alias_references(ordered, alias_map)
                if rewritten is not None:
                    ordered.replace(rewritten)

    return select_expr


def _normalize_query_ast(root_expr: exp.Expression) -> exp.Expression:
    for node in root_expr.walk():
        if isinstance(node, exp.Select):
            _expand_select_aliases_in_clauses(node)
    return root_expr


def normalize_query_sql_for_duckdb(sql_text: str) -> str:
    parsed = sqlglot.parse_one(sql_text, read="duckdb")
    normalized = _normalize_query_ast(parsed)
    return normalized.sql(dialect="duckdb")


def _sql_query_depth(expr: exp.Expression) -> int:
    child_depths = [_sql_query_depth(child) for child in expr.iter_expressions() if isinstance(child, exp.Expression)]
    base = 1 if isinstance(expr, (exp.Query, exp.Subquery, exp.Union, exp.Intersect, exp.Except)) else 0
    return base + (max(child_depths) if child_depths else 0)


def _unwrap_projection_expr(expr: exp.Expression) -> exp.Expression:
    cur = expr
    while isinstance(cur, (exp.Alias, exp.Paren)):
        cur = cur.this
    return cur


def _projection_is_direct_column(expr: exp.Expression) -> bool:
    cur = _unwrap_projection_expr(expr)
    return isinstance(cur, exp.Column) and not isinstance(cur.this, exp.Star)


def _source_width_from_relation(
    relation: exp.Expression,
    base_col_n: int,
    query_width_cache: Dict[int, Optional[int]],
    cte_widths: Dict[str, Optional[int]],
) -> Optional[int]:
    if isinstance(relation, exp.Table):
        name = relation.name
        return cte_widths.get(name, base_col_n)
    if isinstance(relation, exp.Subquery):
        inner = relation.this
        if isinstance(inner, exp.Expression):
            return _query_output_width(inner, base_col_n, query_width_cache, cte_widths)
    return None


def _relation_aliases(relation: exp.Expression) -> List[str]:
    aliases: List[str] = []
    alias = _alias_or_name(relation)
    if alias:
        aliases.append(alias)
    if isinstance(relation, exp.Table) and relation.name and relation.name not in aliases:
        aliases.append(relation.name)
    return aliases


def _query_output_width(
    expr: exp.Expression,
    base_col_n: int,
    query_width_cache: Dict[int, Optional[int]],
    cte_widths: Dict[str, Optional[int]],
) -> Optional[int]:
    cache_key = id(expr)
    if cache_key in query_width_cache:
        return query_width_cache[cache_key]

    target = expr
    if isinstance(target, exp.Subquery):
        target = target.this
    if isinstance(target, (exp.Union, exp.Intersect, exp.Except)):
        left = _query_output_width(target.this, base_col_n, query_width_cache, cte_widths) if isinstance(target.this, exp.Expression) else None
        right = _query_output_width(target.expression, base_col_n, query_width_cache, cte_widths) if isinstance(target.expression, exp.Expression) else None
        out = left if left is not None else right
        query_width_cache[cache_key] = out
        return out
    if not isinstance(target, exp.Select):
        found_select = target.find(exp.Select) if isinstance(target, exp.Expression) else None
        out = _query_output_width(found_select, base_col_n, query_width_cache, cte_widths) if isinstance(found_select, exp.Expression) else None
        query_width_cache[cache_key] = out
        return out

    source_widths: Dict[str, Optional[int]] = {}
    total_source_width = 0
    total_known = True
    from_items = _from_items(target)
    join_items = list(target.args.get("joins") or [])
    for rel in from_items + join_items:
        width = _source_width_from_relation(rel, base_col_n, query_width_cache, cte_widths)
        for name in _relation_aliases(rel):
            source_widths[name] = width
        if width is None:
            total_known = False
        else:
            total_source_width += int(width)

    width_total = 0
    unknown = False
    for proj in list(target.expressions or []):
        cur = _unwrap_projection_expr(proj)
        if isinstance(cur, exp.Star):
            if total_known:
                width_total += total_source_width
            else:
                unknown = True
                break
        elif isinstance(cur, exp.Column) and isinstance(cur.this, exp.Star):
            tbl = cur.table
            scoped_width = source_widths.get(tbl) if tbl else (total_source_width if total_known else None)
            if scoped_width is None:
                unknown = True
                break
            width_total += int(scoped_width)
        else:
            width_total += 1

    out = None if unknown else int(width_total)
    query_width_cache[cache_key] = out
    return out


def analyze_sql_projection_stats(sql_text: str, base_columns: Optional[List[str]] = None) -> Dict[str, Any]:
    try:
        parsed = _normalize_query_ast(sqlglot.parse_one(sql_text, read="duckdb"))
    except Exception as e:
        return {
            "targeted_source_column_count": None,
            "targeted_source_columns": [],
            "max_derived_column_count": None,
            "max_stage_column_count": None,
            "stage_projection_counts": [],
            "error": str(e),
        }

    base_col_n = len(base_columns or [])
    query_width_cache: Dict[int, Optional[int]] = {}
    cte_widths: Dict[str, Optional[int]] = {}
    stage_projection_counts: List[Dict[str, Any]] = []
    targeted_source_columns: set = set()

    with_clause = parsed.args.get("with_")
    if with_clause is not None:
        for cte in with_clause.expressions or []:
            cte_name = cte.alias_or_name
            cte_query = cte.this
            if cte_name and isinstance(cte_query, exp.Expression):
                cte_widths[cte_name] = _query_output_width(cte_query, base_col_n, query_width_cache, cte_widths)

    for idx, select_expr in enumerate(parsed.find_all(exp.Select)):
        select_output_width = _query_output_width(select_expr, base_col_n, query_width_cache, cte_widths)
        derived_count = 0
        for proj in list(select_expr.expressions or []):
            cur = _unwrap_projection_expr(proj)
            if not _projection_is_direct_column(proj) and not isinstance(cur, exp.Star):
                derived_count += 1
            for col in proj.find_all(exp.Column):
                if isinstance(col.this, exp.Star):
                    continue
                if col.name:
                    targeted_source_columns.add(col.name)
        stage_projection_counts.append({
            "stage_index": idx,
            "derived_column_count": int(derived_count),
            "output_column_count": int(select_output_width) if select_output_width is not None else None,
        })

    max_derived = max((x["derived_column_count"] for x in stage_projection_counts), default=0)
    known_widths = [x["output_column_count"] for x in stage_projection_counts if x["output_column_count"] is not None]
    return {
        "targeted_source_column_count": int(len(targeted_source_columns)),
        "targeted_source_columns": sorted(str(x) for x in targeted_source_columns),
        "max_derived_column_count": int(max_derived),
        "max_stage_column_count": int(max(known_widths)) if known_widths else None,
        "stage_projection_counts": stage_projection_counts,
        "error": None,
    }


def analyze_sql_difficulty(sql_text: str) -> Dict[str, Any]:
    try:
        parsed = _normalize_query_ast(sqlglot.parse_one(sql_text, read="duckdb"))
    except Exception as e:
        return {
            "label": "unknown",
            "score": None,
            "signature": "parse_error",
            "clauses": [],
            "features": {},
            "error": str(e),
        }

    has_where = bool(parsed.find(exp.Where))
    has_group_by = bool(parsed.find(exp.Group))
    has_having = bool(parsed.find(exp.Having))
    has_order_by = bool(parsed.find(exp.Order))
    has_limit = bool(parsed.find(exp.Limit))
    has_qualify = bool(parsed.find(exp.Qualify))
    has_distinct = any(bool(node.args.get("distinct")) for node in parsed.find_all(exp.Select))

    cte_count = sum(1 for _ in parsed.find_all(exp.CTE))
    join_count = sum(1 for _ in parsed.find_all(exp.Join))
    subquery_count = sum(1 for _ in parsed.find_all(exp.Subquery))
    set_op_count = sum(1 for _ in parsed.walk() if isinstance(_, (exp.Union, exp.Intersect, exp.Except)))
    aggregate_count = sum(1 for _ in parsed.walk() if isinstance(_, exp.AggFunc))
    window_count = sum(1 for _ in parsed.walk() if isinstance(_, exp.Window))
    case_count = sum(1 for _ in parsed.walk() if isinstance(_, exp.Case))
    select_count = sum(1 for _ in parsed.find_all(exp.Select))
    query_depth = _sql_query_depth(parsed)

    clauses: List[str] = ["select"]
    if has_where:
        clauses.append("where")
    if has_group_by:
        clauses.append("group_by")
    if has_having:
        clauses.append("having")
    if has_order_by:
        clauses.append("order_by")
    if has_limit:
        clauses.append("limit")
    if has_qualify:
        clauses.append("qualify")
    if has_distinct:
        clauses.append("distinct")
    if aggregate_count:
        clauses.append("aggregate")
    if case_count:
        clauses.append("case")
    if join_count:
        clauses.append("join")
    if cte_count:
        clauses.append("cte")
    if subquery_count:
        clauses.append("subquery")
    if window_count:
        clauses.append("window")
    if set_op_count:
        clauses.append("set_op")

    score = 0
    score += 1 if has_where else 0
    score += 1 if has_order_by else 0
    score += 1 if has_limit else 0
    score += 2 if has_group_by else 0
    score += 2 if has_having else 0
    score += 1 if has_distinct else 0
    score += min(join_count * 2, 6)
    score += min(cte_count * 2, 6)
    score += min(subquery_count * 2, 6)
    score += min(set_op_count * 3, 6)
    score += min(window_count * 3, 6)
    score += min(case_count, 4)
    score += 1 if aggregate_count > 0 else 0
    score += max(0, query_depth - 1)

    if score <= 2:
        label = "easy"
    elif score <= 5:
        label = "medium"
    elif score <= 9:
        label = "hard"
    else:
        label = "expert"

    return {
        "label": label,
        "score": int(score),
        "signature": "+".join(clauses),
        "clauses": clauses,
        "features": {
            "has_where": has_where,
            "has_group_by": has_group_by,
            "has_having": has_having,
            "has_order_by": has_order_by,
            "has_limit": has_limit,
            "has_qualify": has_qualify,
            "has_distinct": has_distinct,
            "select_count": int(select_count),
            "query_depth": int(query_depth),
            "aggregate_count": int(aggregate_count),
            "case_count": int(case_count),
            "join_count": int(join_count),
            "cte_count": int(cte_count),
            "subquery_count": int(subquery_count),
            "window_count": int(window_count),
            "set_op_count": int(set_op_count),
        },
        "error": None,
    }


def _ensure_supported_select(select_expr: exp.Expression, table_name: str = "df") -> Tuple[bool, Optional[str]]:
    if not isinstance(select_expr, exp.Select):
        return False, "only_select_supported"
    if select_expr.args.get("joins"):
        return False, "joins_not_supported"
    if any(isinstance(node, (exp.Union, exp.Intersect, exp.Except)) for node in select_expr.walk()):
        return False, "set_ops_not_supported"
    if any(isinstance(node, exp.Window) for node in select_expr.walk()):
        return False, "window_not_supported"
    from_items = _from_items(select_expr)
    if not from_items:
        return True, None
    if len(from_items) != 1:
        return False, "from_shape_not_supported"
    source = from_items[0]
    if not isinstance(source, (exp.Table, exp.Subquery)):
        return False, "only_table_sources_supported"
    return True, None


def _build_select_sql(
    source_sql: str,
    select_parts: List[str],
    where_expr: Optional[exp.Expression] = None,
    group_exprs: Optional[List[str]] = None,
    having_expr: Optional[exp.Expression] = None,
    order_expr: Optional[exp.Expression] = None,
) -> str:
    sql_text = f"SELECT {', '.join(select_parts)} FROM {source_sql}"
    if where_expr is not None:
        sql_text += f" WHERE {where_expr.sql(dialect='duckdb')}"
    if group_exprs:
        sql_text += f" GROUP BY {', '.join(group_exprs)}"
    if having_expr is not None:
        sql_text += f" HAVING {having_expr.sql(dialect='duckdb')}"
    if order_expr is not None:
        sql_text += f" {order_expr.sql(dialect='duckdb')}"
    return sql_text


def _execute_group_trace(
    source_sql: str,
    source_name: str,
    trace_col_sql: str,
    trace_env: Dict[str, pd.DataFrame],
    trace_df: pd.DataFrame,
    where_expr: Optional[exp.Expression],
    group_exprs_sql: List[str],
    having_expr: Optional[exp.Expression],
    order_expr: Optional[exp.Expression],
) -> Tuple[pd.DataFrame, str]:
    select_parts = [f"{g} AS __g{i}" for i, g in enumerate(group_exprs_sql)]
    select_parts.append(f"LIST({trace_col_sql} ORDER BY {trace_col_sql}) AS __trace_row_idxs")
    env = dict(trace_env)
    env[source_name] = trace_df
    sql_text = _build_select_sql(
        source_sql=source_sql,
        select_parts=select_parts,
        where_expr=where_expr,
        group_exprs=group_exprs_sql if group_exprs_sql else None,
        having_expr=having_expr,
        order_expr=order_expr,
    )
    return _run_sql_on_env(env, sql_text), sql_text


def _execute_final_trace(
    select_expr: exp.Select,
    trace_col_sql: str,
    trace_env: Dict[str, pd.DataFrame],
    trace_df: pd.DataFrame,
    source_name: Optional[str],
    materialize_subquery_source: bool,
    grouped: bool,
) -> Tuple[pd.DataFrame, str]:
    select_copy = select_expr.copy()
    if materialize_subquery_source and source_name is not None:
        from_clause = select_copy.args.get("from_")
        if from_clause is not None:
            from_items = list(from_clause.expressions or [])
            if not from_items and getattr(from_clause, "this", None) is not None:
                from_items = [from_clause.this]
            if len(from_items) == 1 and isinstance(from_items[0], exp.Subquery):
                materialized_source = sqlglot.parse_one(
                    f"SELECT * FROM {source_name}",
                    read="duckdb",
                ).args["from_"]
                select_copy.set("from_", materialized_source)
    if grouped:
        prov_expr = sqlglot.parse_one(
            f"SELECT LIST({trace_col_sql} ORDER BY {trace_col_sql}) AS __trace_row_idxs",
            read="duckdb",
        ).expressions[0]
    else:
        prov_expr = sqlglot.parse_one(
            f"SELECT {trace_col_sql} AS __trace_row_idx_out",
            read="duckdb",
        ).expressions[0]
    select_copy.append("expressions", prov_expr)
    sql_text = select_copy.sql(dialect="duckdb")
    env = dict(trace_env)
    if source_name is not None:
        env[source_name] = trace_df
    return _run_sql_on_env(env, sql_text), sql_text


def _node_entry(
    steps: List[Dict[str, Any]],
    *,
    node_type: str,
    label: str,
    sql_fragment: str,
    input_row_indices: List[int],
    output_row_indices: List[int],
    children: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    node_id = f"n{len(steps) + 1}"
    node = {
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "sql_fragment": sql_fragment,
        "input_row_indices": [int(x) for x in input_row_indices],
        "output_row_indices": [int(x) for x in output_row_indices],
        "children": children or [],
    }
    if extra:
        node.update(extra)
    steps.append({k: v for k, v in node.items() if k != "children"})
    return node


def _steps_to_row_progression_json(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    include_node_types = {
        "filter_where",
        "group_by",
        "filter_having",
        "project",
        "order_by",
    }
    step_entries: List[Dict[str, Any]] = []
    max_width = 0
    for step in steps:
        node_type = step.get("node_type")
        if node_type not in include_node_types:
            continue
        if node_type == "group_by" and step.get("sql_fragment") == "GLOBAL AGGREGATE":
            continue
        vals = [int(x) for x in (step.get("output_row_indices") or [])]
        max_width = max(max_width, len(vals))
        step_entries.append({
            "step_index": len(step_entries),
            "node_id": step.get("node_id"),
            "label": step.get("label"),
            "node_type": node_type,
            "row_indices": vals,
            "row_count": len(vals),
        })
    return {
        "num_steps": len(step_entries),
        "max_row_count": max_width,
        "steps": step_entries,
    }


def _trace_select_with_env(
    select_expr: exp.Select,
    env_actual: Dict[str, pd.DataFrame],
    env_trace: Dict[str, pd.DataFrame],
    *,
    label: str,
) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    ok, reason = _ensure_supported_select(select_expr)
    if not ok:
        raise ValueError(reason or "unsupported_query")

    from_items = _from_items(select_expr)
    if not from_items:
        final_actual_df = _run_sql_on_env({k: v for k, v in env_actual.items()}, select_expr.sql(dialect="duckdb"))
        scan_rows = _sorted_unique([x for df_ in env_trace.values() for x in _union_all_base_row_ids(df_)])
        output_row_provenance = [scan_rows[:] for _ in range(len(final_actual_df))]
        root = _node_entry(
            steps,
            node_type="query",
            label=label,
            sql_fragment=select_expr.sql(dialect="duckdb"),
            input_row_indices=scan_rows,
            output_row_indices=scan_rows,
            extra={
                "step_sql": select_expr.sql(dialect="duckdb"),
                "output_row_to_base_rows": output_row_provenance,
            },
        )
        return {
            "actual_df": final_actual_df,
            "output_row_provenance": output_row_provenance,
            "row_indices_scanned": scan_rows,
            "row_indices_contributing": scan_rows,
            "provenance_tree": root,
            "provenance_steps": steps,
            "step_row_progression": _steps_to_row_progression_json(steps),
        }

    source = from_items[0]
    if isinstance(source, exp.Subquery):
        source_alias = _alias_or_name(source)
        inner_query = source.this
        if not source_alias or not isinstance(inner_query, exp.Select):
            raise ValueError("only_table_sources_supported")
        traced_source = _trace_select_with_env(inner_query, env_actual, env_trace, label=f"{label}:subquery:{source_alias}")
        env_actual = dict(env_actual)
        env_trace = dict(env_trace)
        env_actual[source_alias] = traced_source["actual_df"]
        env_trace[source_alias] = _make_trace_df_from_output(
            traced_source["actual_df"],
            traced_source["output_row_provenance"],
        )
        source_is_subquery = True
        source_name = source_alias
        source_sql = source_alias
        source_trace_ref = f"{source_alias}.__trace_row_idx"
        source_trace_df = env_trace[source_name]
    else:
        source_is_subquery = False
        source_name = source.name
        source_sql = source.sql(dialect="duckdb")
        source_trace_ref = f"{_alias_or_name(source) or source_name}.__trace_row_idx"
        source_trace_df = env_trace[source_name]

    children_chain: List[Dict[str, Any]] = []
    scan_rows = _union_all_base_row_ids(source_trace_df)
    current_node = _node_entry(
        steps,
        node_type="scan",
        label=f"{label}:scan",
        sql_fragment=f"FROM {source_sql}",
        input_row_indices=scan_rows,
        output_row_indices=scan_rows,
        extra={
            "step_sql": f"SELECT __trace_row_idx, __source_row_ids FROM {source_sql}",
            "output_row_to_base_rows": [[int(x)] for x in scan_rows],
        },
    )
    children_chain.append(current_node)

    where_expr = select_expr.args.get("where")
    filtered_trace_df = source_trace_df
    joins_present = bool(select_expr.args.get("joins"))
    if where_expr is not None and not joins_present:
        where_sql = _build_select_sql(
            source_sql=source_sql,
            select_parts=[f"{source_trace_ref} AS __trace_row_idx"],
            where_expr=where_expr.this if isinstance(where_expr, exp.Where) else where_expr,
        )
        trace_env_for_where = dict(env_trace)
        trace_env_for_where[source_name] = source_trace_df
        where_df = _run_sql_on_env(trace_env_for_where, where_sql)
        kept_trace_ids = _normalize_trace_idx_list(where_df["__trace_row_idx"].tolist()) if "__trace_row_idx" in where_df.columns else []
        filtered_trace_df = source_trace_df[source_trace_df["__trace_row_idx"].isin(kept_trace_ids)].copy()
        where_rows = _union_all_base_row_ids(filtered_trace_df)
        where_node = _node_entry(
            steps,
            node_type="filter_where",
            label=f"{label}:where",
            sql_fragment=(where_expr.this if isinstance(where_expr, exp.Where) else where_expr).sql(dialect="duckdb"),
            input_row_indices=scan_rows,
            output_row_indices=where_rows,
            extra={
                "step_sql": where_sql,
                "output_row_to_base_rows": [[int(x)] for x in where_rows],
            },
        )
        current_node["children"] = [where_node]
        current_node = where_node

    group_clause = select_expr.args.get("group")
    having_expr = select_expr.args.get("having")
    order_expr = select_expr.args.get("order")
    group_exprs_sql = [g.sql(dialect="duckdb") for g in group_clause.expressions] if group_clause else []
    grouped = bool(group_exprs_sql) or _has_aggregate(select_expr) or having_expr is not None

    final_actual_df = _run_sql_on_env({k: v for k, v in env_actual.items()}, select_expr.sql(dialect="duckdb"))
    output_row_provenance: List[List[int]] = []

    if grouped:
        pre_group_prov: List[List[int]] = [scan_rows[:]] if scan_rows else []
        pre_group_sql = ""
        group_keys: List[Dict[str, Any]] = []
        if not joins_present:
            pre_group_df, pre_group_sql = _execute_group_trace(
                source_sql,
                source_name,
                source_trace_ref,
                env_trace,
                source_trace_df,
                where_expr.this if isinstance(where_expr, exp.Where) else where_expr,
                group_exprs_sql,
                None,
                None,
            )
            pre_group_prov = [
                _flatten_base_row_ids(filtered_trace_df, _normalize_trace_idx_list(v))
                for v in pre_group_df.get("__trace_row_idxs", []).tolist()
            ] if "__trace_row_idxs" in pre_group_df.columns else []
            group_keys = [
                {k: normalize_cell(v) for k, v in row.items() if k.startswith("__g")}
                for row in pre_group_df.to_dict(orient="records")
            ] if len(pre_group_df) else []
        group_node = _node_entry(
            steps,
            node_type="group_by",
            label=f"{label}:group_by",
            sql_fragment=(group_clause.sql(dialect="duckdb") if group_clause is not None else "GLOBAL AGGREGATE"),
            input_row_indices=_union_all_base_row_ids(filtered_trace_df),
            output_row_indices=_unique_preserve([x for ids in pre_group_prov for x in ids]),
            extra={
                "step_sql": pre_group_sql,
                "group_keys": group_keys,
                    "group_count": int(len(pre_group_prov)),
                    "output_row_to_base_rows": pre_group_prov,
                },
            )
        current_node["children"] = [group_node]
        current_node = group_node

        if having_expr is not None:
            having_prov = pre_group_prov
            having_sql = ""
            if not joins_present:
                try:
                    having_df, having_sql = _execute_group_trace(
                        source_sql,
                        source_name,
                        source_trace_ref,
                        env_trace,
                        source_trace_df,
                        where_expr.this if isinstance(where_expr, exp.Where) else where_expr,
                        group_exprs_sql,
                        having_expr.this if isinstance(having_expr, exp.Having) else having_expr,
                        None,
                    )
                    having_prov = [
                        _flatten_base_row_ids(filtered_trace_df, _normalize_trace_idx_list(v))
                        for v in having_df.get("__trace_row_idxs", []).tolist()
                    ] if "__trace_row_idxs" in having_df.columns else []
                except Exception:
                    having_prov = pre_group_prov
            having_node = _node_entry(
                steps,
                node_type="filter_having",
                label=f"{label}:having",
                sql_fragment=(having_expr.this if isinstance(having_expr, exp.Having) else having_expr).sql(dialect="duckdb"),
                input_row_indices=group_node["output_row_indices"],
                output_row_indices=_unique_preserve([x for ids in having_prov for x in ids]),
                extra={
                    "step_sql": having_sql,
                    "group_count": int(len(having_prov)),
                    "output_row_to_base_rows": having_prov,
                },
            )
            current_node["children"] = [having_node]
            current_node = having_node

        final_trace_df, final_trace_sql = _execute_final_trace(
            select_expr,
            source_trace_ref,
            env_trace,
            source_trace_df,
            source_name,
            source_is_subquery,
            True,
        )
        output_row_provenance = [
            _flatten_base_row_ids(source_trace_df, _normalize_trace_idx_list(v))
            for v in final_trace_df.get("__trace_row_idxs", []).tolist()
        ] if "__trace_row_idxs" in final_trace_df.columns else []
    else:
        final_trace_df, final_trace_sql = _execute_final_trace(
            select_expr,
            source_trace_ref,
            env_trace,
            source_trace_df,
            source_name,
            source_is_subquery,
            False,
        )
        output_row_provenance = [
            _flatten_base_row_ids(source_trace_df, [int(v)])
            for v in final_trace_df.get("__trace_row_idx_out", []).tolist()
        ] if "__trace_row_idx_out" in final_trace_df.columns else []

    project_output_rows = _unique_preserve([x for ids in output_row_provenance for x in ids])
    project_node = _node_entry(
        steps,
        node_type="project",
        label=f"{label}:project",
        sql_fragment="SELECT ...",
        input_row_indices=current_node["output_row_indices"],
        output_row_indices=project_output_rows,
        extra={
            "step_sql": final_trace_sql,
            "output_row_to_base_rows": output_row_provenance,
        },
    )
    current_node["children"] = [project_node]
    current_node = project_node

    if order_expr is not None:
        order_node = _node_entry(
            steps,
            node_type="order_by",
            label=f"{label}:order_by",
            sql_fragment=order_expr.sql(dialect="duckdb"),
            input_row_indices=project_output_rows,
            output_row_indices=_unique_preserve([x for ids in output_row_provenance for x in ids]),
            extra={
                "step_sql": final_trace_sql,
                "output_row_to_base_rows": output_row_provenance,
            },
        )
        current_node["children"] = [order_node]
        current_node = order_node

    root = _node_entry(
        steps,
        node_type="query",
        label=label,
        sql_fragment=select_expr.sql(dialect="duckdb"),
        input_row_indices=scan_rows,
        output_row_indices=current_node["output_row_indices"],
        children=children_chain,
        extra={
            "step_sql": select_expr.sql(dialect="duckdb"),
            "output_row_to_base_rows": output_row_provenance,
        },
    )

    return {
        "actual_df": final_actual_df,
        "output_row_provenance": output_row_provenance,
        "row_indices_scanned": scan_rows,
        "row_indices_contributing": _sorted_unique([x for ids in output_row_provenance for x in ids]),
        "provenance_tree": root,
        "provenance_steps": steps,
        "step_row_progression": _steps_to_row_progression_json(steps),
    }


def extract_row_indices_from_query(query: str, df: pd.DataFrame, result_df: Optional[pd.DataFrame], table_name: str = "df") -> Dict[str, Any]:
    try:
        parsed = _normalize_query_ast(sqlglot.parse_one(query, read="duckdb"))
        parsed_with = parsed.args.get("with_")
        if parsed_with is not None and parsed_with.args.get("recursive"):
            raise ValueError("recursive_cte_not_supported")

        base_actual = df.copy()
        env_actual: Dict[str, pd.DataFrame] = {table_name: base_actual}
        env_trace: Dict[str, pd.DataFrame] = {table_name: _make_base_trace_df(df)}

        cte_nodes: List[Dict[str, Any]] = []
        cte_steps: List[Dict[str, Any]] = []
        with_clause = parsed.args.get("with_")
        if with_clause is not None:
            for cte in with_clause.expressions:
                cte_name = cte.alias_or_name
                cte_query = cte.this
                if not isinstance(cte_query, exp.Select):
                    raise ValueError("cte_query_type_not_supported")
                traced = _trace_select_with_env(cte_query, env_actual, env_trace, label=f"cte:{cte_name}")
                env_actual[cte_name] = traced["actual_df"]
                env_trace[cte_name] = _make_trace_df_from_output(traced["actual_df"], traced["output_row_provenance"])
                cte_nodes.append({
                    **traced["provenance_tree"],
                    "node_type": "cte",
                    "cte_name": cte_name,
                })
                cte_steps.extend(traced["provenance_steps"])

        main_query = parsed.copy()
        main_query.set("with_", None)
        if not isinstance(main_query, exp.Select):
            raise ValueError("main_query_type_not_supported")
        traced_main = _trace_select_with_env(main_query, env_actual, env_trace, label="final_query")

        tree = traced_main["provenance_tree"]
        if cte_nodes:
            tree["children"] = cte_nodes + tree.get("children", [])

        return {
            "row_indices_scanned": traced_main["row_indices_scanned"],
            "row_indices_contributing": traced_main["row_indices_contributing"],
            "row_indices_scanned_count": len(traced_main["row_indices_scanned"]),
            "row_indices_contributing_count": len(traced_main["row_indices_contributing"]),
            "output_row_provenance": traced_main["output_row_provenance"],
            "provenance_tree": tree,
            "provenance_steps": cte_steps + traced_main["provenance_steps"],
            "step_row_progression": _steps_to_row_progression_json(cte_steps + traced_main["provenance_steps"]),
            "provenance_supported": True,
            "provenance_error": None,
        }
    except Exception as e:
        return {
            "row_indices_scanned": [],
            "row_indices_contributing": [],
            "row_indices_scanned_count": 0,
            "row_indices_contributing_count": 0,
            "output_row_provenance": None,
            "provenance_tree": None,
            "provenance_steps": [],
            "step_row_progression": {"num_steps": 0, "max_row_count": 0, "steps": []},
            "provenance_supported": False,
            "provenance_error": str(e),
        }

# -----------------------------
# Template loader (copied)
# -----------------------------
def read_json_local(path: str) -> Any:
    return read_json(path)

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
        mapped = []
        for t in raw:
            if not isinstance(t, dict):
                continue
            mapped.append({
                "template_id": t.get("template_id", t.get("id")),
                "idx": t.get("idx"),
                "item_id": t.get("item_id", t.get("id")),
                "question": t.get("question", ""),
                "paraphrases": t.get("paraphrases") or [],
                "sql": t.get("sql") or t.get("query"),
                "original_sql": t.get("original_sql"),
                "description": t.get("description") or t.get("exp"),
                "variables": t.get("variables") or [],
                "primary_key": t.get("primary_key"),
                "intent": t.get("intent"),
                "structure": t.get("structure"),
            })
        return mapped

    data = read_json_local(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "final" in data and isinstance(data["final"], list):
        return data["final"]
    raise ValueError(f"Template JSON must be a list, or a dict with key 'final' as a list. Got: {type(data)} in {path}")

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
    return merged

# -----------------------------
# Split labeling helpers (copied semantics)
# -----------------------------
def _has_temporality(rec: Dict[str, Any]) -> bool:
    pred = rec.get("temporal_predicate")
    rel = rec.get("temporal_relation")
    if pred is None:
        return False
    if isinstance(pred, str) and pred.replace(" ", "") == "(1=1)":
        return False
    return True if pred is not None else bool(rel)


# -----------------------------
# Variable normalization helper
# -----------------------------
def normalize_variables_list(vars_any: Any) -> List[str]:
    """Normalize a template's `variables` field to a list of variable names.

    Handles cases where JSON templates store variables as:
      - list[str]
      - comma-separated string
      - single string
      - tuple/set
    Avoids the common pitfall where `list("temporal_predicate")` becomes a list of characters.
    """
    if vars_any is None:
        return []
    if isinstance(vars_any, list):
        return [str(v).strip() for v in vars_any if str(v).strip()]
    if isinstance(vars_any, (tuple, set)):
        return [str(v).strip() for v in list(vars_any) if str(v).strip()]
    if isinstance(vars_any, str):
        s = vars_any.strip()
        if not s:
            return []
        # Split on commas if present; otherwise split on whitespace
        if "," in s:
            parts = [p.strip() for p in s.split(",")]
        else:
            parts = [p.strip() for p in s.split()]
        return [p for p in parts if p]
    # Fallback: try to iterate, but avoid turning arbitrary objects into character lists
    try:
        it = list(vars_any)
        # If the iterable is a list of single-character strings, treat as invalid and return empty
        if it and all(isinstance(x, str) and len(x) == 1 for x in it):
            return []
        return [str(v).strip() for v in it if str(v).strip()]
    except Exception:
        return []

def _init_group_from_variables(variables: Any) -> str:
    variables = normalize_variables_list(variables)
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

def record_key(match_path: str, template_index: Any, init_id: Any, temporal_relation: Any, span_bucket: Any = None) -> str:
    return "|".join([
        str(match_path),
        str(template_index),
        str(init_id),
        "" if temporal_relation is None else str(temporal_relation),
        "" if span_bucket is None else str(span_bucket),
    ])

# -----------------------------
# Temporal predicate helper (simplified)
# -----------------------------
def snap_over_ball(x: float) -> float:
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
    b1 = snap_over_ball(rng.uniform(lo, hi))
    b2 = snap_over_ball(rng.uniform(lo, hi))
    if b1 == b2:
        b2 = snap_over_ball(rng.uniform(lo, hi))
    a, b = tuple(sorted((b1, b2)))
    r = str(relation).lower()

    sql_map = {
        "before":        f"({field} < {a})",
        "after":         f"({field} > {b})",
        "before_or_at":  f"({field} <= {a})",
        "after_or_at":   f"({field} >= {b})",
        "between":       f"({field} BETWEEN {a} AND {b})",
        "overlaps":      f"({field} <= {b} AND {a} <= {field})",
    }
    nl_map = {
        "before":        f"when over is before {a}",
        "after":         f"when over is after {b}",
        "before_or_at":  f"when over is at or before {a}",
        "after_or_at":   f"when over is at or after {b}",
        "between":       f"when over is between {a} and {b}",
        "overlaps":      f"when over falls between {a} and {b}",
    }
    if r not in sql_map:
        return "(1=1)", "the entire match", None
    return sql_map[r], nl_map[r], r

def pick_relation(rng: random.Random) -> str:
    return rng.choice(["before", "after", "before_or_at", "after_or_at", "between", "overlaps"])

def compute_entity_spans(df: pd.DataFrame, overs_num: pd.Series, col: str) -> Dict[str, Dict[str, float]]:
    """Compute per-entity min/max overs and count of appearances.

    Returns dict: name -> {min_over, max_over, count}
    """
    out: Dict[str, Dict[str, float]] = {}
    if col not in df.columns:
        return out

    tmp = pd.DataFrame({"name": df[col], "ov": overs_num})
    tmp = tmp.dropna(subset=["name", "ov"])
    if tmp.empty:
        return out

    grp = tmp.groupby("name")["ov"].agg(["min", "max", "count"]).reset_index()
    for _, r in grp.iterrows():
        out[str(r["name"])] = {
            "min_over": float(r["min"]),
            "max_over": float(r["max"]),
            "count": float(r["count"]),
        }
    return out


def eligible_by_span(
    spans: Dict[str, Dict[str, float]],
    o_min: Optional[float],
    o_max: Optional[float],
    bucket: str,
    min_rows: int = 1,
    coverage_threshold: float = 0.8,
) -> set:
    """Return entity names whose over-span matches the requested bucket.

    bucket: first_half | second_half | middle | almost_entire
    """
    if o_min is None or o_max is None or not (o_min < o_max):
        return set(spans.keys())

    T = float(o_max - o_min)
    mid = float(o_min + 0.5 * T)
    one_third = float(o_min + (1.0 / 3.0) * T)
    two_third = float(o_min + (2.0 / 3.0) * T)

    b = (bucket or "").lower().strip()
    out = set()

    for name, s in spans.items():
        mn = float(s.get("min_over", o_min))
        mx = float(s.get("max_over", o_max))
        cnt = int(float(s.get("count", 0)))
        if cnt < int(min_rows):
            continue

        cov = (mx - mn) / T if T > 0 else 1.0

        if b == "first_half":
            if mx <= mid:
                out.add(name)
        elif b == "second_half":
            if mn >= mid:
                out.add(name)
        elif b == "middle":
            if mn >= one_third and mx <= two_third:
                out.add(name)
        elif b == "almost_entire":
            if cov >= float(coverage_threshold):
                out.add(name)
        else:
            out.add(name)

    return out

# -----------------------------
# Param sampler (minimal; reuse your current behavior by importing if desired)
# -----------------------------
def sample_params_for_template(
    df: pd.DataFrame,
    variables: List[str],
    rng: random.Random,
    df_scope: Optional[pd.DataFrame] = None,
    allowed_batsmen: Optional[set] = None,
    allowed_bowlers: Optional[set] = None,
) -> Optional[Dict[str, Any]]:
    """Sample initialization params for a template.

    - If df_scope is provided, sample batsman/bowler only from that scoped subset.
    - If allowed_batsmen/allowed_bowlers are provided, further restrict sampling.
    """
    params: Dict[str, Any] = {"table_name": "df"}
    scope = df_scope if df_scope is not None else df

    batsmen = scope["batsman"].dropna().unique().tolist() if "batsman" in scope.columns else []
    bowlers = scope["bowler"].dropna().unique().tolist() if "bowler" in scope.columns else []

    if allowed_batsmen is not None:
        batsmen = [x for x in batsmen if x in allowed_batsmen]
    if allowed_bowlers is not None:
        bowlers = [x for x in bowlers if x in allowed_bowlers]

    if "batsman" in variables:
        if not batsmen:
            return None
        params["batsman"] = rng.choice(batsmen)
    if "bowler" in variables:
        if not bowlers:
            return None
        params["bowler"] = rng.choice(bowlers)

    # temporal handled outside
    return params

# -----------------------------
# Pipeline config for split mode
# -----------------------------
@dataclass
class SplitConfig:
    templates_paths: List[str]
    matches_glob: str
    output_dir: str
    seed: int = 42
    context_max_chars: int = 0
    answer_max_rows: int = 0
    drop_zeroish: bool = False
    max_zeroish_frac: float = 0.02
    max_init_attempts: int = 20

    # split knobs
    split_num_matches: int = 5
    min_match_rows: int = 201
    split_templates_per_match: int = 5
    split_inits_per_template_per_match: int = 3
    temporal_all_phrases: bool = True
    split_use_base_question_only: bool = False

    # New: template coverage knobs
    cover_all_templates_once: bool = False
    cover_all_templates_pool: str = "all"  # all | init_relevant
    
    # span-conditioned initialization (optional)
    span_init_mode: str = "none"  # none | batsman | bowler | both
    # Provide either span_bucket (single) or span_buckets (comma-separated). If span_buckets is set, it takes precedence.
    # Valid values: first_half, second_half, middle, almost_entire, entire
    # Special value: all -> expands to first_half, second_half, entire
    span_bucket: str = ""  # single bucket
    span_buckets: str = ""  # comma-separated buckets
    span_min_rows: int = 1
    span_coverage_threshold: float = 0.8

    # disjointness
    exclude_keys_json: str = ""


def generate_split_dataset(cfg: SplitConfig) -> Dict[str, Any]:
    rng = random.Random(cfg.seed)
    ensure_dir(cfg.output_dir)

    exclude_keys = set()
    if cfg.exclude_keys_json:
        try:
            obj = read_json(cfg.exclude_keys_json)
            keys = obj.get("keys") if isinstance(obj, dict) else None
            if isinstance(keys, list):
                exclude_keys = set(str(k) for k in keys)
        except Exception:
            exclude_keys = set()

    templates = load_templates(cfg.templates_paths)
    # Normalize variables for all templates (JSON sometimes stores this as a string)
    for tt in templates:
        tt["variables"] = normalize_variables_list(tt.get("variables"))
    for i, t in enumerate(templates):
        t["template_index"] = i

    match_paths_all = sorted(glob.glob(cfg.matches_glob))
    if not match_paths_all:
        raise FileNotFoundError(f"No match CSV files found for glob: {cfg.matches_glob}")

    eligible_match_paths: List[str] = []
    skipped_small_matches: List[Dict[str, Any]] = []
    for match_path in match_paths_all:
        try:
            row_count = int(len(pd.read_csv(match_path)))
        except Exception as e:
            skipped_small_matches.append({
                "match_path": match_path,
                "error": f"read_csv failed during match filtering: {e}",
            })
            continue
        if row_count > int(cfg.min_match_rows):
            eligible_match_paths.append(match_path)
        else:
            skipped_small_matches.append({
                "match_path": match_path,
                "row_count": row_count,
                "error": f"match has {row_count} rows; requires > {int(cfg.min_match_rows)}",
            })

    if not eligible_match_paths:
        raise ValueError(
            f"No eligible match CSV files found for glob: {cfg.matches_glob} with row count > {int(cfg.min_match_rows)}"
        )

    chosen_matches = rng.sample(eligible_match_paths, min(cfg.split_num_matches, len(eligible_match_paths)))

    # Template pool selection
    def _is_init_relevant(vars_list: Any) -> bool:
        """
        Templates that are interesting for initialization / temporality-focused analysis:
          - any batsman/bowler variables
          - OR temporal-related variables (predicate or phrase)
        """
        s = set(normalize_variables_list(vars_list))
        return any(v in s for v in [
            "batsman", "batsman1", "batsman2",
            "bowler", "bowler1", "bowler2",
            "temporal_predicate",
            "temporal_phrase",
        ])

    pool_mode = (cfg.cover_all_templates_pool or "all").lower().strip()
    if pool_mode == "init_relevant":
        templates_pool = [tt for tt in templates if _is_init_relevant(tt.get("variables") or [])]
    else:
        templates_pool = list(templates)

    # Pre-assign templates to matches when we want full coverage across the sampled matches.
    templates_by_match: Dict[str, List[Dict[str, Any]]] = {}
    if cfg.cover_all_templates_once:
        if not chosen_matches:
            raise ValueError("No matches selected; cannot cover templates.")
        # Ensure capacity is enough to cover all templates at least once.
        num_m = len(chosen_matches)
        num_t = len(templates_pool)
        per_match_cap = max(int(cfg.split_templates_per_match), int(math.ceil(num_t / max(1, num_m))))

        shuffled = list(templates_pool)
        rng.shuffle(shuffled)
        for m in chosen_matches:
            templates_by_match[m] = []

        # Round-robin assignment of templates to matches.
        for i, tt in enumerate(shuffled):
            m = chosen_matches[i % num_m]
            templates_by_match[m].append(tt)

        # If any match exceeds cap (shouldn't happen with computed cap), truncate deterministically.
        for m in chosen_matches:
            if len(templates_by_match[m]) > per_match_cap:
                templates_by_match[m] = templates_by_match[m][:per_match_cap]

    out_rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = list(skipped_small_matches)
    kept = 0
    kept_zeroish = 0

    def zeroish_ok(is_zeroish: bool) -> bool:
        nonlocal kept, kept_zeroish
        if not is_zeroish:
            return True
        if cfg.max_zeroish_frac <= 0:
            return False
        return (kept_zeroish + 1) / max(1, kept + 1) <= cfg.max_zeroish_frac

    for match_i, match_path in enumerate(chosen_matches):
        try:
            df = pd.read_csv(match_path)
        except Exception as e:
            errors.append({"match_path": match_path, "error": f"read_csv failed: {e}"})
            continue

        full_context_no_overs = build_context_from_df(df, include_overs=False, max_chars=cfg.context_max_chars)
        full_context_with_overs = build_context_from_df(df, include_overs=True, max_chars=cfg.context_max_chars)

        overs_series = pd.to_numeric(df["overs"], errors="coerce").dropna() if "overs" in df.columns else pd.Series([], dtype=float)
        o_min = float(overs_series.min()) if not overs_series.empty else None
        o_max = float(overs_series.max()) if not overs_series.empty else None

        overs_num = pd.to_numeric(df["overs"], errors="coerce") if "overs" in df.columns else pd.Series([np.nan] * len(df))

        batsman_spans = compute_entity_spans(df, overs_num, "batsman")
        bowler_spans = compute_entity_spans(df, overs_num, "bowler")

        mode = (cfg.span_init_mode or "none").lower().strip()

        # Span bucket expansion: allow one run to generate multiple conditions.
        # Precedence: span_buckets (comma-separated) > span_bucket (single).
        raw_buckets = (cfg.span_buckets or "").strip()
        if raw_buckets:
            span_bucket_list = [b.strip().lower() for b in raw_buckets.split(",") if b.strip()]
        else:
            sb = (cfg.span_bucket or "").strip().lower()
            span_bucket_list = [sb] if sb else [""]

        # Special keyword: all -> first_half, second_half, entire
        if len(span_bucket_list) == 1 and span_bucket_list[0] == "all":
            span_bucket_list = ["first_half", "second_half", "entire"]

        # Normalize synonyms
        norm_map = {
            "full": "entire",
            "whole": "entire",
            "entire_match": "entire",
        }
        span_bucket_list = [norm_map.get(b, b) for b in span_bucket_list]

        # Precompute allowed sets per bucket.
        allowed_by_bucket: Dict[str, Tuple[Optional[set], Optional[set]]] = {}
        for bname in span_bucket_list:
            b = (bname or "").lower().strip()
            # "entire" means no restriction.
            if mode == "none" or not b or b == "entire":
                allowed_by_bucket[bname] = (None, None)
                continue

            ab = None
            aw = None
            if mode in {"batsman", "both"}:
                ab = eligible_by_span(
                    batsman_spans,
                    o_min,
                    o_max,
                    bucket=b,
                    min_rows=cfg.span_min_rows,
                    coverage_threshold=cfg.span_coverage_threshold,
                )
            if mode in {"bowler", "both"}:
                aw = eligible_by_span(
                    bowler_spans,
                    o_min,
                    o_max,
                    bucket=b,
                    min_rows=cfg.span_min_rows,
                    coverage_threshold=cfg.span_coverage_threshold,
                )
            allowed_by_bucket[bname] = (ab, aw)

        # Determine chosen_templates for this match
        if cfg.cover_all_templates_once:
            chosen_templates = templates_by_match.get(match_path, [])
        else:
            # Default behavior: sample a subset from the pool.
            # We prioritize templates that are \"init relevant\" (batsman/bowler/temporal)
            # so that we get a healthy mix of temporal + entity-initialized questions,
            # rather than only generic temporal templates.
            base_pool = templates_pool
            if not base_pool:
                continue

            k = min(cfg.split_templates_per_match, len(base_pool))

            init_relevant_pool = [
                tt for tt in base_pool
                if _is_init_relevant(tt.get("variables") or [])
            ]
            non_init_pool = [tt for tt in base_pool if tt not in init_relevant_pool]

            if init_relevant_pool:
                n_init = min(len(init_relevant_pool), k)
                chosen_init = rng.sample(init_relevant_pool, n_init)
                remaining = k - n_init
                if remaining > 0 and non_init_pool:
                    chosen_other = rng.sample(
                        non_init_pool,
                        min(remaining, len(non_init_pool)),
                    )
                else:
                    chosen_other = []
                chosen_templates = chosen_init + chosen_other
            else:
                # Fallback: no init-relevant templates in this pool; sample uniformly.
                chosen_templates = rng.sample(base_pool, k)

        for t in chosen_templates:
            sql_template = t.get("original_sql") if t.get("original_sql") else t.get("sql")
            sql_template = normalize_sql_template_placeholders(sql_template)
            if not sql_template:
                continue

            # Normalize declared variables, and also infer variables from placeholders in SQL/question.
            variables = normalize_variables_list(t.get("variables"))

            inferred_vars: set = set()
            try:
                inferred_vars.update(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(sql_template)))
            except Exception:
                pass
            try:
                q0 = str(t.get("question") or "")
                inferred_vars.update(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", q0))
                paras = t.get("paraphrases") or []
                if isinstance(paras, list):
                    for qq in paras:
                        inferred_vars.update(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(qq)))
            except Exception:
                pass

            # Merge and drop known non-init placeholders
            variables = sorted(set(variables) | set(inferred_vars))

            for init_salt in range(cfg.split_inits_per_template_per_match):
                # Generate one init per requested span bucket (e.g., first_half/second_half/entire) in the same run.
                for span_bucket_name in span_bucket_list:
                    rels: List[Optional[str]] = [None]
                    if "temporal_predicate" in variables and cfg.temporal_all_phrases:
                        rels = [None, "before", "after", "before_or_at", "after_or_at", "between", "overlaps"]
                    elif "temporal_predicate" in variables:
                        rel_seed = cfg.seed + 99991 * (init_salt + 1) + 17 * (int(t["template_index"]) + 1) + 101 * (match_i + 1)
                        rels = [pick_relation(random.Random(rel_seed))]

                    for rel in rels:
                        made_record = False
                        zeroish_retry_reason: Optional[str] = None

                        for attempt in range(max(1, int(cfg.max_init_attempts))):
                            attempt_seed = (
                                cfg.seed
                                + 99991 * (init_salt + 1)
                                + 17 * (int(t["template_index"]) + 1)
                                + 101 * (match_i + 1)
                                + 1009 * (attempt + 1)
                                + 53 * (len(out_rows) + 1)
                            )
                            rng_local = random.Random(attempt_seed)
                            allowed_batsmen, allowed_bowlers = allowed_by_bucket.get(span_bucket_name, (None, None))

                            params_raw = {"table_name": "df"}
                            p = sample_params_for_template(
                                df,
                                variables,
                                rng_local,
                                allowed_batsmen=allowed_batsmen,
                                allowed_bowlers=allowed_bowlers,
                            ) if variables else {"table_name": "df"}
                            if p is None:
                                continue
                            params_raw.update(p)

                            init_params = {k: params_raw.get(k) for k in ["batsman", "bowler", "bowler1", "bowler2"] if k in params_raw}
                            init_id = hashlib.md5(json.dumps(init_params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:8]
                            params_raw_local = dict(params_raw)

                            if "temporal_predicate" in variables:
                                if o_min is None or o_max is None or o_min == o_max:
                                    params_raw_local["temporal_predicate"] = "(1=1)"
                                    params_raw_local["temporal_phrase"] = "the entire match"
                                    params_raw_local["temporal_relation"] = None
                                else:
                                    pred, phrase, rel_used = build_temporal_with_phrase(rel, o_min, o_max, field="overs", rng=rng_local)
                                    params_raw_local["temporal_predicate"] = pred
                                    params_raw_local["temporal_phrase"] = phrase
                                    params_raw_local["temporal_relation"] = rel_used

                            params_sql = build_params_sql(sql_template, params_raw_local)
                            try:
                                sql_text = safe_format(sql_template, params_sql)
                                normalized_sql_text = normalize_query_sql_for_duckdb(sql_text)
                                sql_difficulty = analyze_sql_difficulty(normalized_sql_text)
                                sql_projection_stats = analyze_sql_projection_stats(
                                    normalized_sql_text,
                                    base_columns=[str(c) for c in df.columns.tolist()],
                                )
                                ans_df = execute_sql_on_df(df, normalized_sql_text, table_name=params_raw_local.get("table_name", "df"))

                                z = is_zeroish_result(ans_df)
                                if cfg.drop_zeroish and z:
                                    zeroish_retry_reason = "drop_zeroish"
                                    continue
                                if not zeroish_ok(z):
                                    zeroish_retry_reason = f"zeroish_cap_exceeded:{cfg.max_zeroish_frac}"
                                    continue

                                row_info = extract_row_indices_from_query(normalized_sql_text, df, ans_df, table_name=params_raw_local.get("table_name", "df"))
                                contrib = row_info.get("row_indices_contributing") or []
                                ctx = build_context_from_df_rows(df, contrib, include_overs=False, max_chars=cfg.context_max_chars)
                                ctx_ov = build_context_from_df_rows(df, contrib, include_overs=True, max_chars=cfg.context_max_chars)

                                q_base = (t.get("question") or "").strip()
                                q_paras = t.get("paraphrases") or []
                                if not isinstance(q_paras, list):
                                    q_paras = []
                                q_choices = [q_base] if q_base else []
                                q_choices += [str(x).strip() for x in q_paras if str(x).strip()]

                                if cfg.split_use_base_question_only and q_base:
                                    q_tmpl = q_base
                                elif q_choices:
                                    q_tmpl = rng_local.choice(q_choices)
                                else:
                                    q_tmpl = ""

                                q_params: Dict[str, Any] = dict(params_raw_local)
                                q_params.setdefault("temporal_phrase", "")
                                q_params.setdefault("temporal_relation", params_raw_local.get("temporal_relation"))

                                try:
                                    question_text = safe_format(str(q_tmpl), q_params) if q_tmpl else ""
                                except Exception:
                                    question_text = str(q_tmpl) if q_tmpl else ""

                                rec = {
                                    "match_idx": match_i,
                                    "match_path": match_path,
                                    "template_index": t["template_index"],
                                    "template_id": t.get("template_id"),
                                    "idx": t.get("idx"),
                                    "item_id": t.get("item_id"),
                                    "primary_key": t.get("primary_key"),
                                    "variables": variables,
                                    "question": question_text,
                                    "sql": normalized_sql_text,
                                    "sql_difficulty": sql_difficulty,
                                    "sql_projection_stats": sql_projection_stats,
                                    "params_raw": params_raw_local,
                                    "params_sql": params_sql,
                                    "answer": df_to_answer_json(ans_df, max_rows=cfg.answer_max_rows),
                                    "answer_rows": int(ans_df.shape[0]),
                                    "answer_cols": int(ans_df.shape[1]),
                                    "is_zeroish": bool(z),
                                    "num_rows_scanned": int(row_info.get("row_indices_scanned_count") or len(row_info.get("row_indices_scanned") or [])),
                                    "num_rows_contributing": int(row_info.get("row_indices_contributing_count") or len(contrib)),
                                    "step_row_progression": row_info.get("step_row_progression") or [],
                                    "provenance_supported": bool(row_info.get("provenance_supported")),
                                    "provenance_error": row_info.get("provenance_error"),
                                    "temporal_relation": params_raw_local.get("temporal_relation"),
                                    "temporal_phrase": params_raw_local.get("temporal_phrase"),
                                    "temporal_predicate": params_raw_local.get("temporal_predicate"),
                                    "is_temporal": bool(_has_temporality({
                                        "temporal_predicate": params_raw_local.get("temporal_predicate"),
                                        "temporal_relation": params_raw_local.get("temporal_relation"),
                                    })),
                                    "span_init_mode": mode,
                                    "span_bucket": (span_bucket_name if span_bucket_name else None),
                                    "init_params": init_params,
                                    "init_id": init_id,
                                    "context": ctx,
                                    "context_with_overs": ctx_ov,
                                    "context_full": full_context_no_overs,
                                    "context_full_with_overs": full_context_with_overs,
                                }

                                init_grp = _init_group_from_variables(rec.get("variables"))
                                has_tmp = _has_temporality(rec)
                                if init_grp == "none" and not has_tmp:
                                    splits: List[str] = []
                                else:
                                    tmp = "temporal" if has_tmp else "non_temporal"
                                    splits = [tmp]
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
                                    splits = sorted(set(splits))
                                rec["splits"] = splits
                                rec["is_temporal"] = bool(_has_temporality(rec))

                                k = record_key(match_path, t["template_index"], init_id, rec.get("temporal_relation"), rec.get("span_bucket"))
                                if k in exclude_keys:
                                    continue

                                if not rec["provenance_supported"]:
                                    errors.append({
                                        "match_path": match_path,
                                        "template_index": t.get("template_index"),
                                        "template_id": t.get("template_id"),
                                        "item_id": t.get("item_id"),
                                        "error": f"skipped_unsupported_provenance: {rec.get('provenance_error')}",
                                    })
                                    continue

                                out_rows.append(rec)
                                kept += 1
                                if z:
                                    kept_zeroish += 1
                                made_record = True
                                break

                            except Exception as e:
                                errors.append({
                                    "match_path": match_path,
                                    "template_index": t.get("template_index"),
                                    "error": str(e),
                                    "sql_template_preview": (sql_template[:250] if isinstance(sql_template, str) else None),
                                })
                                continue

                        if not made_record and zeroish_retry_reason is not None:
                            errors.append({
                                "match_path": match_path,
                                "template_index": t.get("template_index"),
                                "template_id": t.get("template_id"),
                                "item_id": t.get("item_id"),
                                "error": f"skipped_after_zeroish_retries: {zeroish_retry_reason}",
                            })

    for sample_idx, row in enumerate(out_rows):
        row["sample_idx"] = sample_idx

    out_path = os.path.join(cfg.output_dir, "dataset.split_analysis.json")
    write_json(out_path, {"metadata": cfg.__dict__, "records": out_rows})

    # -----------------------------
    # Summary / diagnostics
    # -----------------------------
    summary_path = os.path.join(cfg.output_dir, "dataset.split_summary.json")
    pairs_path = os.path.join(cfg.output_dir, "dataset.match_template_pairs.csv")

    try:
        rec_df = pd.DataFrame(out_rows)

        # Basic match inventory
        matches_used = sorted(rec_df["match_path"].dropna().astype(str).unique().tolist()) if "match_path" in rec_df.columns else []

        # Template inventories
        template_id_counts = rec_df["template_id"].fillna("").astype(str).value_counts().to_dict() if "template_id" in rec_df.columns else {}
        item_id_counts = rec_df["item_id"].fillna("").astype(str).value_counts().to_dict() if "item_id" in rec_df.columns else {}
        template_index_counts = rec_df["template_index"].value_counts().to_dict() if "template_index" in rec_df.columns else {}

        # Span distribution overall and per template
        span_counts_overall = rec_df["span_bucket"].fillna("none").astype(str).value_counts().to_dict() if "span_bucket" in rec_df.columns else {}

        span_by_template: Dict[str, Any] = {}
        if "template_id" in rec_df.columns and "span_bucket" in rec_df.columns:
            g = rec_df.copy()
            g["template_id"] = g["template_id"].fillna("").astype(str)
            g["span_bucket"] = g["span_bucket"].fillna("none").astype(str)
            for tid, sub in g.groupby("template_id"):
                span_by_template[tid] = sub["span_bucket"].value_counts().to_dict()

        # Temporal counts overall and per template
        temporal_counts_overall = rec_df["is_temporal"].value_counts().to_dict() if "is_temporal" in rec_df.columns else {}
        provenance_supported_counts = rec_df["provenance_supported"].value_counts().to_dict() if "provenance_supported" in rec_df.columns else {}
        provenance_error_counts = rec_df["provenance_error"].fillna("").astype(str).value_counts().to_dict() if "provenance_error" in rec_df.columns else {}

        temporal_by_template: Dict[str, Any] = {}
        if "template_id" in rec_df.columns and "is_temporal" in rec_df.columns:
            g2 = rec_df.copy()
            g2["template_id"] = g2["template_id"].fillna("").astype(str)
            for tid, sub in g2.groupby("template_id"):
                temporal_by_template[tid] = sub["is_temporal"].value_counts().to_dict()

        # How many have a non-trivial temporal predicate string (not None and not (1=1))
        nontrivial_temporal_predicate_counts = {}
        if "temporal_predicate" in rec_df.columns:
            tp = rec_df["temporal_predicate"].fillna("").astype(str)
            nontriv = tp.str.replace(" ", "", regex=False).ne("(1=1)") & tp.ne("")
            nontrivial_temporal_predicate_counts = nontriv.value_counts().to_dict()

        # Matches x templates pairs (counts)
        pair_counts: List[Dict[str, Any]] = []
        if "match_path" in rec_df.columns and "template_id" in rec_df.columns:
            p = rec_df.copy()
            p["match_path"] = p["match_path"].fillna("").astype(str)
            p["template_id"] = p["template_id"].fillna("").astype(str)
            if "item_id" in p.columns:
                p["item_id"] = p["item_id"].fillna("").astype(str)
            grp_cols = ["match_path", "template_id"] + (["item_id"] if "item_id" in p.columns else [])
            pc = p.groupby(grp_cols).size().reset_index(name="count").sort_values(["count"], ascending=False)
            pair_counts = pc.to_dict(orient="records")
            # Also write a CSV for easy inspection
            pc.to_csv(pairs_path, index=False)

        # Also provide match-level summary: how many records per match, and span distribution per match
        per_match: Dict[str, Any] = {}
        if "match_path" in rec_df.columns:
            mm = rec_df.copy()
            mm["match_path"] = mm["match_path"].fillna("").astype(str)
            if "span_bucket" in mm.columns:
                mm["span_bucket"] = mm["span_bucket"].fillna("none").astype(str)
            for m, sub in mm.groupby("match_path"):
                d: Dict[str, Any] = {"count": int(len(sub))}
                if "span_bucket" in sub.columns:
                    d["span_bucket_counts"] = sub["span_bucket"].value_counts().to_dict()
                if "template_id" in sub.columns:
                    d["template_id_counts"] = sub["template_id"].fillna("").astype(str).value_counts().to_dict()
                per_match[m] = d

        summary_obj: Dict[str, Any] = {
            "num_records": int(len(out_rows)),
            "num_matches": int(len(matches_used)),
            "matches_used": matches_used,
            "min_match_rows": int(cfg.min_match_rows),
            "max_zeroish_frac": float(cfg.max_zeroish_frac),
            "max_init_attempts": int(cfg.max_init_attempts),
            "drop_zeroish": bool(cfg.drop_zeroish),
            "template_id_counts": template_id_counts,
            "item_id_counts": item_id_counts,
            "template_index_counts": template_index_counts,
            "span_bucket_counts_overall": span_counts_overall,
            "span_bucket_counts_by_template_id": span_by_template,
            "temporal_counts_overall": temporal_counts_overall,
            "temporal_counts_by_template_id": temporal_by_template,
            "provenance_supported_counts": provenance_supported_counts,
            "provenance_error_counts": provenance_error_counts,
            "nontrivial_temporal_predicate_counts": nontrivial_temporal_predicate_counts,
            "match_template_pair_counts": pair_counts,
            "per_match_summary": per_match,
            "cover_all_templates_once": bool(cfg.cover_all_templates_once),
            "cover_all_templates_pool": pool_mode,
            "num_templates_in_pool": int(len(templates_pool)),
            "outputs": {
                "dataset": out_path,
                "summary": summary_path,
                "pairs_csv": pairs_path if os.path.exists(pairs_path) else None,
            },
        }
        write_json(summary_path, summary_obj)
    except Exception as e:
        # Don't fail dataset generation due to summary issues
        errors.append({"match_path": None, "error": f"summary failed: {e}"})

    if errors:
        write_json(os.path.join(cfg.output_dir, "errors.split_analysis.json"), errors)

    return {
        "dataset_path": out_path,
        "summary_path": summary_path,
        "pairs_csv_path": pairs_path if os.path.exists(pairs_path) else None,
        "num_records": len(out_rows),
        "num_errors": len(errors),
    }


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates", nargs="+", default=["output/converted_params/test_generated_sql_nl_progress_5k_4_removed_fixed.json"])
    ap.add_argument("--matches_glob", default="Cricket_tables/*.csv")
    ap.add_argument("--out_dir", default="output_dataset_split")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--context_max_chars", type=int, default=0)
    ap.add_argument("--answer_max_rows", type=int, default=0)
    ap.add_argument("--drop_zeroish", action="store_true")
    ap.add_argument("--max_zeroish_frac", type=float, default=0.02)
    ap.add_argument("--max_init_attempts", type=int, default=20,
                    help="Retries per match/template/init/span/temporal combination when sampling non-zeroish results.")

    ap.add_argument("--split_num_matches", type=int, default=5)
    ap.add_argument("--min_match_rows", type=int, default=201,
                    help="Only sample match CSVs with more than this many rows.")
    ap.add_argument("--split_templates_per_match", type=int, default=5)
    ap.add_argument("--split_inits_per_template_per_match", type=int, default=3)
    ap.add_argument("--temporal_all_phrases", action="store_true", default=True, help="Generate all temporal relation variants when template includes temporal_predicate (default: enabled).")
    ap.add_argument("--split_use_base_question_only", action="store_true")
    ap.add_argument("--cover_all_templates_once", action="store_true", help="Ensure every template in the selected pool is used at least once across the sampled matches. Templates are distributed across matches; not every template is paired with every match.")
    ap.add_argument("--cover_all_templates_pool", type=str, default="all", help="Template pool for coverage: all | init_relevant")
    ap.add_argument("--exclude_keys_json", type=str, default="")

    ap.add_argument("--span_init_mode", type=str, default="none",
                    help="Span-conditioned init for entities based on their min/max over presence. Options: none|batsman|bowler|both")
    ap.add_argument("--span_bucket", type=str, default="",
                    help="Single span bucket to condition on: first_half|second_half|middle|almost_entire|entire")
    ap.add_argument("--span_buckets", type=str, default="",
                    help="Comma-separated span buckets to generate in one run. Example: first_half,second_half,entire . Special: all -> first_half,second_half,entire")
    ap.add_argument("--span_min_rows", type=int, default=1,
                    help="Minimum number of rows/appearances for an entity to be eligible")
    ap.add_argument("--span_coverage_threshold", type=float, default=0.8,
                    help="Coverage threshold for almost_entire span bucket")

    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    cfg = SplitConfig(
        templates_paths=args.templates,
        matches_glob=args.matches_glob,
        output_dir=args.out_dir,
        seed=args.seed,
        context_max_chars=args.context_max_chars,
        answer_max_rows=args.answer_max_rows,
        drop_zeroish=args.drop_zeroish,
        max_zeroish_frac=args.max_zeroish_frac,
        max_init_attempts=args.max_init_attempts,
        split_num_matches=args.split_num_matches,
        min_match_rows=args.min_match_rows,
        split_templates_per_match=args.split_templates_per_match,
        split_inits_per_template_per_match=args.split_inits_per_template_per_match,
        temporal_all_phrases=args.temporal_all_phrases,
        split_use_base_question_only=args.split_use_base_question_only,
        cover_all_templates_once=args.cover_all_templates_once,
        cover_all_templates_pool=args.cover_all_templates_pool,
        exclude_keys_json=args.exclude_keys_json,
        span_init_mode=args.span_init_mode,
        span_bucket=args.span_bucket,
        span_buckets=args.span_buckets,
        span_min_rows=args.span_min_rows,
        span_coverage_threshold=args.span_coverage_threshold,
    )
    generate_split_dataset(cfg)


# python src/core/generate_questions_split.py \
#   --templates data/data_final/test_generated_sql_nl.json data/data_manual_template/template_q_param_cricket_pk.py \
#   --matches_glob "data/Cricket_tables/*.csv" \
#   --out_dir data/output_dataset_split \
#   --seed 42 \
#   --context_max_chars 0 \
#   --answer_max_rows 0 \
#   --span_init_mode both \
#   --span_buckets all \
#   --temporal_all_phrases \
#   --cover_all_templates_pool init_relevant \
#   --cover_all_templates_once \
#   --min_match_rows 200

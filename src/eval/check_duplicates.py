#!/usr/bin/env python3
"""
run_extracted_queries.py

Usage examples:
  python run_extracted_queries.py --csv "Cricket_tables/Ball by Ball Commentary & Live Score - AFG vs AUS, 10th Match, Group B.csv" --json /path/to/file_with_final.json
  python run_extracted_queries.py --csv match.csv --sql-file extracted_queries.sql

Requirements:
  pip install pandas pandasql
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import pandasql as ps
import hashlib
import csv
import os
import textwrap

# ---------- Helpers ----------
def compute_hash_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def normalize_sql_text(sql: str) -> str:
    if sql is None:
        return ""
    s = sql.strip().replace("\r\n", "\n").replace("\r", "\n")
    # collapse >2 blank lines
    lines = []
    blank = 0
    for L in s.split("\n"):
        if L.strip() == "":
            blank += 1
        else:
            blank = 0
        if blank <= 2:
            lines.append(L.rstrip())
    return "\n".join(lines).strip()

def _normalize_df_for_compare(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize values for hashing while ignoring column names.

    Fast path:
      - reset index
      - round float columns
      - normalize NaN -> None

    NOTE: We intentionally do NOT sort rows here. Order-independence is achieved
    in df_signature() by sorting the per-row hashes.
    """
    if df is None:
        return pd.DataFrame()

    d = df.copy().reset_index(drop=True)

    # Round floats to reduce tiny numeric noise
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].round(12)

    # Normalize missing values
    d = d.where(pd.notnull(d), None)
    return d

def df_signature(df: pd.DataFrame) -> str:
    """Content-only signature (ignores column names) using fast row hashing.

    Duplicate criteria:
      1) same number of rows
      2) same number of columns
      3) same content ignoring column names (multiset of row values)

    Implementation:
      - normalize values (round floats, normalize NaNs)
      - build a temporary DataFrame from only the raw values (columns become 0..n-1)
      - compute a vectorized per-row hash via pd.util.hash_pandas_object
      - sort those row hashes to make row order irrelevant
      - hash (nrows, ncols, row_hashes) to produce the final signature
    """
    dnorm = _normalize_df_for_compare(df)
    nrows, ncols = dnorm.shape

    if nrows == 0 or ncols == 0:
        payload = {"nrows": nrows, "ncols": ncols, "row_hashes": []}
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    # Ignore original column names by hashing only the values matrix
    values_df = pd.DataFrame(dnorm.to_numpy(copy=False))

    # Vectorized per-row hashing (returns uint64)
    row_hashes_u64 = pd.util.hash_pandas_object(values_df, index=False).to_numpy()

    # Sort to make comparison order-independent
    row_hashes_u64.sort()

    payload = {
        "nrows": nrows,
        "ncols": ncols,
        "row_hashes": row_hashes_u64.tolist(),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def all_zero_or_nan_columns(df: pd.DataFrame) -> List[str]:
    """Return list of column names where every value is either 0 or NaN.

    Rules:
      - For numeric columns: flag if all values are NaN OR all values are (0 or NaN).
      - For non-numeric columns: try coercing to numeric; if coercion yields at least one non-NaN,
        apply the same rule on the coerced numeric values. Otherwise, only flag if the original column is all NaN.

    This matches: "any column yielded all 0s or nans".
    """
    if df is None or df.shape[1] == 0:
        return []

    bad_cols: List[str] = []
    for col in df.columns:
        s = df[col]

        # If already numeric, use directly
        if pd.api.types.is_numeric_dtype(s):
            mask = s.isna() | (s == 0)
            if mask.all():
                bad_cols.append(str(col))
            continue

        # Try to coerce to numeric for strings/objects
        s_num = pd.to_numeric(s, errors="coerce")
        if s_num.notna().any():
            mask = s_num.isna() | (s_num == 0)
            if mask.all():
                bad_cols.append(str(col))
        else:
            # Non-numeric column: only flag if it's entirely missing
            if s.isna().all():
                bad_cols.append(str(col))

    return bad_cols

# ---------- Extraction logic ----------
def find_final_nodes(obj: Any, path: str = "") -> List[Tuple[str, Any]]:
    results: List[Tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            if k == "final":
                results.append((new_path, v))
            results.extend(find_final_nodes(v, new_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{path}[{i}]"
            results.extend(find_final_nodes(item, new_path))
    return results

def extract_sqls_from_json(json_path: Path) -> List[Dict[str, Any]]:
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    finals = find_final_nodes(data, path="")
    extracted: List[Dict[str, Any]] = []
    for final_path, final_value in finals:
        if not isinstance(final_value, list):
            continue
        for idx, item in enumerate(final_value):
            if not isinstance(item, dict):
                continue
            sql_raw = item.get("sql")
            if not isinstance(sql_raw, str):
                continue
            sql = normalize_sql_text(sql_raw)
            extracted.append({
                "final_path": final_path,
                "index_in_final": idx,
                "item_id": item.get("item_id"),
                "template_id": item.get("template_id"),
                "round_idx": item.get("round_idx"),
                "intent": item.get("intent"),
                "question": item.get("question"),
                "sql": sql,
                "sql_hash": compute_hash_string(sql),
            })
    return extracted

def extract_sqls_from_sql_file(sql_file: Path) -> List[Dict[str, Any]]:
    # Simple splitter: separate queries by a blank line that starts with "-- Query" or by lines with only ';' separated queries
    content = sql_file.read_text(encoding="utf-8")
    # split by delimiter '-- Query' blocks if present, else split by two newlines
    parts = []
    if "-- Query" in content:
        blocks = content.split("-- Query")
        for b in blocks:
            s = b.strip()
            if not s:
                continue
            # remove any leading comment number
            lines = [l for l in s.splitlines() if not l.strip().startswith("--")]
            block_sql = "\n".join(lines).strip()
            if block_sql:
                parts.append(block_sql)
    else:
        # naive split by two blank lines
        for blk in content.split("\n\n"):
            s = blk.strip()
            if s:
                parts.append(s)
    out = []
    for i, p in enumerate(parts):
        sql = normalize_sql_text(p)
        out.append({
            "final_path": f"sql_file[{sql_file.name}]",
            "index_in_final": i,
            "item_id": None,
            "template_id": None,
            "round_idx": None,
            "intent": None,
            "question": None,
            "sql": sql,
            "sql_hash": compute_hash_string(sql),
        })
    return out

# ---------- Execute + compare ----------
def run_queries_on_df(df: pd.DataFrame, queries: List[Dict[str, Any]], out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    zero_or_nan_findings: List[Dict[str, Any]] = []
    results_meta: List[Dict[str, Any]] = []
    sig_map: Dict[str, List[int]] = {}  # signature -> list of result indices
    results_cache: List[pd.DataFrame] = []

    for i, q in enumerate(queries):
        sql = q["sql"]
        meta = q.copy()
        meta["index"] = i
        try:
            # Run using pandasql; df is available as 'df'
            res = ps.sqldf(sql, {"df": df})
            # Save result CSV for inspection
            safe_name = meta.get("item_id") or f"q_{i}"
            out_csv = out_dir / f"{safe_name}_result_{i}.csv"
            res.to_csv(out_csv, index=False)
            meta["result_rows"] = len(res)
            meta["result_cols"] = res.shape[1]
            meta["result_path"] = str(out_csv)
            # compute canonical signature for duplicates detection
            sig = df_signature(res)
            meta["result_signature"] = sig
            # Track columns that are entirely 0 or NaN for manual inspection
            bad_cols = all_zero_or_nan_columns(res)
            meta["all_zero_or_nan_columns"] = bad_cols
            if bad_cols:
                zero_or_nan_findings.append({
                    "query_index": i,
                    "item_id": meta.get("item_id"),
                    "final_path": meta.get("final_path"),
                    "index_in_final": meta.get("index_in_final"),
                    "template_id": meta.get("template_id"),
                    "round_idx": meta.get("round_idx"),
                    "intent": meta.get("intent"),
                    "question": meta.get("question"),
                    "sql": meta.get("sql"),
                    "result_path": meta.get("result_path"),
                    "result_rows": meta.get("result_rows"),
                    "result_cols": meta.get("result_cols"),
                    "columns_all_zero_or_nan": bad_cols,
                })
            results_cache.append(res)
            sig_map.setdefault(sig, []).append(i)
            results_meta.append(meta)
        except Exception as e:
            meta["error"] = repr(e)
            meta["result_rows"] = None
            meta["result_cols"] = None
            meta["result_path"] = None
            meta["result_signature"] = None
            meta["all_zero_or_nan_columns"] = []
            results_cache.append(pd.DataFrame())
            results_meta.append(meta)

    # Build duplicate groups (exact matches)
    duplicate_groups = [inds for inds in sig_map.values() if len(inds) > 1]

    # Find near-matches: same shape & same column names but different content
    # Near-matches can be very expensive (O(n^2)). Disable by default for speed.
    near_matches: List[Tuple[int, int]] = []

    report = {
        "total_queries": len(queries),
        "results_meta": results_meta,
        "duplicate_groups": duplicate_groups,
        "near_matches": near_matches
    }

    # Save summary json
    summary = {
        "total_queries": report["total_queries"],
        "num_duplicates_groups": len(report["duplicate_groups"]),
        "duplicate_groups": report["duplicate_groups"],
        "num_near_matches": len(report["near_matches"]) 
    }
    (out_dir / "report_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Build detailed duplicates info (expand each group with metadata for manual review)
    duplicates_info: List[Dict[str, Any]] = []
    for gid, group in enumerate(duplicate_groups, start=1):
        members = []
        for idx in group:
            meta = results_meta[idx]
            # Include entire template + execution metadata for manual inspection
            full_entry = meta.copy()
            full_entry["query_index"] = idx
            members.append(full_entry)
        duplicates_info.append({
            "duplicate_group_id": gid,
            "signature": results_meta[group[0]].get("result_signature"),
            "members": members
        })

    # Write duplicates JSON for easy inspection
    (out_dir / "duplicates.json").write_text(json.dumps(duplicates_info, indent=2), encoding="utf-8")

    # Also write a CSV with one row per duplicated query (handy to open in Excel)
    csv_path = out_dir / "duplicates_details.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as cf:
        fieldnames = [
            "duplicate_group_id", "signature", "query_index", "item_id",
            "final_path", "index_in_final", "sql_hash", "sql", "result_path",
            "result_rows", "result_cols"
        ]
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for group in duplicates_info:
            gid = group["duplicate_group_id"]
            sig = group.get("signature")
            for m in group["members"]:
                writer.writerow({
                    "duplicate_group_id": gid,
                    "signature": sig,
                    "query_index": m.get("query_index"),
                    "item_id": m.get("item_id"),
                    "final_path": m.get("final_path"),
                    "index_in_final": m.get("index_in_final"),
                    "sql_hash": m.get("sql_hash"),
                    "sql": (m.get("sql") or "")[:10000],
                    "result_path": m.get("result_path"),
                    "result_rows": m.get("result_rows"),
                    "result_cols": m.get("result_cols"),
                })

    # Write columns-all-zero-or-NaN findings for manual inspection
    zero_nan_json = out_dir / "all_zero_or_nan_columns.json"
    zero_nan_csv = out_dir / "all_zero_or_nan_columns.csv"

    (out_dir / "all_zero_or_nan_columns.json").write_text(
        json.dumps(zero_or_nan_findings, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    with zero_nan_csv.open("w", newline="", encoding="utf-8") as cf:
        fieldnames = [
            "query_index", "item_id", "final_path", "index_in_final", "template_id", "round_idx",
            "columns_all_zero_or_nan", "result_rows", "result_cols", "result_path", "intent", "question", "sql"
        ]
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for row in zero_or_nan_findings:
            writer.writerow({
                "query_index": row.get("query_index"),
                "item_id": row.get("item_id"),
                "final_path": row.get("final_path"),
                "index_in_final": row.get("index_in_final"),
                "template_id": row.get("template_id"),
                "round_idx": row.get("round_idx"),
                "columns_all_zero_or_nan": ",".join(row.get("columns_all_zero_or_nan", [])),
                "result_rows": row.get("result_rows"),
                "result_cols": row.get("result_cols"),
                "result_path": row.get("result_path"),
                "intent": row.get("intent"),
                "question": (row.get("question") or "").replace("\n", " "),
                "sql": (row.get("sql") or "")[:10000],
            })

    print(f"Wrote duplicates JSON: {(out_dir / 'duplicates.json')}")
    print(f"Wrote duplicates CSV : {csv_path}")
    print(f"Wrote all-zero/NaN column report JSON: {zero_nan_json}")
    print(f"Wrote all-zero/NaN column report CSV : {zero_nan_csv}")

    return report

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Run extracted SQL queries against a match CSV (df) and detect duplicate result sets.")
    parser.add_argument("--csv", required=True, help="Path to match CSV file to load into 'df'.")
    parser.add_argument("--json", type=str, help="Path to JSON file that contains 'final' arrays with 'sql' keys.")
    parser.add_argument("--sql-file", type=str, help="Path to a .sql file (alternative to --json).")
    parser.add_argument("--out-dir", type=str, default="output/results", help="Directory to write results.")
    parser.add_argument("--no-dedupe", action="store_true", help="(No effect here) keep for parity.")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print("CSV not found:", csv_path)
        return

    # load CSV
    print("Loading CSV into pandas DataFrame:", csv_path)
    # Try to read with default encoding; if fails try latin-1
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        df = pd.read_csv(csv_path, encoding="latin-1")
    print("Loaded df shape:", df.shape)

    queries: List[Dict[str, Any]] = []
    if args.json:
        json_path = Path(args.json)
        if not json_path.exists():
            print("JSON not found:", json_path)
            return
        print("Extracting SQLs from JSON:", json_path)
        queries = extract_sqls_from_json(json_path)
        print("Extracted", len(queries), "queries from JSON.")
    elif args.sql_file:
        sql_file = Path(args.sql_file)
        if not sql_file.exists():
            print("SQL file not found:", sql_file)
            return
        queries = extract_sqls_from_sql_file(sql_file)
        print("Loaded", len(queries), "queries from SQL file.")
    else:
        print("No JSON or SQL file provided. Nothing to run.")
        return

    if not queries:
        print("No queries extracted. Exiting.")
        return

    out_dir = Path(args.out_dir)
    print("Running queries and saving results into:", out_dir)
    report = run_queries_on_df(df, queries, out_dir)

    print("Finished. Summary:")
    print("  total queries:", report["total_queries"])
    print("  duplicate groups (exact matches):", len(report["duplicate_groups"]))
    print("  near matches (same shape/cols but different content):", len(report["near_matches"]))
    print("See output folder for per-query CSVs and output/report_summary.json")

if __name__ == "__main__":
    main()
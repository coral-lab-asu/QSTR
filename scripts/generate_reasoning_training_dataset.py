#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required to run this script.") from exc

try:
    from src.core.generate_questions_split import (
        execute_sql_on_df,
        extract_row_indices_from_query,
        normalize_query_sql_for_duckdb,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Failed to import the SQL provenance helpers from src/core/generate_questions_split.py. "
        f"Original import error: {exc!r}. "
        "Run this script from the repo root with the environment that has duckdb and sqlglot."
    ) from exc


CANONICAL_NUMERIC_COLUMNS = [
    "batsman_runs",
    "batsman_fours",
    "batsman_sixes",
    "batsman_bowls_faced",
    "bowler_bowls_done",
    "bowler_runs_given",
    "bowler_wickets",
    "team_runs",
    "runs",
]

CANONICAL_TEXT_COLUMNS = [
    "bowler",
    "batsman",
    "dismissal",
]

SQL_SIGNAL_TO_COLUMNS = {
    "batsman_runs": {"batsman_runs"},
    "bowler_wickets": {"bowler_wickets", "dismissal"},
    "dismissal": {"dismissal", "bowler_wickets"},
    "batsman_fours": {"batsman_fours"},
    "batsman_sixes": {"batsman_sixes"},
    "batsman_bowls_faced": {"batsman_bowls_faced"},
    "bowler_bowls_done": {"bowler_bowls_done"},
    "bowler_runs_given": {"bowler_runs_given"},
    "runs_given_bool": {"bowler_runs_given"},
    "team_runs": {"team_runs"},
    "runs": {"runs"},
    "overs": {"overs"},
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Generate a symbolic reasoning-training dataset from cricket-overall.json "
            "using gold SQL provenance and the underlying ball-by-ball CSV tables."
        )
    )
    p.add_argument(
        "--dataset",
        default="dataset-cricket/cricket-overall.json",
        help="Path to the input dataset JSON.",
    )
    p.add_argument(
        "--match-dir",
        default="data-old-run/Cricket_tables",
        help="Directory containing the source match CSV files.",
    )
    p.add_argument(
        "--output",
        default="dataset-cricket/reasoning-training-symbolic.jsonl",
        help="Output JSONL path for symbolic training records.",
    )
    p.add_argument(
        "--errors-output",
        default="dataset-cricket/reasoning-training-symbolic.errors.json",
        help="Path to write records that could not be processed.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of records to process.",
    )
    p.add_argument(
        "--group-keys-preview",
        type=int,
        default=8,
        help="Maximum number of group key examples to keep per group-by step.",
    )
    p.add_argument(
        "--include-context",
        action="store_true",
        help="Include context_full_with_overs in each output record.",
    )
    return p.parse_args()


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict) or "records" not in obj or not isinstance(obj["records"], list):
        raise ValueError(f"Unsupported dataset format: {path}")
    return obj["records"]


def _resolve_match_csv(match_path: str, match_dir: Path) -> Path:
    name = Path(match_path).name
    candidates = [
        match_dir / name,
        Path("data/Cricket_tables") / name,
        Path(match_path),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not resolve match CSV for {match_path}")


def _normalize_primary_key(primary_key: Any) -> List[str]:
    if primary_key is None:
        return []
    if isinstance(primary_key, str):
        return [primary_key]
    if isinstance(primary_key, (list, tuple)):
        return [str(x) for x in primary_key]
    return [str(primary_key)]


def _safe_int(v: Any) -> Optional[int]:
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return int(v)
    except Exception:
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None


def _normalize_cell(v: Any) -> Any:
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return float(v)
    return v


def _row_key_from_answer_row(columns: Sequence[str], row: Sequence[Any], primary_key: Sequence[str]) -> Dict[str, Any]:
    col_to_val = {str(c): _normalize_cell(v) for c, v in zip(columns, row)}
    return {k: col_to_val.get(k) for k in primary_key}


def _serialize_evidence_row(row: pd.Series) -> str:
    parts: List[str] = []
    over = row.get("overs")
    over_txt = str(over) if over is not None else "?"
    parts.append(over_txt)

    entity_bits: List[str] = []
    bowler = row.get("bowler")
    batsman = row.get("batsman")
    if isinstance(bowler, str) and bowler.strip():
        entity_bits.append(f"bowler={bowler}")
    if isinstance(batsman, str) and batsman.strip():
        entity_bits.append(f"batsman={batsman}")
    if entity_bits:
        parts.append(" | ".join(entity_bits))

    attr_bits: List[str] = []
    for col in [
        "batsman_runs",
        "bowler_wickets",
        "dismissal",
        "batsman_fours",
        "batsman_sixes",
        "bowler_bowls_done",
        "batsman_bowls_faced",
        "bowler_runs_given",
    ]:
        val = row.get(col)
        if val is None:
            continue
        try:
            if pd.isna(val):
                continue
        except Exception:
            pass
        norm = _normalize_cell(val)
        if col == "dismissal" and (norm is None or str(norm).strip() == ""):
            continue
        attr_bits.append(f"{col}={norm}")
    if attr_bits:
        parts.append(" | ".join(attr_bits))

    return " | ".join(parts)


def _compute_canonical_stats(df: pd.DataFrame) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "num_events": int(len(df)),
        "first_over": None,
        "last_over": None,
        "unique_bowlers": [],
        "unique_batsmen": [],
        "dot_ball_count": 0,
        "dismissal_count": 0,
        "boundary_event_count": 0,
    }
    if df.empty:
        return stats

    overs_num = pd.to_numeric(df.get("overs"), errors="coerce")
    if not overs_num.empty:
        min_over = overs_num.min()
        max_over = overs_num.max()
        if pd.notna(min_over):
            stats["first_over"] = float(min_over)
        if pd.notna(max_over):
            stats["last_over"] = float(max_over)

    for col in CANONICAL_NUMERIC_COLUMNS:
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        stats[f"sum_{col}"] = float(vals.fillna(0).sum())

    if "bowler" in df.columns:
        stats["unique_bowlers"] = sorted({str(x) for x in df["bowler"].dropna().tolist() if str(x).strip()})
    if "batsman" in df.columns:
        stats["unique_batsmen"] = sorted({str(x) for x in df["batsman"].dropna().tolist() if str(x).strip()})

    if "batsman_runs" in df.columns:
        batsman_runs = pd.to_numeric(df["batsman_runs"], errors="coerce").fillna(0)
        stats["dot_ball_count"] = int((batsman_runs == 0).sum())

    if "dismissal" in df.columns:
        dismissals = df["dismissal"].fillna("").astype(str).str.strip()
        stats["dismissal_count"] = int(dismissals.ne("").sum())

    if "batsman_fours" in df.columns and "batsman_sixes" in df.columns:
        fours = pd.to_numeric(df["batsman_fours"], errors="coerce").fillna(0)
        sixes = pd.to_numeric(df["batsman_sixes"], errors="coerce").fillna(0)
        stats["boundary_event_count"] = int(((fours > 0) | (sixes > 0)).sum())

    return stats


def _infer_relevant_columns(
    *,
    sql_text: str,
    question: str,
    primary_key: Sequence[str],
    answer_columns: Sequence[str],
) -> List[str]:
    signals = f"{sql_text}\n{question}\n{' '.join(primary_key)}\n{' '.join(answer_columns)}".lower()
    relevant = {"overs"}
    for col in primary_key:
        relevant.add(str(col))
    for col in answer_columns:
        col_str = str(col)
        if col_str in {"bowler", "batsman", "dismissal"}:
            relevant.add(col_str)
    for token, cols in SQL_SIGNAL_TO_COLUMNS.items():
        if token.lower() in signals:
            relevant.update(cols)
    if "dot" in signals:
        relevant.update({"batsman_runs"})
    if "boundary" in signals:
        relevant.update({"batsman_fours", "batsman_sixes"})
    if "wicket" in signals:
        relevant.update({"bowler_wickets", "dismissal"})
    if "ball" in signals:
        relevant.update({"bowler_bowls_done", "batsman_bowls_faced"})
    ordered = [
        "overs",
        "bowler",
        "batsman",
        "batsman_runs",
        "bowler_wickets",
        "dismissal",
        "batsman_fours",
        "batsman_sixes",
        "batsman_bowls_faced",
        "bowler_bowls_done",
        "bowler_runs_given",
        "team_runs",
        "runs",
    ]
    return [col for col in ordered if col in relevant]


def _serialize_minimal_event(row: pd.Series, relevant_columns: Sequence[str]) -> Dict[str, Any]:
    event: Dict[str, Any] = {"over_ball": str(row.get("overs")) if row.get("overs") is not None else "?"}
    for col in relevant_columns:
        if col == "overs":
            continue
        if col not in row.index:
            continue
        val = row.get(col)
        try:
            if pd.isna(val):
                continue
        except Exception:
            pass
        norm = _normalize_cell(val)
        if col == "dismissal" and (norm is None or str(norm).strip() == ""):
            continue
        event[col] = norm
    return event


def _compute_task_stats(
    df: pd.DataFrame,
    *,
    relevant_columns: Sequence[str],
    sql_text: str,
    question: str,
) -> Dict[str, Any]:
    signals = f"{sql_text}\n{question}".lower()
    stats: Dict[str, Any] = {"num_events": int(len(df))}
    if df.empty:
        return stats

    if "overs" in df.columns and any(x in signals for x in ["overs", "over", "powerplay", "death", "first 10", "first 6"]):
        overs_num = pd.to_numeric(df["overs"], errors="coerce")
        if not overs_num.empty:
            min_over = overs_num.min()
            max_over = overs_num.max()
            if pd.notna(min_over):
                stats["first_over"] = float(min_over)
            if pd.notna(max_over):
                stats["last_over"] = float(max_over)

    if "batsman_runs" in relevant_columns and "batsman_runs" in df.columns:
        vals = pd.to_numeric(df["batsman_runs"], errors="coerce").fillna(0)
        stats["sum_batsman_runs"] = float(vals.sum())
        if any(x in signals for x in ["dot", "no run", "dot ball"]):
            stats["dot_ball_count"] = int((vals == 0).sum())

    if "bowler_runs_given" in relevant_columns and "bowler_runs_given" in df.columns:
        vals = pd.to_numeric(df["bowler_runs_given"], errors="coerce").fillna(0)
        stats["sum_bowler_runs_given"] = float(vals.sum())

    if "bowler_wickets" in relevant_columns and "bowler_wickets" in df.columns:
        vals = pd.to_numeric(df["bowler_wickets"], errors="coerce").fillna(0)
        stats["sum_bowler_wickets"] = float(vals.sum())

    if "batsman_bowls_faced" in relevant_columns and "batsman_bowls_faced" in df.columns:
        vals = pd.to_numeric(df["batsman_bowls_faced"], errors="coerce").fillna(0)
        stats["sum_batsman_bowls_faced"] = float(vals.sum())

    if "bowler_bowls_done" in relevant_columns and "bowler_bowls_done" in df.columns:
        vals = pd.to_numeric(df["bowler_bowls_done"], errors="coerce").fillna(0)
        stats["sum_bowler_bowls_done"] = float(vals.sum())

    if ("batsman_fours" in relevant_columns or "batsman_sixes" in relevant_columns) and "batsman_fours" in df.columns and "batsman_sixes" in df.columns:
        fours = pd.to_numeric(df["batsman_fours"], errors="coerce").fillna(0)
        sixes = pd.to_numeric(df["batsman_sixes"], errors="coerce").fillna(0)
        if "batsman_fours" in relevant_columns:
            stats["sum_batsman_fours"] = float(fours.sum())
        if "batsman_sixes" in relevant_columns:
            stats["sum_batsman_sixes"] = float(sixes.sum())
        if any(x in signals for x in ["boundary", "four", "six"]):
            stats["boundary_event_count"] = int(((fours > 0) | (sixes > 0)).sum())

    if "dismissal" in relevant_columns and "dismissal" in df.columns:
        dismissals = df["dismissal"].fillna("").astype(str).str.strip()
        stats["dismissal_count"] = int(dismissals.ne("").sum())

    return stats


def _build_operator_plan(
    provenance_steps: Sequence[Dict[str, Any]],
    *,
    group_keys_preview: int,
) -> List[Dict[str, Any]]:
    include_types = {"filter_where", "group_by", "filter_having", "project", "order_by"}
    plan: List[Dict[str, Any]] = []
    for step in provenance_steps:
        node_type = step.get("node_type")
        if node_type not in include_types:
            continue
        entry: Dict[str, Any] = {
            "node_type": node_type,
            "label": step.get("label"),
            "sql_fragment": step.get("sql_fragment"),
            "input_row_count": len(step.get("input_row_indices") or []),
            "output_row_count": len(step.get("output_row_indices") or []),
        }
        if node_type == "group_by":
            group_keys = step.get("group_keys") or []
            entry["group_count"] = int(step.get("group_count") or len(group_keys))
            entry["group_keys_preview"] = group_keys[:group_keys_preview]
        plan.append(entry)
    return plan


def _rows_from_answer(answer: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    columns = [str(c) for c in (answer.get("columns") or [])]
    rows = answer.get("rows") or []
    clean_rows = [[_normalize_cell(v) for v in row] for row in rows]
    return columns, clean_rows


def _build_training_record(
    rec: Dict[str, Any],
    *,
    match_dir: Path,
    group_keys_preview: int,
    include_context: bool,
) -> Dict[str, Any]:
    primary_key = _normalize_primary_key(rec.get("primary_key"))
    csv_path = _resolve_match_csv(str(rec["match_path"]), match_dir)
    match_df = pd.read_csv(csv_path)

    sql_text = normalize_query_sql_for_duckdb(str(rec["sql"]))
    _ = execute_sql_on_df(match_df, sql_text, table_name="df")
    prov = extract_row_indices_from_query(sql_text, match_df, None, table_name="df")
    if not prov.get("provenance_supported"):
        raise ValueError(f"Unsupported provenance: {prov.get('provenance_error')}")

    answer_columns, answer_rows = _rows_from_answer(rec["answer"])
    relevant_columns = _infer_relevant_columns(
        sql_text=sql_text,
        question=str(rec.get("question") or ""),
        primary_key=primary_key,
        answer_columns=answer_columns,
    )
    output_row_provenance = prov.get("output_row_provenance") or []
    if len(output_row_provenance) != len(answer_rows):
        raise ValueError(
            f"Output provenance row count mismatch: {len(output_row_provenance)} provenance rows vs "
            f"{len(answer_rows)} answer rows"
        )

    rows: List[Dict[str, Any]] = []
    compressed_rows: List[Dict[str, Any]] = []
    for row_idx, (final_row, base_indices) in enumerate(zip(answer_rows, output_row_provenance)):
        row_key = _row_key_from_answer_row(answer_columns, final_row, primary_key)
        base_indices_clean = [idx for idx in (_safe_int(x) for x in base_indices) if idx is not None]
        evidence_df = match_df.iloc[base_indices_clean].copy() if base_indices_clean else match_df.iloc[0:0].copy()
        evidence_ledger = [_serialize_evidence_row(row) for _, row in evidence_df.iterrows()]
        rows.append(
            {
                "row_index": row_idx,
                "row_key": row_key,
                "provenance_base_row_indices": base_indices_clean,
                "evidence_ledger": evidence_ledger,
                "intermediate_stats": _compute_canonical_stats(evidence_df),
                "final_row": final_row,
            }
        )
        compressed_rows.append(
            {
                "row_index": row_idx,
                "row_key": row_key,
                "minimal_evidence": [
                    _serialize_minimal_event(row, relevant_columns)
                    for _, row in evidence_df.iterrows()
                ],
                "task_stats": _compute_task_stats(
                    evidence_df,
                    relevant_columns=relevant_columns,
                    sql_text=sql_text,
                    question=str(rec.get("question") or ""),
                ),
                "final_row": final_row,
            }
        )

    training_record: Dict[str, Any] = {
        "sample_id": rec.get("sample_id"),
        "record_id": rec.get("record_id"),
        "match_path": rec.get("match_path"),
        "question": rec.get("question"),
        "intent": rec.get("intent"),
        "description": rec.get("description"),
        "structure": rec.get("structure"),
        "primary_key": primary_key,
        "answer_columns": answer_columns,
        "sql": sql_text,
        "raw_symbolic_trajectory": {
            "operator_plan": _build_operator_plan(
                prov.get("provenance_steps") or [],
                group_keys_preview=group_keys_preview,
            ),
            "row_indices_scanned_count": int(prov.get("row_indices_scanned_count") or len(prov.get("row_indices_scanned") or [])),
            "row_indices_contributing_count": int(
                prov.get("row_indices_contributing_count") or len(prov.get("row_indices_contributing") or [])
            ),
            "rows": rows,
            "final_table": {
                "columns": answer_columns,
                "rows": answer_rows,
            },
        },
        "compressed_training_target": {
            "operator_plan": _build_operator_plan(
                prov.get("provenance_steps") or [],
                group_keys_preview=group_keys_preview,
            ),
            "relevant_columns": relevant_columns,
            "rows": compressed_rows,
            "final_table": {
                "columns": answer_columns,
                "rows": answer_rows,
            },
        },
    }
    if include_context:
        training_record["context_full_with_overs"] = rec.get("context_full_with_overs")
    return training_record


def _iter_records(records: Sequence[Dict[str, Any]], limit: Optional[int]) -> Iterable[Dict[str, Any]]:
    if limit is None:
        yield from records
        return
    for rec in records[: max(limit, 0)]:
        yield rec


def main() -> None:
    args = _parse_args()
    dataset_path = Path(args.dataset)
    match_dir = Path(args.match_dir)
    output_path = Path(args.output)
    errors_path = Path(args.errors_output)

    records = _load_dataset(dataset_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors_path.parent.mkdir(parents=True, exist_ok=True)

    errors: List[Dict[str, Any]] = []
    written = 0

    with output_path.open("w", encoding="utf-8") as fout:
        for rec in _iter_records(records, args.limit):
            try:
                training_record = _build_training_record(
                    rec,
                    match_dir=match_dir,
                    group_keys_preview=args.group_keys_preview,
                    include_context=args.include_context,
                )
                fout.write(json.dumps(training_record, ensure_ascii=True) + "\n")
                written += 1
            except Exception as exc:
                errors.append(
                    {
                        "sample_id": rec.get("sample_id"),
                        "record_id": rec.get("record_id"),
                        "match_path": rec.get("match_path"),
                        "error": str(exc),
                    }
                )

    errors_path.write_text(json.dumps({"num_errors": len(errors), "errors": errors}, indent=2))
    print(
        json.dumps(
            {
                "dataset": str(dataset_path),
                "output": str(output_path),
                "errors_output": str(errors_path),
                "written": written,
                "num_errors": len(errors),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

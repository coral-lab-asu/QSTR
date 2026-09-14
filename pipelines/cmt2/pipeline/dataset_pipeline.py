"""Shared data-pipeline primitives for CMT2.

The legacy CMT2 scripts produce both JSON containers (with a ``final`` list)
and JSONL datasets.  This module gives both formats one small, testable
interface for validation and deduplication.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_SQL = re.compile(
    r"\b(attach|call|copy|create|delete|detach|drop|export|import|insert|install|load|pragma|update)\b",
    flags=re.IGNORECASE,
)
_EXTERNAL_SCAN_SQL = re.compile(
    r"\b(glob|httpfs|parquet_scan|postgres_scan|read_blob|read_csv|read_csv_auto|read_json|read_json_auto|read_parquet|read_text|sqlite_scan)\s*\(",
    flags=re.IGNORECASE,
)


def _records_from_payload(payload: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)], {}
    if isinstance(payload, dict):
        for key in ("final", "records", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)], payload
    raise ValueError("Expected a list or an object containing final/records/items.")


def load_records(path: str | Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load JSON or JSONL records and return records plus container metadata."""
    source = Path(path)
    if source.suffix.lower() == ".jsonl":
        records: List[Dict[str, Any]] = []
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL record {line_number} is not an object.")
            records.append(value)
        return records, {}

    return _records_from_payload(json.loads(source.read_text(encoding="utf-8")))


def write_records(
    path: str | Path,
    records: Iterable[Dict[str, Any]],
    *,
    envelope: Optional[Dict[str, Any]] = None,
) -> None:
    """Write records as JSONL or JSON while preserving a JSON envelope when supplied."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = list(records)
    if destination.suffix.lower() == ".jsonl":
        with destination.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return

    payload: Any = rows
    if envelope is not None:
        payload = dict(envelope)
        key = next((k for k in ("final", "records", "items") if isinstance(payload.get(k), list)), "final")
        payload[key] = rows
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy scalar values into stable JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 12)
    if isinstance(value, (str, int, bool)):
        return value
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_value(item())
        except Exception:
            pass
    return str(value)


def answer_signature(answer: Any) -> str:
    if not isinstance(answer, dict):
        return ""
    columns = [_json_value(value) for value in (answer.get("columns") or [])]
    rows = [[_json_value(value) for value in row] for row in (answer.get("rows") or [])]
    # SQL does not guarantee row order without a complete ORDER BY, and ties
    # may still be returned in either order. Preserve duplicate rows while
    # comparing the result as a multiset.
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    payload = json.dumps({"columns": columns, "rows": rows}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_sql(sql: Any) -> str:
    if not isinstance(sql, str):
        return ""
    return re.sub(r"\s+", " ", sql.strip().lower())


def is_read_only_sql(sql: Any) -> bool:
    """Allow one SELECT/WITH statement and reject mutation or external-scan operations."""
    if not isinstance(sql, str) or not sql.strip():
        return False
    scrubbed = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    scrubbed = re.sub(r"--[^\n]*", " ", scrubbed)
    scrubbed = re.sub(r"'(?:''|[^'])*'", "''", scrubbed)
    statement = scrubbed.strip()
    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if ";" in statement:
        return False
    if not re.match(r"^(select|with)\b", statement, flags=re.IGNORECASE):
        return False
    return not _FORBIDDEN_SQL.search(statement) and not _EXTERNAL_SCAN_SQL.search(statement)


def _resolve_csv(record: Dict[str, Any], default_csv: Optional[str | Path]) -> Optional[Path]:
    candidate = record.get("match_path") or record.get("csv_path") or default_csv
    if not candidate:
        return None
    path = Path(str(candidate))
    if path.exists():
        return path
    rooted = PROJECT_ROOT / path
    return rooted if rooted.exists() else path


def _answer_from_frame(frame: Any) -> Dict[str, Any]:
    columns = [str(column) for column in frame.columns]
    rows = []
    for row in frame.itertuples(index=False, name=None):
        rows.append([_json_value(value) for value in row])
    return {"columns": columns, "rows": rows}


def validate_records(
    records: Iterable[Dict[str, Any]],
    *,
    default_csv: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Execute every SQL record and compare it with its stored answer when present."""
    try:
        import duckdb
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - exercised in deployment environments
        raise RuntimeError("Validation requires pandas and duckdb.") from exc

    cache: Dict[str, Any] = {}
    details: List[Dict[str, Any]] = []
    for index, record in enumerate(records):
        sql = record.get("sql") or record.get("query")
        csv_path = _resolve_csv(record, default_csv)
        detail: Dict[str, Any] = {
            "index": index,
            "record_id": record.get("record_id") or record.get("item_id"),
            "csv_path": str(csv_path) if csv_path else None,
            "sql_present": isinstance(sql, str) and bool(sql.strip()),
            "ok": False,
        }
        if not detail["sql_present"]:
            detail["error"] = "missing sql/query"
            details.append(detail)
            continue
        if not is_read_only_sql(sql):
            detail["error"] = "non-read-only or external-access SQL rejected"
            details.append(detail)
            continue
        if csv_path is None or not csv_path.exists():
            detail["error"] = "CSV source not found"
            details.append(detail)
            continue

        cache_key = str(csv_path.resolve())
        if cache_key not in cache:
            cache[cache_key] = pd.read_csv(csv_path)
        frame = cache[cache_key]
        connection = duckdb.connect(database=":memory:")
        try:
            connection.register("df", frame)
            result = connection.execute(str(sql)).fetchdf()
            actual_answer = _answer_from_frame(result)
        except Exception as exc:
            detail["error"] = str(exc)
            details.append(detail)
            continue
        finally:
            connection.close()

        expected = record.get("answer")
        if not isinstance(expected, dict):
            expected = record.get("ground_truth_table")
        answer_match = not isinstance(expected, dict) or answer_signature(expected) == answer_signature(actual_answer)
        detail.update({
            "ok": bool(answer_match),
            "answer_match": bool(answer_match),
            "answer_checked": isinstance(expected, dict),
            "row_count": int(len(result)),
            "column_count": int(result.shape[1]),
            "result_signature": answer_signature(actual_answer),
        })
        if not answer_match:
            detail["error"] = "stored answer does not match SQL execution"
        details.append(detail)

    valid_count = sum(1 for item in details if item.get("ok"))
    return {
        "total_records": len(details),
        "valid_records": valid_count,
        "invalid_records": len(details) - valid_count,
        "records": details,
    }


def deduplicate_records(records: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Keep the first record for each source/result (or source/SQL) fingerprint."""
    kept: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    seen: Dict[Tuple[str, str], int] = {}
    for index, record in enumerate(records):
        source = str(record.get("match_path") or record.get("csv_path") or "")
        result_key = answer_signature(record.get("answer"))
        fingerprint = result_key or canonical_sql(record.get("sql") or record.get("query"))
        key = (source, fingerprint)
        if fingerprint and key in seen:
            removed.append({
                "index": index,
                "duplicate_of": seen[key],
                "record_id": record.get("record_id") or record.get("item_id"),
                "reason": "same source and result/SQL fingerprint",
                "record": record,
            })
            continue
        if fingerprint:
            seen[key] = index
        kept.append(record)
    return kept, removed

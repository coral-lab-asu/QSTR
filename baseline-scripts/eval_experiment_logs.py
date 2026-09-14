import argparse
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.eval.table_metrics_evaluator import TableMetricsEvaluator  # noqa: E402

DEFAULTS = {
    "dataset": "dataset-cricket/cricket-overall.json",
    "model": "gpt-4.1",
    "baseline": "REACT",
    "seed": 0,
    "num_votes": 5,
    "parser": None,
    "log_dir": None,
    "out_predictions": None,
    "out_samplewise": None,
    "out_summary": None,
}

BASELINE_TO_PARSER = {
    "ZS_COT": "zscot",
    "ZSCOT": "zscot",
    "COT": "cot",
    "CHAIN_OF_THOUGHT": "cot",
    "ONEPASS_COT": "onepass_cot",
    "ONE_PASS_COT": "onepass_cot",
    "ROW_COT": "row_cot",
    "ROWCOT": "row_cot",
    "ROW_COT_MODULAR": "row_cot_modular",
    "ROWCOT_MODULAR": "row_cot_modular",
    "EVIDENCE_THEN_COMPUTE": "etc",
    "EVIDENCETHENCOMPUTE": "etc",
    "ETC": "etc",
    "REACT": "react",
    "SC_VOTE": "scvote",
    "SCVOTE": "scvote",
    "LTM": "ltm",
    "LEAST_TO_MOST": "ltm",
}


def read_dataset(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".jsonl"):
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "records" in obj:
        return obj["records"]
    if isinstance(obj, list):
        return obj
    raise ValueError(f"Unsupported dataset format: {path}")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _json_loads_relaxed(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    sanitized: List[str] = []
    in_str = False
    esc = False
    quote = ""
    for ch in text:
        if in_str:
            if esc:
                sanitized.append(ch)
                esc = False
                continue
            if ch == "\\":
                sanitized.append(ch)
                esc = True
                continue
            if ch == quote:
                sanitized.append(ch)
                in_str = False
                continue
            if ch == "\n":
                sanitized.append("\\n")
                continue
            if ch == "\r":
                sanitized.append("\\r")
                continue
            if ch == "\t":
                sanitized.append("\\t")
                continue
            if ord(ch) < 32:
                sanitized.append(f"\\u{ord(ch):04x}")
                continue
            sanitized.append(ch)
            continue

        sanitized.append(ch)
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            esc = False

    return json.loads("".join(sanitized))


def extract_json_obj(text: str) -> Any:
    text = (text or "").strip()
    try:
        return _json_loads_relaxed(text)
    except Exception:
        pass

    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            candidate = parts[i]
            lines = candidate.splitlines()
            if lines and lines[0].strip().lower() in ("json", "jsonl", "javascript"):
                candidate = "\n".join(lines[1:])
            candidate = candidate.strip()
            if not candidate:
                continue
            try:
                return _json_loads_relaxed(candidate)
            except Exception:
                continue

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response.")
    depth = 0
    in_str = False
    esc = False
    quote = ""

    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return _json_loads_relaxed(text[start : i + 1])
    raise ValueError("Could not parse JSON object from response.")


def validate_table(
    obj: Any,
    expected_cols: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Output is not a JSON object."
    cols = obj.get("columns")
    rows = obj.get("rows")
    if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
        return False, None, "Missing or invalid 'columns' list."
    if cols != expected_cols:
        return False, None, "Columns do not match expected headers."
    if not isinstance(rows, list):
        return False, None, "Missing or invalid 'rows' list."
    for row in rows:
        if not isinstance(row, list):
            return False, None, "Row is not a list."
        if len(row) != len(cols):
            return False, None, "Row length does not match columns."
    return True, {"columns": cols, "rows": rows}, ""


def normalize_pred_table(pred: Any) -> Optional[Dict[str, Any]]:
    if isinstance(pred, dict):
        if "columns" in pred and "rows" in pred:
            return {"columns": pred.get("columns") or [], "rows": pred.get("rows") or []}
        if "table" in pred and isinstance(pred["table"], dict):
            table = pred["table"]
            return normalize_pred_table(table)
        if "table" in pred and isinstance(pred["table"], list):
            t = pred["table"]
            if len(t) == 0:
                return {"columns": [], "rows": []}
            if isinstance(t[0], dict):
                cols = list(t[0].keys())
                rows = [[row.get(c) for c in cols] for row in t]
                return {"columns": cols, "rows": rows}
    if isinstance(pred, list):
        if len(pred) == 0:
            return {"columns": [], "rows": []}
        if isinstance(pred[0], dict):
            cols = list(pred[0].keys())
            rows = [[row.get(c) for c in cols] for row in pred]
            return {"columns": cols, "rows": rows}
    return None


def is_zeroish_table(table: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(table, dict):
        return False
    rows = table.get("rows")
    if not isinstance(rows, list):
        return False
    if len(rows) == 0:
        return True
    for row in rows:
        if not isinstance(row, list):
            return False
        for cell in row:
            if cell is None:
                continue
            numeric = _normalize_numeric_string(cell)
            if numeric is not None and numeric == "0":
                continue
            if isinstance(cell, str) and not cell.strip():
                continue
            return False
    return True


def build_dataset_map(dataset: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(dataset):
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        normalized = dict(item)
        pk = normalized.get("primary_key")
        if isinstance(pk, str):
            normalized["primary_key"] = [pk]
        elif not isinstance(pk, list):
            normalized["primary_key"] = None
        out[str(sample_id)] = normalized
    return out


def load_log_files(log_dir: str) -> List[str]:
    files = []
    for name in os.listdir(log_dir):
        if name.endswith(".json"):
            files.append(os.path.join(log_dir, name))
    files.sort()
    return files


def attempt_number_from_path(path: str) -> int:
    base = os.path.splitext(os.path.basename(path))[0]
    if "_a" not in base:
        return -1
    suffix = base.rsplit("_a", 1)[-1]
    try:
        return int(suffix)
    except Exception:
        return -1


def sum_attempt_usages(attempts: Any) -> Dict[str, int]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    if isinstance(attempts, dict):
        flattened: List[Dict[str, Any]] = []
        for value in attempts.values():
            if isinstance(value, list):
                flattened.extend([x for x in value if isinstance(x, dict)])
        attempts_iter = flattened
    elif isinstance(attempts, list):
        attempts_iter = [x for x in attempts if isinstance(x, dict)]
    else:
        attempts_iter = []

    for attempt in attempts_iter:
        usage = attempt.get("usage") or {}
        for key in total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                total[key] += int(value)
    return total


def average_usage_over_successful_samples(reconstructed: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    success_rows = [row for row in reconstructed if row.get("pred_table") is not None]
    if not success_rows:
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    totals = [sum_attempt_usages(row.get("attempts") or []) for row in success_rows]
    n = len(totals)
    return {
        "input_tokens": sum(x["input_tokens"] for x in totals) / n,
        "output_tokens": sum(x["output_tokens"] for x in totals) / n,
        "total_tokens": sum(x["total_tokens"] for x in totals) / n,
    }


def load_predictions_jsonl(predictions_path: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    reconstructed: List[Dict[str, Any]] = []
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for raw in read_dataset(predictions_path):
        sample_id = raw.get("sample_id")
        if sample_id is None:
            sample_id = raw.get("record_id")
        if sample_id is None:
            continue

        ds = ds_map.get(str(sample_id))
        headers = ((ds or {}).get("answer") or {}).get("columns") or raw.get("headers") or []
        expected_rows = (ds or {}).get("answer_rows")
        original_record_id = (ds or {}).get("record_id", raw.get("original_record_id"))

        attempts = raw.get("attempts") or []
        if isinstance(attempts, (list, dict)):
            per_sample_usage = sum_attempt_usages(attempts)
        else:
            per_sample_usage = {
                "input_tokens": int((raw.get("usage_total_per_sample") or {}).get("input_tokens") or 0),
                "output_tokens": int((raw.get("usage_total_per_sample") or {}).get("output_tokens") or 0),
                "total_tokens": int((raw.get("usage_total_per_sample") or {}).get("total_tokens") or 0),
            }
        for key in usage_total:
            usage_total[key] += int(per_sample_usage.get(key) or 0)

        pred_table = raw.get("pred_table")
        if pred_table is None:
            pred_table = raw.get("pred_answer")
        if pred_table is None:
            pred_table = normalize_pred_table(raw)
        else:
            pred_table = normalize_pred_table(pred_table)

        success = False
        error = raw.get("error")
        if pred_table is not None:
            try:
                ok, table, err = validate_table(pred_table, headers, expected_rows)
                if ok:
                    pred_table = table
                    success = True
                    error = None
                else:
                    pred_table = None
                    error = err
            except Exception as exc:
                pred_table = None
                error = str(exc)

        reconstructed.append(
            {
                "record_id": str(sample_id),
                "sample_id": int(sample_id) if str(sample_id).isdigit() else sample_id,
                "original_record_id": original_record_id,
                "question": (ds or {}).get("question", raw.get("question")),
                "headers": headers,
                "expected_rows": expected_rows,
                "pred_table": pred_table,
                "success": success,
                "error": error,
                "attempts": attempts,
                "usage_total_per_sample": per_sample_usage,
                "chosen_attempt": raw.get("chosen_attempt"),
                "chosen_plan_attempt": raw.get("chosen_plan_attempt"),
                "chosen_fill_attempt": raw.get("chosen_fill_attempt"),
            }
        )

    return reconstructed, usage_total


def _parse_table_response(
    response_text: str,
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    candidate = parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("final_table"), dict):
        candidate = parsed.get("final_table")
    table_candidate = normalize_pred_table(candidate)
    if table_candidate is None:
        return False, None, "Missing or invalid 'columns' list."
    return validate_table(table_candidate, headers, expected_rows)


def _normalize_numeric_string(value: Any) -> Optional[str]:
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            dec = Decimal(text)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            dec = Decimal(str(value))
        else:
            return None
    except (InvalidOperation, ValueError):
        return None

    normalized = format(dec.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if normalized in ("", "-0"):
        normalized = "0"
    return normalized


def _canonicalize_cell(value: Any) -> Any:
    if value is None:
        return None
    numeric = _normalize_numeric_string(value)
    if numeric is not None:
        return {"type": "num", "value": numeric}
    if isinstance(value, str):
        return {"type": "str", "value": " ".join(value.strip().split()).lower()}
    return {"type": type(value).__name__, "value": value}


def _canonicalize_table(table: Dict[str, Any], pk_cols: Optional[List[str]]) -> Dict[str, Any]:
    cols = [str(c) for c in (table.get("columns") or [])]
    rows = table.get("rows") or []
    col_idx = {c: i for i, c in enumerate(cols)}
    canonical_rows: List[List[Any]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        canonical_rows.append([_canonicalize_cell(cell) for cell in row])

    def _value_sort_key(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _row_sort_key(row: List[Any]) -> Tuple[str, ...]:
        if pk_cols and all(c in col_idx for c in pk_cols):
            return tuple(_value_sort_key(row[col_idx[c]]) for c in pk_cols)
        return tuple(_value_sort_key(v) for v in row)

    canonical_rows.sort(key=_row_sort_key)
    return {"columns": cols, "rows": canonical_rows}


def _vote_over_candidates(valid_candidates: List[Dict[str, Any]], pk_cols: Optional[List[str]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for candidate in valid_candidates:
        canonical_table = _canonicalize_table(candidate["pred_table"], pk_cols)
        canonical_key = json.dumps(canonical_table, ensure_ascii=False, sort_keys=False)
        payload = dict(candidate)
        payload["canonical_key"] = canonical_key
        grouped.setdefault(canonical_key, []).append(payload)

    ranked_groups = sorted(
        grouped.values(),
        key=lambda group: (-len(group), min(int(x["vote_idx"]) for x in group)),
    )
    winner_group = ranked_groups[0]
    representative = min(winner_group, key=lambda x: (int(x["vote_idx"]), int(x.get("attempt_used", 10**9))))
    vote_counts = [
        {
            "vote_count": len(group),
            "vote_indices": [int(x["vote_idx"]) for x in sorted(group, key=lambda y: int(y["vote_idx"]))],
            "representative_vote_idx": int(min(group, key=lambda y: int(y["vote_idx"]))["vote_idx"]),
        }
        for group in ranked_groups
    ]
    return {
        "chosen_vote_idx": int(representative["vote_idx"]),
        "winner_vote_count": len(winner_group),
        "valid_candidate_n": len(valid_candidates),
        "vote_counts": vote_counts,
        "pred_table": representative["pred_table"],
    }


def parse_zscot_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, List[str]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        sample_id = metadata.get("sample_id")
        if sample_id is None:
            continue
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, paths in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        best_table = None
        best_attempt = None
        last_error = None
        attempts_meta: List[Dict[str, Any]] = []

        for path in sorted(paths, key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            usage = log.get("usage") or {}
            attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
            try:
                ok, table, err = _parse_table_response(response_text, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    best_table = table
                    best_attempt = attempt_idx
                    last_error = None
                else:
                    last_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                last_error = str(exc)
            attempts_meta.append(attempt_info)

        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "pred_table": best_table,
                "success": best_table is not None,
                "error": None if best_table is not None else last_error,
                "attempts": attempts_meta,
                "usage_total_per_sample": sum_attempt_usages(attempts_meta),
                "chosen_attempt": best_attempt,
            }
        )

    return reconstructed, usage_total


def parse_scvote_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, Dict[int, List[str]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    filename_pattern = re.compile(r"(\d+)_v(\d+)_a(\d+)\.json$")

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        sample_id = metadata.get("sample_id")
        vote_idx = metadata.get("vote_idx")
        if sample_id is None or vote_idx is None:
            match = filename_pattern.match(os.path.basename(path))
            if not match:
                continue
            sample_id = match.group(1)
            vote_idx = int(match.group(2))
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), {}).setdefault(int(vote_idx), []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, vote_groups in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")
        pk_cols = ds.get("primary_key")
        if pk_cols is not None and not isinstance(pk_cols, list):
            pk_cols = None

        attempts_meta: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        valid_candidates: List[Dict[str, Any]] = []
        last_error = None

        for vote_idx, paths in sorted(vote_groups.items()):
            best_table = None
            best_attempt = None
            vote_error = None
            vote_attempt_count = 0
            for path in sorted(paths, key=attempt_number_from_path):
                with open(path, "r", encoding="utf-8") as f:
                    log = json.load(f)
                response_text = log.get("response_text", "")
                attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
                usage = log.get("usage") or {}
                attempt_info = {
                    "vote_idx": vote_idx,
                    "attempt": attempt_idx,
                    "path": path,
                    "usage": usage,
                }
                try:
                    ok, table, err = _parse_table_response(response_text, headers, expected_rows)
                    attempt_info["valid"] = ok
                    attempt_info["error"] = err
                    if ok and best_table is None:
                        best_table = table
                        best_attempt = attempt_idx
                        vote_error = None
                    elif not ok:
                        vote_error = err
                except Exception as exc:
                    attempt_info["valid"] = False
                    attempt_info["error"] = str(exc)
                    vote_error = str(exc)
                attempts_meta.append(attempt_info)
                vote_attempt_count += 1

            candidates.append(
                {
                    "vote_idx": vote_idx,
                    "valid": best_table is not None,
                    "attempt_count": vote_attempt_count,
                    "attempt_used": best_attempt,
                    "error": None if best_table is not None else vote_error,
                    "pred_table": best_table,
                }
            )
            if best_table is not None:
                valid_candidates.append(
                    {
                        "vote_idx": vote_idx,
                        "attempt_used": best_attempt if best_attempt is not None else 0,
                        "pred_table": best_table,
                    }
                )
            elif vote_error:
                last_error = vote_error

        winner = _vote_over_candidates(valid_candidates, pk_cols) if valid_candidates else None
        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "pred_table": winner["pred_table"] if winner else None,
                "success": winner is not None,
                "error": None if winner else last_error,
                "attempts": attempts_meta,
                "candidates": candidates,
                "chosen_vote_idx": winner["chosen_vote_idx"] if winner else None,
                "winner_vote_count": winner["winner_vote_count"] if winner else 0,
                "valid_candidate_n": winner["valid_candidate_n"] if winner else 0,
                "vote_counts": winner["vote_counts"] if winner else [],
                "usage_total_per_sample": sum_attempt_usages(attempts_meta),
            }
        )

    return reconstructed, usage_total


def parse_react_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, Dict[str, List[str]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    filename_stage_pattern = re.compile(r"(\d+)_(plan|fill)_a(\d+)\.json$")

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        sample_id = metadata.get("sample_id")
        stage = metadata.get("stage")
        if sample_id is None or stage not in {"plan", "fill"}:
            match = filename_stage_pattern.match(os.path.basename(path))
            if not match:
                continue
            sample_id = match.group(1)
            stage = match.group(2)
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), {}).setdefault(stage, []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, stage_groups in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        planner_output = None
        planner_error = None
        chosen_plan_attempt = None
        plan_attempts: List[Dict[str, Any]] = []
        for path in sorted(stage_groups.get("plan", []), key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            attempt_info = {
                "attempt": attempt_idx,
                "path": path,
                "usage": usage,
            }
            try:
                parsed = extract_json_obj(response_text)
                row_headers = parsed.get("row_headers") if isinstance(parsed, dict) else None
                plan = parsed.get("plan") if isinstance(parsed, dict) else None
                ok = isinstance(row_headers, list) and isinstance(plan, str) and bool(plan.strip())
                attempt_info["valid"] = ok
                attempt_info["error"] = "" if ok else "Missing or invalid planner fields."
                if ok:
                    planner_output = {"row_headers": row_headers, "plan": plan.strip()}
                    chosen_plan_attempt = attempt_idx
                    planner_error = None
                else:
                    planner_error = attempt_info["error"]
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                planner_error = str(exc)
            plan_attempts.append(attempt_info)

        pred_table = None
        fill_reasoning = None
        fill_error = None
        chosen_fill_attempt = None
        fill_attempts: List[Dict[str, Any]] = []
        for path in sorted(stage_groups.get("fill", []), key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            attempt_info = {
                "attempt": attempt_idx,
                "path": path,
                "usage": usage,
            }
            try:
                parsed = extract_json_obj(response_text)
                table_candidate = parsed
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("final_table"), dict):
                        if isinstance(parsed.get("reasoning_trace"), str) and parsed.get("reasoning_trace").strip():
                            fill_reasoning = parsed.get("reasoning_trace").strip()
                        table_candidate = parsed.get("final_table")
                    elif isinstance(parsed.get("table"), dict):
                        if isinstance(parsed.get("reasoning"), str) and parsed.get("reasoning").strip():
                            fill_reasoning = parsed.get("reasoning").strip()
                        table_candidate = parsed.get("table")
                table_candidate = normalize_pred_table(table_candidate)
                ok, table, err = validate_table(table_candidate, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    pred_table = table
                    chosen_fill_attempt = attempt_idx
                    fill_error = None
                else:
                    fill_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                fill_error = str(exc)
            fill_attempts.append(attempt_info)

        attempts_meta = {
            "plan": plan_attempts,
            "fill": fill_attempts,
        }
        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "planner_output": planner_output,
                "fill_reasoning": fill_reasoning,
                "pred_table": pred_table,
                "success": pred_table is not None,
                "error": None if pred_table is not None else (fill_error or planner_error),
                "attempts": attempts_meta,
                "usage_total_per_sample": {
                    key: sum_attempt_usages(plan_attempts).get(key, 0) + sum_attempt_usages(fill_attempts).get(key, 0)
                    for key in ("input_tokens", "output_tokens", "total_tokens")
                },
                "chosen_plan_attempt": chosen_plan_attempt,
                "chosen_fill_attempt": chosen_fill_attempt,
            }
        )

    return reconstructed, usage_total


def _validate_ltm_plan(obj: Any) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Planner output is not a JSON object."
    steps = obj.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, None, "Planner output must contain a non-empty 'steps' list."

    required_fields = (
        "step_id",
        "name",
        "depends_on",
        "uses_context",
        "input_keys",
        "output_key",
        "system_instruction",
        "user_instruction",
        "expected_output",
    )
    normalized_steps: List[Dict[str, Any]] = []
    seen_step_ids = set()
    seen_output_keys = set()
    prior_step_ids: List[str] = []
    step_outputs_by_id: Dict[str, str] = {}

    for raw_step in steps:
        if not isinstance(raw_step, dict):
            return False, None, "Every planner step must be a JSON object."
        for field in required_fields:
            if field not in raw_step:
                return False, None, f"Planner step missing required field '{field}'."

        step_id = raw_step.get("step_id")
        name = raw_step.get("name")
        depends_on = raw_step.get("depends_on")
        uses_context = raw_step.get("uses_context")
        input_keys = raw_step.get("input_keys")
        output_key = raw_step.get("output_key")
        system_instruction = raw_step.get("system_instruction")
        user_instruction = raw_step.get("user_instruction")
        expected_output = raw_step.get("expected_output")

        if not isinstance(step_id, str) or not step_id.strip():
            return False, None, "Each step_id must be a non-empty string."
        if step_id in seen_step_ids:
            return False, None, f"Duplicate step_id '{step_id}'."
        if not isinstance(name, str) or not name.strip():
            return False, None, f"Step '{step_id}' has invalid name."
        if not isinstance(depends_on, list) or not all(isinstance(x, str) for x in depends_on):
            return False, None, f"Step '{step_id}' has invalid depends_on."
        if not isinstance(uses_context, bool):
            return False, None, f"Step '{step_id}' has invalid uses_context."
        if not isinstance(input_keys, list) or not all(isinstance(x, str) for x in input_keys):
            return False, None, f"Step '{step_id}' has invalid input_keys."
        if not isinstance(output_key, str) or not output_key.strip():
            return False, None, f"Step '{step_id}' has invalid output_key."
        if output_key in seen_output_keys:
            return False, None, f"Duplicate output_key '{output_key}'."
        if not isinstance(system_instruction, str) or not system_instruction.strip():
            return False, None, f"Step '{step_id}' has invalid system_instruction."
        if not isinstance(user_instruction, str) or not user_instruction.strip():
            return False, None, f"Step '{step_id}' has invalid user_instruction."
        if not isinstance(expected_output, str) or not expected_output.strip():
            return False, None, f"Step '{step_id}' has invalid expected_output."

        for dep in depends_on:
            if dep not in prior_step_ids:
                return False, None, f"Step '{step_id}' depends on unknown or later step '{dep}'."

        allowed_input_keys = {step_outputs_by_id[dep] for dep in depends_on}
        if any(key not in allowed_input_keys for key in input_keys):
            return False, None, f"Step '{step_id}' input_keys must come from dependency outputs."

        normalized_steps.append(
            {
                "step_id": step_id.strip(),
                "name": name.strip(),
                "depends_on": list(depends_on),
                "uses_context": uses_context,
                "input_keys": list(input_keys),
                "output_key": output_key.strip(),
                "system_instruction": system_instruction.strip(),
                "user_instruction": user_instruction.strip(),
                "expected_output": expected_output.strip(),
                "stage_tag": raw_step.get("stage_tag"),
            }
        )
        seen_step_ids.add(step_id)
        seen_output_keys.add(output_key)
        prior_step_ids.append(step_id)
        step_outputs_by_id[step_id] = output_key

    if normalized_steps[-1]["output_key"] != "final_table":
        return False, None, "The final planner step must produce output_key 'final_table'."

    return True, {"steps": normalized_steps}, ""


def _parse_ltm_step_output(
    response_text: str,
    output_key: str,
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Any], str]:
    parsed = extract_json_obj(response_text)
    if output_key == "final_table":
        candidate = parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("final_table"), dict):
            candidate = parsed.get("final_table")
        table_candidate = normalize_pred_table(candidate)
        if table_candidate is None:
            return False, None, "Missing or invalid 'columns' list."
        return validate_table(table_candidate, headers, expected_rows)

    if not isinstance(parsed, dict):
        return False, None, "Step output is not a JSON object."
    if output_key not in parsed:
        return False, None, f"Missing expected top-level key '{output_key}'."
    return True, parsed.get(output_key), ""


def _validate_cot_reasoning_steps(obj: Any) -> Tuple[bool, Optional[List[Dict[str, Any]]], str]:
    if not isinstance(obj, list) or not obj:
        return False, None, "Missing or invalid 'reasoning_steps' list."

    normalized: List[Dict[str, Any]] = []
    prev_step_num = 0
    for idx, raw_step in enumerate(obj):
        if not isinstance(raw_step, dict):
            return False, None, f"Reasoning step at index {idx} is not an object."
        if "step" not in raw_step or "name" not in raw_step or "output" not in raw_step:
            return False, None, f"Reasoning step at index {idx} is missing required fields."

        step_num = raw_step.get("step")
        name = raw_step.get("name")
        if not isinstance(step_num, int):
            return False, None, f"Reasoning step at index {idx} has non-integer 'step'."
        if step_num <= prev_step_num:
            return False, None, "Reasoning step numbers must be strictly increasing."
        if not isinstance(name, str) or not name.strip():
            return False, None, f"Reasoning step {step_num} has invalid 'name'."

        normalized.append(
            {
                "step": step_num,
                "name": name.strip(),
                "output": raw_step.get("output"),
            }
        )
        prev_step_num = step_num

    return True, normalized, ""


def _parse_cot_response(
    response_text: str,
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    if not isinstance(parsed, dict):
        return False, None, "Output is not a JSON object."

    ok_steps, reasoning_steps, err_steps = _validate_cot_reasoning_steps(parsed.get("reasoning_steps"))
    if not ok_steps:
        return False, None, err_steps

    final_table = parsed.get("final_table")
    table_candidate = normalize_pred_table(final_table)
    if table_candidate is None:
        return False, None, "Missing or invalid 'final_table'."
    ok, table, err = validate_table(table_candidate, headers, expected_rows)
    if not ok:
        return False, None, err

    return True, {"reasoning_steps": reasoning_steps, "pred_table": table}, ""


def _parse_onepass_cot_response(
    response_text: str,
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    if not isinstance(parsed, dict):
        return False, None, "Output is not a JSON object."

    reasoning_trace = parsed.get("reasoning_trace")
    if not isinstance(reasoning_trace, str) or not reasoning_trace.strip():
        return False, None, "Missing or invalid 'reasoning_trace' string."

    final_table = parsed.get("final_table")
    table_candidate = normalize_pred_table(final_table)
    if table_candidate is None:
        return False, None, "Missing or invalid 'final_table'."
    ok, table, err = validate_table(table_candidate, headers, expected_rows)
    if not ok:
        return False, None, err

    return True, {"reasoning_trace": reasoning_trace.strip(), "pred_table": table}, ""


def _validate_row_reasoning(obj: Any) -> Tuple[bool, Optional[List[Dict[str, Any]]], str]:
    if not isinstance(obj, list) or not obj:
        return False, None, "Missing or invalid 'row_reasoning' list."

    normalized: List[Dict[str, Any]] = []
    for idx, raw_item in enumerate(obj):
        if not isinstance(raw_item, dict):
            return False, None, f"row_reasoning item at index {idx} is not an object."
        row_key = raw_item.get("row_key")
        trace = raw_item.get("trace")
        if not isinstance(row_key, dict):
            return False, None, f"row_reasoning item at index {idx} has invalid 'row_key'."
        if not isinstance(trace, str) or not trace.strip():
            return False, None, f"row_reasoning item at index {idx} has invalid 'trace'."
        normalized.append({"row_key": row_key, "trace": trace.strip()})

    return True, normalized, ""


def _parse_row_cot_response(
    response_text: str,
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    if not isinstance(parsed, dict):
        return False, None, "Output is not a JSON object."

    ok_reasoning, row_reasoning, err_reasoning = _validate_row_reasoning(parsed.get("row_reasoning"))
    if not ok_reasoning:
        return False, None, err_reasoning

    final_table = parsed.get("final_table")
    table_candidate = normalize_pred_table(final_table)
    if table_candidate is None:
        return False, None, "Missing or invalid 'final_table'."
    ok, table, err = validate_table(table_candidate, headers, expected_rows)
    if not ok:
        return False, None, err

    if len(row_reasoning) != len(table["rows"]):
        return False, None, "row_reasoning count must equal final_table row count."

    return True, {"row_reasoning": row_reasoning, "pred_table": table}, ""


def _parse_row_cot_modular_response(
    response_text: str,
    headers: List[str],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    if not isinstance(parsed, dict):
        return False, None, "Output is not a JSON object."

    reasoning_trace = parsed.get("reasoning_trace")
    if not isinstance(reasoning_trace, str) or not reasoning_trace.strip():
        return False, None, "Missing or invalid 'reasoning_trace' string."

    final_table = parsed.get("final_table")
    table_candidate = normalize_pred_table(final_table)
    if table_candidate is None:
        return False, None, "Missing or invalid 'final_table'."
    ok, table, err = validate_table(table_candidate, headers, expected_rows=1)
    if not ok:
        return False, None, err
    if len(table["rows"]) != 1:
        return False, None, "final_table must contain exactly one row."

    return True, {"reasoning_trace": reasoning_trace.strip(), "pred_table": table}, ""


def _validate_etc_extractor_rows(obj: Any) -> Tuple[bool, Optional[List[Dict[str, Any]]], str]:
    if not isinstance(obj, list) or not obj:
        return False, None, "Missing or invalid 'rows' list."

    normalized: List[Dict[str, Any]] = []
    for idx, raw_item in enumerate(obj):
        if not isinstance(raw_item, dict):
            return False, None, f"rows[{idx}] is not an object."
        row_key = raw_item.get("row_key")
        row_evidence = raw_item.get("row_evidence")
        if not isinstance(row_key, dict):
            return False, None, f"rows[{idx}].row_key is invalid."
        if not isinstance(row_evidence, list) or not row_evidence:
            return False, None, f"rows[{idx}].row_evidence is invalid."
        evidence_norm: List[str] = []
        for item in row_evidence:
            if not isinstance(item, str) or not item.strip():
                return False, None, f"rows[{idx}].row_evidence contains invalid items."
            evidence_norm.append(item.strip())
        normalized.append({"row_key": row_key, "row_evidence": evidence_norm})
    return True, normalized, ""


def _parse_etc_extract_response(
    response_text: str,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    if not isinstance(parsed, dict):
        return False, None, "Extractor output is not a JSON object."
    ok_rows, rows, err_rows = _validate_etc_extractor_rows(parsed.get("rows"))
    if not ok_rows:
        return False, None, err_rows
    return True, {"rows": rows}, ""


def _parse_etc_compute_response(
    response_text: str,
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    parsed = extract_json_obj(response_text)
    if not isinstance(parsed, dict):
        return False, None, "Compute output is not a JSON object."
    rows = parsed.get("rows")
    if not isinstance(rows, list) or not rows:
        return False, None, "Missing or invalid 'rows' list."
    normalized_rows: List[Dict[str, Any]] = []
    for idx, raw_item in enumerate(rows):
        if not isinstance(raw_item, dict):
            return False, None, f"rows[{idx}] is not an object."
        row_key = raw_item.get("row_key")
        intermediate_stats = raw_item.get("intermediate_stats")
        calculation_trace = raw_item.get("calculation_trace")
        final_row = raw_item.get("final_row")
        if not isinstance(row_key, dict):
            return False, None, f"rows[{idx}].row_key is invalid."
        if not isinstance(intermediate_stats, dict):
            return False, None, f"rows[{idx}].intermediate_stats is invalid."
        if not isinstance(calculation_trace, str) or not calculation_trace.strip():
            return False, None, f"rows[{idx}].calculation_trace is invalid."
        if not isinstance(final_row, list):
            return False, None, f"rows[{idx}].final_row is invalid."
        normalized_rows.append(
            {
                "row_key": row_key,
                "intermediate_stats": intermediate_stats,
                "calculation_trace": calculation_trace.strip(),
                "final_row": final_row,
            }
        )

    final_table = parsed.get("final_table")
    table_candidate = normalize_pred_table(final_table)
    if table_candidate is None:
        return False, None, "Missing or invalid 'final_table'."
    ok, table, err = validate_table(table_candidate, headers, expected_rows)
    if not ok:
        return False, None, err
    if len(normalized_rows) != len(table["rows"]):
        return False, None, "rows count must equal final_table row count."
    return True, {"rows": normalized_rows, "pred_table": table}, ""


def parse_etc_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, Dict[str, List[str]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    filename_stage_pattern = re.compile(r"(\d+)_(extract|compute)_a(\d+)\.json$")

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        stage = metadata.get("stage")
        sample_id = metadata.get("sample_id")
        if sample_id is None or stage not in {"extract", "compute"}:
            match = filename_stage_pattern.match(os.path.basename(path))
            if not match:
                continue
            sample_id = match.group(1)
            stage = match.group(2)
        if metadata.get("baseline") not in {None, "EVIDENCE_THEN_COMPUTE"} and "stage" in metadata:
            continue
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), {}).setdefault(stage, []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, stage_groups in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        extractor_output = None
        extract_error = None
        chosen_extract_attempt = None
        extract_attempts: List[Dict[str, Any]] = []
        for path in sorted(stage_groups.get("extract", []), key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
            try:
                ok, payload, err = _parse_etc_extract_response(response_text)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    extractor_output = payload
                    chosen_extract_attempt = attempt_idx
                    extract_error = None
                else:
                    extract_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                extract_error = str(exc)
            extract_attempts.append(attempt_info)

        compute_rows = None
        pred_table = None
        compute_error = None
        chosen_compute_attempt = None
        compute_attempts: List[Dict[str, Any]] = []
        for path in sorted(stage_groups.get("compute", []), key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
            try:
                ok, payload, err = _parse_etc_compute_response(response_text, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    compute_rows = payload["rows"]
                    pred_table = payload["pred_table"]
                    chosen_compute_attempt = attempt_idx
                    compute_error = None
                else:
                    compute_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                compute_error = str(exc)
            compute_attempts.append(attempt_info)

        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "extractor_output": extractor_output,
                "compute_rows": compute_rows,
                "pred_table": pred_table,
                "success": pred_table is not None,
                "error": None if pred_table is not None else (compute_error or extract_error),
                "attempts": {
                    "extract": extract_attempts,
                    "compute": compute_attempts,
                },
                "usage_total_per_sample": {
                    key: sum_attempt_usages(extract_attempts).get(key, 0) + sum_attempt_usages(compute_attempts).get(key, 0)
                    for key in ("input_tokens", "output_tokens", "total_tokens")
                },
                "chosen_extract_attempt": chosen_extract_attempt,
                "chosen_compute_attempt": chosen_compute_attempt,
            }
        )

    return reconstructed, usage_total


def parse_ltm_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, Dict[str, List[str]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        if metadata.get("baseline") != "LTM":
            continue
        sample_id = metadata.get("sample_id")
        stage_tag = metadata.get("stage_tag")
        if sample_id is None or not isinstance(stage_tag, str):
            continue
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), {}).setdefault(stage_tag, []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, stage_groups in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        planner_output = None
        planner_error = None
        chosen_plan_attempt = None
        plan_attempts: List[Dict[str, Any]] = []

        for path in sorted(stage_groups.get("plan", []), key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            metadata = log.get("metadata") or {}
            attempt_idx = metadata.get("attempt", attempt_number_from_path(path))
            attempt_info = {
                "stage": "plan",
                "stage_kind": metadata.get("stage_kind"),
                "step_id": None,
                "output_key": None,
                "attempt": attempt_idx,
                "path": path,
                "usage": usage,
            }
            try:
                parsed = extract_json_obj(response_text)
                ok, normalized_plan, err = _validate_ltm_plan(parsed)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    planner_output = normalized_plan
                    chosen_plan_attempt = attempt_idx
                    planner_error = None
                else:
                    planner_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                planner_error = str(exc)
            plan_attempts.append(attempt_info)

        step_attempts: List[Dict[str, Any]] = []
        chosen_step_attempts: Dict[str, Optional[int]] = {}
        outputs: Dict[str, Any] = {}
        pred_table = None
        final_error = None

        if planner_output is not None:
            for step in planner_output["steps"]:
                stage_tag = step.get("stage_tag")
                if not stage_tag:
                    stage_tag = f"{step['step_id']}_{re.sub(r'[^a-z0-9]+', '_', step['name'].lower()).strip('_') or 'step'}"
                paths = sorted(stage_groups.get(stage_tag, []), key=attempt_number_from_path)
                chosen_step_attempts[step["step_id"]] = None

                for path in paths:
                    with open(path, "r", encoding="utf-8") as f:
                        log = json.load(f)
                    response_text = log.get("response_text", "")
                    usage = log.get("usage") or {}
                    metadata = log.get("metadata") or {}
                    attempt_idx = metadata.get("attempt", attempt_number_from_path(path))
                    attempt_info = {
                        "stage": stage_tag,
                        "stage_kind": metadata.get("stage_kind"),
                        "step_id": metadata.get("step_id", step["step_id"]),
                        "output_key": metadata.get("output_key", step["output_key"]),
                        "attempt": attempt_idx,
                        "path": path,
                        "usage": usage,
                    }
                    try:
                        ok, payload, err = _parse_ltm_step_output(
                            response_text=response_text,
                            output_key=step["output_key"],
                            headers=headers,
                            expected_rows=expected_rows,
                        )
                        attempt_info["valid"] = ok
                        attempt_info["error"] = err
                        if ok and chosen_step_attempts[step["step_id"]] is None:
                            outputs[step["output_key"]] = payload
                            chosen_step_attempts[step["step_id"]] = attempt_idx
                            final_error = None
                            if step["output_key"] == "final_table":
                                pred_table = payload
                        elif not ok:
                            final_error = err
                    except Exception as exc:
                        attempt_info["valid"] = False
                        attempt_info["error"] = str(exc)
                        final_error = str(exc)
                    step_attempts.append(attempt_info)

        attempts_meta = plan_attempts + step_attempts
        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "planner_output": planner_output,
                "pred_table": pred_table,
                "success": pred_table is not None,
                "error": None if pred_table is not None else (final_error or planner_error),
                "attempts": attempts_meta,
                "usage_total_per_sample": sum_attempt_usages(attempts_meta),
                "chosen_plan_attempt": chosen_plan_attempt,
                "chosen_step_attempts": chosen_step_attempts,
            }
        )

    return reconstructed, usage_total


def parse_cot_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, List[str]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        if metadata.get("baseline") not in {None, "COT"}:
            continue
        sample_id = metadata.get("sample_id")
        if sample_id is None:
            base = os.path.splitext(os.path.basename(path))[0]
            if "_a" not in base:
                continue
            sample_id = base.rsplit("_a", 1)[0]
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, paths in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        best_table = None
        best_reasoning_steps = None
        best_attempt = None
        last_error = None
        attempts_meta: List[Dict[str, Any]] = []

        for path in sorted(paths, key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            usage = log.get("usage") or {}
            attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
            try:
                ok, payload, err = _parse_cot_response(response_text, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    best_table = payload["pred_table"]
                    best_reasoning_steps = payload["reasoning_steps"]
                    best_attempt = attempt_idx
                    last_error = None
                else:
                    last_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                last_error = str(exc)
            attempts_meta.append(attempt_info)

        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "reasoning_steps": best_reasoning_steps,
                "pred_table": best_table,
                "success": best_table is not None,
                "error": None if best_table is not None else last_error,
                "attempts": attempts_meta,
                "usage_total_per_sample": sum_attempt_usages(attempts_meta),
                "chosen_attempt": best_attempt,
            }
        )

    return reconstructed, usage_total


def parse_onepass_cot_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, List[str]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        if metadata.get("baseline") not in {"ONEPASS_COT"}:
            continue
        sample_id = metadata.get("sample_id")
        if sample_id is None:
            base = os.path.splitext(os.path.basename(path))[0]
            if "_a" not in base:
                continue
            sample_id = base.rsplit("_a", 1)[0]
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, paths in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        best_table = None
        best_reasoning_trace = None
        best_attempt = None
        last_error = None
        attempts_meta: List[Dict[str, Any]] = []

        for path in sorted(paths, key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            usage = log.get("usage") or {}
            attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
            try:
                ok, payload, err = _parse_onepass_cot_response(response_text, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    best_table = payload["pred_table"]
                    best_reasoning_trace = payload["reasoning_trace"]
                    best_attempt = attempt_idx
                    last_error = None
                else:
                    last_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                last_error = str(exc)
            attempts_meta.append(attempt_info)

        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "reasoning_trace": best_reasoning_trace,
                "pred_table": best_table,
                "success": best_table is not None,
                "error": None if best_table is not None else last_error,
                "attempts": attempts_meta,
                "usage_total_per_sample": sum_attempt_usages(attempts_meta),
                "chosen_attempt": best_attempt,
            }
        )

    return reconstructed, usage_total


def parse_row_cot_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, List[str]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        if metadata.get("baseline") not in {"ROW_COT", "ROW_COT_GEMINI"}:
            continue
        sample_id = metadata.get("sample_id")
        if sample_id is None:
            base = os.path.splitext(os.path.basename(path))[0]
            if "_a" not in base:
                continue
            sample_id = base.rsplit("_a", 1)[0]
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, paths in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        best_table = None
        best_row_reasoning = None
        best_attempt = None
        last_error = None
        attempts_meta: List[Dict[str, Any]] = []

        for path in sorted(paths, key=attempt_number_from_path):
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
            response_text = log.get("response_text", "")
            attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
            usage = log.get("usage") or {}
            attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
            try:
                ok, payload, err = _parse_row_cot_response(response_text, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    best_table = payload["pred_table"]
                    best_row_reasoning = payload["row_reasoning"]
                    best_attempt = attempt_idx
                    last_error = None
                else:
                    last_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                last_error = str(exc)
            attempts_meta.append(attempt_info)

        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "row_reasoning": best_row_reasoning,
                "pred_table": best_table,
                "success": best_table is not None,
                "error": None if best_table is not None else last_error,
                "attempts": attempts_meta,
                "usage_total_per_sample": sum_attempt_usages(attempts_meta),
                "chosen_attempt": best_attempt,
            }
        )

    return reconstructed, usage_total


def parse_row_cot_modular_logs(log_dir: str, ds_map: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    grouped_logs: Dict[str, Dict[int, List[str]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for path in load_log_files(log_dir):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)
        metadata = log.get("metadata") or {}
        if metadata.get("baseline") != "ROW_COT_MODULAR":
            continue
        sample_id = metadata.get("sample_id")
        row_idx = metadata.get("row_idx")
        if sample_id is None or row_idx is None:
            base = os.path.splitext(os.path.basename(path))[0]
            match = re.match(r"^(.+)_row(\d+)_a\d+$", base)
            if not match:
                continue
            sample_id = match.group(1)
            row_idx = int(match.group(2))
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped_logs.setdefault(str(sample_id), {}).setdefault(int(row_idx), []).append(path)

    reconstructed: List[Dict[str, Any]] = []
    for sample_id, row_groups in sorted(grouped_logs.items(), key=lambda kv: int(kv[0])):
        ds = ds_map.get(sample_id)
        if ds is None:
            continue
        headers = (ds.get("answer") or {}).get("columns") or []
        expected_rows = ds.get("answer_rows")
        original_record_id = ds.get("record_id")

        best_rows: Dict[int, List[Any]] = {}
        best_row_reasoning: Dict[int, Dict[str, Any]] = {}
        chosen_attempts: Dict[int, Optional[int]] = {}
        last_error = None
        attempts_meta: Dict[str, List[Dict[str, Any]]] = {}

        for row_idx, paths in sorted(row_groups.items()):
            row_attempts: List[Dict[str, Any]] = []
            best_attempt = None
            for path in sorted(paths, key=attempt_number_from_path):
                with open(path, "r", encoding="utf-8") as f:
                    log = json.load(f)
                response_text = log.get("response_text", "")
                attempt_idx = (log.get("metadata") or {}).get("attempt", attempt_number_from_path(path))
                usage = log.get("usage") or {}
                attempt_info = {"attempt": attempt_idx, "path": path, "usage": usage}
                try:
                    ok, payload, err = _parse_row_cot_modular_response(response_text, headers)
                    attempt_info["valid"] = ok
                    attempt_info["error"] = err
                    if ok:
                        row = payload["pred_table"]["rows"][0]
                        best_rows[row_idx] = row
                        best_row_reasoning[row_idx] = {
                            "row_key": {},
                            "trace": payload["reasoning_trace"],
                        }
                        best_attempt = attempt_idx
                        last_error = None
                    else:
                        last_error = err
                except Exception as exc:
                    attempt_info["valid"] = False
                    attempt_info["error"] = str(exc)
                    last_error = str(exc)
                row_attempts.append(attempt_info)
            attempts_meta[f"row_{row_idx}"] = row_attempts
            chosen_attempts[row_idx] = best_attempt

        pred_table = None
        row_reasoning = None
        if best_rows:
            rows = [best_rows[idx] for idx in sorted(best_rows)]
            ok, table, err = validate_table({"columns": headers, "rows": rows}, headers, expected_rows)
            if ok:
                pred_table = table
                row_reasoning = [best_row_reasoning[idx] for idx in sorted(best_row_reasoning)]
                last_error = None
            else:
                last_error = err

        reconstructed.append(
            {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": original_record_id,
                "question": ds.get("question"),
                "headers": headers,
                "expected_rows": expected_rows,
                "row_reasoning": row_reasoning,
                "pred_table": pred_table,
                "success": pred_table is not None,
                "error": None if pred_table is not None else last_error,
                "attempts": attempts_meta,
                "usage_total_per_sample": {
                    key: sum(sum_attempt_usages(v).get(key, 0) for v in attempts_meta.values())
                    for key in ("input_tokens", "output_tokens", "total_tokens")
                },
                "chosen_attempts": chosen_attempts,
            }
        )

    return reconstructed, usage_total


PARSERS = {
    "zscot": parse_zscot_logs,
    "cot": parse_cot_logs,
    "onepass_cot": parse_onepass_cot_logs,
    "row_cot": parse_row_cot_logs,
    "row_cot_modular": parse_row_cot_modular_logs,
    "etc": parse_etc_logs,
    "scvote": parse_scvote_logs,
    "react": parse_react_logs,
    "ltm": parse_ltm_logs,
}


def infer_parser_from_baseline(baseline: str) -> str:
    parser = BASELINE_TO_PARSER.get((baseline or "").upper())
    if parser is None:
        raise ValueError(
            f"Could not infer parser for baseline '{baseline}'. "
            f"Set --parser explicitly or add it to BASELINE_TO_PARSER."
        )
    return parser


def canonicalize_baseline_name(baseline: str) -> str:
    name = (baseline or "").upper()
    aliases = {
        "ZSCOT": "ZS_COT",
        "ZS_COT": "ZS_COT",
        "COT": "COT",
        "CHAIN_OF_THOUGHT": "COT",
        "ONEPASS_COT": "ONEPASS_COT",
        "ONE_PASS_COT": "ONEPASS_COT",
        "ROWCOT": "ROW_COT",
        "ROW_COT": "ROW_COT",
        "ROWCOT_MODULAR": "ROW_COT_MODULAR",
        "ROW_COT_MODULAR": "ROW_COT_MODULAR",
        "ETC": "EVIDENCE_THEN_COMPUTE",
        "EVIDENCETHENCOMPUTE": "EVIDENCE_THEN_COMPUTE",
        "EVIDENCE_THEN_COMPUTE": "EVIDENCE_THEN_COMPUTE",
        "SCVOTE": "SC_VOTE",
        "SC_VOTE": "SC_VOTE",
        "REACT": "REACT",
        "LTM": "LTM",
        "LEAST_TO_MOST": "LTM",
    }
    return aliases.get(name, name)


def derive_default_paths(model: str, baseline: str, seed: int, num_votes: Optional[int] = None) -> Dict[str, str]:
    baseline_upper = canonicalize_baseline_name(baseline)
    if baseline_upper == "SC_VOTE":
        votes = int(num_votes if num_votes is not None else DEFAULTS["num_votes"])
        base = f"baseline-results/{model}/{baseline_upper}/{votes}"
        return {
            "log_dir": f"{base}/logs/{baseline_upper}_run_{seed}_{votes}",
            "out_predictions": f"{base}/reconstructed_predictions.jsonl",
            "out_samplewise": f"{base}/eval.samplewise.jsonl",
            "out_summary": f"{base}/eval.summary.json",
        }
    return {
        "log_dir": f"baseline-results/{model}/{baseline_upper}/logs/{baseline_upper}_run_{seed}",
        "out_predictions": f"baseline-results/{model}/{baseline_upper}/reconstructed_predictions.jsonl",
        "out_samplewise": f"baseline-results/{model}/{baseline_upper}/eval.samplewise.jsonl",
        "out_summary": f"baseline-results/{model}/{baseline_upper}/eval.summary.json",
    }


def evaluate_reconstructed_predictions(
    reconstructed: List[Dict[str, Any]],
    ds_map: Dict[str, Dict[str, Any]],
    dataset_path: str,
    parser_name: str,
    source_path: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    samplewise: List[Dict[str, Any]] = []
    agg = {
        "n_total": 0,
        "n_eval": 0,
        "missing_pred_n": 0,
        "exact_match_n": 0,
        "row_match_n": 0,
        "col_match_n": 0,
        "content_match_n": 0,
        "pk_eval_n": 0,
        "pk_exact_n": 0,
        "pk_precision_sum": 0.0,
        "pk_recall_sum": 0.0,
        "pk_f1_sum": 0.0,
        "pk_cell_eval_n": 0,
        "pk_cell_acc_sum": 0.0,
        "zero_null_cell_eval_n": 0,
        "zero_null_tp": 0,
        "zero_null_fp": 0,
        "zero_null_fn": 0,
        "zero_null_tn": 0,
        "gold_zeroish_n": 0,
        "gold_zeroish_pred_zeroish_n": 0,
        "gold_zeroish_pred_missing_n": 0,
        "zeroish_sample_tp": 0,
        "zeroish_sample_fp": 0,
        "zeroish_sample_fn": 0,
        "zeroish_sample_tn": 0,
        "num_eval_n": 0,
        "numeric_pair_n": 0,
        "numeric_overcount_n": 0,
        "numeric_undercount_n": 0,
        "rmse_sum": 0.0,
        "mae_sum": 0.0,
    }

    for pred in reconstructed:
        sample_id = str(pred.get("record_id"))
        ds = ds_map.get(sample_id)
        if ds is None:
            continue

        agg["n_total"] += 1
        pred_table = pred.get("pred_table")
        gold_is_zeroish = bool(ds.get("is_zeroish"))
        if gold_is_zeroish:
            agg["gold_zeroish_n"] += 1
        if pred_table is None:
            agg["missing_pred_n"] += 1
            if gold_is_zeroish:
                agg["gold_zeroish_pred_missing_n"] += 1
                agg["zeroish_sample_fn"] += 1
            else:
                agg["zeroish_sample_tn"] += 1
            samplewise.append(
                {
                    "record_id": pred.get("record_id"),
                    "sample_id": pred.get("sample_id"),
                    "original_record_id": pred.get("original_record_id"),
                    "question": pred.get("question"),
                    "missing_pred": True,
                    "gold_is_zeroish": gold_is_zeroish,
                    "pred_is_zeroish": False,
                    "Overcount%": None,
                    "Undercount%": None,
                    "error": pred.get("error"),
                    "attempts": pred.get("attempts"),
                }
            )
            continue

        out = TableMetricsEvaluator.compare_tables(ds["answer"], pred_table, primary_key=ds.get("primary_key"))
        pred_is_zeroish = is_zeroish_table(pred_table)
        if gold_is_zeroish and pred_is_zeroish:
            agg["gold_zeroish_pred_zeroish_n"] += 1
        if gold_is_zeroish and pred_is_zeroish:
            agg["zeroish_sample_tp"] += 1
        elif gold_is_zeroish and not pred_is_zeroish:
            agg["zeroish_sample_fn"] += 1
        elif not gold_is_zeroish and pred_is_zeroish:
            agg["zeroish_sample_fp"] += 1
        else:
            agg["zeroish_sample_tn"] += 1
        agg["n_eval"] += 1
        tm = out["table_match"]
        agg["exact_match_n"] += 1 if tm.get("exact_match") else 0
        agg["row_match_n"] += 1 if tm.get("row_match") else 0
        agg["col_match_n"] += 1 if tm.get("col_match") else 0
        agg["content_match_n"] += 1 if tm.get("content_match") else 0

        pkm = out["pk_metrics"]
        if not pkm.get("pk_eval_skipped"):
            agg["pk_eval_n"] += 1
            agg["pk_exact_n"] += 1 if pkm.get("pk_exact_set_match") else 0
            agg["pk_precision_sum"] += float(pkm.get("pk_precision") or 0.0)
            agg["pk_recall_sum"] += float(pkm.get("pk_recall") or 0.0)
            agg["pk_f1_sum"] += float(pkm.get("pk_f1") or 0.0)

        pkcm = out["pk_cell_metrics"]
        if not pkcm.get("pk_cell_eval_skipped"):
            agg["pk_cell_eval_n"] += 1
            agg["pk_cell_acc_sum"] += float(pkcm.get("cell_acc") or 0.0)
            znm = pkcm.get("zero_null_metrics") or {}
            if not znm.get("zero_null_eval_skipped"):
                agg["zero_null_cell_eval_n"] += int(znm.get("eval_cell_n") or 0)
                agg["zero_null_tp"] += int(znm.get("tp") or 0)
                agg["zero_null_fp"] += int(znm.get("fp") or 0)
                agg["zero_null_fn"] += int(znm.get("fn") or 0)
                agg["zero_null_tn"] += int(znm.get("tn") or 0)

        nm = out["numeric_metrics"]
        if not nm.get("numeric_eval_skipped"):
            agg["num_eval_n"] += 1
            numeric_macro = nm["macro"]
            rmse = numeric_macro.get("weighted_rmse")
            mae = numeric_macro.get("weighted_mae")
            agg["numeric_pair_n"] += int(numeric_macro.get("total_numeric_pairs") or 0)
            agg["numeric_overcount_n"] += int(numeric_macro.get("overcount_n") or 0)
            agg["numeric_undercount_n"] += int(numeric_macro.get("undercount_n") or 0)
            agg["rmse_sum"] += float(rmse) if rmse is not None else 0.0
            agg["mae_sum"] += float(mae) if mae is not None else 0.0

        sample_record = {
            "record_id": pred.get("record_id"),
            "sample_id": pred.get("sample_id"),
            "original_record_id": pred.get("original_record_id"),
            "question": pred.get("question"),
            "pred_table": pred_table,
            "gold_table": ds["answer"],
            "gold_is_zeroish": gold_is_zeroish,
            "pred_is_zeroish": pred_is_zeroish,
            "table_match": tm,
            "pk_metrics": pkm,
            "pk_cell_metrics": pkcm,
            "numeric_metrics": nm,
            "Overcount%": (nm.get("macro") or {}).get("Overcount%"),
            "Undercount%": (nm.get("macro") or {}).get("Undercount%"),
            "attempts": pred.get("attempts"),
        }
        if "chosen_attempt" in pred:
            sample_record["chosen_attempt"] = pred.get("chosen_attempt")
        if "chosen_plan_attempt" in pred:
            sample_record["chosen_plan_attempt"] = pred.get("chosen_plan_attempt")
        if "chosen_fill_attempt" in pred:
            sample_record["chosen_fill_attempt"] = pred.get("chosen_fill_attempt")
        samplewise.append(sample_record)

    summary = {
        "n_total": agg["n_total"],
        "n_eval": agg["n_eval"],
        "missing_pred_n": agg["missing_pred_n"],
        "exact_match_rate": (agg["exact_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "row_match_rate": (agg["row_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "col_match_rate": (agg["col_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "content_match_rate": (agg["content_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "pk_exact_rate": (agg["pk_exact_n"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_precision_avg": (agg["pk_precision_sum"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_recall_avg": (agg["pk_recall_sum"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_f1_avg": (agg["pk_f1_sum"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_cell_acc_avg": (agg["pk_cell_acc_sum"] / agg["pk_cell_eval_n"]) if agg["pk_cell_eval_n"] else None,
        "zero_null_cell_accuracy": (
            (agg["zero_null_tp"] + agg["zero_null_tn"]) / agg["zero_null_cell_eval_n"]
        ) if agg["zero_null_cell_eval_n"] else None,
        "zero_null_cell_precision": (
            agg["zero_null_tp"] / (agg["zero_null_tp"] + agg["zero_null_fp"])
        ) if (agg["zero_null_tp"] + agg["zero_null_fp"]) else None,
        "zero_null_cell_recall": (
            agg["zero_null_tp"] / (agg["zero_null_tp"] + agg["zero_null_fn"])
        ) if (agg["zero_null_tp"] + agg["zero_null_fn"]) else None,
        "zero_null_cell_f1": (
            2.0 * agg["zero_null_tp"] / (
                2.0 * agg["zero_null_tp"] + agg["zero_null_fp"] + agg["zero_null_fn"]
            )
        ) if (2.0 * agg["zero_null_tp"] + agg["zero_null_fp"] + agg["zero_null_fn"]) else None,
        "zero_null_gold_cell_n": agg["zero_null_tp"] + agg["zero_null_fn"],
        "zero_null_pred_cell_n": agg["zero_null_tp"] + agg["zero_null_fp"],
        "zero_null_eval_cell_n": agg["zero_null_cell_eval_n"],
        "gold_zeroish_n": agg["gold_zeroish_n"],
        "gold_zeroish_pred_zeroish_n": agg["gold_zeroish_pred_zeroish_n"],
        "gold_zeroish_pred_missing_n": agg["gold_zeroish_pred_missing_n"],
        "gold_zeroish_pred_zeroish_rate": (
            agg["gold_zeroish_pred_zeroish_n"] / agg["gold_zeroish_n"]
        ) if agg["gold_zeroish_n"] else None,
        "zeroish_pred_accuracy": (
            (agg["zeroish_sample_tp"] + agg["zeroish_sample_tn"]) / agg["n_total"]
        ) if agg["n_total"] else None,
        "zeroish_pred_precision": (
            agg["zeroish_sample_tp"] / (agg["zeroish_sample_tp"] + agg["zeroish_sample_fp"])
        ) if (agg["zeroish_sample_tp"] + agg["zeroish_sample_fp"]) else None,
        "zeroish_pred_recall": (
            agg["zeroish_sample_tp"] / (agg["zeroish_sample_tp"] + agg["zeroish_sample_fn"])
        ) if (agg["zeroish_sample_tp"] + agg["zeroish_sample_fn"]) else None,
        "zeroish_pred_f1": (
            2.0 * agg["zeroish_sample_tp"] / (
                2.0 * agg["zeroish_sample_tp"] + agg["zeroish_sample_fp"] + agg["zeroish_sample_fn"]
            )
        ) if (2.0 * agg["zeroish_sample_tp"] + agg["zeroish_sample_fp"] + agg["zeroish_sample_fn"]) else None,
        "Overcount%": (
            100.0 * agg["numeric_overcount_n"] / agg["numeric_pair_n"]
        ) if agg["numeric_pair_n"] else None,
        "Undercount%": (
            100.0 * agg["numeric_undercount_n"] / agg["numeric_pair_n"]
        ) if agg["numeric_pair_n"] else None,
        "rmse_avg": (agg["rmse_sum"] / agg["num_eval_n"]) if agg["num_eval_n"] else None,
        "mae_avg": (agg["mae_sum"] / agg["num_eval_n"]) if agg["num_eval_n"] else None,
    }

    metadata = {
        "dataset": dataset_path,
        "parser": parser_name,
        "source_path": source_path,
        "summary": summary,
        "agg": agg,
    }
    return samplewise, summary, metadata


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate experiment logs with baseline-specific parsers.")
    ap.add_argument("--dataset", default=DEFAULTS["dataset"])
    ap.add_argument("--model", default=DEFAULTS["model"])
    ap.add_argument("--baseline", default=DEFAULTS["baseline"])
    ap.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    ap.add_argument("--num-votes", type=int, default=DEFAULTS["num_votes"])
    ap.add_argument("--parser", choices=sorted(PARSERS.keys()), default=DEFAULTS["parser"])
    ap.add_argument("--log-dir", default=DEFAULTS["log_dir"])
    ap.add_argument("--out-predictions", default=DEFAULTS["out_predictions"])
    ap.add_argument("--out-samplewise", default=DEFAULTS["out_samplewise"])
    ap.add_argument("--out-summary", default=DEFAULTS["out_summary"])
    args = ap.parse_args()

    baseline_name = canonicalize_baseline_name(args.baseline)
    derived = derive_default_paths(args.model, baseline_name, args.seed, args.num_votes)
    parser_name = args.parser or infer_parser_from_baseline(baseline_name)
    log_dir = args.log_dir or derived["log_dir"]
    out_predictions = args.out_predictions or derived["out_predictions"]
    out_samplewise = args.out_samplewise or derived["out_samplewise"]
    out_summary = args.out_summary or derived["out_summary"]

    ensure_dir(os.path.dirname(out_predictions))
    ensure_dir(os.path.dirname(out_samplewise))
    ensure_dir(os.path.dirname(out_summary))

    dataset = read_dataset(args.dataset)
    ds_map = build_dataset_map(dataset)

    if os.path.isfile(log_dir) and log_dir.endswith(".jsonl"):
        reconstructed, usage_total = load_predictions_jsonl(log_dir, ds_map)
        source_path = log_dir
        parser_used = "jsonl"
    else:
        parser_fn = PARSERS[parser_name]
        reconstructed, usage_total = parser_fn(log_dir, ds_map)
        source_path = log_dir
        parser_used = parser_name
    samplewise, _, summary_meta = evaluate_reconstructed_predictions(
        reconstructed=reconstructed,
        ds_map=ds_map,
        dataset_path=args.dataset,
        parser_name=parser_used,
        source_path=source_path,
    )
    summary_meta["summary"]["usage_total"] = usage_total
    summary_meta["summary"]["usage_avg_per_successful_sample"] = average_usage_over_successful_samples(reconstructed)
    summary_meta["agg"]["input_tokens"] = usage_total["input_tokens"]
    summary_meta["agg"]["output_tokens"] = usage_total["output_tokens"]
    summary_meta["agg"]["total_tokens"] = usage_total["total_tokens"]
    summary_meta["model"] = args.model
    summary_meta["baseline"] = baseline_name
    summary_meta["seed"] = args.seed
    if baseline_name == "SC_VOTE":
        summary_meta["num_votes"] = args.num_votes

    with open(out_predictions, "w", encoding="utf-8") as f:
        for row in reconstructed:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(out_samplewise, "w", encoding="utf-8") as f:
        for row in samplewise:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(summary_meta, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary_meta["summary"], indent=2))


if __name__ == "__main__":
    main()


# python baseline-scripts/eval_experiment_logs.py \
#   --dataset dataset-cricket/cricket-overall.json \
#   --model "Qwen/Qwen2.5-72B-Instruct" \
#   --baseline SC_VOTE \
#   --seed 0 \
#   --log-dir baseline-results/Qwen/Qwen2.5-72B-Instruct/SC_VOTE/reconstructed_predictions.jsonl


# python baseline-scripts/eval_experiment_logs.py \
#   --dataset dataset-cricket/dataset.split_analysis.json \
#   --model "meta-llama/Llama-3.3-70B-Instruct" \
#   --baseline COT \
#   --seed 0 \
#   --log-dir baseline-results-split-analysis/meta-llama/Llama-3.3-70B-Instruct/COT/reconstructed_predictions.jsonl \
#   --out-predictions baseline-results-split-analysis-eval/meta-llama/Llama-3.3-70B-Instruct/COT/reconstructed_predictions.jsonl \
#   --out-samplewise baseline-results-split-analysis-eval/meta-llama/Llama-3.3-70B-Instruct/COT/eval.samplewise.jsonl \
#   --out-summary baseline-results-split-analysis-eval/meta-llama/Llama-3.3-70B-Instruct/COT/eval.summary.json

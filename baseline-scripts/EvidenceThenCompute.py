import argparse
import importlib.util
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple


BASELINE_NAME = "EVIDENCE_THEN_COMPUTE"


_REACT_SPEC = importlib.util.spec_from_file_location(
    "_react_shared", os.path.join(os.path.dirname(__file__), "ReAct.py")
)
if _REACT_SPEC is None or _REACT_SPEC.loader is None:
    raise ImportError("Could not load shared helpers from ReAct.py")
_react = importlib.util.module_from_spec(_REACT_SPEC)
sys.modules["_react_shared"] = _react
_REACT_SPEC.loader.exec_module(_react)


InferenceConfig = _react.InferenceConfig
InferenceService = _react.InferenceService
read_dataset = _react.read_dataset
ensure_dir = _react.ensure_dir
get_run_log_dir = _react.get_run_log_dir
extract_json_obj = _react.extract_json_obj
derive_row_key_columns = _react.derive_row_key_columns
normalize_primary_key = _react.normalize_primary_key
validate_table = _react.validate_table


DEFAULTS = {
    "dataset": "artifacts/runs/benchmark/dataset.jsonl",
    "n": -1,
    "seed": 0,
    "shuffle": False,
    "provider": "openai",
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "api_key": "",
    "base_url": "http://localhost:8001/v1",
    "temperature": 0,
    "max_tokens": 15000,
    "max_retries": 5,
    "log_dir": None,
    "run_id": None,
    "out": None,
    "summary_out": None,
    "workers": 5,
}

DEFAULTS["log_dir"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/logs"
DEFAULTS["run_id"] = f"{BASELINE_NAME}_run_{DEFAULTS['seed']}"
DEFAULTS["out"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/predictions.jsonl"
DEFAULTS["summary_out"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/summary.json"


CRICKET_POLICIES = """
Cricket policies:
- Runs: credit only off-the-bat (exclude byes/leg-byes). For no-balls, bat runs are credited separately; the +1 nb is NOT bat runs.
- Balls faced: increment for every delivery except wides (no-balls DO count as a ball faced).
- Fours/Sixes: only for off-the-bat boundaries; exclude byes/leg-byes.
- Bowler balls: count only legal deliveries (wides/no-balls do NOT add to balls).
- Bowler runs given: includes all conceded (incl. wides, no-balls, byes/leg-byes).
- Bowler wickets: credit only bowler-attributable dismissals (b, c off bowler, lbw, st off bowler, hit wicket). Do NOT credit run out.
- Overs: floor(balls/6) "." (balls % 6).
""".strip()


EXTRACT_SYSTEM_PROMPT = """
You are an expert cricket analyst and data annotator.

Goal:
- Read ball-by-ball cricket commentary and identify the output rows needed to answer the question.
- For each output row, extract the commentary evidence needed to compute that row later.
- Do NOT compute final answer values in this stage.

Return STRICT JSON only.
Do not include markdown.
Do not include any text outside the JSON object.

You must preserve the exact meaning of the question.
Do not invent rows, evidence, formulas, or values not supported by the commentary.

You MUST identify rows using these row key columns:
{row_key_columns_json}

The final answer table will use these exact columns:
{headers_json}

Primary key:
{primary_key_json}

Output format (STRICT JSON only):
{{
  "rows": [
    {{
      "row_key": {{"<row_key_col_1>": "<value>"}},
      "row_evidence": [
        "compact evidence item 1",
        "compact evidence item 2"
      ]
    }}
  ]
}}

Requirements:
- rows must be a non-empty list.
- Each row item must contain:
  - "row_key": a JSON object
  - "row_evidence": a non-empty list of strings
- row_evidence should contain only evidence relevant to that row.
- Every evidence item must begin with the delivery identifier in the form "over.ball | ...", using the over and ball numbers exactly as they appear in the commentary.
- Do NOT copy full commentary sentences or long quotes from the passage.
- Use compact normalized evidence items of the form:
  "over.ball | relevant entities | event type | relevant attributes"
- Include only the entities and attributes needed to answer the question, such as batsman, bowler, runs, wicket, boundary, extras, or phase when relevant.
- Keep each evidence item concise and factual. Omit narrative detail that is not needed for the downstream calculation.
- Do not compute final row values.
- Do not output final_table in this stage.
- Do not include hypothetical examples or placeholder text.

{cricket_policies}
""".strip()


COMPUTE_SYSTEM_PROMPT = """
You are an expert cricket analyst and data annotator.

Goal:
- Compute the final answer table using only the extracted row evidence provided.
- For each row, derive any needed intermediate statistics and compute the final row values.
- Do not invent evidence beyond what is provided.

Return STRICT JSON only.
Do not include markdown.
Do not include any text outside the JSON object.

You must preserve the exact meaning of the question.
If a value cannot be computed from the provided evidence, use null.

The final answer table must use these exact columns in exact order:
{headers_json}

Row key columns:
{row_key_columns_json}

Primary key:
{primary_key_json}

Output format (STRICT JSON only):
{{
  "rows": [
    {{
      "row_key": {{"<row_key_col_1>": "<value>"}},
      "intermediate_stats": {{
        "stat_1": 0,
        "stat_2": 0
      }},
      "calculation_trace": "free-form explanation of how the row values were computed from the evidence",
      "final_row": [<row_col_1>, <row_col_2>, ...]
    }}
  ],
  "final_table": {{
    "columns": {headers_json},
    "rows": [
      [<row1_col1>, <row1_col2>, ...],
      [<row2_col1>, <row2_col2>, ...]
    ]
  }}
}}

Requirements:
- rows must be a non-empty list.
- Each row item must contain:
  - "row_key": a JSON object
  - "intermediate_stats": a JSON object
  - "calculation_trace": a non-empty string
  - "final_row": a list
- final_table must be present.
- final_table.columns must match exactly and in order.
- Every final_table row must have the same number of cells as columns.
- final_table cells must contain concrete JSON values only.
- For numeric final_table cells, output the computed value directly as a JSON number, not an expression.
- Use null for missing or unsupported values.
- Do not output a different schema.

{cricket_policies}
""".strip()


EXTRACT_USER_PROMPT = """
<question>
{question}
</question>

<target_columns>
{headers_json}
</target_columns>

<row_key_columns>
{row_key_columns_json}
</row_key_columns>

<primary_key>
{primary_key_json}
</primary_key>

<commentary>
{context}
</commentary>
""".strip()


COMPUTE_USER_PROMPT = """
<question>
{question}
</question>

<target_columns>
{headers_json}
</target_columns>

<row_key_columns>
{row_key_columns_json}
</row_key_columns>

<primary_key>
{primary_key_json}
</primary_key>

<extracted_rows>
{rows_with_evidence_json}
</extracted_rows>
""".strip()


def validate_extractor_output(
    obj: Any,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Extractor output is not a JSON object."
    rows = obj.get("rows")
    if not isinstance(rows, list) or not rows:
        return False, None, "Missing or invalid 'rows' list."
    normalized_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, None, f"rows[{idx}] is not an object."
        row_key = row.get("row_key")
        row_evidence = row.get("row_evidence")
        if not isinstance(row_key, dict):
            return False, None, f"rows[{idx}].row_key is invalid."
        if not isinstance(row_evidence, list) or not row_evidence:
            return False, None, f"rows[{idx}].row_evidence is invalid."
        evidence_norm: List[str] = []
        for item in row_evidence:
            if not isinstance(item, str) or not item.strip():
                return False, None, f"rows[{idx}].row_evidence contains invalid items."
            evidence_norm.append(item.strip())
        normalized_rows.append({"row_key": row_key, "row_evidence": evidence_norm})
    return True, {"rows": normalized_rows}, ""


def validate_compute_output(
    obj: Any,
    headers: List[str],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Compute output is not a JSON object."
    rows = obj.get("rows")
    if not isinstance(rows, list) or not rows:
        return False, None, "Missing or invalid 'rows' list."

    normalized_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, None, f"rows[{idx}] is not an object."
        row_key = row.get("row_key")
        intermediate_stats = row.get("intermediate_stats")
        calculation_trace = row.get("calculation_trace")
        final_row = row.get("final_row")
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

    ok_table, table, err_table = validate_table(obj.get("final_table"), headers)
    if not ok_table:
        return False, None, err_table
    if len(normalized_rows) != len(table["rows"]):
        return False, None, "rows count must equal final_table row count."
    return True, {"rows": normalized_rows, "pred_table": table}, ""


def build_extract_system_prompt(headers: List[str], row_key_columns: List[str], primary_key: Optional[List[str]]) -> str:
    return EXTRACT_SYSTEM_PROMPT.format(
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        cricket_policies=CRICKET_POLICIES,
    )


def build_extract_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    primary_key: Optional[List[str]],
    context: str,
) -> str:
    return EXTRACT_USER_PROMPT.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        context=context,
    )


def build_compute_system_prompt(headers: List[str], row_key_columns: List[str], primary_key: Optional[List[str]]) -> str:
    return COMPUTE_SYSTEM_PROMPT.format(
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        cricket_policies=CRICKET_POLICIES,
    )


def build_compute_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    primary_key: Optional[List[str]],
    extractor_output: Dict[str, Any],
) -> str:
    return COMPUTE_USER_PROMPT.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        rows_with_evidence_json=json.dumps(extractor_output.get("rows", []), ensure_ascii=False, indent=2),
    )


def index_run_logs(run_log_dir: Optional[str]) -> Tuple[Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]], Dict[str, int]]:
    grouped: Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return grouped, usage_total

    pattern = re.compile(r"(\d+)_(extract|compute)_a(\d+)\.json$")
    for name in os.listdir(run_log_dir):
        match = pattern.match(name)
        if not match:
            continue
        sample_id, stage, attempt = match.group(1), match.group(2), int(match.group(3))
        path = os.path.join(run_log_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            continue
        usage = log.get("usage") or {}
        for key in usage_total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped.setdefault(sample_id, {}).setdefault(stage, []).append((attempt, path, log))

    for sample_id in grouped:
        for stage in grouped[sample_id]:
            grouped[sample_id][stage].sort(key=lambda x: x[0])
    return grouped, usage_total


def parse_extract_attempts(
    logs: List[Tuple[int, str, Dict[str, Any]]],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], int, Optional[str]]:
    attempts: List[Dict[str, Any]] = []
    extractor_output = None
    last_error: Optional[str] = None
    next_attempt = 0
    for attempt, path, log in logs:
        response_text = log.get("response_text", "")
        usage = log.get("usage") or {}
        attempt_info = {
            "attempt": attempt,
            "path": path,
            "response_text": response_text,
            "usage": usage,
        }
        try:
            parsed = extract_json_obj(response_text)
            ok, payload, err = validate_extractor_output(parsed)
            attempt_info["valid"] = ok
            attempt_info["error"] = err
            if ok:
                extractor_output = payload
                last_error = None
            else:
                last_error = err
        except Exception as exc:
            attempt_info["valid"] = False
            attempt_info["error"] = str(exc)
            last_error = str(exc)
        attempts.append(attempt_info)
        next_attempt = max(next_attempt, attempt + 1)
    return extractor_output, attempts, next_attempt, last_error


def parse_compute_attempts(
    logs: List[Tuple[int, str, Dict[str, Any]]],
    headers: List[str],
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]], List[Dict[str, Any]], int, Optional[str]]:
    compute_rows = None
    pred_table = None
    attempts: List[Dict[str, Any]] = []
    last_error: Optional[str] = None
    next_attempt = 0
    for attempt, path, log in logs:
        response_text = log.get("response_text", "")
        usage = log.get("usage") or {}
        attempt_info = {
            "attempt": attempt,
            "path": path,
            "response_text": response_text,
            "usage": usage,
        }
        try:
            parsed = extract_json_obj(response_text)
            ok, payload, err = validate_compute_output(parsed, headers)
            attempt_info["valid"] = ok
            attempt_info["error"] = err
            if ok:
                compute_rows = payload["rows"]
                pred_table = payload["pred_table"]
                last_error = None
            else:
                last_error = err
        except Exception as exc:
            attempt_info["valid"] = False
            attempt_info["error"] = str(exc)
            last_error = str(exc)
        attempts.append(attempt_info)
        next_attempt = max(next_attempt, attempt + 1)
    return compute_rows, pred_table, attempts, next_attempt, last_error


def load_existing_log_state(
    log_index: Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]],
    dataset_items: List[Dict[str, Any]],
    max_retries: int,
) -> Dict[str, Dict[str, Any]]:
    completed: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(dataset_items):
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        record_id = str(sample_id)
        stage_logs = log_index.get(record_id, {})
        if not stage_logs:
            continue

        headers = (item.get("answer") or {}).get("columns") or []
        row_key_columns, row_key_source = derive_row_key_columns(
            normalize_primary_key(item.get("primary_key")),
            headers,
            item.get("answer_rows"),
        )
        extractor_output, extract_attempts, next_extract_attempt, extract_error = parse_extract_attempts(
            stage_logs.get("extract", [])
        )
        compute_rows, pred_table, compute_attempts, next_compute_attempt, compute_error = parse_compute_attempts(
            stage_logs.get("compute", []),
            headers,
        )

        if pred_table is not None:
            completed[record_id] = {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": item.get("record_id"),
                "question": item.get("question", ""),
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": item.get("answer_rows"),
                "extractor_output": extractor_output,
                "compute_rows": compute_rows,
                "pred_table": pred_table,
                "success": True,
                "error": None,
                "extract_attempts": extract_attempts,
                "compute_attempts": compute_attempts,
            }
            continue

        extract_exhausted = next_extract_attempt > max_retries
        compute_exhausted = extractor_output is not None and next_compute_attempt > max_retries
        if extract_exhausted or compute_exhausted:
            completed[record_id] = {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": item.get("record_id"),
                "question": item.get("question", ""),
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": item.get("answer_rows"),
                "extractor_output": extractor_output,
                "compute_rows": compute_rows,
                "pred_table": None,
                "success": False,
                "error": compute_error if extractor_output is not None else extract_error,
                "extract_attempts": extract_attempts,
                "compute_attempts": compute_attempts,
            }
    return completed


def run() -> None:
    parser = argparse.ArgumentParser(description="Evidence-then-compute baseline runner.")
    parser.add_argument("--dataset", default=DEFAULTS["dataset"])
    parser.add_argument("--n", type=int, default=DEFAULTS["n"])
    parser.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    parser.add_argument("--shuffle", action="store_true", default=DEFAULTS["shuffle"])
    parser.add_argument("--provider", default=DEFAULTS["provider"])
    parser.add_argument("--model", default=DEFAULTS["model"])
    parser.add_argument("--api-key", default=DEFAULTS["api_key"])
    parser.add_argument("--base-url", default=DEFAULTS["base_url"])
    parser.add_argument("--temperature", type=float, default=DEFAULTS["temperature"])
    parser.add_argument("--max-tokens", type=int, default=DEFAULTS["max_tokens"])
    parser.add_argument("--max-retries", type=int, default=DEFAULTS["max_retries"])
    parser.add_argument("--log-dir", default=DEFAULTS["log_dir"])
    parser.add_argument("--run-id", default=DEFAULTS["run_id"])
    parser.add_argument("--out", default=DEFAULTS["out"])
    parser.add_argument("--summary-out", default=DEFAULTS["summary_out"])
    parser.add_argument("--workers", type=int, default=DEFAULTS["workers"])
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.out))
    ensure_dir(os.path.dirname(args.summary_out))

    data = read_dataset(args.dataset)
    data.sort(key=lambda item: int(item.get("sample_id", 10**18)))
    if args.shuffle:
        random.Random(args.seed).shuffle(data)
    if args.n is not None and args.n >= 0:
        data = data[: args.n]

    run_log_dir = get_run_log_dir(args.log_dir, args.run_id)
    log_index, existing_usage = index_run_logs(run_log_dir)
    completed_from_logs = load_existing_log_state(log_index, data, args.max_retries)

    cfg = InferenceConfig(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        log_dir=args.log_dir,
        run_id=args.run_id,
    )
    svc = InferenceService(cfg)

    total_usage = dict(existing_usage)
    results: List[Dict[str, Any]] = list(completed_from_logs.values())
    pending_items: List[Tuple[int, Dict[str, Any]]] = []

    for idx, item in enumerate(data):
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        if str(sample_id) in completed_from_logs:
            continue
        pending_items.append((idx, item))

    def process_one(idx: int, item: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        record_id = str(sample_id)
        original_record_id = item.get("record_id")
        question = item.get("question", "")
        context = (item.get("context_full_with_overs") or item.get("context") or item.get("context_full") or "")
        headers = (item.get("answer") or {}).get("columns") or []
        expected_rows = item.get("answer_rows")
        primary_key = normalize_primary_key(item.get("primary_key"))
        row_key_columns, row_key_source = derive_row_key_columns(primary_key, headers, expected_rows)

        prior_stage_logs = log_index.get(record_id, {})
        extractor_output, extract_attempts, next_extract_attempt, extract_error = parse_extract_attempts(
            prior_stage_logs.get("extract", [])
        )
        compute_rows, pred_table, compute_attempts, next_compute_attempt, compute_error = parse_compute_attempts(
            prior_stage_logs.get("compute", []),
            headers,
        )
        usage_acc = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        if pred_table is not None:
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": expected_rows,
                "extractor_output": extractor_output,
                "compute_rows": compute_rows,
                "pred_table": pred_table,
                "success": True,
                "error": None,
                "extract_attempts": extract_attempts,
                "compute_attempts": compute_attempts,
                "_idx": idx,
            }, usage_acc

        extract_system_prompt = build_extract_system_prompt(headers, row_key_columns, primary_key)
        extract_user_prompt = build_extract_user_prompt(question, headers, row_key_columns, primary_key, context)
        for attempt in range(next_extract_attempt, args.max_retries + 1):
            attempt_id = f"{record_id}_extract_a{attempt}"
            prompt_to_send = extract_user_prompt
            if attempt > next_extract_attempt and extract_error:
                prompt_to_send = (
                    extract_user_prompt
                    + "\n\nPrevious extract output was invalid: "
                    + extract_error
                    + "\nFix it and output ONLY valid JSON with rows, row_key, and row_evidence."
                )
            resp = svc.generate(
                system_prompt=extract_system_prompt,
                user_prompt=prompt_to_send,
                sample_id=attempt_id,
                metadata={
                    "baseline": BASELINE_NAME,
                    "record_id": original_record_id,
                    "sample_id": sample_id,
                    "stage": "extract",
                    "attempt": attempt,
                },
            )
            usage = resp.usage or {}
            for key in usage_acc:
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    usage_acc[key] += int(value)
            attempt_info = {"attempt": attempt, "response_text": resp.text, "usage": usage}
            if resp.error:
                extract_error = resp.error
                attempt_info["valid"] = False
                attempt_info["error"] = resp.error
                extract_attempts.append(attempt_info)
                continue
            try:
                parsed = extract_json_obj(resp.text)
                ok, payload, err = validate_extractor_output(parsed)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    extractor_output = payload
                    extract_error = None
                    extract_attempts.append(attempt_info)
                    break
                extract_error = err
            except Exception as exc:
                extract_error = str(exc)
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
            extract_attempts.append(attempt_info)

        if extractor_output is None:
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": expected_rows,
                "extractor_output": None,
                "compute_rows": None,
                "pred_table": None,
                "success": False,
                "error": extract_error,
                "extract_attempts": extract_attempts,
                "compute_attempts": compute_attempts,
                "_idx": idx,
            }, usage_acc

        compute_system_prompt = build_compute_system_prompt(headers, row_key_columns, primary_key)
        compute_user_prompt = build_compute_user_prompt(question, headers, row_key_columns, primary_key, extractor_output)
        for attempt in range(next_compute_attempt, args.max_retries + 1):
            attempt_id = f"{record_id}_compute_a{attempt}"
            prompt_to_send = compute_user_prompt
            if attempt > next_compute_attempt and compute_error:
                prompt_to_send = (
                    compute_user_prompt
                    + "\n\nPrevious compute output was invalid: "
                    + compute_error
                    + "\nFix it and output ONLY valid JSON with rows, intermediate_stats, calculation_trace, final_row, and final_table."
                )
            resp = svc.generate(
                system_prompt=compute_system_prompt,
                user_prompt=prompt_to_send,
                sample_id=attempt_id,
                metadata={
                    "baseline": BASELINE_NAME,
                    "record_id": original_record_id,
                    "sample_id": sample_id,
                    "stage": "compute",
                    "attempt": attempt,
                },
            )
            usage = resp.usage or {}
            for key in usage_acc:
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    usage_acc[key] += int(value)
            attempt_info = {"attempt": attempt, "response_text": resp.text, "usage": usage}
            if resp.error:
                compute_error = resp.error
                attempt_info["valid"] = False
                attempt_info["error"] = resp.error
                compute_attempts.append(attempt_info)
                continue
            try:
                parsed = extract_json_obj(resp.text)
                ok, payload, err = validate_compute_output(parsed, headers)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    compute_rows = payload["rows"]
                    pred_table = payload["pred_table"]
                    compute_error = None
                    compute_attempts.append(attempt_info)
                    break
                compute_error = err
            except Exception as exc:
                compute_error = str(exc)
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
            compute_attempts.append(attempt_info)

        return {
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "row_key_columns": row_key_columns,
            "row_key_source": row_key_source,
            "expected_rows": expected_rows,
            "extractor_output": extractor_output,
            "compute_rows": compute_rows,
            "pred_table": pred_table,
            "success": pred_table is not None,
            "error": None if pred_table is not None else compute_error,
            "extract_attempts": extract_attempts,
            "compute_attempts": compute_attempts,
            "_idx": idx,
        }, usage_acc

    total = len(data)
    done = len(completed_from_logs)
    if completed_from_logs:
        print(f"Resuming from logs: {done} completed samples found in {run_log_dir}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(process_one, idx, item) for idx, item in pending_items]
        for future in as_completed(futures):
            result, usage_step = future.result()
            results.append(result)
            for key in total_usage:
                total_usage[key] += int(usage_step.get(key, 0))
            done += 1
            print(f"[{done}/{total}] {result['record_id']} success={result['success']}")

    results.sort(key=lambda row: row.get("_idx", 0))
    for row in results:
        row.pop("_idx", None)

    with open(args.out, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "n": len(results),
        "success_n": sum(1 for row in results if row["success"]),
        "failure_n": sum(1 for row in results if not row["success"]),
        "extract_success_n": sum(1 for row in results if row.get("extractor_output") is not None),
        "compute_success_n": sum(1 for row in results if row.get("pred_table") is not None),
        "usage_total": total_usage,
        "dataset": args.dataset,
        "provider": args.provider,
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "max_retries": args.max_retries,
        "output_path": args.out,
        "log_dir": args.log_dir,
    }
    with open(args.summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()

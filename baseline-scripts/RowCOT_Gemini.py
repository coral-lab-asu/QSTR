import argparse
import importlib.util
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple


BASELINE_NAME = "ROW_COT_GEMINI"


_COT_SPEC = importlib.util.spec_from_file_location(
    "_cot_shared", os.path.join(os.path.dirname(__file__), "COT.py")
)
if _COT_SPEC is None or _COT_SPEC.loader is None:
    raise ImportError("Could not load shared helpers from COT.py")
_cot = importlib.util.module_from_spec(_COT_SPEC)
_COT_SPEC.loader.exec_module(_cot)


InferenceConfig = _cot.InferenceConfig
InferenceService = _cot.InferenceService
read_dataset = _cot.read_dataset
ensure_dir = _cot.ensure_dir
get_run_log_dir = _cot.get_run_log_dir
extract_json_obj = _cot.extract_json_obj
derive_row_key_columns = _cot.derive_row_key_columns
normalize_primary_key = _cot.normalize_primary_key
validate_table = _cot.validate_table
sum_usage_from_attempts = _cot.sum_usage_from_attempts


DEFAULTS = {
    "dataset": "dataset-cricket/cricket-overall.json",
    "n": -1,
    "only_universal_ids": True,
    "seed": 0,
    "shuffle": False,
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "api_key": os.getenv("GEMINI_API_KEY", ""),
    "base_url": "",
    "temperature": 0.0,
    "max_tokens": 32000,
    "max_retries": 3 ,
    "log_dir": None,
    "run_id": None,
    "out": None,
    "summary_out": None,
    "workers": 8,
}

DEFAULTS["log_dir"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/logs"
DEFAULTS["run_id"] = f"{BASELINE_NAME}_run_{DEFAULTS['seed']}"
DEFAULTS["out"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/predictions.jsonl"
DEFAULTS["summary_out"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/summary.json"

UNIVERSAL_IDS_PATH = "dataset-cricket/universal_sample_ids.json"


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


def parse_bool_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


SYSTEM_PROMPT_TEMPLATE = """
You are an expert cricket analyst and data annotator.

Goal:
- Read ball-by-ball cricket commentary and answer the question.
- Reason briefly in a row-by-row manner before producing the final answer table.
- Use the commentary as the source of truth.

Return STRICT JSON only.
Do not include markdown.
Do not include any text outside the JSON object.

You must preserve the exact meaning of the question.
Do not invent alternative formulas, scaling factors, definitions, fallback conventions, sentinel values, or hypothetical example values.
If a value is undefined or cannot be supported from the commentary, use null.

If the question implies a metric such as strike rate, economy, ratio, percentage, average, count, total, or frequency, use the definition implied by the question itself and the cricket policies below.
If returning a percentage column, always express it on a 0-100 scale unless the question explicitly says otherwise.

Question:
{question}

You MUST produce a final table with EXACT columns in EXACT order:
{headers_json}

Row key columns:
{row_key_columns_json}

Primary key:
{primary_key_json}

Output format (STRICT JSON only):
{{
  "row_reasoning": [
    {{
      "row_key": {{"<row_key_col_1>": "<value>", "<row_key_col_2>": "<value>"}},
      "trace": "free-form working trace for this row"
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
- row_reasoning must be a non-empty list.
- Each row_reasoning item must contain:
  - "row_key": a JSON object
  - "trace": a non-empty string
- There must be exactly one row_reasoning item for each row in final_table.
- Do not enumerate every delivery.
- Do not restate commentary unless essential.
- Do not explain basic simple arithmetic.
- You can show the working of each row calculation but keep it brief (3-4 sentences).
- final_table must be present.
- final_table.columns must match the required columns exactly and in order.
- Every final_table row must have the same number of cells as columns.
- final_table cells must contain concrete JSON values only.
- For numeric final_table cells, output the computed number directly as a JSON number, not an arithmetic expression or formula string.
- Never put expressions such as "1 / 24", "(1 * 100) / 24", or similar operations inside final_table.
- Use null for missing or undefined values.
- Do not output a different schema.

Cricket policies:
{cricket_policies}
""".strip()


USER_PROMPT_TEMPLATE = """
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


def validate_row_reasoning(obj: Any) -> Tuple[bool, Optional[List[Dict[str, Any]]], str]:
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


def validate_row_cot_response(
    obj: Any,
    expected_cols: List[str],
    expected_rows: Optional[int],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Output is not a JSON object."

    ok_reasoning, row_reasoning, err_reasoning = validate_row_reasoning(obj.get("row_reasoning"))
    if not ok_reasoning:
        return False, None, err_reasoning

    ok_table, table, err_table = validate_table(obj.get("final_table"), expected_cols, expected_rows)
    if not ok_table:
        return False, None, err_table

    if len(row_reasoning) != len(table["rows"]):
        return False, None, "row_reasoning count must equal final_table row count."

    return True, {"row_reasoning": row_reasoning, "pred_table": table}, ""


def build_system_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    primary_key: Optional[List[str]],
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        cricket_policies=CRICKET_POLICIES,
    )


def build_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    primary_key: Optional[List[str]],
    context: str,
) -> str:
    return USER_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        context=context,
    )


def is_json_failure_error(error: Optional[str]) -> bool:
    if not error:
        return False
    err = error.lower()
    patterns = (
        "json",
        "parse",
        "no json object found",
        "could not parse json object",
        "output is not a json object",
        "missing or invalid 'row_reasoning' list",
        "row_reasoning item",
        "row_reasoning count must equal final_table row count",
        "missing or invalid 'columns' list",
        "missing or invalid 'rows' list",
        "row is not a list",
    )
    return any(pattern in err for pattern in patterns)


def get_sample_id(item: Dict[str, Any], fallback_idx: int) -> int:
    sample_id = item.get("sample_id")
    if sample_id is None:
        sample_id = fallback_idx
    return int(sample_id)


def load_universal_sample_ids() -> set[int]:
    with open(UNIVERSAL_IDS_PATH, "r", encoding="utf-8") as f:
        obj = json.load(f)
    sample_ids = obj.get("sample_ids", [])
    return {int(x) for x in sample_ids}


def load_existing_log_state(
    run_log_dir: Optional[str],
    dataset_items: List[Dict[str, Any]],
    max_retries: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    completed: Dict[str, Dict[str, Any]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return completed, usage_total

    ds_by_sample: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(dataset_items):
        sample_id = get_sample_id(item, idx)
        ds_by_sample[str(sample_id)] = item

    grouped: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    for name in os.listdir(run_log_dir):
        match = re.match(r"(\d+)_a(\d+)\.json$", name)
        if not match:
            continue
        sample_id, attempt = match.group(1), int(match.group(2))
        path = os.path.join(run_log_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            continue
        metadata = log.get("metadata") or {}
        if metadata.get("baseline") != BASELINE_NAME:
            continue
        usage = log.get("usage") or {}
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                usage_total[key] += int(value)
        grouped.setdefault(sample_id, []).append((attempt, log))

    for sample_id, logs in grouped.items():
        item = ds_by_sample.get(sample_id)
        if item is None:
            continue
        logs.sort(key=lambda x: x[0])
        ans = item.get("answer") or {}
        headers = ans.get("columns") or []
        expected_rows = item.get("answer_rows")
        attempts_meta: List[Dict[str, Any]] = []
        best_table = None
        best_row_reasoning = None
        error_msg = ""

        for attempt, log in logs:
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            attempt_info = {
                "attempt": attempt,
                "response_text": response_text,
                "usage": usage,
            }
            try:
                obj = extract_json_obj(response_text)
                ok, payload, err = validate_row_cot_response(obj, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    best_table = payload["pred_table"]
                    best_row_reasoning = payload["row_reasoning"]
                    error_msg = ""
                else:
                    error_msg = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                error_msg = str(exc)
            attempts_meta.append(attempt_info)

        exhausted = len(logs) >= (max_retries + 1)
        if best_table is not None or exhausted:
            completed[sample_id] = {
                "record_id": sample_id,
                "sample_id": int(sample_id),
                "original_record_id": item.get("record_id"),
                "question": item.get("question", ""),
                "headers": headers,
                "expected_rows": expected_rows,
                "pred_table": best_table,
                "row_reasoning": best_row_reasoning,
                "success": best_table is not None,
                "error": None if best_table is not None else error_msg,
                "attempts": attempts_meta,
            }

    return completed, usage_total


def run() -> None:
    parser = argparse.ArgumentParser(description="Single-prompt row-wise visible CoT baseline runner.")
    parser.add_argument("--dataset", default=DEFAULTS["dataset"])
    parser.add_argument("--n", type=int, default=DEFAULTS["n"])
    parser.add_argument("--only-universal-ids", type=parse_bool_flag, default=DEFAULTS["only_universal_ids"])
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
    parser.add_argument("--workers", type=int, default=DEFAULTS["workers"], help="Number of worker threads")
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.out))
    ensure_dir(os.path.dirname(args.summary_out))

    data = read_dataset(args.dataset)
    if args.only_universal_ids:
        allowed_ids = load_universal_sample_ids()
        data = [
            item
            for idx, item in enumerate(data)
            if get_sample_id(item, idx) in allowed_ids
        ]
    data.sort(key=lambda item: int(item.get("sample_id", 10**18)))
    if args.shuffle:
        random.Random(args.seed).shuffle(data)
    if args.n is not None and args.n >= 0:
        data = data[: args.n]

    run_log_dir = get_run_log_dir(args.log_dir, args.run_id)
    completed_from_logs, existing_usage = load_existing_log_state(run_log_dir, data, args.max_retries)

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
        sample_id = get_sample_id(item, idx)
        if str(sample_id) in completed_from_logs:
            continue
        pending_items.append((idx, item))

    def process_one(idx: int, item: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
        sample_id = get_sample_id(item, idx)
        record_id = str(sample_id)
        original_record_id = item.get("record_id")
        question = item.get("question", "")
        context = item.get("context_full_with_overs", item.get("context", ""))
        ans = item.get("answer") or {}
        headers = ans.get("columns") or []
        expected_rows = item.get("answer_rows")
        primary_key = normalize_primary_key(item.get("primary_key"))
        row_key_columns, row_key_source = derive_row_key_columns(primary_key, headers, expected_rows)

        system_prompt = build_system_prompt(question, headers, row_key_columns, primary_key)
        user_prompt = build_user_prompt(question, headers, row_key_columns, primary_key, context)

        attempts: List[Dict[str, Any]] = []
        success = False
        pred_table = None
        row_reasoning = None
        error_msg = ""
        usage_acc = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        start_attempt = 0

        if run_log_dir and os.path.isdir(run_log_dir):
            prior_attempts: List[Tuple[int, Dict[str, Any]]] = []
            for name in os.listdir(run_log_dir):
                match = re.match(rf"{re.escape(record_id)}_a(\d+)\.json$", name)
                if not match:
                    continue
                attempt_num = int(match.group(1))
                path = os.path.join(run_log_dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        log = json.load(f)
                except Exception:
                    continue
                metadata = log.get("metadata") or {}
                if metadata.get("baseline") != BASELINE_NAME:
                    continue
                prior_attempts.append((attempt_num, log))
            prior_attempts.sort(key=lambda x: x[0])
            if prior_attempts:
                start_attempt = prior_attempts[-1][0] + 1
                for attempt_num, log in prior_attempts:
                    usage = log.get("usage") or {}
                    attempts.append(
                        {
                            "attempt": attempt_num,
                            "response_text": log.get("response_text", ""),
                            "usage": usage,
                        }
                    )
                    try:
                        obj = extract_json_obj(log.get("response_text", ""))
                        ok, payload, err = validate_row_cot_response(obj, headers, expected_rows)
                        attempts[-1]["valid"] = ok
                        attempts[-1]["error"] = err
                        if ok:
                            success = True
                            pred_table = payload["pred_table"]
                            row_reasoning = payload["row_reasoning"]
                            error_msg = ""
                        else:
                            error_msg = err
                    except Exception as exc:
                        attempts[-1]["valid"] = False
                        attempts[-1]["error"] = str(exc)
                        error_msg = str(exc)
                if success or start_attempt > args.max_retries:
                    result = {
                        "record_id": record_id,
                        "sample_id": sample_id,
                        "original_record_id": original_record_id,
                        "question": question,
                        "headers": headers,
                        "expected_rows": expected_rows,
                        "row_key_columns": row_key_columns,
                        "row_key_source": row_key_source,
                        "pred_table": pred_table,
                        "row_reasoning": row_reasoning,
                        "success": success,
                        "error": error_msg,
                        "attempts": attempts,
                        "_idx": idx,
                    }
                    return result, usage_acc

        for attempt in range(start_attempt, args.max_retries + 1):
            attempt_id = f"{record_id}_a{attempt}"
            prompt_to_send = user_prompt
            if attempt > 0 and error_msg:
                prompt_to_send = (
                    user_prompt
                    + "\n\nPrevious output was invalid: "
                    + error_msg
                    + "\nFix it and output ONLY valid JSON with row_reasoning and final_table."
                )

            resp = svc.generate(
                system_prompt=system_prompt,
                user_prompt=prompt_to_send,
                sample_id=attempt_id,
                metadata={
                    "baseline": BASELINE_NAME,
                    "record_id": original_record_id,
                    "sample_id": sample_id,
                    "attempt": attempt,
                },
            )

            usage = resp.usage or {}
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    usage_acc[key] += int(value)

            attempts.append(
                {
                    "attempt": attempt,
                    "response_text": resp.text,
                    "usage": usage,
                }
            )
            if resp.error:
                attempts[-1]["error"] = resp.error
                error_msg = resp.error
                continue

            try:
                obj = extract_json_obj(resp.text)
                ok, payload, err = validate_row_cot_response(obj, headers, expected_rows)
                attempts[-1]["valid"] = ok
                attempts[-1]["error"] = err
                if ok:
                    success = True
                    pred_table = payload["pred_table"]
                    row_reasoning = payload["row_reasoning"]
                    error_msg = ""
                    break
                error_msg = err
            except Exception as exc:
                attempts[-1]["valid"] = False
                attempts[-1]["error"] = str(exc)
                error_msg = str(exc)

        result = {
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
            "row_key_columns": row_key_columns,
            "row_key_source": row_key_source,
            "pred_table": pred_table,
            "row_reasoning": row_reasoning,
            "success": success,
            "error": error_msg,
            "attempts": attempts,
            "_idx": idx,
        }
        return result, usage_acc

    total = len(data)
    done = 0
    if completed_from_logs:
        done = len(completed_from_logs)
        print(f"Resuming from logs: {done} completed samples found in {run_log_dir}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(process_one, idx, item) for idx, item in pending_items]
        for fut in as_completed(futures):
            res, usage_acc = fut.result()
            results.append(res)
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                total_usage[key] += int(usage_acc.get(key, 0))
            done += 1
            status = "success" if res["success"] else "failure"
            print(
                f"[{done}/{total}] idx={res['_idx']} sample_id={res['sample_id']} "
                f"record_id={res['record_id']} status={status}"
            )

    results.sort(key=lambda r: r.get("_idx", 0))
    for row in results:
        row.pop("_idx", None)

    with open(args.out, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    success_results = [row for row in results if row["success"]]
    success_usage_totals = [sum_usage_from_attempts(row.get("attempts", [])) for row in success_results]
    success_n = len(success_results)

    if success_n:
        avg_success_usage = {
            "input_tokens": sum(x["input_tokens"] for x in success_usage_totals) / success_n,
            "output_tokens": sum(x["output_tokens"] for x in success_usage_totals) / success_n,
            "total_tokens": sum(x["total_tokens"] for x in success_usage_totals) / success_n,
        }
    else:
        avg_success_usage = {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    exhausted_failures = [row for row in results if not row["success"]]
    json_failures = [row for row in exhausted_failures if is_json_failure_error(row.get("error"))]

    summary = {
        "n": len(results),
        "success_n": success_n,
        "failure_n": sum(1 for row in results if not row["success"]),
        "usage_total": total_usage,
        "usage_avg_per_successful_sample": avg_success_usage,
        "max_attempts_any_sample": max((len(row.get("attempts", [])) for row in results), default=0),
        "max_retries_used_any_sample": max((len(row.get("attempts", [])) - 1 for row in results), default=0),
        "max_retries_used_failed_sample": max((len(row.get("attempts", [])) - 1 for row in exhausted_failures), default=0),
        "max_retries_used_json_failure": max((len(row.get("attempts", [])) - 1 for row in json_failures), default=0),
        "json_failure_n": len(json_failures),
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

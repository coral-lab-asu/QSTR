import argparse
import importlib.util
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple


BASELINE_NAME = "ROW_COT_MODULAR"


def _load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), filename))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load shared helpers from {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_cot = _load_module("COT.py", "_cot_shared_modular")
_react = _load_module("ReAct.py", "_react_shared_modular")


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

index_react_logs = _react.index_run_logs
parse_planner_attempts = _react.parse_planner_attempts


DEFAULTS = {
    "dataset": "artifacts/runs/benchmark/dataset.jsonl",
    "n": -1,
    "only_universal_ids": False,
    "seed": 0,
    "shuffle": False,
    "provider": "openai",
    "model": "meta-llama/Llama-3.3-70B-Instruct",
    "api_key": "EMPTY",
    "base_url": "http://localhost:8002/v1",
    "temperature": 0.0,
    "max_tokens": 15000,
    "max_retries": 7,
    "log_dir": None,
    "run_id": None,
    "out": None,
    "summary_out": None,
    "workers": 8,
    "planner_log_dir": "baseline-results/meta-llama/Llama-3.3-70B-Instruct/REACT/logs",
    "planner_run_id": "REACT_run_0",
}

DEFAULTS["log_dir"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/logs"
DEFAULTS["run_id"] = f"{BASELINE_NAME}_run_{DEFAULTS['seed']}"
DEFAULTS["out"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/predictions.jsonl"
DEFAULTS["summary_out"] = f"baseline-results/{DEFAULTS['model']}/{BASELINE_NAME}/summary.json"
DEFAULTS["planner_log_dir"] = f"baseline-results/{DEFAULTS['model']}/REACT/logs"
DEFAULTS["planner_run_id"] = f"REACT_run_{DEFAULTS['seed']}"

UNIVERSAL_IDS_PATH = os.getenv("QSTR_SAMPLE_IDS", "dataset-cricket/universal_sample_ids.json")


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


ROW_SYSTEM_PROMPT_TEMPLATE = """
You are an expert cricket analyst filling one output row of a structured answer table from ball-by-ball commentary.

Goal:
- Read ball-by-ball cricket commentary and answer the question for exactly one requested row.
- Use the supplied row header and plan as guidance.
- Fill exactly one row of the final table.

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

You MUST produce exactly one row with these final columns in exact order:
{headers_json}

Row key columns:
{row_key_columns_json}

Target row header:
{target_row_header_json}

Plan:
{plan_text}

One-row table skeleton:
{row_skeleton_json}

Output format (STRICT JSON only):
{{
  "reasoning_trace": "brief explanation of how this row was computed",
  "final_table": {{
    "columns": {headers_json},
    "rows": [
      [<col1>, <col2>, ...]
    ]
  }}
}}

Requirements:
- reasoning_trace must be a non-empty string.
- Keep reasoning_trace brief.
- Do not enumerate every delivery.
- Do not restate commentary unless essential.
- Do not explain basic simple arithmetic.
- final_table must be present.
- final_table.columns must match the required columns exactly and in order.
- final_table.rows must contain exactly one row.
- The single output row must preserve the requested row-header values in the row-key columns.
- final_table cells must contain concrete JSON values only.
- For numeric final_table cells, output the computed number directly as a JSON number, not an arithmetic expression or formula string.
- Use null for missing or undefined values.
- Do not output a different schema.

Cricket policies:
{cricket_policies}
""".strip()


ROW_USER_PROMPT_TEMPLATE = """
Question:
{question}

Final table columns:
{headers_json}

Row-key columns:
{row_key_columns_json}

Target row header:
{target_row_header_json}

Plan:
{plan_text}

One-row table skeleton:
{row_skeleton_json}

Ball-by-ball commentary:
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>
""".strip()


def validate_row_fill_response(
    obj: Any,
    expected_cols: List[str],
    row_key_columns: List[str],
    target_row_header: Dict[str, Any],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Output is not a JSON object."

    reasoning_trace = obj.get("reasoning_trace")
    if not isinstance(reasoning_trace, str) or not reasoning_trace.strip():
        return False, None, "Missing or invalid 'reasoning_trace'."

    ok_table, table, err_table = validate_table(obj.get("final_table"), expected_cols, expected_rows=1)
    if not ok_table:
        return False, None, err_table

    if len(table["rows"]) != 1:
        return False, None, "final_table must contain exactly one row."

    row_values = table["rows"][0]

    for key_col in row_key_columns:
        if key_col in expected_cols:
            idx = expected_cols.index(key_col)
            expected_value = target_row_header.get(key_col)
            actual_value = row_values[idx]
            if actual_value != expected_value:
                return False, None, f"final_table key cell for '{key_col}' does not match the requested row header."

    return True, {
        "row_key": target_row_header,
        "reasoning_trace": reasoning_trace.strip(),
        "pred_table": table,
    }, ""


def build_row_system_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    target_row_header: Dict[str, Any],
    plan_text: str,
    row_skeleton: Dict[str, Any],
) -> str:
    return ROW_SYSTEM_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        target_row_header_json=json.dumps(target_row_header, ensure_ascii=False),
        plan_text=plan_text,
        row_skeleton_json=json.dumps(row_skeleton, ensure_ascii=False),
        cricket_policies=CRICKET_POLICIES,
    )


def build_row_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    target_row_header: Dict[str, Any],
    plan_text: str,
    row_skeleton: Dict[str, Any],
    context: str,
) -> str:
    return ROW_USER_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        target_row_header_json=json.dumps(target_row_header, ensure_ascii=False),
        plan_text=plan_text,
        row_skeleton_json=json.dumps(row_skeleton, ensure_ascii=False),
        context=context,
    )


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


def parse_bool_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


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
        "missing or invalid 'reasoning_trace'",
        "final_table must contain exactly one row",
    )
    return any(pattern in err for pattern in patterns)


def build_row_skeleton(
    headers: List[str],
    row_key_columns: List[str],
    target_row_header: Dict[str, Any],
) -> Dict[str, Any]:
    row = []
    for col in headers:
        if col in row_key_columns:
            row.append(target_row_header.get(col))
        else:
            row.append(None)
    return {"columns": headers, "rows": [row]}


def load_existing_row_logs(
    run_log_dir: Optional[str],
    sample_id: str,
    row_count: int,
    max_retries: int,
    expected_cols: List[str],
    row_key_columns: List[str],
    row_headers: List[Dict[str, Any]],
) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, List[Dict[str, Any]]], Dict[str, int], Optional[str], bool]:
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return {}, {}, usage_total, None, False

    grouped: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
    pattern = re.compile(rf"^{re.escape(sample_id)}_row(\d+)_a(\d+)\.json$")
    for name in os.listdir(run_log_dir):
        match = pattern.match(name)
        if not match:
            continue
        row_idx, attempt = int(match.group(1)), int(match.group(2))
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
        grouped.setdefault(row_idx, []).append((attempt, log))

    completed_rows: Dict[int, Dict[str, Any]] = {}
    attempts_by_row: Dict[int, List[Dict[str, Any]]] = {}
    last_error: Optional[str] = None
    exhausted_failure = False

    for row_idx in range(row_count):
        logs = sorted(grouped.get(row_idx, []), key=lambda x: x[0])
        attempts_meta: List[Dict[str, Any]] = []
        best_row = None
        row_error: Optional[str] = None
        for attempt, log in logs:
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            attempt_info = {
                "attempt": attempt,
                "response_text": response_text,
                "usage": usage,
            }
            try:
                parsed = extract_json_obj(response_text)
                ok, payload, err = validate_row_fill_response(
                    parsed,
                    expected_cols,
                    row_key_columns,
                    row_headers[row_idx],
                )
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    best_row = payload
                    row_error = None
                else:
                    row_error = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                row_error = str(exc)
            attempts_meta.append(attempt_info)
        attempts_by_row[row_idx] = attempts_meta
        if best_row is not None:
            completed_rows[row_idx] = best_row
        elif logs and len(logs) >= (max_retries + 1):
            exhausted_failure = True
            last_error = row_error
        elif row_error:
            last_error = row_error

    return completed_rows, attempts_by_row, usage_total, last_error, exhausted_failure


def run() -> None:
    parser = argparse.ArgumentParser(description="Modular row-wise baseline that reuses saved ReAct planner outputs.")
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
    parser.add_argument("--workers", type=int, default=DEFAULTS["workers"])
    parser.add_argument("--planner-log-dir", default=DEFAULTS["planner_log_dir"])
    parser.add_argument("--planner-run-id", default=DEFAULTS["planner_run_id"])
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

    planner_log_dir = get_run_log_dir(args.planner_log_dir, args.planner_run_id)
    planner_log_index, _ = index_react_logs(planner_log_dir)

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
    run_log_dir = get_run_log_dir(args.log_dir, args.run_id)

    results: List[Dict[str, Any]] = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def process_one(idx: int, item: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
        sample_id = get_sample_id(item, idx)
        record_id = str(sample_id)
        original_record_id = item.get("record_id")
        question = item.get("question", "")
        context = (item.get("context_full_with_overs") or item.get("context") or item.get("context_full") or "")
        ans = item.get("answer") or {}
        headers = ans.get("columns") or []
        expected_rows = item.get("answer_rows")
        primary_key = normalize_primary_key(item.get("primary_key"))
        row_key_columns, row_key_source = derive_row_key_columns(primary_key, headers, expected_rows)

        planner_output, plan_attempts, _, plan_error = parse_planner_attempts(
            planner_log_index.get(record_id, {}).get("plan", []),
            row_key_columns,
        )
        if planner_output is None:
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "expected_rows": expected_rows,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "planner_output": None,
                "row_reasoning": None,
                "pred_table": None,
                "success": False,
                "error": f"Missing reusable planner output: {plan_error or 'no valid ReAct planner log found.'}",
                "plan_attempts": plan_attempts,
                "row_attempts": {},
                "_idx": idx,
            }, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        row_headers = planner_output["row_headers"]
        existing_rows, row_attempts, usage_acc, existing_error, exhausted_failure = load_existing_row_logs(
            run_log_dir,
            record_id,
            len(row_headers),
            args.max_retries,
            headers,
            row_key_columns,
            row_headers,
        )

        if exhausted_failure:
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "expected_rows": expected_rows,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "planner_output": planner_output,
                "row_reasoning": None,
                "pred_table": None,
                "success": False,
                "error": existing_error,
                "plan_attempts": plan_attempts,
                "row_attempts": row_attempts,
                "_idx": idx,
            }, usage_acc

        row_results = dict(existing_rows)
        for row_idx, row_header in enumerate(row_headers):
            if row_idx in row_results:
                continue

            row_skeleton = build_row_skeleton(headers, row_key_columns, row_header)
            plan_text = planner_output.get("plan", "")
            system_prompt = build_row_system_prompt(question, headers, row_key_columns, row_header, plan_text, row_skeleton)
            user_prompt = build_row_user_prompt(question, headers, row_key_columns, row_header, plan_text, row_skeleton, context)
            prior_attempts = row_attempts.get(row_idx, [])
            start_attempt = len(prior_attempts)
            row_error = existing_error or ""

            for attempt in range(start_attempt, args.max_retries + 1):
                prompt_to_send = user_prompt
                if attempt > 0 and row_error:
                    prompt_to_send = (
                        user_prompt
                        + "\n\nPrevious output was invalid: "
                        + row_error
                        + "\nFix it and output ONLY valid JSON with reasoning_trace and final_table containing exactly one row."
                    )

                resp = svc.generate(
                    system_prompt=system_prompt,
                    user_prompt=prompt_to_send,
                    sample_id=f"{record_id}_row{row_idx}_a{attempt}",
                    metadata={
                        "baseline": BASELINE_NAME,
                        "record_id": original_record_id,
                        "sample_id": sample_id,
                        "row_idx": row_idx,
                        "attempt": attempt,
                    },
                )

                usage = resp.usage or {}
                for key in usage_acc:
                    value = usage.get(key)
                    if isinstance(value, (int, float)):
                        usage_acc[key] += int(value)

                attempt_info = {
                    "attempt": attempt,
                    "response_text": resp.text,
                    "usage": usage,
                }

                if resp.error:
                    attempt_info["valid"] = False
                    attempt_info["error"] = resp.error
                    row_attempts.setdefault(row_idx, []).append(attempt_info)
                    row_error = resp.error
                    continue

                try:
                    parsed = extract_json_obj(resp.text)
                    ok, payload, err = validate_row_fill_response(parsed, headers, row_key_columns, row_header)
                    attempt_info["valid"] = ok
                    attempt_info["error"] = err
                    row_attempts.setdefault(row_idx, []).append(attempt_info)
                    if ok:
                        row_results[row_idx] = payload
                        row_error = ""
                        break
                    row_error = err
                except Exception as exc:
                    attempt_info["valid"] = False
                    attempt_info["error"] = str(exc)
                    row_attempts.setdefault(row_idx, []).append(attempt_info)
                    row_error = str(exc)

            if row_idx not in row_results:
                return {
                    "record_id": record_id,
                    "sample_id": sample_id,
                    "original_record_id": original_record_id,
                    "question": question,
                    "headers": headers,
                    "expected_rows": expected_rows,
                    "row_key_columns": row_key_columns,
                    "row_key_source": row_key_source,
                    "planner_output": planner_output,
                    "row_reasoning": None,
                    "pred_table": None,
                    "success": False,
                    "error": row_error or "Failed to produce a valid row output.",
                    "plan_attempts": plan_attempts,
                    "row_attempts": row_attempts,
                    "_idx": idx,
                }, usage_acc

        row_reasoning = [
            {"row_key": row_results[row_idx]["row_key"], "trace": row_results[row_idx]["reasoning_trace"]}
            for row_idx in range(len(row_headers))
        ]
        rows = [row_results[row_idx]["pred_table"]["rows"][0] for row_idx in range(len(row_headers))]
        pred_table = {"columns": headers, "rows": rows}
        ok, table, err = validate_table(pred_table, headers, expected_rows)
        if not ok:
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "expected_rows": expected_rows,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "planner_output": planner_output,
                "row_reasoning": row_reasoning,
                "pred_table": None,
                "success": False,
                "error": err,
                "plan_attempts": plan_attempts,
                "row_attempts": row_attempts,
                "_idx": idx,
            }, usage_acc

        return {
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
            "row_key_columns": row_key_columns,
            "row_key_source": row_key_source,
            "planner_output": planner_output,
            "row_reasoning": row_reasoning,
            "pred_table": table,
            "success": True,
            "error": None,
            "plan_attempts": plan_attempts,
            "row_attempts": row_attempts,
            "_idx": idx,
        }, usage_acc

    total = len(data)
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(process_one, idx, item) for idx, item in enumerate(data)]
        for fut in as_completed(futures):
            res, usage_acc = fut.result()
            results.append(res)
            for key in total_usage:
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
    success_usage_totals = []
    for row in success_results:
        merged_attempts: List[Dict[str, Any]] = list(row.get("plan_attempts", []))
        for attempts in (row.get("row_attempts") or {}).values():
            merged_attempts.extend(attempts)
        success_usage_totals.append(sum_usage_from_attempts(merged_attempts))
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
        "baseline": BASELINE_NAME,
        "dataset": args.dataset,
        "model": args.model,
        "provider": args.provider,
        "planner_log_dir": planner_log_dir,
        "n": len(results),
        "success_n": success_n,
        "failure_n": len(results) - success_n,
        "planner_success_n": sum(1 for row in results if row.get("planner_output") is not None),
        "json_failure_n": len(json_failures),
        "usage_total": total_usage,
        "usage_avg_success": avg_success_usage,
    }

    with open(args.summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()

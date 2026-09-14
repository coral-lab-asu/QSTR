import argparse
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.inference import InferenceConfig, InferenceService  # noqa: E402

DEFAULTS = {
    "dataset": "dataset-cricket/cricket-overall.json",
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

DEFAULTS["log_dir"] = f"baseline-results/{DEFAULTS['model']}/REACT/logs"
DEFAULTS["run_id"] = f"REACT_run_{DEFAULTS['seed']}"
DEFAULTS["out"] = f"baseline-results/{DEFAULTS['model']}/REACT/predictions.jsonl"
DEFAULTS["summary_out"] = f"baseline-results/{DEFAULTS['model']}/REACT/summary.json"

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

PLANNER_SYSTEM_PROMPT = """
You are an expert cricket analyst planning a table extraction task from ball-by-ball commentary.

Your job in this step is NOT to compute the final table values.
Your job is to output:
1. the row headers that the final table should contain
2. a concise operational plan explaining how the final table should be computed from the commentary

You must output STRICT JSON only.

Definitions:
- "row headers" means the identifying values for each row, using the provided row-key columns only.
- "plan" means a concise text explanation of how to compute the final table, including:
  - what entities or row groups to track
  - what filters to apply
  - what intermediate quantities to count or aggregate
  - what parts of the commentary to inspect
  - any global context needed such as max over, ordered deliveries, cumulative conditions, streak logic, phase boundaries, or pairwise interactions

Rules:
- Do not compute final numeric cell values unless absolutely necessary to identify whether a row should exist.
- Do not include example values, sample calculations, speculative statistics, or instantiated formulas.
- Do not invent rows that are unsupported by the commentary.
- Use the provided row-key columns only when constructing row_headers.
- row_headers must reflect all row inclusion, grouping, and ranking constraints from the question.
- If there is only one output row and no natural row-key columns, use a single empty object: {}.
- The plan should be short and operational, not verbose.
- The plan may mention cricket-specific counting rules when relevant.
- No markdown. No explanations outside the JSON.

{cricket_policies}

Output schema:
{
  "row_headers": [
    {"<row_key_col_1>": "<value>", "<row_key_col_2>": "<value>"},
    ...
  ],
  "plan": "<concise operational plan>"
}
""".strip()

PLANNER_USER_PROMPT_TEMPLATE = """
Question:
{question}

Final table columns:
{headers_json}

Row-key columns:
{row_key_columns_json}

Dataset primary key metadata:
{primary_key_json}

Ball-by-ball commentary:
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>
""".strip()

FILL_SYSTEM_PROMPT = """
You are an expert cricket analyst filling a final structured table from ball-by-ball commentary.

You are given:
1. the original question
2. the final target columns
3. the row-key columns
4. the row headers identified in a previous planning step
5. a detailed reasoning plan from the previous step
6. an empty table skeleton
7. the full commentary

Your task is to fill the final table.

Output STRICT JSON only using this schema:
{
  "reasoning_trace": "<free-form working trace for this instance>",
  "final_table": {
    "columns": ["<exact col 1>", "<exact col 2>", "..."],
    "rows": [
      [<row1col1>, <row1col2>, ...],
      [<row2col1>, <row2col2>, ...]
    ]
  }
}

Rules:
- Columns must match exactly and in the same order.
- Preserve the provided row structure unless the plan and commentary clearly require a correction.
- Use the commentary as the source of truth.
- Use the plan as guidance for what to compute and where to look.
- Fill all non-key cells using the commentary and the plan.
- reasoning_trace must describe the actual computation for this instance, including relevant entities, filters, intermediate counts, and derived values when useful.
- Do not output generic instructions, hypothetical examples, or placeholder numbers.
- final_table cells must contain concrete JSON values only.
- For numeric final_table cells, output the computed number directly as a JSON number, not an arithmetic expression or formula string.
- If returning percentages, use a 0-100 scale unless the question clearly asks for a ratio, fraction, or per-ball frequency.
- Use null when a value truly cannot be determined from the commentary.
- No markdown. No explanations outside the JSON.

{cricket_policies}
""".strip()

FILL_USER_PROMPT_TEMPLATE = """
Question:
{question}

Final table columns:
{headers_json}

Row-key columns:
{row_key_columns_json}

Planner output:
{planner_json}

Empty table skeleton:
{empty_table_json}

Ball-by-ball commentary:
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>
""".strip()


def read_dataset(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".jsonl"):
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
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


def get_run_log_dir(log_dir: str, run_id: Optional[str]) -> Optional[str]:
    if not log_dir:
        return None
    if run_id:
        return os.path.join(log_dir, run_id)
    return log_dir


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


def sum_usage_from_attempts(attempts: List[Dict[str, Any]]) -> Dict[str, int]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for attempt in attempts or []:
        usage = attempt.get("usage") or {}
        for key in total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                total[key] += int(value)
    return total


def is_metric_header(header: str) -> bool:
    h = (header or "").strip().lower()
    if not h:
        return False
    metric_markers = (
        "strike_rate",
        "economy",
        "percentage",
        "ratio",
        "avg_",
        "average",
        "frequency",
        "conversion",
        "cumulative",
        "longest",
        "shortest",
        "maximum",
        "minimum",
        "count",
    )
    if any(marker in h for marker in metric_markers):
        return True
    if h.startswith(("total_", "max_", "min_", "num_", "count_")):
        return True
    if h.endswith(("_rate", "_percentage", "_ratio", "_count", "_frequency")):
        return True
    if h in {
        "runs",
        "balls",
        "wickets",
        "dot_balls",
        "boundaries",
        "fours",
        "sixes",
    }:
        return True
    return False


def derive_row_key_columns(
    primary_key: Optional[List[str]],
    headers: List[str],
    expected_rows: Optional[int],
) -> Tuple[List[str], str]:
    heuristic_prefix: List[str] = []
    for header in headers:
        if heuristic_prefix and is_metric_header(header):
            break
        if not heuristic_prefix and is_metric_header(header):
            break
        heuristic_prefix.append(header)

    filtered_pk = []
    for col in primary_key or []:
        if col in headers and not is_metric_header(col):
            filtered_pk.append(col)

    if heuristic_prefix and filtered_pk:
        refined = [col for col in heuristic_prefix if col in filtered_pk]
        if refined:
            return refined, "metadata_refined_by_header_prefix"

    if heuristic_prefix:
        if expected_rows == 1 and len(heuristic_prefix) == len(headers):
            return [], "single_row_no_obvious_key"
        return heuristic_prefix, "header_prefix"

    if filtered_pk:
        return filtered_pk, "metadata_filtered"

    if expected_rows == 1:
        return [], "single_row_no_key"

    if headers:
        return [headers[0]], "fallback_first_column"
    return [], "no_columns"


def normalize_primary_key(primary_key: Any) -> Optional[List[str]]:
    if primary_key is None:
        return None
    if isinstance(primary_key, list):
        cols = [col for col in primary_key if isinstance(col, str) and col]
        return cols or None
    if isinstance(primary_key, str) and primary_key:
        return [primary_key]
    return None


def dedupe_row_headers(row_headers: List[Dict[str, Any]], row_key_columns: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for row_header in row_headers:
        normalized = {key: row_header.get(key) for key in row_key_columns}
        key = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def validate_planner_output(
    obj: Any,
    row_key_columns: List[str],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Planner output is not a JSON object."
    row_headers = obj.get("row_headers")
    plan = obj.get("plan")
    if not isinstance(row_headers, list):
        return False, None, "Missing or invalid 'row_headers' list."
    if not isinstance(plan, str) or not plan.strip():
        return False, None, "Missing or invalid 'plan' string."
    normalized_rows: List[Dict[str, Any]] = []
    allowed = set(row_key_columns)
    for row_header in row_headers:
        if not isinstance(row_header, dict):
            return False, None, "Each row header must be a JSON object."
        keys = set(row_header.keys())
        if allowed:
            if not keys.issubset(allowed):
                return False, None, "Row header contains keys outside the row-key columns."
            normalized_rows.append({key: row_header.get(key) for key in row_key_columns})
        else:
            if keys:
                return False, None, "Row headers must be empty objects when there are no row-key columns."
            normalized_rows.append({})

    normalized_rows = dedupe_row_headers(normalized_rows, row_key_columns)
    if not normalized_rows:
        if row_key_columns:
            return False, None, "Planner output did not identify any rows."
        normalized_rows = [{}]

    return True, {"row_headers": normalized_rows, "plan": plan.strip()}, ""


def extract_table_and_reasoning(obj: Any) -> Tuple[Any, Optional[str]]:
    if isinstance(obj, dict):
        if isinstance(obj.get("final_table"), dict):
            reasoning = obj.get("reasoning_trace")
            return obj.get("final_table"), reasoning.strip() if isinstance(reasoning, str) and reasoning.strip() else None
        if isinstance(obj.get("table"), dict):
            reasoning = obj.get("reasoning")
            return obj.get("table"), reasoning.strip() if isinstance(reasoning, str) and reasoning.strip() else None
    return obj, None


def validate_table(
    obj: Any,
    expected_cols: List[str],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Output is not a JSON object."
    cols = obj.get("columns")
    rows = obj.get("rows")
    if not isinstance(cols, list):
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


def build_empty_table(
    headers: List[str],
    row_key_columns: List[str],
    row_headers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    rows = []
    for row_header in row_headers:
        row = []
        for header in headers:
            if header in row_key_columns:
                row.append(row_header.get(header))
            else:
                row.append(None)
        rows.append(row)
    return {"columns": headers, "rows": rows}


def build_planner_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    primary_key: Optional[List[str]],
    context: str,
) -> str:
    return PLANNER_USER_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
        context=context,
    )


def build_planner_system_prompt() -> str:
    return PLANNER_SYSTEM_PROMPT.replace("{cricket_policies}", CRICKET_POLICIES)


def build_fill_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    planner_output: Dict[str, Any],
    empty_table: Dict[str, Any],
    context: str,
) -> str:
    return FILL_USER_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        planner_json=json.dumps(planner_output, ensure_ascii=False),
        empty_table_json=json.dumps(empty_table, ensure_ascii=False),
        context=context,
    )


def build_fill_system_prompt() -> str:
    return FILL_SYSTEM_PROMPT.replace("{cricket_policies}", CRICKET_POLICIES)


def index_run_logs(run_log_dir: Optional[str]) -> Tuple[Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]], Dict[str, int]]:
    grouped: Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return grouped, usage_total

    pattern = re.compile(r"(\d+)_(plan|fill)_a(\d+)\.json$")
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


def parse_planner_attempts(
    logs: List[Tuple[int, str, Dict[str, Any]]],
    row_key_columns: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], int, Optional[str]]:
    attempts: List[Dict[str, Any]] = []
    planner_output = None
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
            ok, planner, err = validate_planner_output(parsed, row_key_columns)
            attempt_info["valid"] = ok
            attempt_info["error"] = err
            if ok:
                planner_output = planner
                last_error = None
            else:
                last_error = err
        except Exception as exc:
            attempt_info["valid"] = False
            attempt_info["error"] = str(exc)
            last_error = str(exc)
        attempts.append(attempt_info)
        next_attempt = max(next_attempt, attempt + 1)
    return planner_output, attempts, next_attempt, last_error


def parse_fill_attempts(
    logs: List[Tuple[int, str, Dict[str, Any]]],
    expected_cols: List[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]], int, Optional[str]]:
    pred_table = None
    reasoning = None
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
            table_candidate, attempt_reasoning = extract_table_and_reasoning(parsed)
            ok, table, err = validate_table(table_candidate, expected_cols)
            attempt_info["valid"] = ok
            attempt_info["error"] = err
            if ok:
                pred_table = table
                reasoning = attempt_reasoning
                last_error = None
            else:
                last_error = err
        except Exception as exc:
            attempt_info["valid"] = False
            attempt_info["error"] = str(exc)
            last_error = str(exc)
        attempts.append(attempt_info)
        next_attempt = max(next_attempt, attempt + 1)
    return pred_table, reasoning, attempts, next_attempt, last_error


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
        planner_output, plan_attempts, next_plan_attempt, plan_error = parse_planner_attempts(
            stage_logs.get("plan", []),
            row_key_columns,
        )
        pred_table, fill_reasoning, fill_attempts, next_fill_attempt, fill_error = parse_fill_attempts(
            stage_logs.get("fill", []),
            headers,
        )

        if pred_table is not None:
            empty_table = build_empty_table(headers, row_key_columns, planner_output["row_headers"]) if planner_output else None
            completed[record_id] = {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": item.get("record_id"),
                "question": item.get("question", ""),
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": item.get("answer_rows"),
                "planner_output": planner_output,
                "empty_table": empty_table,
                "fill_reasoning": fill_reasoning,
                "pred_table": pred_table,
                "success": True,
                "error": None,
                "plan_attempts": plan_attempts,
                "fill_attempts": fill_attempts,
            }
            continue

        plan_exhausted = next_plan_attempt > max_retries
        fill_exhausted = planner_output is not None and next_fill_attempt > max_retries
        if plan_exhausted or fill_exhausted:
            empty_table = build_empty_table(headers, row_key_columns, planner_output["row_headers"]) if planner_output else None
            completed[record_id] = {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": item.get("record_id"),
                "question": item.get("question", ""),
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": item.get("answer_rows"),
                "planner_output": planner_output,
                "empty_table": empty_table,
                "fill_reasoning": fill_reasoning,
                "pred_table": None,
                "success": False,
                "error": fill_error if planner_output is not None else plan_error,
                "plan_attempts": plan_attempts,
                "fill_attempts": fill_attempts,
            }
    return completed


def run() -> None:
    parser = argparse.ArgumentParser(description="ReAct-style planner/filler baseline runner.")
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
        context = item.get("context_full_with_overs", item.get("context", ""))
        headers = (item.get("answer") or {}).get("columns") or []
        expected_rows = item.get("answer_rows")
        primary_key = normalize_primary_key(item.get("primary_key"))
        row_key_columns, row_key_source = derive_row_key_columns(primary_key, headers, expected_rows)

        prior_stage_logs = log_index.get(record_id, {})
        planner_output, plan_attempts, next_plan_attempt, plan_error = parse_planner_attempts(
            prior_stage_logs.get("plan", []),
            row_key_columns,
        )
        pred_table, fill_reasoning, fill_attempts, next_fill_attempt, fill_error = parse_fill_attempts(
            prior_stage_logs.get("fill", []),
            headers,
        )
        usage_acc = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        if pred_table is not None:
            empty_table = build_empty_table(headers, row_key_columns, planner_output["row_headers"]) if planner_output else None
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": expected_rows,
                "planner_output": planner_output,
                "empty_table": empty_table,
                "fill_reasoning": fill_reasoning,
                "pred_table": pred_table,
                "success": True,
                "error": None,
                "plan_attempts": plan_attempts,
                "fill_attempts": fill_attempts,
                "_idx": idx,
            }, usage_acc

        planner_system_prompt = build_planner_system_prompt()
        planner_user_prompt = build_planner_user_prompt(question, headers, row_key_columns, primary_key, context)
        for attempt in range(next_plan_attempt, args.max_retries + 1):
            attempt_id = f"{record_id}_plan_a{attempt}"
            prompt_to_send = planner_user_prompt
            if attempt > next_plan_attempt and plan_error:
                prompt_to_send = (
                    planner_user_prompt
                    + "\n\nPrevious planner output was invalid: "
                    + plan_error
                    + "\nFix it and output ONLY valid JSON."
                )
            resp = svc.generate(
                system_prompt=planner_system_prompt,
                user_prompt=prompt_to_send,
                sample_id=attempt_id,
                metadata={
                    "record_id": original_record_id,
                    "sample_id": sample_id,
                    "stage": "plan",
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
                plan_error = resp.error
                attempt_info["valid"] = False
                attempt_info["error"] = resp.error
                plan_attempts.append(attempt_info)
                continue
            try:
                parsed = extract_json_obj(resp.text)
                ok, planner, err = validate_planner_output(parsed, row_key_columns)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    planner_output = planner
                    plan_error = None
                    plan_attempts.append(attempt_info)
                    break
                plan_error = err
            except Exception as exc:
                plan_error = str(exc)
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
            plan_attempts.append(attempt_info)

        if planner_output is None:
            return {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "expected_rows": expected_rows,
                "planner_output": None,
                "empty_table": None,
                "fill_reasoning": None,
                "pred_table": None,
                "success": False,
                "error": plan_error,
                "plan_attempts": plan_attempts,
                "fill_attempts": fill_attempts,
                "_idx": idx,
            }, usage_acc

        empty_table = build_empty_table(headers, row_key_columns, planner_output["row_headers"])
        fill_system_prompt = build_fill_system_prompt()
        fill_user_prompt = build_fill_user_prompt(question, headers, row_key_columns, planner_output, empty_table, context)
        for attempt in range(next_fill_attempt, args.max_retries + 1):
            attempt_id = f"{record_id}_fill_a{attempt}"
            prompt_to_send = fill_user_prompt
            if attempt > next_fill_attempt and fill_error:
                prompt_to_send = (
                    fill_user_prompt
                    + "\n\nPrevious fill output was invalid: "
                    + fill_error
                    + "\nFix it and output ONLY valid JSON with reasoning_trace and final_table."
                )
            resp = svc.generate(
                system_prompt=fill_system_prompt,
                user_prompt=prompt_to_send,
                sample_id=attempt_id,
                metadata={
                    "record_id": original_record_id,
                    "sample_id": sample_id,
                    "stage": "fill",
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
                fill_error = resp.error
                attempt_info["valid"] = False
                attempt_info["error"] = resp.error
                fill_attempts.append(attempt_info)
                continue
            try:
                parsed = extract_json_obj(resp.text)
                table_candidate, reasoning = extract_table_and_reasoning(parsed)
                ok, table, err = validate_table(table_candidate, headers)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok:
                    pred_table = table
                    fill_reasoning = reasoning
                    fill_error = None
                    fill_attempts.append(attempt_info)
                    break
                fill_error = err
            except Exception as exc:
                fill_error = str(exc)
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
            fill_attempts.append(attempt_info)

        return {
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "row_key_columns": row_key_columns,
            "row_key_source": row_key_source,
            "expected_rows": expected_rows,
            "planner_output": planner_output,
            "empty_table": empty_table,
            "fill_reasoning": fill_reasoning,
            "pred_table": pred_table,
            "success": pred_table is not None,
            "error": None if pred_table is not None else fill_error,
            "plan_attempts": plan_attempts,
            "fill_attempts": fill_attempts,
            "_idx": idx,
        }, usage_acc

    total = len(data)
    done = len(completed_from_logs)
    if completed_from_logs:
        print(f"Resuming from logs: {done} completed samples found in {run_log_dir}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(process_one, idx, item) for idx, item in pending_items]
        for future in as_completed(futures):
            result, usage_acc = future.result()
            results.append(result)
            for key in total_usage:
                total_usage[key] += int(usage_acc.get(key, 0))
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
        "planner_success_n": sum(1 for row in results if row.get("planner_output") is not None),
        "fill_success_n": sum(1 for row in results if row.get("pred_table") is not None),
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

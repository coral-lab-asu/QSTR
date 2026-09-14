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
    "dataset": "artifacts/runs/benchmark/dataset.jsonl",
    "n": -1,
    "seed": 0,
    "shuffle": False,
    "provider": "openai",
    "model": "meta-llama/Llama-3.3-70B-Instruct",
    "api_key": "",
    "base_url": "http://localhost:8001/v1",
    "temperature": 0.0,
    "planner_max_tokens": 10000,
    "step_max_tokens": 15000,
    "planner_max_retries": 3,
    "step_max_retries": 5,
    "max_plan_steps": 5,
    "log_dir": None,
    "run_id": None,
    "out": None,
    "summary_out": None,
    "workers": 8,
}

DEFAULTS["log_dir"] = f"baseline-results/{DEFAULTS['model']}/LTM/logs"
DEFAULTS["run_id"] = f"LTM_run_{DEFAULTS['seed']}"
DEFAULTS["out"] = f"baseline-results/{DEFAULTS['model']}/LTM/predictions.jsonl"
DEFAULTS["summary_out"] = f"baseline-results/{DEFAULTS['model']}/LTM/summary.json"


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


PLANNER_SYSTEM_PROMPT = f"""
You are designing a prompt-program for a cricket reasoning workflow.

Your task is to break the question into a small set of LLM sub-tasks that can be executed to obtain the final answer table.

Return STRICT JSON only.

You are not solving the question yourself.
You are writing a plan for other LLM calls to execute.

The plan must be a directed acyclic graph of at most 5 steps.
Each step may depend on earlier steps.
Independent steps may be run in parallel.

Each step must contain:
- step_id
- name
- depends_on
- uses_context
- input_keys
- output_key
- system_instruction
- user_instruction
- expected_output

Field definitions:
- step_id: unique string like "s1", "s2"
- name: short readable name for the step
- depends_on: list of prior step_ids required before running this step
- uses_context: true if this step needs the full match commentary, else false
- input_keys: list of named outputs from prior steps that should be provided to this step
- output_key: the name under which this step's output will be stored
- system_instruction: the system prompt for the LLM that will execute this step
- user_instruction: the user prompt content specific to this step
- expected_output: short description of what this step should return

Requirements:
- Use at most 5 steps.
- Prefer fewer steps when possible.
- The final step must produce output_key = "final_table".
- The final step should depend on whatever prior outputs are needed.
- Use uses_context = true only when the step genuinely needs commentary.
- input_keys must reference only outputs produced by dependency steps.
- The plan should be executable and minimal.
- Do not include redundant steps.
- Do not include markdown.
- Do not include any text outside the JSON object.

Cricket policies:
{CRICKET_POLICIES}

The output must have exactly this top-level shape:
{{
  "steps": [
    {{
      "step_id": "s1",
      "name": "example_name",
      "depends_on": [],
      "uses_context": true,
      "input_keys": [],
      "output_key": "example_output",
      "system_instruction": "...",
      "user_instruction": "...",
      "expected_output": "..."
    }}
  ]
}}

Example

Question:
Show me a comprehensive list of every batsman and bowler pair, detailing their total runs scored against each other, the balls exchanged, and the boundaries hit.

Target columns:
["batsman", "bowler", "total_runs", "balls_faced", "boundaries"]

Row key columns:
["batsman", "bowler"]

Good output:
{{
  "steps": [
    {{
      "step_id": "s1",
      "name": "identify_batsmen",
      "depends_on": [],
      "uses_context": true,
      "input_keys": [],
      "output_key": "batsmen",
      "system_instruction": "Identify all batsmen who appear in batting-versus-bowling interactions in the commentary.",
      "user_instruction": "Return the distinct batsmen mentioned in the commentary who face at least one delivery.",
      "expected_output": "A JSON object with a top-level key batsmen containing the list of batsmen."
    }},
    {{
      "step_id": "s2",
      "name": "identify_bowlers",
      "depends_on": [],
      "uses_context": true,
      "input_keys": [],
      "output_key": "bowlers",
      "system_instruction": "Identify all bowlers who appear in batting-versus-bowling interactions in the commentary.",
      "user_instruction": "Return the distinct bowlers mentioned in the commentary who bowl at least one delivery.",
      "expected_output": "A JSON object with a top-level key bowlers containing the list of bowlers."
    }},
    {{
      "step_id": "s3",
      "name": "identify_pairs",
      "depends_on": ["s1", "s2"],
      "uses_context": true,
      "input_keys": ["batsmen", "bowlers"],
      "output_key": "pairs",
      "system_instruction": "Determine every batsman-bowler pair that exchanges at least one ball in the commentary.",
      "user_instruction": "Using the identified batsmen and bowlers plus the commentary, return all active batsman-bowler pairs.",
      "expected_output": "A JSON object with a top-level key pairs containing the list of active batsman-bowler pairs."
    }},
    {{
      "step_id": "s4",
      "name": "compute_pair_stats",
      "depends_on": ["s3"],
      "uses_context": true,
      "input_keys": ["pairs"],
      "output_key": "pair_stats",
      "system_instruction": "Compute batting statistics for each batsman-bowler pair from the commentary.",
      "user_instruction": "For each pair, compute total_runs, balls_faced, and boundaries from the commentary.",
      "expected_output": "A JSON object with a top-level key pair_stats containing detailed pairwise statistics."
    }},
    {{
      "step_id": "s5",
      "name": "build_final_table",
      "depends_on": ["s4"],
      "uses_context": false,
      "input_keys": ["pair_stats"],
      "output_key": "final_table",
      "system_instruction": "Convert the computed pairwise statistics into the final answer table.",
      "user_instruction": "Return the final table with exact columns: batsman, bowler, total_runs, balls_faced, boundaries.",
      "expected_output": "A strict JSON table with columns and rows."
    }}
  ]
}}
""".strip()


PLANNER_USER_PROMPT_TEMPLATE = """
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

<planning_goal>
Create a prompt-program of at most 5 LLM steps that can be executed to solve this question.
The steps may form a dependency graph, not just a linear chain.
The final step must output the final answer table.
</planning_goal>

<guidance>
- If the task is simple, use fewer steps.
- If useful, split entity discovery, pair discovery, filtering, aggregation, and final table construction into separate steps.
- Steps that do not require context should avoid using context.
- The final step should usually not re-read commentary if prior structured outputs are sufficient.
</guidance>
""".strip()


EXECUTOR_SYSTEM_PROMPT_TEMPLATE = f"""
You are executing one step in a multi-step cricket table extraction workflow.

Return STRICT JSON only.

You are not solving a new task.
You are solving one part of the original question for the whole workflow.
You must preserve the meaning and global constraints of the original question while executing only the current step.

You must follow the step-specific instructions exactly.
You may use prior step outputs when they are provided.
If commentary is provided, treat it as the source of truth.
Do not include markdown.
Do not include explanations outside the JSON object.

Cricket policies:
{CRICKET_POLICIES}

Step-specific system instruction:
{{system_instruction}}

Current step output_key:
{{output_key}}

Expected output:
{{expected_output}}

Output rules:
- For non-final steps, return a JSON object whose top-level key is exactly the current output_key.
- For the final step where output_key is "final_table", return either:
  1. a strict JSON table object with top-level keys "columns" and "rows", or
  2. a JSON object with top-level key "final_table" whose value is a strict JSON table object.
- A strict JSON table object must have:
  {{{{
    "columns": [...],
    "rows": [...]
  }}}}
- The final table columns must match the target columns exactly and in order.
- Each final table row must have the same number of cells as columns.
""".strip()


EXECUTOR_USER_PROMPT_TEMPLATE = """
<original_question_for_the_full_workflow>
{question}
</original_question_for_the_full_workflow>

<your_job_in_this_call>
You are solving only the current step below.
Do not redefine the task.
Keep the full meaning, inclusion criteria, exclusion criteria, grouping rules, and output intent of the original question in mind while doing this part.
</your_job_in_this_call>

<question>
{question}
</question>

<target_columns>
{headers_json}
</target_columns>

<row_key_columns>
{row_key_columns_json}
</row_key_columns>

<current_step>
{step_json}
</current_step>

<step_user_instruction>
{user_instruction}
</step_user_instruction>

<available_inputs>
{available_inputs_json}
</available_inputs>

{context_block}
""".strip()


def read_dataset(path):
    from src.benchmark_data import read_dataset as load_benchmark
    return load_benchmark(path)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_run_log_dir(log_dir: str, run_id: Optional[str]) -> Optional[str]:
    if not log_dir:
        return None
    if run_id:
        return os.path.join(log_dir, run_id)
    return log_dir


def slugify_name(text: str) -> str:
    lowered = (text or "").strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or "step"


def make_stage_tag(step: Dict[str, Any]) -> str:
    return f"{step['step_id']}_{slugify_name(step['name'])}"


def new_usage_tracker() -> Dict[str, Dict[str, int]]:
    zero = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return {
        "planner": dict(zero),
        "executor": dict(zero),
        "overall": dict(zero),
    }


def add_usage(tracker: Dict[str, Dict[str, int]], usage: Dict[str, Any], stage_kind: str) -> None:
    bucket = "planner" if stage_kind == "planner" else "executor"
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            tracker[bucket][key] += int(value)
            tracker["overall"][key] += int(value)


def merge_usage(dest: Dict[str, Dict[str, int]], src: Dict[str, Dict[str, int]]) -> None:
    for bucket in ("planner", "executor", "overall"):
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            dest[bucket][key] += int(src[bucket][key])


def extract_json_obj(text: str) -> Any:
    text = (text or "").strip()
    try:
        return json.loads(text)
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
                return json.loads(candidate)
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
                return json.loads(text[start : i + 1])
    raise ValueError("Could not parse JSON object from response.")


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
    if h in {"runs", "balls", "wickets", "dot_balls", "boundaries", "fours", "sixes"}:
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


def validate_table(obj: Any, expected_cols: List[str]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
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


def validate_plan(obj: Any, max_plan_steps: int) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(obj, dict):
        return False, None, "Planner output is not a JSON object."
    steps = obj.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, None, "Planner output must contain a non-empty 'steps' list."
    if len(steps) > max_plan_steps:
        return False, None, f"Planner output exceeds max_plan_steps={max_plan_steps}."

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

    seen_step_ids = set()
    seen_output_keys = set()
    normalized_steps: List[Dict[str, Any]] = []
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

        normalized = {
            "step_id": step_id.strip(),
            "name": name.strip(),
            "depends_on": list(depends_on),
            "uses_context": uses_context,
            "input_keys": list(input_keys),
            "output_key": output_key.strip(),
            "system_instruction": system_instruction.strip(),
            "user_instruction": user_instruction.strip(),
            "expected_output": expected_output.strip(),
        }
        normalized["stage_tag"] = make_stage_tag(normalized)
        normalized_steps.append(normalized)
        seen_step_ids.add(step_id)
        seen_output_keys.add(output_key)
        prior_step_ids.append(step_id)
        step_outputs_by_id[step_id] = output_key

    if normalized_steps[-1]["output_key"] != "final_table":
        return False, None, "The final planner step must produce output_key 'final_table'."

    return True, {"steps": normalized_steps}, ""


def validate_intermediate_output(obj: Any, output_key: str) -> Tuple[bool, Optional[Any], str]:
    if not isinstance(obj, dict):
        return False, None, "Step output is not a JSON object."
    if output_key not in obj:
        return False, None, f"Missing expected top-level key '{output_key}'."
    value = obj.get(output_key)
    if value is None:
        return False, None, f"Top-level key '{output_key}' is null."
    return True, value, ""


def validate_step_output(step: Dict[str, Any], obj: Any, expected_cols: List[str]) -> Tuple[bool, Optional[Any], str]:
    output_key = step["output_key"]
    if output_key == "final_table":
        candidate = obj
        if isinstance(obj, dict) and "final_table" in obj and isinstance(obj.get("final_table"), dict):
            candidate = obj.get("final_table")
        ok, table, err = validate_table(candidate, expected_cols)
        return ok, table, err
    return validate_intermediate_output(obj, output_key)


def build_planner_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    primary_key: Optional[List[str]],
) -> str:
    return PLANNER_USER_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        primary_key_json=json.dumps(primary_key, ensure_ascii=False),
    )


def build_executor_system_prompt(step: Dict[str, Any]) -> str:
    return EXECUTOR_SYSTEM_PROMPT_TEMPLATE.format(
        system_instruction=step["system_instruction"],
        output_key=step["output_key"],
        expected_output=step["expected_output"],
    )


def build_executor_user_prompt(
    question: str,
    headers: List[str],
    row_key_columns: List[str],
    step: Dict[str, Any],
    available_inputs: Dict[str, Any],
    context: str,
) -> str:
    context_block = "<commentary>\n{context}\n</commentary>".format(context=context) if step["uses_context"] else "<commentary>\nNOT_PROVIDED\n</commentary>"
    return EXECUTOR_USER_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=json.dumps(headers, ensure_ascii=False),
        row_key_columns_json=json.dumps(row_key_columns, ensure_ascii=False),
        step_json=json.dumps(
            {
                "step_id": step["step_id"],
                "name": step["name"],
                "depends_on": step["depends_on"],
                "uses_context": step["uses_context"],
                "input_keys": step["input_keys"],
                "output_key": step["output_key"],
                "expected_output": step["expected_output"],
            },
            ensure_ascii=False,
        ),
        user_instruction=step["user_instruction"],
        available_inputs_json=json.dumps(available_inputs, ensure_ascii=False),
        context_block=context_block,
    )


def sum_usage_from_attempts(attempts: List[Dict[str, Any]], stage_kind: Optional[str] = None) -> Dict[str, int]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for attempt in attempts or []:
        if stage_kind is not None and attempt.get("stage_kind") != stage_kind:
            continue
        usage = attempt.get("usage") or {}
        for key in total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                total[key] += int(value)
    return total


def make_attempt_record(
    *,
    stage: str,
    stage_kind: str,
    attempt: int,
    path: Optional[str],
    usage: Dict[str, Any],
    valid: bool,
    error: str,
    step_id: Optional[str] = None,
    output_key: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "stage": stage,
        "stage_kind": stage_kind,
        "step_id": step_id,
        "output_key": output_key,
        "attempt": attempt,
        "path": path,
        "usage": usage,
        "valid": valid,
        "error": error,
    }


def index_run_logs(run_log_dir: Optional[str]) -> Tuple[Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]], Dict[str, Dict[str, int]]]:
    grouped: Dict[str, Dict[str, List[Tuple[int, str, Dict[str, Any]]]]] = {}
    usage_total = new_usage_tracker()
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return grouped, usage_total

    for name in os.listdir(run_log_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(run_log_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            continue

        metadata = log.get("metadata") or {}
        if metadata.get("baseline") != "LTM":
            continue
        sample_id = metadata.get("sample_id")
        stage_tag = metadata.get("stage_tag")
        attempt = metadata.get("attempt")
        stage_kind = metadata.get("stage_kind")
        if sample_id is None or not isinstance(stage_tag, str) or not isinstance(attempt, int):
            continue

        add_usage(usage_total, log.get("usage") or {}, stage_kind or "executor")
        grouped.setdefault(str(sample_id), {}).setdefault(stage_tag, []).append((attempt, path, log))

    for sample_id in grouped:
        for stage_tag in grouped[sample_id]:
            grouped[sample_id][stage_tag].sort(key=lambda x: x[0])
    return grouped, usage_total


def reconstruct_sample_state(
    idx: int,
    item: Dict[str, Any],
    sample_logs: Dict[str, List[Tuple[int, str, Dict[str, Any]]]],
    planner_max_retries: int,
    step_max_retries: int,
    max_plan_steps: int,
) -> Dict[str, Any]:
    sample_id = item.get("sample_id")
    if sample_id is None:
        sample_id = idx
    record_id = str(sample_id)
    original_record_id = item.get("record_id")
    question = item.get("question", "")
    ans = item.get("answer") or {}
    headers = ans.get("columns") or []
    expected_rows = item.get("answer_rows")
    pk = item.get("primary_key")
    if pk is None:
        pk_list = None
    elif isinstance(pk, list):
        pk_list = pk
    elif isinstance(pk, str):
        pk_list = [pk]
    else:
        pk_list = None
    row_key_columns, row_key_source = derive_row_key_columns(pk_list, headers, expected_rows)

    attempts: List[Dict[str, Any]] = []
    outputs: Dict[str, Any] = {}
    plan = None
    next_plan_attempt = 0
    step_next_attempts: Dict[str, int] = {}
    error_msg = ""

    plan_logs = sample_logs.get("plan", [])
    for attempt, path, log in plan_logs:
        usage = log.get("usage") or {}
        try:
            obj = extract_json_obj(log.get("response_text", ""))
            ok, normalized_plan, err = validate_plan(obj, max_plan_steps)
        except Exception as exc:
            ok, normalized_plan, err = False, None, str(exc)
        attempts.append(
            make_attempt_record(
                stage="plan",
                stage_kind="planner",
                attempt=attempt,
                path=path,
                usage=usage,
                valid=ok,
                error=err,
            )
        )
        if ok and plan is None:
            plan = normalized_plan
            error_msg = ""
        elif not ok:
            error_msg = err
        next_plan_attempt = max(next_plan_attempt, attempt + 1)

    if plan is None:
        complete = len(plan_logs) >= (planner_max_retries + 1)
        return {
            "complete": complete,
            "success": False,
            "pred_table": None,
            "error": error_msg,
            "plan": None,
            "outputs": outputs,
            "attempts": attempts,
            "next_plan_attempt": next_plan_attempt,
            "step_next_attempts": step_next_attempts,
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
            "row_key_columns": row_key_columns,
            "row_key_source": row_key_source,
        }

    for step in plan["steps"]:
        stage_tag = step["stage_tag"]
        logs = sample_logs.get(stage_tag, [])
        valid_output = None
        last_error = ""
        next_attempt = 0

        missing_inputs = [key for key in step["input_keys"] if key not in outputs]
        if missing_inputs:
            error_msg = f"Missing dependency outputs for step '{stage_tag}': {missing_inputs}"
            return {
                "complete": False,
                "success": False,
                "pred_table": None,
                "error": error_msg,
                "plan": plan,
                "outputs": outputs,
                "attempts": attempts,
                "next_plan_attempt": next_plan_attempt,
                "step_next_attempts": step_next_attempts,
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "expected_rows": expected_rows,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
            }

        for attempt, path, log in logs:
            usage = log.get("usage") or {}
            try:
                obj = extract_json_obj(log.get("response_text", ""))
                ok, payload, err = validate_step_output(step, obj, headers)
            except Exception as exc:
                ok, payload, err = False, None, str(exc)
            attempts.append(
                make_attempt_record(
                    stage=stage_tag,
                    stage_kind="executor",
                    step_id=step["step_id"],
                    output_key=step["output_key"],
                    attempt=attempt,
                    path=path,
                    usage=usage,
                    valid=ok,
                    error=err,
                )
            )
            if ok and valid_output is None:
                valid_output = payload
                last_error = ""
            elif not ok:
                last_error = err
            next_attempt = max(next_attempt, attempt + 1)

        step_next_attempts[stage_tag] = next_attempt
        if valid_output is not None:
            outputs[step["output_key"]] = valid_output
            continue
        if len(logs) >= (step_max_retries + 1):
            error_msg = last_error
            return {
                "complete": True,
                "success": False,
                "pred_table": None,
                "error": error_msg,
                "plan": plan,
                "outputs": outputs,
                "attempts": attempts,
                "next_plan_attempt": next_plan_attempt,
                "step_next_attempts": step_next_attempts,
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "expected_rows": expected_rows,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
            }
        error_msg = last_error
        return {
            "complete": False,
            "success": False,
            "pred_table": None,
            "error": error_msg,
            "plan": plan,
            "outputs": outputs,
            "attempts": attempts,
            "next_plan_attempt": next_plan_attempt,
            "step_next_attempts": step_next_attempts,
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
            "row_key_columns": row_key_columns,
            "row_key_source": row_key_source,
        }

    return {
        "complete": True,
        "success": True,
        "pred_table": outputs.get("final_table"),
        "error": "",
        "plan": plan,
        "outputs": outputs,
        "attempts": attempts,
        "next_plan_attempt": next_plan_attempt,
        "step_next_attempts": step_next_attempts,
        "record_id": record_id,
        "sample_id": sample_id,
        "original_record_id": original_record_id,
        "question": question,
        "headers": headers,
        "expected_rows": expected_rows,
        "row_key_columns": row_key_columns,
        "row_key_source": row_key_source,
    }


def load_existing_log_state(
    run_log_dir: Optional[str],
    dataset_items: List[Dict[str, Any]],
    planner_max_retries: int,
    step_max_retries: int,
    max_plan_steps: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, int]], Dict[str, Dict[str, Any]]]:
    completed: Dict[str, Dict[str, Any]] = {}
    partial: Dict[str, Dict[str, Any]] = {}
    grouped, usage_total = index_run_logs(run_log_dir)

    for idx, item in enumerate(dataset_items):
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        state = reconstruct_sample_state(
            idx=idx,
            item=item,
            sample_logs=grouped.get(str(sample_id), {}),
            planner_max_retries=planner_max_retries,
            step_max_retries=step_max_retries,
            max_plan_steps=max_plan_steps,
        )
        if state["complete"]:
            completed[str(sample_id)] = state
        elif state["plan"] is not None or state["attempts"]:
            partial[str(sample_id)] = state

    return completed, usage_total, partial


def preflight_step(step: Dict[str, Any], outputs: Dict[str, Any], context: str) -> Tuple[bool, str]:
    if step["uses_context"] and not (context or "").strip():
        return False, f"Step '{step['stage_tag']}' requires commentary but context is empty."
    missing = [key for key in step["input_keys"] if key not in outputs]
    if missing:
        return False, f"Step '{step['stage_tag']}' missing required input_keys: {missing}"
    if not step["system_instruction"].strip():
        return False, f"Step '{step['stage_tag']}' has empty system_instruction."
    if not step["user_instruction"].strip():
        return False, f"Step '{step['stage_tag']}' has empty user_instruction."
    return True, ""


def is_json_failure_error(error: Optional[str]) -> bool:
    if not error:
        return False
    err = error.lower()
    patterns = (
        "json",
        "parse",
        "no json object found",
        "could not parse json object",
        "not a json object",
        "missing expected top-level key",
        "missing or invalid 'columns' list",
        "missing or invalid 'rows' list",
        "row length does not match columns",
        "planner output",
    )
    return any(pattern in err for pattern in patterns)


def run() -> None:
    parser = argparse.ArgumentParser(description="Least-to-most prompting baseline runner.")
    parser.add_argument("--dataset", default=DEFAULTS["dataset"])
    parser.add_argument("--n", type=int, default=DEFAULTS["n"])
    parser.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    parser.add_argument("--shuffle", action="store_true", default=DEFAULTS["shuffle"])
    parser.add_argument("--provider", default=DEFAULTS["provider"])
    parser.add_argument("--model", default=DEFAULTS["model"])
    parser.add_argument("--api-key", default=DEFAULTS["api_key"])
    parser.add_argument("--base-url", default=DEFAULTS["base_url"])
    parser.add_argument("--temperature", type=float, default=DEFAULTS["temperature"])
    parser.add_argument("--planner-max-tokens", type=int, default=DEFAULTS["planner_max_tokens"])
    parser.add_argument("--step-max-tokens", type=int, default=DEFAULTS["step_max_tokens"])
    parser.add_argument("--planner-max-retries", type=int, default=DEFAULTS["planner_max_retries"])
    parser.add_argument("--step-max-retries", type=int, default=DEFAULTS["step_max_retries"])
    parser.add_argument("--max-plan-steps", type=int, default=DEFAULTS["max_plan_steps"])
    parser.add_argument("--log-dir", default=DEFAULTS["log_dir"])
    parser.add_argument("--run-id", default=DEFAULTS["run_id"])
    parser.add_argument("--out", default=DEFAULTS["out"])
    parser.add_argument("--summary-out", default=DEFAULTS["summary_out"])
    parser.add_argument("--workers", type=int, default=DEFAULTS["workers"], help="Number of worker threads")
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
    completed_from_logs, existing_usage, partial_states = load_existing_log_state(
        run_log_dir=run_log_dir,
        dataset_items=data,
        planner_max_retries=args.planner_max_retries,
        step_max_retries=args.step_max_retries,
        max_plan_steps=args.max_plan_steps,
    )

    cfg = InferenceConfig(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        temperature=args.temperature,
        max_tokens=args.step_max_tokens,
        log_dir=args.log_dir,
        run_id=args.run_id,
    )
    svc = InferenceService(cfg)

    total_usage = existing_usage
    results: List[Dict[str, Any]] = list(completed_from_logs.values())
    pending_items: List[Tuple[int, Dict[str, Any], Optional[Dict[str, Any]]]] = []

    for idx, item in enumerate(data):
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        key = str(sample_id)
        if key in completed_from_logs:
            continue
        pending_items.append((idx, item, partial_states.get(key)))

    def process_one(idx: int, item: Dict[str, Any], prior_state: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, int]]]:
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        record_id = str(sample_id)
        original_record_id = item.get("record_id")
        question = item.get("question", "")
        context = (item.get("context_full_with_overs") or item.get("context") or item.get("context_full") or "")
        ans = item.get("answer") or {}
        headers = ans.get("columns") or []
        expected_rows = item.get("answer_rows")
        pk = item.get("primary_key")
        if pk is None:
            primary_key = None
        elif isinstance(pk, list):
            primary_key = pk
        elif isinstance(pk, str):
            primary_key = [pk]
        else:
            primary_key = None

        row_key_columns, row_key_source = derive_row_key_columns(primary_key, headers, expected_rows)
        plan = prior_state.get("plan") if prior_state else None
        outputs = dict(prior_state.get("outputs", {})) if prior_state else {}
        attempts = list(prior_state.get("attempts", [])) if prior_state else []
        next_plan_attempt = prior_state.get("next_plan_attempt", 0) if prior_state else 0
        step_next_attempts = dict(prior_state.get("step_next_attempts", {})) if prior_state else {}
        error_msg = prior_state.get("error", "") if prior_state else ""
        usage_acc = new_usage_tracker()

        if plan is None:
            planner_user_prompt = build_planner_user_prompt(
                question=question,
                headers=headers,
                row_key_columns=row_key_columns,
                primary_key=primary_key,
            )

            for attempt in range(next_plan_attempt, args.planner_max_retries + 1):
                attempt_id = f"{record_id}_plan_a{attempt}"
                resp = svc.generate(
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    user_prompt=planner_user_prompt,
                    sample_id=attempt_id,
                    temperature=args.temperature,
                    max_tokens=args.planner_max_tokens,
                    metadata={
                        "baseline": "LTM",
                        "record_id": original_record_id,
                        "sample_id": sample_id,
                        "attempt": attempt,
                        "stage_kind": "planner",
                        "stage_tag": "plan",
                    },
                )
                add_usage(usage_acc, resp.usage or {}, "planner")
                path = os.path.join(run_log_dir, f"{attempt_id}.json") if run_log_dir else None
                if resp.error:
                    ok, normalized_plan, err = False, None, resp.error
                else:
                    try:
                        obj = extract_json_obj(resp.text)
                        ok, normalized_plan, err = validate_plan(obj, args.max_plan_steps)
                    except Exception as exc:
                        ok, normalized_plan, err = False, None, str(exc)

                attempts.append(
                    make_attempt_record(
                        stage="plan",
                        stage_kind="planner",
                        attempt=attempt,
                        path=path,
                        usage=resp.usage or {},
                        valid=ok,
                        error=err,
                    )
                )

                if ok:
                    plan = normalized_plan
                    error_msg = ""
                    break
                error_msg = err

            if plan is None:
                return (
                    {
                        "record_id": record_id,
                        "sample_id": sample_id,
                        "original_record_id": original_record_id,
                        "question": question,
                        "headers": headers,
                        "expected_rows": expected_rows,
                        "row_key_columns": row_key_columns,
                        "row_key_source": row_key_source,
                        "plan": None,
                        "pred_table": None,
                        "success": False,
                        "error": error_msg,
                        "attempts": attempts,
                        "_idx": idx,
                    },
                    usage_acc,
                )

        assert plan is not None

        for step in plan["steps"]:
            output_key = step["output_key"]
            stage_tag = step["stage_tag"]
            if output_key in outputs:
                continue

            ok, preflight_error = preflight_step(step, outputs, context)
            if not ok:
                return (
                    {
                        "record_id": record_id,
                        "sample_id": sample_id,
                        "original_record_id": original_record_id,
                        "question": question,
                        "headers": headers,
                        "expected_rows": expected_rows,
                        "row_key_columns": row_key_columns,
                        "row_key_source": row_key_source,
                        "plan": plan,
                        "pred_table": None,
                        "success": False,
                        "error": preflight_error,
                        "attempts": attempts,
                        "_idx": idx,
                    },
                    usage_acc,
                )

            start_attempt = step_next_attempts.get(stage_tag, 0)
            available_inputs = {key: outputs[key] for key in step["input_keys"]}

            for attempt in range(start_attempt, args.step_max_retries + 1):
                attempt_id = f"{record_id}_{stage_tag}_a{attempt}"
                resp = svc.generate(
                    system_prompt=build_executor_system_prompt(step),
                    user_prompt=build_executor_user_prompt(
                        question=question,
                        headers=headers,
                        row_key_columns=row_key_columns,
                        step=step,
                        available_inputs=available_inputs,
                        context=context,
                    ),
                    sample_id=attempt_id,
                    temperature=args.temperature,
                    max_tokens=args.step_max_tokens,
                    metadata={
                        "baseline": "LTM",
                        "record_id": original_record_id,
                        "sample_id": sample_id,
                        "attempt": attempt,
                        "stage_kind": "executor",
                        "stage_tag": stage_tag,
                        "step_id": step["step_id"],
                        "step_name": step["name"],
                        "output_key": output_key,
                    },
                )
                add_usage(usage_acc, resp.usage or {}, "executor")
                path = os.path.join(run_log_dir, f"{attempt_id}.json") if run_log_dir else None
                if resp.error:
                    valid, payload, err = False, None, resp.error
                else:
                    try:
                        obj = extract_json_obj(resp.text)
                        valid, payload, err = validate_step_output(step, obj, headers)
                    except Exception as exc:
                        valid, payload, err = False, None, str(exc)

                attempts.append(
                    make_attempt_record(
                        stage=stage_tag,
                        stage_kind="executor",
                        step_id=step["step_id"],
                        output_key=output_key,
                        attempt=attempt,
                        path=path,
                        usage=resp.usage or {},
                        valid=valid,
                        error=err,
                    )
                )

                if valid:
                    outputs[output_key] = payload
                    error_msg = ""
                    break
                error_msg = err

            if output_key not in outputs:
                return (
                    {
                        "record_id": record_id,
                        "sample_id": sample_id,
                        "original_record_id": original_record_id,
                        "question": question,
                        "headers": headers,
                        "expected_rows": expected_rows,
                        "row_key_columns": row_key_columns,
                        "row_key_source": row_key_source,
                        "plan": plan,
                        "pred_table": None,
                        "success": False,
                        "error": error_msg,
                        "attempts": attempts,
                        "_idx": idx,
                    },
                    usage_acc,
                )

        pred_table = outputs.get("final_table")
        success = pred_table is not None
        return (
            {
                "record_id": record_id,
                "sample_id": sample_id,
                "original_record_id": original_record_id,
                "question": question,
                "headers": headers,
                "expected_rows": expected_rows,
                "row_key_columns": row_key_columns,
                "row_key_source": row_key_source,
                "plan": plan,
                "pred_table": pred_table,
                "success": success,
                "error": "" if success else error_msg,
                "attempts": attempts,
                "_idx": idx,
            },
            usage_acc,
        )

    total = len(data)
    done = len(completed_from_logs)
    if completed_from_logs:
        print(f"Resuming from logs: {done} completed samples found in {run_log_dir}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(process_one, idx, item, state) for idx, item, state in pending_items]
        for fut in as_completed(futures):
            res, usage_acc = fut.result()
            results.append(res)
            merge_usage(total_usage, usage_acc)
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
    success_n = len(success_results)

    if success_n:
        planner_success_totals = [sum_usage_from_attempts(row.get("attempts", []), "planner") for row in success_results]
        executor_success_totals = [sum_usage_from_attempts(row.get("attempts", []), "executor") for row in success_results]
        overall_success_totals = [sum_usage_from_attempts(row.get("attempts", []), None) for row in success_results]
        avg_success_usage = {
            "planner": {
                "input_tokens": sum(x["input_tokens"] for x in planner_success_totals) / success_n,
                "output_tokens": sum(x["output_tokens"] for x in planner_success_totals) / success_n,
                "total_tokens": sum(x["total_tokens"] for x in planner_success_totals) / success_n,
            },
            "executor": {
                "input_tokens": sum(x["input_tokens"] for x in executor_success_totals) / success_n,
                "output_tokens": sum(x["output_tokens"] for x in executor_success_totals) / success_n,
                "total_tokens": sum(x["total_tokens"] for x in executor_success_totals) / success_n,
            },
            "overall": {
                "input_tokens": sum(x["input_tokens"] for x in overall_success_totals) / success_n,
                "output_tokens": sum(x["output_tokens"] for x in overall_success_totals) / success_n,
                "total_tokens": sum(x["total_tokens"] for x in overall_success_totals) / success_n,
            },
        }
    else:
        avg_success_usage = {
            "planner": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
            "executor": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
            "overall": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        }

    exhausted_failures = [row for row in results if not row["success"]]
    planner_failures = [row for row in exhausted_failures if not any(a.get("stage_kind") == "executor" and a.get("valid") for a in row.get("attempts", []))]
    json_failures = [row for row in exhausted_failures if is_json_failure_error(row.get("error"))]

    summary = {
        "n": len(results),
        "success_n": success_n,
        "failure_n": len(results) - success_n,
        "usage_total": total_usage,
        "usage_avg_per_successful_sample": avg_success_usage,
        "max_steps_planned_any_sample": max((len((row.get("plan") or {}).get("steps", [])) for row in results), default=0),
        "avg_steps_planned_successful_sample": (
            sum(len((row.get("plan") or {}).get("steps", [])) for row in success_results) / success_n if success_n else None
        ),
        "max_attempts_any_step": max((len(row.get("attempts", [])) for row in results), default=0),
        "planner_failure_n": len(planner_failures),
        "executor_failure_n": len(exhausted_failures) - len(planner_failures),
        "final_table_failure_n": len([row for row in exhausted_failures if any(a.get("output_key") == "final_table" for a in row.get("attempts", []))]),
        "json_failure_n": len(json_failures),
        "dataset": args.dataset,
        "provider": args.provider,
        "model": args.model,
        "temperature": args.temperature,
        "planner_max_tokens": args.planner_max_tokens,
        "step_max_tokens": args.step_max_tokens,
        "planner_max_retries": args.planner_max_retries,
        "step_max_retries": args.step_max_retries,
        "max_plan_steps": args.max_plan_steps,
        "output_path": args.out,
        "log_dir": args.log_dir,
    }
    with open(args.summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()

import argparse
import json
import math
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.inference import InferenceConfig, InferenceService  # noqa: E402

DEFAULTS = {
    "dataset": "artifacts/runs/benchmark/dataset.jsonl",
    "n": 5,
    "seed": 0,
    "shuffle": False,
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "api_key": os.getenv("GEMINI_API_KEY", ""),
    "base_url": "",
    "temperature": 0.6,
    "max_tokens": 32000,
    "max_retries": 5,
    "num_votes": 5,
    "log_dir": None,
    "run_id": None,
    "out": None,
    "summary_out": None,
    "workers": 5,
    "numeric_vote_tolerance": 0.2,
}


def derive_output_paths(model: str, seed: int, num_votes: int) -> Dict[str, str]:
    base = f"baseline-results/{model}/SC_VOTE/{num_votes}"
    return {
        "log_dir": f"{base}/logs",
        "run_id": f"SC_VOTE_run_{seed}_{num_votes}",
        "out": f"{base}/predictions.jsonl",
        "summary_out": f"{base}/summary.json",
    }


DEFAULTS.update(derive_output_paths(DEFAULTS["model"], DEFAULTS["seed"], DEFAULTS["num_votes"]))

SYSTEM_PROMPT_TEMPLATE = """
You are an expert cricket analyst and data annotator.

Goal:
- Read ball-by-ball cricket commentary (line-by-line).
- Answer the question by producing a structured table.

Rules:
- Do not invent facts not supported by the text.
- Output STRICT JSON only. No markdown. No explanations.
- If returning a percentage column, always express it on a 0-100 scale (not 0-1).

Question:
{question}

You MUST output a table with EXACT columns (order preserved):
{headers_json}

Output format (STRICT JSON only):
{{
  "reasoning_trace": "free-form working trace for this instance",
  "final_table": {{
    "columns": [{headers_inline}],
    "rows": [
      [<row1_col1>, <row1_col2>, ...],
      ...
    ]
  }}
}}

Constraints:
- reasoning_trace should describe the actual computation for this instance, including relevant entities, filters, intermediate counts, and derived values when useful.
- Do not output generic instructions, hypothetical examples, or placeholder numbers.
- final_table.columns must match EXACTLY and in the same order.
- Every final_table row must have the same number of cells as columns.
- final_table cells must contain concrete JSON values only.
- For numeric final_table cells, output the computed number directly as a JSON number, not an arithmetic expression or formula string.
- Use null for unknown values.
- Reason explicitly in reasoning_trace before producing the final table.

{cricket_policies}
"""

CRICKET_POLICIES = """
Cricket policies:
- Runs: credit only off-the-bat (exclude byes/leg-byes). For no-balls, bat runs are credited separately; the +1 nb is NOT bat runs.
- Balls faced: increment for every delivery except wides (no-balls DO count as a ball faced).
- Fours/Sixes: only for off-the-bat boundaries; exclude byes/leg-byes.
- Bowler balls: count only legal deliveries (wides/no-balls do NOT add to balls).
- Bowler runs given: includes all conceded (incl. wides, no-balls, byes/leg-byes).
- Bowler wickets: credit only bowler-attributable dismissals (b, c off bowler, lbw, st off bowler, hit wicket). Do NOT credit run out.
- Overs: floor(balls/6) "." (balls % 6).
"""

USER_PROMPT_TEMPLATE = """
Context (ball-by-ball commentary lines):
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>
"""


def normalize_primary_key(primary_key: Any) -> Optional[List[str]]:
    if primary_key is None:
        return None
    if isinstance(primary_key, list):
        cols = [col for col in primary_key if isinstance(col, str) and col]
        return cols or None
    if isinstance(primary_key, str) and primary_key:
        return [primary_key]
    return None


def read_dataset(path):
    from src.benchmark_data import read_dataset as load_benchmark
    return load_benchmark(path)


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def get_run_log_dir(log_dir: str, run_id: Optional[str]) -> Optional[str]:
    if not log_dir:
        return None
    if run_id:
        return os.path.join(log_dir, run_id)
    return log_dir


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


def validate_table(obj: Any, expected_cols: List[str], expected_rows: Optional[int]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
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
    for r in rows:
        if not isinstance(r, list):
            return False, None, "Row is not a list."
        if len(r) != len(cols):
            return False, None, "Row length does not match columns."
    return True, {"columns": cols, "rows": rows}, ""


def extract_table_and_reasoning_trace(obj: Any) -> Tuple[Any, Optional[str]]:
    if isinstance(obj, dict) and isinstance(obj.get("final_table"), dict):
        reasoning = obj.get("reasoning_trace")
        return obj.get("final_table"), reasoning.strip() if isinstance(reasoning, str) and reasoning.strip() else None
    return obj, None


def build_system_prompt(question: str, headers: List[str]) -> str:
    headers_json = json.dumps(headers, ensure_ascii=False)
    headers_inline = ", ".join([json.dumps(h, ensure_ascii=False) for h in headers])
    return SYSTEM_PROMPT_TEMPLATE.format(
        question=question,
        headers_json=headers_json,
        headers_inline=headers_inline,
        cricket_policies=CRICKET_POLICIES.strip(),
    )


def build_user_prompt(context: str) -> str:
    return USER_PROMPT_TEMPLATE.format(context=context)


def sum_usage_from_attempts(attempts: List[Dict[str, Any]]) -> Dict[str, int]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for attempt in attempts or []:
        usage = attempt.get("usage") or {}
        for key in total:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                total[key] += int(value)
    return total


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
        "missing or invalid 'columns' list",
        "missing or invalid 'rows' list",
        "row is not a list",
    )
    return any(pattern in err for pattern in patterns)


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


def canonicalize_cell(value: Any) -> Any:
    if value is None:
        return None
    numeric = _normalize_numeric_string(value)
    if numeric is not None:
        return {"type": "num", "value": numeric}
    if isinstance(value, str):
        return {"type": "str", "value": " ".join(value.strip().split()).lower()}
    return {"type": type(value).__name__, "value": value}


def _value_sort_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _candidate_sort_key(payload: Dict[str, Any]) -> Tuple[int, int]:
    return int(payload["vote_idx"]), int(payload.get("attempt_used", 10**9))


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", value.strip().lower())
    return " ".join(normalized.split())


def _build_pk_component(value: Any) -> Dict[str, Any]:
    numeric = _normalize_numeric_string(value)
    if numeric is not None:
        return {
            "kind": "num",
            "full": numeric,
            "surname": numeric,
            "tokens": [numeric],
            "initial": numeric[:1],
        }
    if value is None:
        return {"kind": "none", "full": None, "surname": None, "tokens": [], "initial": None}
    if isinstance(value, str):
        full = _normalize_text(value)
        tokens = full.split() if full else []
        surname = tokens[-1] if tokens else ""
        initial = tokens[0][:1] if tokens else ""
        return {
            "kind": "str",
            "full": full,
            "surname": surname,
            "tokens": tokens,
            "initial": initial,
        }
    return {
        "kind": type(value).__name__,
        "full": value,
        "surname": None,
        "tokens": [],
        "initial": None,
    }


def _pk_component_signature(component: Dict[str, Any]) -> Tuple[str, Any]:
    return component["kind"], component["full"]


def _prepare_candidate_table(candidate: Dict[str, Any], pk_cols: Optional[List[str]]) -> Dict[str, Any]:
    table = candidate["pred_table"]
    cols = [str(c) for c in (table.get("columns") or [])]
    rows = table.get("rows") or []
    col_idx = {c: i for i, c in enumerate(cols)}
    pk_enabled = bool(pk_cols) and all(c in col_idx for c in pk_cols)

    row_entries: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        canonical_row = [canonicalize_cell(cell) for cell in row]
        pk_components = None
        pk_signature = None
        if pk_enabled:
            pk_components = tuple(_build_pk_component(row[col_idx[c]] if col_idx[c] < len(row) else None) for c in pk_cols or [])
            pk_signature = tuple(_pk_component_signature(component) for component in pk_components)
            sort_key = tuple(_value_sort_key(v) for v in pk_signature)
        else:
            sort_key = tuple(_value_sort_key(v) for v in canonical_row)
        row_entries.append(
            {
                "row": list(row),
                "canonical_row": canonical_row,
                "pk_components": pk_components,
                "pk_signature": pk_signature,
                "sort_key": sort_key,
            }
        )

    row_entries.sort(key=lambda entry: entry["sort_key"])

    payload = dict(candidate)
    payload.update(
        {
            "columns": cols,
            "pk_enabled": pk_enabled,
            "row_entries": row_entries,
            "cluster_ids_in_order": (),
            "cluster_entry_map": {},
        }
    )
    return payload


def _pk_component_similarity_cost(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    if left["kind"] != right["kind"]:
        return 1.0

    if left["kind"] == "num":
        return 0.0 if left["full"] == right["full"] else 1.0

    if left["kind"] == "none":
        return 0.0

    if left["kind"] == "str":
        left_full = left["full"] or ""
        right_full = right["full"] or ""
        if left_full == right_full:
            return 0.0

        left_tokens = set(left["tokens"])
        right_tokens = set(right["tokens"])
        if left_tokens and right_tokens and left["surname"] and left["surname"] == right["surname"]:
            if left_tokens <= right_tokens or right_tokens <= left_tokens:
                return 0.2
            if left["initial"] and right["initial"] and left["initial"] == right["initial"]:
                return 0.25
            if len(left["tokens"]) == 1 or len(right["tokens"]) == 1:
                return 0.35

        full_similarity = SequenceMatcher(None, left_full, right_full).ratio()
        if full_similarity >= 0.95:
            return 1.0 - full_similarity
        return 1.0

    return 0.0 if left["full"] == right["full"] else 1.0


def _pk_entry_similarity_cost(left_entry: Dict[str, Any], right_entry: Dict[str, Any], pk_cols: List[str]) -> float:
    left_components = left_entry.get("pk_components") or ()
    right_components = right_entry.get("pk_components") or ()
    if len(left_components) != len(right_components):
        return 1.0

    total = 0.0
    for left_component, right_component in zip(left_components, right_components):
        total += _pk_component_similarity_cost(left_component, right_component)
    return total / max(1, len(pk_cols))


def _cluster_component_at(cluster: Dict[str, Any], pk_index: int) -> Optional[Dict[str, Any]]:
    if not cluster["members"]:
        return None
    components = cluster["members"][0]["entry"].get("pk_components") or ()
    if pk_index >= len(components):
        return None
    return components[pk_index]


def _is_ambiguous_surname_only_match(
    entry: Dict[str, Any],
    cluster: Dict[str, Any],
    surname_cluster_counts: List[Dict[str, int]],
) -> bool:
    entry_components = entry.get("pk_components") or ()
    for pk_index, component in enumerate(entry_components):
        if component["kind"] != "str" or len(component["tokens"]) != 1 or not component["surname"]:
            continue
        cluster_component = _cluster_component_at(cluster, pk_index)
        if cluster_component is None or cluster_component["kind"] != "str":
            continue
        if cluster_component["full"] == component["full"]:
            continue
        if cluster_component["surname"] == component["surname"] and surname_cluster_counts[pk_index].get(component["surname"], 0) > 1:
            return True
    return False


def _hungarian(cost: List[List[float]]) -> List[Tuple[int, int]]:
    n = len(cost)
    m = len(cost[0]) if n else 0
    if n == 0 or m == 0:
        return []

    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    out: List[Tuple[int, int]] = []
    for j in range(1, m + 1):
        if p[j] != 0:
            out.append((p[j] - 1, j - 1))
    return out


def _cluster_candidate_rows_by_pk(
    prepared_candidates: List[Dict[str, Any]],
    pk_cols: List[str],
) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    unmatched_cost = 5.0
    mismatch_cost = 10.0
    clusters: List[Dict[str, Any]] = []
    next_cluster_id = 0

    for prepared in sorted(prepared_candidates, key=_candidate_sort_key):
        row_entries = prepared["row_entries"]
        cluster_ids: List[Optional[int]] = [None] * len(row_entries)
        if not clusters:
            for row_idx, entry in enumerate(row_entries):
                cluster = {
                    "cluster_id": next_cluster_id,
                    "members": [{"candidate": prepared, "entry": entry}],
                    "sort_key": entry["sort_key"],
                }
                clusters.append(cluster)
                cluster_ids[row_idx] = next_cluster_id
                next_cluster_id += 1
        else:
            size = max(len(row_entries), len(clusters))
            cost = [[unmatched_cost for _ in range(size)] for _ in range(size)]
            surname_cluster_counts: List[Dict[str, int]] = [dict() for _ in range(len(pk_cols))]
            for cluster in clusters:
                for pk_index in range(len(pk_cols)):
                    component = _cluster_component_at(cluster, pk_index)
                    if component is None or component["kind"] != "str" or not component["surname"]:
                        continue
                    surname_cluster_counts[pk_index][component["surname"]] = (
                        surname_cluster_counts[pk_index].get(component["surname"], 0) + 1
                    )
            for row_idx, entry in enumerate(row_entries):
                for cluster_idx, cluster in enumerate(clusters):
                    sim_cost = min(
                        _pk_entry_similarity_cost(entry, member["entry"], pk_cols)
                        for member in cluster["members"]
                    )
                    if _is_ambiguous_surname_only_match(entry, cluster, surname_cluster_counts):
                        cost[row_idx][cluster_idx] = mismatch_cost
                    else:
                        cost[row_idx][cluster_idx] = sim_cost if sim_cost < 1.0 else mismatch_cost

            assignments = _hungarian(cost)
            matched_rows = set()
            for row_idx, cluster_idx in assignments:
                if row_idx >= len(row_entries) or cluster_idx >= len(clusters):
                    continue
                if cost[row_idx][cluster_idx] >= unmatched_cost:
                    continue
                cluster = clusters[cluster_idx]
                cluster["members"].append({"candidate": prepared, "entry": row_entries[row_idx]})
                if row_entries[row_idx]["sort_key"] < cluster["sort_key"]:
                    cluster["sort_key"] = row_entries[row_idx]["sort_key"]
                cluster_ids[row_idx] = cluster["cluster_id"]
                matched_rows.add(row_idx)

            for row_idx, entry in enumerate(row_entries):
                if row_idx in matched_rows:
                    continue
                cluster = {
                    "cluster_id": next_cluster_id,
                    "members": [{"candidate": prepared, "entry": entry}],
                    "sort_key": entry["sort_key"],
                }
                clusters.append(cluster)
                cluster_ids[row_idx] = next_cluster_id
                next_cluster_id += 1

        prepared["cluster_ids_in_order"] = tuple(
            cluster_id for cluster_id in cluster_ids if cluster_id is not None
        )
        prepared["cluster_entry_map"] = {
            int(cluster_id): row_entries[row_idx]
            for row_idx, cluster_id in enumerate(cluster_ids)
            if cluster_id is not None
        }

    return clusters, {cluster["cluster_id"]: cluster for cluster in clusters}


def _build_vote_counts(groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    return [
        {
            "vote_count": len(group),
            "vote_indices": [int(x["vote_idx"]) for x in sorted(group, key=lambda item: int(item["vote_idx"]))],
            "representative_vote_idx": int(min(group, key=lambda item: int(item["vote_idx"]))["vote_idx"]),
        }
        for group in groups
    ]


def _cluster_numeric_cell_entries(
    cell_entries: List[Dict[str, Any]],
    numeric_vote_tolerance: float,
) -> Optional[List[Dict[str, Any]]]:
    numeric_entries = [entry for entry in cell_entries if entry.get("numeric_value") is not None]
    if not numeric_entries:
        return None

    best_cluster: Optional[List[Dict[str, Any]]] = None
    best_key: Optional[Tuple[int, float, Tuple[int, int]]] = None
    seen_signatures = set()
    for center_entry in numeric_entries:
        center_value = float(center_entry["numeric_value"])
        cluster = [
            entry
            for entry in numeric_entries
            if abs(float(entry["numeric_value"]) - center_value) <= numeric_vote_tolerance
        ]
        signature = tuple(sorted(_candidate_sort_key(entry) for entry in cluster))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        total_distance = sum(abs(float(entry["numeric_value"]) - center_value) for entry in cluster)
        cluster_key = (-len(cluster), total_distance, min(_candidate_sort_key(entry) for entry in cluster))
        if best_key is None or cluster_key < best_key:
            best_key = cluster_key
            best_cluster = cluster
    return best_cluster


def _representative_numeric_value(cluster: List[Dict[str, Any]]) -> Any:
    return min(
        cluster,
        key=lambda entry: (
            sum(abs(float(entry["numeric_value"]) - float(other["numeric_value"])) for other in cluster),
            _candidate_sort_key(entry),
        ),
    )["raw_value"]


def _vote_cell_value(
    cell_entries: List[Dict[str, Any]],
    numeric_vote_tolerance: float,
) -> Tuple[Any, int]:
    numeric_cluster = _cluster_numeric_cell_entries(cell_entries, numeric_vote_tolerance)
    exact_groups: Dict[str, List[Dict[str, Any]]] = {}
    for entry in cell_entries:
        key = _value_sort_key(entry["canonical_value"])
        exact_groups.setdefault(key, []).append(entry)

    best_exact_group = None
    if exact_groups:
        best_exact_group = sorted(
            exact_groups.values(),
            key=lambda group: (-len(group), min(_candidate_sort_key(entry) for entry in group)),
        )[0]

    winning_numeric = False
    if numeric_cluster is not None:
        if best_exact_group is None or len(numeric_cluster) > len(best_exact_group):
            winning_numeric = True
        elif len(numeric_cluster) == len(best_exact_group):
            winning_numeric = min(_candidate_sort_key(entry) for entry in numeric_cluster) < min(
                _candidate_sort_key(entry) for entry in best_exact_group
            )

    if winning_numeric:
        return _representative_numeric_value(numeric_cluster or []), len(numeric_cluster or [])

    exact_group = best_exact_group or []
    representative = min(exact_group, key=_candidate_sort_key)
    return representative["raw_value"], len(exact_group)


def _aggregate_pk_cell_votes(
    prepared_candidates: List[Dict[str, Any]],
    pk_cols: List[str],
    numeric_vote_tolerance: float,
) -> Dict[str, Any]:
    clusters, clusters_by_id = _cluster_candidate_rows_by_pk(prepared_candidates, pk_cols)
    row_groups: Dict[Tuple[int, ...], List[Dict[str, Any]]] = {}
    row_support: Dict[int, int] = {}
    for prepared in prepared_candidates:
        signature = tuple(prepared["cluster_ids_in_order"])
        row_groups.setdefault(signature, []).append(prepared)
        for cluster_id in dict.fromkeys(prepared["cluster_ids_in_order"]):
            row_support[int(cluster_id)] = row_support.get(int(cluster_id), 0) + 1

    ranked_groups = sorted(
        row_groups.values(),
        key=lambda group: (-len(group), min(int(item["vote_idx"]) for item in group)),
    )
    winner_group = ranked_groups[0]
    representative = min(winner_group, key=_candidate_sort_key)
    row_vote_threshold = max(1, (len(prepared_candidates) // 2) + 1)
    selected_cluster_ids = [
        cluster_id
        for cluster_id in representative["cluster_ids_in_order"]
        if row_support.get(int(cluster_id), 0) >= row_vote_threshold
    ]
    if not selected_cluster_ids:
        selected_cluster_ids = list(representative["cluster_ids_in_order"])
    selected_cluster_id_set = set(selected_cluster_ids)
    remaining_majority_keys = sorted(
        [
            cluster_id
            for cluster_id, support in row_support.items()
            if support >= row_vote_threshold and cluster_id not in selected_cluster_id_set
        ],
        key=lambda cluster_id: clusters_by_id[int(cluster_id)]["sort_key"],
    )
    selected_cluster_ids.extend(int(cluster_id) for cluster_id in remaining_majority_keys)

    cols = representative["columns"]
    cell_supports: List[int] = []
    final_rows: List[List[Any]] = []
    for cluster_id in selected_cluster_ids:
        aligned_rows = []
        for prepared in sorted(prepared_candidates, key=_candidate_sort_key):
            entry = prepared["cluster_entry_map"].get(int(cluster_id))
            if entry is not None:
                aligned_rows.append({"candidate": prepared, "entry": entry})
        if not aligned_rows:
            continue

        out_row: List[Any] = []
        for col_idx, _ in enumerate(cols):
            cell_entries = []
            for item in aligned_rows:
                raw_value = item["entry"]["row"][col_idx] if col_idx < len(item["entry"]["row"]) else None
                canonical_value = item["entry"]["canonical_row"][col_idx] if col_idx < len(item["entry"]["canonical_row"]) else None
                numeric_value = None
                if isinstance(canonical_value, dict) and canonical_value.get("type") == "num":
                    try:
                        numeric_value = float(canonical_value["value"])
                    except (TypeError, ValueError):
                        numeric_value = None
                cell_entries.append(
                    {
                        "vote_idx": item["candidate"]["vote_idx"],
                        "attempt_used": item["candidate"].get("attempt_used"),
                        "raw_value": raw_value,
                        "canonical_value": canonical_value,
                        "numeric_value": numeric_value,
                    }
                )
            voted_value, support = _vote_cell_value(cell_entries, numeric_vote_tolerance)
            out_row.append(voted_value)
            cell_supports.append(support)
        final_rows.append(out_row)

    return {
        "chosen_vote_idx": int(representative["vote_idx"]),
        "winner_vote_count": len(winner_group),
        "valid_candidate_n": len(prepared_candidates),
        "vote_counts": _build_vote_counts(ranked_groups),
        "pred_table": {"columns": cols, "rows": final_rows},
        "row_selection_mode": "pk_fuzzy_hungarian",
        "row_vote_threshold": row_vote_threshold,
        "selected_row_n": len(final_rows),
        "cell_vote_support_avg": (sum(cell_supports) / len(cell_supports)) if cell_supports else None,
        "cell_vote_support_min": min(cell_supports) if cell_supports else None,
    }


def _aggregate_row_order_cell_votes(
    prepared_candidates: List[Dict[str, Any]],
    numeric_vote_tolerance: float,
) -> Dict[str, Any]:
    row_count_groups: Dict[int, List[Dict[str, Any]]] = {}
    for prepared in prepared_candidates:
        row_count_groups.setdefault(len(prepared["row_entries"]), []).append(prepared)

    ranked_groups = sorted(
        row_count_groups.values(),
        key=lambda group: (-len(group), min(int(item["vote_idx"]) for item in group)),
    )
    winner_group = ranked_groups[0]
    representative = min(winner_group, key=_candidate_sort_key)
    final_row_count = len(representative["row_entries"])
    cols = representative["columns"]
    cell_supports: List[int] = []
    final_rows: List[List[Any]] = []
    for row_idx in range(final_row_count):
        aligned_rows = []
        for prepared in prepared_candidates:
            if row_idx < len(prepared["row_entries"]):
                aligned_rows.append({"candidate": prepared, "entry": prepared["row_entries"][row_idx]})
        if not aligned_rows:
            continue

        out_row: List[Any] = []
        for col_idx, _ in enumerate(cols):
            cell_entries = []
            for item in aligned_rows:
                raw_value = item["entry"]["row"][col_idx] if col_idx < len(item["entry"]["row"]) else None
                canonical_value = item["entry"]["canonical_row"][col_idx] if col_idx < len(item["entry"]["canonical_row"]) else None
                numeric_value = None
                if isinstance(canonical_value, dict) and canonical_value.get("type") == "num":
                    try:
                        numeric_value = float(canonical_value["value"])
                    except (TypeError, ValueError):
                        numeric_value = None
                cell_entries.append(
                    {
                        "vote_idx": item["candidate"]["vote_idx"],
                        "attempt_used": item["candidate"].get("attempt_used"),
                        "raw_value": raw_value,
                        "canonical_value": canonical_value,
                        "numeric_value": numeric_value,
                    }
                )
            voted_value, support = _vote_cell_value(cell_entries, numeric_vote_tolerance)
            out_row.append(voted_value)
            cell_supports.append(support)
        final_rows.append(out_row)

    return {
        "chosen_vote_idx": int(representative["vote_idx"]),
        "winner_vote_count": len(winner_group),
        "valid_candidate_n": len(prepared_candidates),
        "vote_counts": _build_vote_counts(ranked_groups),
        "pred_table": {"columns": cols, "rows": final_rows},
        "row_selection_mode": "row_order",
        "row_vote_threshold": None,
        "selected_row_n": len(final_rows),
        "cell_vote_support_avg": (sum(cell_supports) / len(cell_supports)) if cell_supports else None,
        "cell_vote_support_min": min(cell_supports) if cell_supports else None,
    }


def vote_over_candidates(
    valid_candidates: List[Dict[str, Any]],
    pk_cols: Optional[List[str]],
    numeric_vote_tolerance: float,
) -> Dict[str, Any]:
    prepared_candidates = [_prepare_candidate_table(candidate, pk_cols) for candidate in valid_candidates]
    if prepared_candidates and prepared_candidates[0]["pk_enabled"]:
        return _aggregate_pk_cell_votes(prepared_candidates, pk_cols or [], numeric_vote_tolerance)
    return _aggregate_row_order_cell_votes(prepared_candidates, numeric_vote_tolerance)


def collect_prior_vote_logs(run_log_dir: Optional[str], record_id: str) -> Dict[int, List[Tuple[int, Dict[str, Any]]]]:
    grouped: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return grouped

    pattern = re.compile(rf"{re.escape(record_id)}_v(\d+)_a(\d+)\.json$")
    for name in os.listdir(run_log_dir):
        match = pattern.match(name)
        if not match:
            continue
        vote_idx = int(match.group(1))
        attempt = int(match.group(2))
        path = os.path.join(run_log_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            continue
        grouped.setdefault(vote_idx, []).append((attempt, log))

    for vote_idx in grouped:
        grouped[vote_idx].sort(key=lambda x: x[0])
    return grouped


def build_result_from_vote_logs(
    idx: int,
    item: Dict[str, Any],
    prior_vote_logs: Dict[int, List[Tuple[int, Dict[str, Any]]]],
    num_votes: int,
    max_retries: int,
    numeric_vote_tolerance: float,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int]]:
    sample_id = item.get("sample_id")
    if sample_id is None:
        sample_id = idx
    record_id = str(sample_id)
    original_record_id = item.get("record_id")
    question = item.get("question", "")
    ans = item.get("answer") or {}
    headers = ans.get("columns") or []
    expected_rows = item.get("answer_rows")
    pk_cols = normalize_primary_key(item.get("primary_key"))

    attempts: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    valid_candidates: List[Dict[str, Any]] = []
    last_errors: List[str] = []
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    complete = True

    for vote_idx in range(num_votes):
        logs = prior_vote_logs.get(vote_idx, [])
        valid_table = None
        valid_reasoning_trace = None
        valid_attempt = None
        error_msg = ""
        for attempt, log in logs:
            response_text = log.get("response_text", "")
            usage = log.get("usage") or {}
            for key in usage_total:
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    usage_total[key] += int(value)
            attempt_info = {
                "vote_idx": vote_idx,
                "attempt": attempt,
                "response_text": response_text,
                "usage": usage,
            }
            try:
                obj = extract_json_obj(response_text)
                table_candidate, reasoning_trace = extract_table_and_reasoning_trace(obj)
                ok, table, err = validate_table(table_candidate, headers, expected_rows)
                attempt_info["valid"] = ok
                attempt_info["error"] = err
                if ok and valid_table is None:
                    valid_table = table
                    valid_reasoning_trace = reasoning_trace
                    valid_attempt = attempt
                    error_msg = ""
                elif not ok:
                    error_msg = err
            except Exception as exc:
                attempt_info["valid"] = False
                attempt_info["error"] = str(exc)
                error_msg = str(exc)
            attempts.append(attempt_info)

        exhausted = len(logs) >= (max_retries + 1)
        if valid_table is None and not exhausted:
            complete = False

        candidate_entry = {
            "vote_idx": vote_idx,
            "valid": valid_table is not None,
            "attempt_count": len(logs),
            "attempt_used": valid_attempt,
            "error": None if valid_table is not None else error_msg,
            "reasoning_trace": valid_reasoning_trace,
            "pred_table": valid_table,
        }
        candidates.append(candidate_entry)
        if valid_table is not None:
            valid_candidates.append(
                {
                    "vote_idx": vote_idx,
                    "attempt_used": valid_attempt if valid_attempt is not None else max_retries,
                    "reasoning_trace": valid_reasoning_trace,
                    "pred_table": valid_table,
                }
            )
        elif error_msg:
            last_errors.append(f"vote {vote_idx}: {error_msg}")

    if not complete:
        return None, usage_total

    winner = vote_over_candidates(valid_candidates, pk_cols, numeric_vote_tolerance) if valid_candidates else None
    result = {
        "record_id": record_id,
        "sample_id": sample_id,
        "original_record_id": original_record_id,
        "question": question,
        "headers": headers,
        "expected_rows": expected_rows,
        "pred_table": winner["pred_table"] if winner else None,
        "success": winner is not None,
        "error": "" if winner else ("; ".join(last_errors) if last_errors else "No valid candidates."),
        "attempts": attempts,
        "candidates": candidates,
        "chosen_vote_idx": winner["chosen_vote_idx"] if winner else None,
        "winner_vote_count": winner["winner_vote_count"] if winner else 0,
        "valid_candidate_n": winner["valid_candidate_n"] if winner else 0,
        "vote_counts": winner["vote_counts"] if winner else [],
        "row_selection_mode": winner["row_selection_mode"] if winner else None,
        "row_vote_threshold": winner["row_vote_threshold"] if winner else None,
        "selected_row_n": winner["selected_row_n"] if winner else 0,
        "cell_vote_support_avg": winner["cell_vote_support_avg"] if winner else None,
        "cell_vote_support_min": winner["cell_vote_support_min"] if winner else None,
        "_idx": idx,
    }
    return result, usage_total


def load_existing_log_state(
    run_log_dir: Optional[str],
    dataset_items: List[Dict[str, Any]],
    num_votes: int,
    max_retries: int,
    numeric_vote_tolerance: float,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    completed: Dict[str, Dict[str, Any]] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not run_log_dir or not os.path.isdir(run_log_dir):
        return completed, usage_total

    for idx, item in enumerate(dataset_items):
        sample_id = item.get("sample_id")
        if sample_id is None:
            sample_id = idx
        record_id = str(sample_id)
        prior_vote_logs = collect_prior_vote_logs(run_log_dir, record_id)
        if not prior_vote_logs:
            continue
        result, usage_acc = build_result_from_vote_logs(
            idx,
            item,
            prior_vote_logs,
            num_votes,
            max_retries,
            numeric_vote_tolerance,
        )
        for key in usage_total:
            usage_total[key] += int(usage_acc.get(key, 0))
        if result is not None:
            completed[record_id] = result

    return completed, usage_total


def max_attempt_index(result: Dict[str, Any]) -> int:
    return max((int(a.get("attempt", 0)) for a in result.get("attempts", [])), default=-1)


def run() -> None:
    parser = argparse.ArgumentParser(description="Self-consistency voting baseline runner.")
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
    parser.add_argument("--num-votes", type=int, default=DEFAULTS["num_votes"])
    parser.add_argument("--numeric-vote-tolerance", type=float, default=DEFAULTS["numeric_vote_tolerance"])
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--summary-out", default=None)
    parser.add_argument("--workers", type=int, default=DEFAULTS["workers"], help="Number of worker threads")
    args = parser.parse_args()

    derived = derive_output_paths(args.model, args.seed, args.num_votes)
    args.log_dir = args.log_dir or derived["log_dir"]
    args.run_id = args.run_id or derived["run_id"]
    args.out = args.out or derived["out"]
    args.summary_out = args.summary_out or derived["summary_out"]

    ensure_dir(os.path.dirname(args.out))
    ensure_dir(os.path.dirname(args.summary_out))

    data = read_dataset(args.dataset)
    data.sort(key=lambda item: int(item.get("sample_id", 10**18)))
    if args.shuffle:
        random.Random(args.seed).shuffle(data)
    if args.n is not None and args.n >= 0:
        data = data[: args.n]

    run_log_dir = get_run_log_dir(args.log_dir, args.run_id)
    completed_from_logs, existing_usage = load_existing_log_state(
        run_log_dir,
        data,
        args.num_votes,
        args.max_retries,
        args.numeric_vote_tolerance,
    )

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
        ans = item.get("answer") or {}
        headers = ans.get("columns") or []
        expected_rows = item.get("answer_rows")
        pk_cols = normalize_primary_key(item.get("primary_key"))

        system_prompt = build_system_prompt(question, headers)
        user_prompt = build_user_prompt(context)

        prior_vote_logs = collect_prior_vote_logs(run_log_dir, record_id)
        attempts: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        valid_candidates: List[Dict[str, Any]] = []
        usage_acc = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        last_errors: List[str] = []

        for vote_idx in range(args.num_votes):
            logs = prior_vote_logs.get(vote_idx, [])
            valid_table = None
            valid_reasoning_trace = None
            valid_attempt = None
            error_msg = ""

            for attempt_num, log in logs:
                usage = log.get("usage") or {}
                attempts.append(
                    {
                        "vote_idx": vote_idx,
                        "attempt": attempt_num,
                        "response_text": log.get("response_text", ""),
                        "usage": usage,
                    }
                )
                try:
                    obj = extract_json_obj(log.get("response_text", ""))
                    table_candidate, reasoning_trace = extract_table_and_reasoning_trace(obj)
                    ok, table, err = validate_table(table_candidate, headers, expected_rows)
                    attempts[-1]["valid"] = ok
                    attempts[-1]["error"] = err
                    if ok and valid_table is None:
                        valid_table = table
                        valid_reasoning_trace = reasoning_trace
                        valid_attempt = attempt_num
                        error_msg = ""
                    elif not ok:
                        error_msg = err
                except Exception as exc:
                    attempts[-1]["valid"] = False
                    attempts[-1]["error"] = str(exc)
                    error_msg = str(exc)

            start_attempt = logs[-1][0] + 1 if logs else 0
            if valid_table is None:
                for attempt in range(start_attempt, args.max_retries + 1):
                    attempt_id = f"{record_id}_v{vote_idx}_a{attempt}"
                    prompt_to_send = user_prompt
                    if attempt > 0 and error_msg:
                        prompt_to_send = (
                            user_prompt
                            + "\n\nPrevious output was invalid: "
                            + error_msg
                            + "\nFix it and output ONLY valid JSON with reasoning_trace and final_table."
                        )

                    resp = svc.generate(
                        system_prompt=system_prompt.strip(),
                        user_prompt=prompt_to_send,
                        sample_id=attempt_id,
                        metadata={
                            "record_id": original_record_id,
                            "sample_id": sample_id,
                            "vote_idx": vote_idx,
                            "attempt": attempt,
                        },
                    )

                    usage = resp.usage or {}
                    for key in usage_acc:
                        value = usage.get(key)
                        if isinstance(value, (int, float)):
                            usage_acc[key] += int(value)

                    attempts.append(
                        {
                            "vote_idx": vote_idx,
                            "attempt": attempt,
                            "response_text": resp.text,
                            "usage": usage,
                        }
                    )
                    if resp.error:
                        attempts[-1]["valid"] = False
                        attempts[-1]["error"] = resp.error
                        error_msg = resp.error
                        continue

                    try:
                        obj = extract_json_obj(resp.text)
                        table_candidate, reasoning_trace = extract_table_and_reasoning_trace(obj)
                        ok, table, err = validate_table(table_candidate, headers, expected_rows)
                        attempts[-1]["valid"] = ok
                        attempts[-1]["error"] = err
                        if ok:
                            valid_table = table
                            valid_reasoning_trace = reasoning_trace
                            valid_attempt = attempt
                            error_msg = ""
                            break
                        error_msg = err
                    except Exception as exc:
                        attempts[-1]["valid"] = False
                        attempts[-1]["error"] = str(exc)
                        error_msg = str(exc)

            candidate_entry = {
                "vote_idx": vote_idx,
                "valid": valid_table is not None,
                "attempt_count": sum(1 for x in attempts if int(x["vote_idx"]) == vote_idx),
                "attempt_used": valid_attempt,
                "error": None if valid_table is not None else error_msg,
                "reasoning_trace": valid_reasoning_trace,
                "pred_table": valid_table,
            }
            candidates.append(candidate_entry)
            if valid_table is not None:
                valid_candidates.append(
                    {
                        "vote_idx": vote_idx,
                        "attempt_used": valid_attempt if valid_attempt is not None else args.max_retries,
                        "reasoning_trace": valid_reasoning_trace,
                        "pred_table": valid_table,
                    }
                )
            elif error_msg:
                last_errors.append(f"vote {vote_idx}: {error_msg}")

        winner = vote_over_candidates(valid_candidates, pk_cols, args.numeric_vote_tolerance) if valid_candidates else None
        result = {
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": original_record_id,
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
            "pred_table": winner["pred_table"] if winner else None,
            "success": winner is not None,
            "error": "" if winner else ("; ".join(last_errors) if last_errors else "No valid candidates."),
            "attempts": attempts,
            "candidates": candidates,
            "chosen_vote_idx": winner["chosen_vote_idx"] if winner else None,
            "winner_vote_count": winner["winner_vote_count"] if winner else 0,
            "valid_candidate_n": winner["valid_candidate_n"] if winner else 0,
            "vote_counts": winner["vote_counts"] if winner else [],
            "row_selection_mode": winner["row_selection_mode"] if winner else None,
            "row_vote_threshold": winner["row_vote_threshold"] if winner else None,
            "selected_row_n": winner["selected_row_n"] if winner else 0,
            "cell_vote_support_avg": winner["cell_vote_support_avg"] if winner else None,
            "cell_vote_support_min": winner["cell_vote_support_min"] if winner else None,
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
            for key in total_usage:
                total_usage[key] += int(usage_acc.get(key, 0))
            done += 1
            status = "success" if res["success"] else "failure"
            print(
                f"[{done}/{total}] idx={res['_idx']} sample_id={res['sample_id']} "
                f"record_id={res['record_id']} status={status}"
            )

    results.sort(key=lambda r: r.get("_idx", 0))
    for result in results:
        result.pop("_idx", None)

    with open(args.out, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    success_results = [r for r in results if r["success"]]
    success_usage_totals = [sum_usage_from_attempts(r.get("attempts", [])) for r in success_results]
    success_n = len(success_results)
    if success_n:
        avg_success_usage = {
            "input_tokens": sum(x["input_tokens"] for x in success_usage_totals) / success_n,
            "output_tokens": sum(x["output_tokens"] for x in success_usage_totals) / success_n,
            "total_tokens": sum(x["total_tokens"] for x in success_usage_totals) / success_n,
        }
        valid_candidate_avg = sum(int(r.get("valid_candidate_n", 0)) for r in success_results) / success_n
        winner_vote_count_avg = sum(int(r.get("winner_vote_count", 0)) for r in success_results) / success_n
        cell_vote_support_avg = (
            sum(float(r["cell_vote_support_avg"]) for r in success_results if r.get("cell_vote_support_avg") is not None)
            / sum(1 for r in success_results if r.get("cell_vote_support_avg") is not None)
            if any(r.get("cell_vote_support_avg") is not None for r in success_results)
            else None
        )
    else:
        avg_success_usage = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        valid_candidate_avg = None
        winner_vote_count_avg = None
        cell_vote_support_avg = None

    exhausted_failures = [r for r in results if not r["success"]]
    json_failures = [r for r in exhausted_failures if is_json_failure_error(r.get("error"))]

    summary = {
        "n": len(results),
        "success_n": success_n,
        "failure_n": sum(1 for r in results if not r["success"]),
        "usage_total": total_usage,
        "usage_avg_per_successful_sample": avg_success_usage,
        "num_votes": args.num_votes,
        "numeric_vote_tolerance": args.numeric_vote_tolerance,
        "valid_candidate_avg": valid_candidate_avg,
        "winner_vote_count_avg": winner_vote_count_avg,
        "cell_vote_support_avg": cell_vote_support_avg,
        "max_attempts_any_sample": max((len(r.get("attempts", [])) for r in results), default=0),
        "max_retries_used_any_sample": max((max_attempt_index(r) for r in results), default=-1),
        "max_retries_used_failed_sample": max((max_attempt_index(r) for r in exhausted_failures), default=-1),
        "max_retries_used_json_failure": max((max_attempt_index(r) for r in json_failures), default=-1),
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

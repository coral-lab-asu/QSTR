import argparse
import difflib
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from tqdm import tqdm

import google.generativeai as genai


MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

PROMPT_TEMPLATE = """You are an expert SQL reviewer.

I will give you:
- a natural language question
- two SQL queries: gnd_sql and pred_sql

Your task:
1. Decide which query answers the question better.
2. If one query is correct, return it.
3. If both queries are incorrect, generate the correct SQL.

---------------------
Dataset description
---------------------

The dataset is a **ball-by-ball cricket dataset**.

Each row represents **one ball (delivery)**.

Columns:

Batting
- batsman → name of the batsman facing the ball
- batsman_runs → runs scored off the bat on that ball
- batsman_fours → indicator of a four hit on that ball (usually 1 or 0)
- batsman_sixes → indicator of a six hit on that ball (usually 1 or 0)
- batsman_bowls_faced → balls faced on that row (ball-level, usually 1 or 0)

Bowling
- bowler → name of the bowler
- bowler_runs_given → runs conceded by the bowler on that ball (includes runs off bat, wides, no-balls; excludes byes and leg-byes)
- bowler_wickets → wickets credited to the bowler on that ball (usually 1 or 0)
- bowler_bowls_done → balls bowled on that row (ball-level, usually 1)

Other
- team_runs → total runs scored by the batting team on that ball (includes extras like wides, byes, leg-byes, etc.)
- overs → decimal representation of the ball number in the innings

Overs encoding:
- 0.1–0.6 → over 1
- 1.1–1.6 → over 2
- 2.1–2.6 → over 3

To obtain the over number use:

CEIL(overs)

Example:
CEIL(0.1) = 1  
CEIL(6.2) = 7

---------------------
Metric rules
---------------------

Strike rate:
SUM(runs) * 100.0 / NULLIF(SUM(balls), 0)

Per-ball rate:
SUM(events) * 1.0 / NULLIF(SUM(balls), 0)

Boundary runs:
batsman_fours * 4 + batsman_sixes * 6

Use NULLIF(...,0) to avoid divide-by-zero.

Use correct columns:
- batsman metrics → batsman_runs, batsman_fours, batsman_sixes, batsman_bowls_faced
- bowler conceded runs → bowler_runs_given

---------------------
Important rule about phases
---------------------

Do NOT assume definitions for Powerplay, Middle Overs, or Death Overs.

Only apply phase filters exactly as defined in the question.

Examples:
- if the question defines powerplay as overs ≤ 6 → use CEIL(overs) <= 6
- if the question defines middle overs as 7–15 → use CEIL(overs) > 6 AND CEIL(overs) <= 15
- if the question defines death overs as last 5 overs → use CEIL(overs) > (SELECT MAX(CEIL(overs)) FROM df) - 5
- It is wrong to use trunc instead of CEIL to get over number

---------------------
What to check
---------------------

When comparing queries verify:
- correct overs filtering
- correct metric formula
- correct aggregation level
- correct GROUP BY
- divide-by-zero protection
- correct ORDER BY
- correct columns used

---------------------
Output format (JSON only)
---------------------

{{
  "decision": "gnd_sql | pred_sql | neither",
  "reason": "short explanation",
  "final_sql": "correct SQL as one string"
}}

Rules:
- If one query is correct → return it.
- If both are incorrect → generate the correct SQL.
- final_sql must be a single SQL string.

---------------------

question: {question}
gnd_sql: {gnd_sql}
pred_sql: {pred_sql}
"""


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def extract_json_obj(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model response.")

    depth = 0
    in_str = False
    esc = False
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
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
                chunk = text[start:i + 1]
                obj = json.loads(chunk)
                if isinstance(obj, dict):
                    return obj
    raise ValueError("Failed to extract JSON object from model response.")


def build_model(model_name: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def call_gemini_api(model, question: str, gnd_sql: str, pred_sql: str) -> Dict[str, Any]:
    full_prompt = PROMPT_TEMPLATE.format(
        question=question or "",
        gnd_sql=gnd_sql or "",
        pred_sql=pred_sql or "",
    )

    raw_response_text = ""
    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(full_prompt)
            raw_response_text = response.text.strip()
            obj = extract_json_obj(raw_response_text)
            decision = obj.get("decision")
            final_sql = obj.get("final_sql")
            if decision not in {"gnd_sql", "pred_sql", "neither"}:
                raise ValueError(f"Unexpected decision: {decision}")
            if not isinstance(final_sql, str) or not final_sql.strip():
                raise ValueError("Missing or empty final_sql in model response.")
            obj["final_sql"] = final_sql.strip()
            obj["raw_response"] = raw_response_text
            obj["prompt"] = full_prompt
            return obj
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                return {
                    "decision": "error",
                    "reason": f"Failed after {MAX_RETRIES} attempts: {e}",
                    "final_sql": "",
                    "raw_response": raw_response_text,
                    "prompt": full_prompt,
                }


def load_mismatch_records(samplewise_path: str) -> List[Dict[str, Any]]:
    data = read_json(samplewise_path)
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"Expected samplewise JSON with a 'records' list: {samplewise_path}")
    return [
        r for r in records
        if isinstance(r, dict)
        and isinstance(r.get("table_match"), dict)
        and (r["table_match"].get("content_match") is not True)
    ]


def choose_target_key(item: Dict[str, Any]) -> str:
    if "original_sql" in item:
        return "original_sql"
    return "sql"


def print_progress(done: int, total: int) -> None:
    pct = (done / total * 100.0) if total else 100.0
    print(f"\rProgress: {done}/{total} ({pct:.1f}%)", end="", flush=True)


def finalize_progress() -> None:
    print("", flush=True)


def question_similarity(a: Any, b: Any) -> float:
    qa = str(a or "").strip().lower()
    qb = str(b or "").strip().lower()
    if not qa and not qb:
        return 1.0
    if not qa or not qb:
        return 0.0
    return difflib.SequenceMatcher(None, qa, qb).ratio()


def resolve_template_match(
    candidates: List[Dict[str, Any]],
    question: Any,
) -> Dict[str, Any] | None:
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda c: (
            question_similarity(question, c["item"].get("question")),
            -int(c["idx"]),
        ),
    )
    return best


def apply_judgements(
    samplewise_path: str,
    templates_path: str,
    output_templates_path: str,
    log_json_path: str,
    log_txt_path: str,
    *,
    model_name: str,
    workers: int,
    limit: int,
) -> Dict[str, Any]:
    mismatch_records = load_mismatch_records(samplewise_path)
    if limit and limit > 0:
        mismatch_records = mismatch_records[:limit]
    templates = read_json(templates_path)
    if not isinstance(templates, list):
        raise ValueError(f"Expected template JSON list: {templates_path}")

    item_map: Dict[str, List[Dict[str, Any]]] = {}
    for idx, item in enumerate(templates):
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        if item_id is not None:
            item_map.setdefault(str(item_id), []).append({"idx": idx, "item": item})

    if output_templates_path == templates_path:
        backup_path = templates_path + ".bak"
        shutil.copyfile(templates_path, backup_path)
    else:
        backup_path = ""

    log_rows: List[Dict[str, Any]] = []
    updated = 0
    missing_item = 0
    total = len(mismatch_records)

    def judge_one(i: int, rec: Dict[str, Any]) -> Dict[str, Any]:
        record_id = str(rec.get("record_id"))
        candidates = item_map.get(record_id, [])
        mapped = resolve_template_match(candidates, rec.get("question"))
        model = build_model(model_name)
        review = call_gemini_api(
            model,
            rec.get("question", ""),
            rec.get("gold_sql", ""),
            rec.get("pred_sql", ""),
        )

        log_row: Dict[str, Any] = {
            "index": i,
            "item_id": record_id,
            "question": rec.get("question"),
            "gnd_truth_sql": rec.get("gold_sql"),
            "pred_sql": rec.get("pred_sql"),
            "table_match": rec.get("table_match"),
            "llm_decision": review.get("decision"),
            "llm_reason": review.get("reason"),
            "llm_final_sql": review.get("final_sql"),
            "duplicate_candidates": len(candidates),
            "status": "",
        }

        if mapped is None:
            log_row["status"] = "item_not_found"
            return {
                "log_row": log_row,
                "template_update": None,
                "missing_item": 1,
                "updated": 0,
            }

        idx = mapped["idx"]
        item = mapped["item"]
        target_key = choose_target_key(item)
        old_sql = item.get(target_key)
        new_sql = review.get("final_sql") or old_sql
        match_score = question_similarity(rec.get("question"), item.get("question"))

        log_row["target_key"] = target_key
        log_row["old_sql"] = old_sql
        log_row["new_sql"] = new_sql
        log_row["matched_template_question"] = item.get("question")
        log_row["question_match_score"] = match_score
        log_row["status"] = "updated" if review.get("decision") != "error" else "llm_error"
        return {
            "log_row": log_row,
            "template_update": {
                "idx": idx,
                "target_key": target_key,
                "new_sql": new_sql,
            },
            "missing_item": 0,
            "updated": 1 if review.get("decision") != "error" else 0,
        }

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [
            ex.submit(judge_one, i, rec)
            for i, rec in enumerate(mismatch_records, start=1)
        ]
        done = 0
        print_progress(done, total)
        for fut in as_completed(futures):
            result = fut.result()
            log_rows.append(result["log_row"])
            missing_item += int(result["missing_item"])
            updated += int(result["updated"])
            template_update = result["template_update"]
            if template_update is not None:
                templates[template_update["idx"]][template_update["target_key"]] = template_update["new_sql"]
            done += 1
            if done % 5 == 0 or done == total:
                print_progress(done, total)
    finalize_progress()

    log_rows.sort(key=lambda row: int(row.get("index", 0)))

    write_json(output_templates_path, templates)
    write_json(log_json_path, log_rows)

    with open(log_txt_path, "w", encoding="utf-8") as f:
        for row in log_rows:
            f.write(f"item_id: {row.get('item_id')}\n")
            f.write(f"status: {row.get('status')}\n")
            f.write(f"decision: {row.get('llm_decision')}\n")
            f.write(f"duplicate_candidates: {row.get('duplicate_candidates')}\n")
            f.write(f"target_key: {row.get('target_key')}\n")
            f.write(f"question_match_score: {row.get('question_match_score')}\n")
            f.write(f"reason: {row.get('llm_reason')}\n")
            f.write(f"question: {row.get('question')}\n")
            f.write(f"matched_template_question: {row.get('matched_template_question')}\n")
            f.write(f"gnd_truth_sql: {row.get('gnd_truth_sql')}\n")
            f.write(f"pred_sql: {row.get('pred_sql')}\n")
            f.write(f"new_sql: {row.get('new_sql')}\n")
            f.write("\n" + "=" * 100 + "\n\n")

    summary = {
        "samplewise_path": samplewise_path,
        "templates_path": templates_path,
        "output_templates_path": output_templates_path,
        "backup_path": backup_path,
        "log_json_path": log_json_path,
        "log_txt_path": log_txt_path,
        "num_mismatch_records": len(mismatch_records),
        "num_updated": updated,
        "num_missing_item": missing_item,
    }
    return summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--samplewise",
        default="data/data_final/test_generated_sql_nl.schema_q_to_sql_eval.samplewise.json",
        help="Path to the samplewise eval JSON.",
    )
    ap.add_argument(
        "--templates",
        default="data/data_final/test_generated_sql_nl.json",
        help="Path to the template JSON to patch.",
    )
    ap.add_argument(
        "--output_templates",
        default="data/data_final/test_generated_sql_nl.json",
        help="Where to write the patched templates JSON. Defaults to in-place update.",
    )
    ap.add_argument(
        "--log_json",
        default="data/data_final/test_generated_sql_nl.llm_judge_log.json",
        help="Path to the structured review log JSON.",
    )
    ap.add_argument(
        "--log_txt",
        default="data/data_final/test_generated_sql_nl.llm_judge_log.txt",
        help="Path to the human-readable review log.",
    )
    ap.add_argument(
        "--model",
        default=MODEL_NAME,
        help="Gemini model name.",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of concurrent LLM-judge workers.",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If >0, process only the first N mismatched records.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    summary = apply_judgements(
        samplewise_path=args.samplewise,
        templates_path=args.templates,
        output_templates_path=args.output_templates,
        log_json_path=args.log_json,
        log_txt_path=args.log_txt,
        model_name=args.model,
        workers=args.workers,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

# python -m src.eval.llm_judge \
#   --samplewise data/data_final/test_generated_sql_nl.schema_q_to_sql_eval.samplewise.json \
#   --templates data/data_final/test_generated_sql_nl.json \
#   --output_templates data/data_final/test_generated_sql_nl.json \
#   --log_json data/data_final/test_generated_sql_nl.llm_judge_log.json \
#   --log_txt data/data_final/test_generated_sql_nl.llm_judge_log.txt \
#   --workers 8 \
#   --limit 10

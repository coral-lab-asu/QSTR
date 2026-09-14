import os
import json
import time
import random
import argparse

try:
    from .config import load_project_env
except ImportError:
    from config import load_project_env


load_project_env()
import sys
from typing import Any, Dict, List, Optional, Tuple

# Parallelization imports
from concurrent.futures import ThreadPoolExecutor, as_completed


try:
    import google.generativeai as genai
except ImportError:
    genai = None
import pandas as pd
import numpy as np
import duckdb



# ---------------------------
# IO helpers
# ---------------------------
def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


SCHEMA_COLS = [
    "overs",
    "team_runs",
    "bowler",
    "batsman",
    "batsman_runs",
    "batsman_fours",
    "batsman_sixes",
    "batsman_bowls_faced",
    "bowler_bowls_done",
    "bowler_runs_given",
    "bowler_wickets",
]

# ---------------------------
# Schema sample rows
# ---------------------------

def get_schema_sample_rows(match_path: str, n: int = 3) -> List[Dict[str, Any]]:
    """Load up to n sample rows from the match CSV using only SCHEMA_COLS.

    Returns a list of dict rows. Missing columns are filled with None.
    If match_path is missing/unreadable, returns an empty list.
    """
    if not match_path or not os.path.exists(match_path):
        return []
    try:
        import pandas as pd  # local import to avoid making pandas a hard requirement elsewhere
        df = pd.read_csv(match_path, nrows=n)
        rows = []
        for _, r in df.iterrows():
            row_obj = {}
            for c in SCHEMA_COLS:
                row_obj[c] = normalize_cell(r[c]) if c in df.columns else None
            rows.append(row_obj)
        return rows
    except Exception:
        return []

def _print_progress(done: int, total: int, per_setting_done: Dict[str, int], *, prefix: str = "Progress") -> None:
    """Print a single-line progress indicator that updates in-place."""
    pct = (done / total * 100.0) if total else 100.0
    parts = [f"{prefix}: {done}/{total} ({pct:.1f}%)"]
    if per_setting_done:
        parts.append(" | " + ", ".join([f"{k}:{per_setting_done.get(k,0)}" for k in sorted(per_setting_done.keys())]))
    msg = "".join(parts)
    # pad/clear line
    sys.stdout.write("\r" + msg + " " * max(0, 10))
    sys.stdout.flush()


def _finalize_progress() -> None:
    sys.stdout.write("\n")
    sys.stdout.flush()


# ---------------------------
# Cell normalization helper
# ---------------------------
def normalize_cell(x):
    if x is None:
        return None
    # numpy/pandas missing
    try:
        if isinstance(x, float) and (np.isnan(x) or np.isinf(x)):
            return None
        if isinstance(x, (np.floating,)):
            if np.isnan(x) or np.isinf(x):
                return None
            return float(x)
        if isinstance(x, (np.integer,)):
            return int(x)
    except Exception:
        pass

    if isinstance(x, str):
        s = x.strip()
        return s if s != "" else None
    return x


# ---------------------------
# Prompting (SQL + TABLE)
# ---------------------------
SYSTEM_PROMPT_SQL = """
You are an expert SQL writer for cricket match data.

Goal:
- Write a SINGLE SQL query that answers the question using a table named df.
- Output STRICT JSON only, with key: sql.
- No markdown. No explanations.

Constraints:
- Output must be: { "sql": "<SQL STRING>" }
- Use only the columns provided in the schema when schema is given.
- Always reference df as the table name.
- If expected output columns are provided, your SQL MUST SELECT exactly those columns in that order (use aliases as needed).
"""

SYSTEM_PROMPT_TABLE = """
You are an expert cricket analyst and data annotator.

Goal:
- Read ball-by-ball cricket commentary (line-by-line).
- Answer the question by producing a structured table.

Rules:
- Do not invent facts not supported by the text.
- Use null for unknowns.
- Output STRICT JSON only. No markdown. No explanations.
"""

USER_CTX_Q_TO_SQL = """
Context (ball-by-ball commentary lines):
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>

Expected output columns (order preserved):
{headers_json}

Question:
{question}

Return STRICT JSON only:
{{ "sql": "<SQL STRING>" }}
"""

USER_CTX_SCHEMA_Q_TO_SQL = """
Context (ball-by-ball commentary lines):
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>

Schema for table df (columns):
{schema_json}

Example rows (JSON, may be partial / illustrative):
{schema_rows_json}

Expected output columns (order preserved):
{headers_json}

Question:
{question}

Return STRICT JSON only:
{{ "sql": "<SQL STRING>" }}
"""

USER_SCHEMA_Q_TO_SQL = """
Schema for table df (columns):
{schema_json}

Example rows (JSON, may be partial / illustrative):
{schema_rows_json}

Expected output columns (order preserved):
{headers_json}

Question:
{question}

Return STRICT JSON only:
{{ "sql": "<SQL STRING>" }}
"""

# New: context + question -> table (with gold headers)
USER_CTX_Q_TO_TABLE = """
Context (ball-by-ball commentary lines):
<<<COMMENTARY_START>>>
{context}
<<<COMMENTARY_END>>>

Question ID: {qid}
Question: {question}

You MUST output a table with EXACT columns (order preserved):
{headers_json}

Return STRICT JSON only:
{{
  "results": [
    {{
      "question_id": "{qid}",
      "question": "{question}",
      "table": [
        {{ "<col1>": <value|null>, "<col2>": <value|null>, ... }}
      ]
    }}
  ],
  "notes": "",
  "confidence": 0.0-1.0
}}
"""

# ---------------------------
# Robust JSON extraction
# ---------------------------
def extract_json_obj(text: str) -> Any:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass

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
        else:
            if ch in ("'", '"'):
                in_str = True
                quote = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i+1]
                    return json.loads(chunk)

    raise ValueError("Failed to extract JSON object.")


# ---------------------------
# SQL execution (post-processing)
# ---------------------------

def execute_sql_on_match_csv(match_path: str, sql: str) -> pd.DataFrame:
    """Execute SQL against a DuckDB table named df backed by the match CSV."""
    df = pd.read_csv(match_path)
    con = duckdb.connect(database=":memory:")
    con.register("df", df)
    try:
        return con.execute(sql).fetchdf()
    finally:
        try:
            con.close()
        except Exception:
            pass


def df_to_answer_json(df: pd.DataFrame, max_rows: int = 200) -> Dict[str, Any]:
    """Convert a DataFrame to the dataset-style answer JSON."""
    if max_rows and max_rows > 0 and len(df) > max_rows:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns.tolist()]
    rows = [[normalize_cell(v) for v in row] for row in df.to_numpy().tolist()]
    return {"columns": cols, "rows": rows}


def run_predicted_sql_and_attach(pred_rows: List[Dict[str, Any]], *, max_rows: int = 200) -> Tuple[int, int]:
    """For each prediction row that has 'pred_sql', execute it and attach results.

    Adds keys:
      - exec_ok: bool
      - exec_error: str|None
      - pred_result: {columns, rows} (only if exec_ok)

    Returns (num_exec_ok, num_exec_fail).
    """
    ok = 0
    fail = 0
    for r in pred_rows:
        pred_sql = r.get("pred_sql")
        match_path = r.get("match_path")
        if not pred_sql:
            continue
        if not match_path or not os.path.exists(match_path):
            r["exec_ok"] = False
            r["exec_error"] = f"match_path missing or not found: {match_path}"
            fail += 1
            continue
        try:
            out_df = execute_sql_on_match_csv(match_path, pred_sql)
            r["exec_ok"] = True
            r["exec_error"] = None
            r["pred_result"] = df_to_answer_json(out_df, max_rows=max_rows)
            ok += 1
        except Exception as e:
            r["exec_ok"] = False
            r["exec_error"] = str(e)
            fail += 1
    return ok, fail


def call_gemini_sql(model, user_prompt: str) -> Dict[str, Any]:
    stitched = f"SYSTEM:\n{SYSTEM_PROMPT_SQL}\n\nUSER:\n{user_prompt}"
    resp = model.generate_content(stitched)
    text = resp.text if hasattr(resp, "text") else str(resp)
    obj = extract_json_obj(text)
    if not isinstance(obj, dict) or "sql" not in obj:
        raise ValueError("Model did not return {\"sql\": ...}")
    if not isinstance(obj["sql"], str) or not obj["sql"].strip():
        raise ValueError("Returned sql is empty or not a string.")
    return obj

def call_gemini_table(model, user_prompt: str) -> Dict[str, Any]:
    stitched = f"SYSTEM:\n{SYSTEM_PROMPT_TABLE}\n\nUSER:\n{user_prompt}"
    resp = model.generate_content(stitched)
    text = resp.text if hasattr(resp, "text") else str(resp)
    obj = extract_json_obj(text)
    if not isinstance(obj, dict) or "results" not in obj:
        raise ValueError("Model did not return payload with 'results'.")
    return obj




# ---------------------------
# Gold headers for table-output setting
# ---------------------------
def get_gold_headers(item: Dict[str, Any]) -> List[str]:
    ans = item.get("answer") or {}
    cols = ans.get("columns") or []
    return [str(c) for c in cols]


def model_table_to_answer_json(
    model_payload: Dict[str, Any],
    expected_headers: List[str],
) -> Dict[str, Any]:
    """
    Convert model's:
      {"results":[{"table":[{"col":v,...}, ...]}], ...}
    into:
      {"columns":[...], "rows":[[...], ...]}
    using expected_headers order.
    """
    results = model_payload.get("results") or []
    if not results or not isinstance(results, list):
        return {"columns": expected_headers, "rows": []}

    # assume first result corresponds to the asked question
    first = results[0]
    table = first.get("table", [])
    if table is None:
        table = []
    if not isinstance(table, list):
        table = []

    rows = []
    for row_obj in table:
        if not isinstance(row_obj, dict):
            continue
        row = [normalize_cell(row_obj.get(h)) for h in expected_headers]
        rows.append(row)

    return {"columns": expected_headers, "rows": rows}


# ---------------------------
# Experiment runner
# ---------------------------
def run_experiment(
    dataset_jsonl: str,
    api_key: str,
    out_dir: str,
    n_samples: int = 50,
    seed: int = 7,
    model_name: str = "gemini-2.5-flash",
    workers: int = 8,
) -> None:
    if genai is None:
        raise RuntimeError("Install hosted-model dependencies with: pip install -e '.[llm]'")
    ensure_dir(out_dir)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    data = read_jsonl(dataset_jsonl)
    if not data:
        raise RuntimeError(f"Empty dataset: {dataset_jsonl}")

    rng = random.Random(seed)
    sample = rng.sample(data, k=min(n_samples, len(data)))

    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_path = os.path.join(out_dir, run_id)
    ensure_dir(run_path)

    settings = ["CTX_SCHEMA_Q_TO_SQL", "SCHEMA_Q_TO_SQL", "CTX_Q_TO_TABLE"]

    def _choose_setting_for_item(item_id: Any) -> str:
        """Deterministically choose ONE setting based on item_id.

        - If item_id is int-like, use modulo.
        - Otherwise hash the string form.
        """
        try:
            idx = int(item_id) % len(settings)
        except Exception:
            idx = abs(hash(str(item_id))) % len(settings)
        return settings[idx]

    preds = []
    fails = []
    prompt_rows = []

    def run_one(
        setting: str,
        item: Dict[str, Any],
        record_id: str,
        question: str,
        context: str,
        match_path: str,
        gold_answer: Dict[str, Any],
        gold_sql: Any,
        schema_cols: List[str],
        schema_rows: List[Dict[str, Any]],
        gold_headers: List[str],
    ) -> Dict[str, Any]:
        """Run one (record, setting) task.

        Returns a dict with keys:
          - ok: bool
          - pred_row: dict (if ok)
          - fail_row: dict (if not ok)
          - prompt_row: dict
        """
        try:
            if setting == "CTX_Q_TO_SQL":
                user_prompt = USER_CTX_Q_TO_SQL.format(
                    context=context,
                    headers_json=json.dumps(gold_headers, ensure_ascii=False),
                    question=question,
                )
                system_prompt_used = SYSTEM_PROMPT_SQL
                user_prompt_used = user_prompt

                model_out = call_gemini_sql(model, user_prompt)
                pred_sql = model_out["sql"].strip()

                pred_row = {
                    "setting": setting,
                    "record_id": record_id,
                    "question": question,
                    "match_path": match_path,
                    "gold_sql": gold_sql,
                    "gold_answer": gold_answer,
                    "expected_headers": gold_headers,
                    "pred_sql": pred_sql,
                    "raw_model_output": model_out,
                }

            elif setting == "CTX_SCHEMA_Q_TO_SQL":
                user_prompt = USER_CTX_SCHEMA_Q_TO_SQL.format(
                    context=context,
                    schema_json=json.dumps(schema_cols, ensure_ascii=False),
                    schema_rows_json=json.dumps(schema_rows, ensure_ascii=False),
                    headers_json=json.dumps(gold_headers, ensure_ascii=False),
                    question=question,
                )
                system_prompt_used = SYSTEM_PROMPT_SQL
                user_prompt_used = user_prompt

                model_out = call_gemini_sql(model, user_prompt)
                pred_sql = model_out["sql"].strip()

                pred_row = {
                    "setting": setting,
                    "record_id": record_id,
                    "question": question,
                    "match_path": match_path,
                    "gold_sql": gold_sql,
                    "gold_answer": gold_answer,
                    "schema_cols": schema_cols,
                    "expected_headers": gold_headers,
                    "pred_sql": pred_sql,
                    "raw_model_output": model_out,
                }

            elif setting == "SCHEMA_Q_TO_SQL":
                user_prompt = USER_SCHEMA_Q_TO_SQL.format(
                    schema_json=json.dumps(schema_cols, ensure_ascii=False),
                    schema_rows_json=json.dumps(schema_rows, ensure_ascii=False),
                    headers_json=json.dumps(gold_headers, ensure_ascii=False),
                    question=question,
                )
                system_prompt_used = SYSTEM_PROMPT_SQL
                user_prompt_used = user_prompt

                model_out = call_gemini_sql(model, user_prompt)
                pred_sql = model_out["sql"].strip()

                pred_row = {
                    "setting": setting,
                    "record_id": record_id,
                    "question": question,
                    "match_path": match_path,
                    "gold_sql": gold_sql,
                    "gold_answer": gold_answer,
                    "schema_cols": schema_cols,
                    "expected_headers": gold_headers,
                    "pred_sql": pred_sql,
                    "raw_model_output": model_out,
                }

            elif setting == "CTX_Q_TO_TABLE":
                user_prompt = USER_CTX_Q_TO_TABLE.format(
                    context=context,
                    qid=record_id,
                    question=question,
                    headers_json=json.dumps(gold_headers, ensure_ascii=False),
                )
                system_prompt_used = SYSTEM_PROMPT_TABLE
                user_prompt_used = user_prompt

                model_payload = call_gemini_table(model, user_prompt)
                pred_answer = model_table_to_answer_json(model_payload, gold_headers)

                pred_row = {
                    "setting": setting,
                    "record_id": record_id,
                    "question": question,
                    "match_path": match_path,
                    "gold_answer": gold_answer,
                    "expected_headers": gold_headers,
                    "pred_answer": pred_answer,
                    "raw_model_output": model_payload,
                }

            else:
                raise ValueError(f"Unknown setting: {setting}")

            stitched_prompt_used = f"SYSTEM:\n{system_prompt_used}\n\nUSER:\n{user_prompt_used}"
            prompt_row = {
                "setting": setting,
                "record_id": record_id,
                "question": question,
                "match_path": match_path,
                "system_prompt": system_prompt_used,
                "user_prompt": user_prompt_used,
                "stitched_prompt": stitched_prompt_used,
            }

            return {"ok": True, "pred_row": pred_row, "prompt_row": prompt_row}

        except Exception as e:
            # still capture prompt when possible
            prompt_row = None
            try:
                stitched_prompt_used = f"SYSTEM:\n{system_prompt_used}\n\nUSER:\n{user_prompt_used}"  # type: ignore
                prompt_row = {
                    "setting": setting,
                    "record_id": record_id,
                    "question": question,
                    "match_path": match_path,
                    "system_prompt": system_prompt_used,  # type: ignore
                    "user_prompt": user_prompt_used,      # type: ignore
                    "stitched_prompt": stitched_prompt_used,
                }
            except Exception:
                pass

            fail_row = {
                "setting": setting,
                "record_id": record_id,
                "question": question,
                "error": str(e),
            }
            out = {"ok": False, "fail_row": fail_row}
            if prompt_row is not None:
                out["prompt_row"] = prompt_row
            return out

    # Some items may run only one setting (when item_id is present)
    total_tasks = 0
    for item in sample:
        total_tasks += 1 if item.get("item_id") is not None else len(settings)
    done_tasks = 0
    per_setting_done = {s: 0 for s in settings}
    _print_progress(done_tasks, total_tasks, per_setting_done)

    # Build tasks
    tasks = []
    for i, item in enumerate(sample):
        record_id = item.get("record_id", f"s{i}")
        question = item.get("question", "")
        context = item.get("context_full", "")
        match_path = item.get("match_path")
        gold_answer = item.get("answer", {"columns": [], "rows": []})
        gold_sql = item.get("sql")

        schema_cols = SCHEMA_COLS
        schema_rows = get_schema_sample_rows(match_path, n=3)
        gold_headers = get_gold_headers(item)

        # Choose which prompt/template setting to run for this item.
        # If item_id exists, run exactly ONE setting deterministically based on item_id.
        # Otherwise, fall back to running all settings (previous behavior).
        item_id = item.get("item_id")
        if item_id is not None:
            item_settings = [_choose_setting_for_item(item_id)]
        else:
            item_settings = settings

        for setting in item_settings:
            tasks.append((setting, item, record_id, question, context, match_path, gold_answer, gold_sql, schema_cols, schema_rows, gold_headers))

    # Run tasks in parallel
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_one, *t) for t in tasks]
        for fut in as_completed(futs):
            res = fut.result()

            if res.get("prompt_row") is not None:
                prompt_rows.append(res["prompt_row"])

            if res.get("ok"):
                preds.append(res["pred_row"])
            else:
                fails.append(res["fail_row"])

            # progress update
            done_tasks += 1
            setting = (res.get("pred_row") or res.get("fail_row") or {}).get("setting")
            if setting in per_setting_done:
                per_setting_done[setting] += 1

            if done_tasks % 5 == 0 or done_tasks == total_tasks:
                _print_progress(done_tasks, total_tasks, per_setting_done)

    _print_progress(done_tasks, total_tasks, per_setting_done, prefix="Completed")
    _finalize_progress()

    # Post-process: execute predicted SQL for SQL settings and attach results
    print("Executing predicted SQL against intended match tables...")
    exec_ok_n, exec_fail_n = run_predicted_sql_and_attach(preds, max_rows=200)
    print(f"SQL execution complete. OK: {exec_ok_n}, Fail: {exec_fail_n}")

    # Save outputs
    write_jsonl(os.path.join(run_path, "predictions.jsonl"), preds)
    write_jsonl(os.path.join(run_path, "failures.jsonl"), fails)
    write_jsonl(os.path.join(run_path, "prompts.jsonl"), prompt_rows)

    # Convenience: write a separate SQL execution results file
    sql_exec_rows = [
        {
            "setting": p.get("setting"),
            "record_id": p.get("record_id"),
            "question": p.get("question"),
            "match_path": p.get("match_path"),
            "pred_sql": p.get("pred_sql"),
            "exec_ok": p.get("exec_ok"),
            "exec_error": p.get("exec_error"),
            "pred_result": p.get("pred_result"),
        }
        for p in preds if p.get("pred_sql")
    ]
    write_jsonl(os.path.join(run_path, "sql_exec_results.jsonl"), sql_exec_rows)

    # Summary aggregates
    summary = {
        "run_id": run_id,
        "dataset": dataset_jsonl,
        "n_samples": len(sample),
        "settings": settings,
        "model": model_name,
        "seed": seed,
        "num_predictions": len(preds),
        "num_failures": len(fails),
        "num_prompts": len(prompt_rows),
        "out_path": run_path,
        "prompts_path": os.path.join(run_path, "prompts.jsonl"),
        "sql_exec_ok": exec_ok_n,
        "sql_exec_fail": exec_fail_n,
        "sql_exec_results_path": os.path.join(run_path, "sql_exec_results.jsonl"),
    }
    write_json(os.path.join(run_path, "summary.json"), summary)

    print("✅ Done")
    print(json.dumps(summary, indent=2))


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="output/dataset_runs/v1/dataset.jsonl")
    ap.add_argument(
        "--roi_config",
        default="",
        help="Path to ROI JSON config (contains analysis_paths). If set, runs a small sample from each analysis_paths dataset.",
    )
    ap.add_argument(
        "--roi_n_per_split",
        type=int,
        default=0,
        help="If >0 and --roi_config is set, number of samples to run per ROI split dataset (e.g., 10 or 20).",
    )
    ap.add_argument("--out_dir", default="runs_sql_table_settings")
    ap.add_argument("--api_key", default="", help="Or set env GEMINI_API_KEY")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--workers", type=int, default=8)
    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    api_key = args.api_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("Provide Gemini API key via --api_key or env GEMINI_API_KEY")

    # If ROI config is provided, run small samples from each ROI split dataset (analysis_paths)
    if args.roi_config and args.roi_n_per_split and args.roi_n_per_split > 0:
        with open(args.roi_config, "r", encoding="utf-8") as f:
            roi_cfg = json.load(f)

        analysis_paths = roi_cfg.get("analysis_paths") or {}
        if not isinstance(analysis_paths, dict) or not analysis_paths:
            raise RuntimeError(f"ROI config has no analysis_paths dict: {args.roi_config}")

        # Put ROI runs under a dedicated subfolder
        roi_out_dir = os.path.join(args.out_dir, "roi_splits")
        ensure_dir(roi_out_dir)

        print(f"Running ROI split suite from: {args.roi_config}")
        print(f"Per-split samples: {args.roi_n_per_split}")

        # Run each split dataset; keep going if some split files are missing
        for split_name, split_path in analysis_paths.items():
            if not split_path or not isinstance(split_path, str):
                print(f"[SKIP] {split_name}: invalid path: {split_path}")
                continue
            if not os.path.exists(split_path):
                print(f"[SKIP] {split_name}: file not found: {split_path}")
                continue

            split_out_dir = os.path.join(roi_out_dir, split_name)
            print(f"\n=== ROI SPLIT: {split_name} ===")
            print(f"Dataset: {split_path}")
            print(f"Output:  {split_out_dir}")

            run_experiment(
                dataset_jsonl=split_path,
                api_key=api_key,
                out_dir=split_out_dir,
                n_samples=args.roi_n_per_split,
                seed=args.seed,
                model_name=args.model,
                workers=args.workers,
            )

    # Default: run the single dataset provided by --dataset
    else:
        run_experiment(
            dataset_jsonl=args.dataset,
            api_key=api_key,
            out_dir=args.out_dir,
            n_samples=args.n,
            seed=args.seed,
            model_name=args.model,
            workers=args.workers,
        )


# python3 run_settings_gemini.py \
#   --roi_config output/dataset_runs/roi_test/roi_config.json \
#   --roi_n_per_split 20 \
#   --out_dir runs_sql_table_settings \
#   --seed 42 \
#   --model gemini-2.5-flash \
#   --workers 8

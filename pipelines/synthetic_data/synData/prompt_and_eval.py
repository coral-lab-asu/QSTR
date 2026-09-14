"""
prompt_and_eval.py — Run inference (Gemini 2.5 Flash) + evaluation on shopkeeper sessions.

Requirements:
  pip install pandas numpy google-genai
  Optional: pip install python-dotenv  (loads .env from project root)

Usage:
  - Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment or in .env at project root.
  - Ensure gold_questions_answers.json and question_schemas.json exist in synData/.
  - Run: python synData/prompt_and_eval.py  (or from synData: python prompt_and_eval.py)

Outputs:
  - synData/experiment/<session_id>/Q1.txt .. Q10.txt  (per-question prompt + model output)
  - synData/experiment/results.txt, results_by_session.csv, results_detail.csv
  - synData/model_eval_summary.csv
"""

import json
import os
import re
import time
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional

# Load .env from project root (parent of synData) if python-dotenv is available
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(_SCRIPT_DIR), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

from google import genai
from google.genai import types

# ----------------------------
# Config: Gemini 2.5 Flash via google-genai
# ----------------------------
GEMINI_MODEL = "gemini-2.5-flash"
API_KEY = os.environ.get("GEMINI_API_KEY") or ""

# How model responses are parsed from text into JSON
JSON_EXTRACTOR_RE = re.compile(r"(\[.*\])", re.DOTALL)  # naive: extract the first JSON array in the text

# Numeric tolerance for "correct" numeric answers
NUM_TOL = 0.4

# Timeout (seconds) for each model call; passed to the HTTP client (milliseconds)
API_TIMEOUT_SEC = 120
# Retries on read timeout (transient network/server slowness)
API_TIMEOUT_RETRIES = 2

# Paths relative to this script's directory so pipeline works from any cwd
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_JSONL = os.path.join(_SCRIPT_DIR, "shopkeeper_sessions", "sessions.jsonl")
GOLD_QA_JSON = os.path.join(_SCRIPT_DIR, "gold_questions_answers.json")
EXPERIMENT_DIR = os.path.join(_SCRIPT_DIR, "experiment")
_QUESTION_SCHEMAS_PATH = os.path.join(_SCRIPT_DIR, "question_schemas.json")
_PRODUCTS_JSON_PATH = os.path.join(_SCRIPT_DIR, "products.json")

def _load_question_schemas():
    if os.path.exists(_QUESTION_SCHEMAS_PATH):
        with open(_QUESTION_SCHEMAS_PATH, "r", encoding="utf-8") as f:
            return {q["qid"]: q for q in json.load(f)}
    raise FileNotFoundError(
        f"question_schemas.json not found at {_QUESTION_SCHEMAS_PATH}. "
        "Run: python sample_questions.py (from synData) or copy question_schemas.json into synData/"
    )

QUESTION_SCHEMAS = _load_question_schemas()

def _load_product_catalog():
    if os.path.exists(_PRODUCTS_JSON_PATH):
        with open(_PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError(
        f"products.json not found at {_PRODUCTS_JSON_PATH}. "
        "Ensure the catalog exists in synData/."
    )

PRODUCT_CATALOG = _load_product_catalog()

# ----------------------------
# Gemini client (google-genai) — created once, reused
# ----------------------------
def _get_gemini_client():
    if not API_KEY:
        raise ValueError(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment or in .env at the project root."
        )
    # timeout in milliseconds for the underlying HTTP client
    http_options = types.HttpOptions(timeout=API_TIMEOUT_SEC * 1000)
    return genai.Client(api_key=API_KEY, http_options=http_options)


# ----------------------------
# Structured JSON: build schema for "array of objects" from question columns
# ----------------------------
def _question_schema_to_json_schema(question_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a JSON Schema for an array of row objects so Gemini returns application/json.
    Used with response_mime_type='application/json' and response_json_schema=...
    """
    columns = question_schema.get("columns", [])
    props = {}
    required = []
    type_map = {"string": "string", "number": "number", "integer": "integer"}
    for c in columns:
        name = c.get("name", "")
        if not name:
            continue
        required.append(name)
        t = (c.get("type") or "string").lower()
        props[name] = {"type": type_map.get(t, "string")}
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


# ----------------------------
# Helper: call model API (Gemini 2.5 Flash via google-genai)
# ----------------------------
def call_model_api(
    prompt: str,
    max_tokens: int = 32000,
    temperature: float = 0.0,
    response_json_schema: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Call Gemini 2.5 Flash via google-genai; returns raw text.
    If response_json_schema is provided, sets response_mime_type='application/json'
    so the model returns structured JSON (e.g. array of objects).
    """
    client = _get_gemini_client()
    config_dict: Dict[str, Any] = {
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_json_schema is not None:
        config_dict["response_mime_type"] = "application/json"
        config_dict["response_json_schema"] = response_json_schema
    last_error = None
    for attempt in range(API_TIMEOUT_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(**config_dict),
            )
            if response.text is not None:
                return response.text
            return "(empty or blocked)"
        except Exception as e:
            last_error = e
            if "timeout" in str(e).lower() or "Timeout" in type(e).__name__:
                if attempt < API_TIMEOUT_RETRIES:
                    time.sleep(2.0 * (attempt + 1))
                    continue
            raise
    if last_error is not None:
        raise last_error
    return "(empty or blocked)"

# ----------------------------
# Build a prompt for the model
# ----------------------------
def build_prompt(question_schema: Dict[str,Any], transcript_lines: List[str]) -> str:
    """
    Build a clear instruction + schema + transcript prompt asking the model to return JSON array rows.
    """
    q_text = question_schema["question"]
    cols = question_schema["columns"]
    col_desc = ", ".join([f"{c['name']} ({c['type']})" + (": "+c.get("description","") if c.get("description") else "") for c in cols])
    instructions = [
        "You are given a shopkeeper transcript. Answer the question by returning a JSON array (not prose).",
        f"Question: {q_text}",
        f"Return an array of objects where each object has these fields (exact names and types): {col_desc}.",
        "Numeric (number) fields must be numbers (floats allowed) and monetary values rounded to 2 decimals.",
        "Return ONLY the JSON array (no additional text).",
        "Example: [{" + ", ".join(f'"{c["name"]}": ...' for c in cols) + "}]"
    ]
    # include a short product catalog so the model can map names to product_ids
    catalog_lines = [
        f"{p.get('product_id')} -> {p.get('name')}"
        for p in PRODUCT_CATALOG
        if p.get("product_id") and p.get("name")
    ]
    catalog_block = "Product Catalog:\n" + "\n".join(catalog_lines)
    # include the deterministic transcript (as plain lines)
    prompt = "\n".join(instructions) + "\n\n" + catalog_block + "\n\nTranscript:\n" + "\n".join(transcript_lines[-500:])  # include last 500 lines if long
    prompt += "\n\nReturn JSON array now:"
    return prompt

# ----------------------------
# Parse model text to JSON array
# ----------------------------
def extract_json_array_from_text(text: str) -> List[Dict[str,Any]]:
    # try direct json.loads first
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    # try to extract a JSON array substring
    m = JSON_EXTRACTOR_RE.search(text)
    if m:
        sub = m.group(1)
        # try to fix common trailing commas issues
        sub = re.sub(r",\s*]", "]", sub)
        sub = re.sub(r",\s*}", "}", sub)
        try:
            parsed = json.loads(sub)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    # fallback: return empty list
    return []

# ----------------------------
# Evaluation metrics
# ----------------------------
def numeric_rmse(pred_vals: List[float], gold_vals: List[float]) -> float:
    if len(pred_vals) == 0:
        return float("nan")
    arr = np.array(pred_vals) - np.array(gold_vals)
    return float(np.sqrt(np.mean(arr * arr)))

def compare_tables_and_score(schema: Dict[str,Any], model_rows: List[Dict[str,Any]], gold_answer: Any) -> Dict[str,Any]:
    """
    Returns a dict with:
      - ok_schema (bool) and schema_errors (list)
      - accuracy (float): fraction of numeric cells within NUM_TOL (or precision@k for top-k)
      - rmse (float): RMSE across numeric cells
      - details for debugging
    """
    # Gold answer shape depends on qid
    qid = schema["qid"]
    result = {"qid": qid, "schema_ok": True, "schema_errors": [], "accuracy": None, "rmse": None, "details": {}}

    # Simple schema validation: presence of required columns
    required_cols = [c["name"] for c in schema["columns"]]
    missing = []
    for r in model_rows:
        for c in required_cols:
            if c not in r:
                missing.append(c)
    if missing:
        result["schema_ok"] = False
        result["schema_errors"].append(f"Missing columns: {sorted(set(missing))}")
    # Convert gold into a better lookup depending on q
    # Q1/Q2: gold is a list of rows for all products: match by product_id
    numeric_cols = [c["name"] for c in schema["columns"] if c["type"]=="number"]
    # helper to extract numbers safely
    def safe_num(x):
        try:
            return float(x)
        except Exception:
            return float("nan")

    if qid in ("Q1","Q2"):
        # build gold lookup by product_id
        gold_lookup = {row["product_id"]: row for row in gold_answer}
        pred_lookup = {row.get("product_id"): row for row in model_rows}
        # iterate over all gold products
        total_cells = 0
        correct_cells = 0
        pred_vals = []
        gold_vals = []
        for pid, gold_row in gold_lookup.items():
            pred_row = pred_lookup.get(pid)
            for nc in numeric_cols:
                total_cells += 1
                gold_val = safe_num(gold_row.get(nc, 0.0))
                if pred_row is None:
                    # missing row => count as incorrect, i.e., predicted value = NaN
                    continue
                pred_val = safe_num(pred_row.get(nc, float("nan")))
                pred_vals.append(pred_val)
                gold_vals.append(gold_val)
                if math.isfinite(pred_val) and abs(pred_val - gold_val) <= NUM_TOL:
                    correct_cells += 1
        result["accuracy"] = (correct_cells / total_cells) if total_cells>0 else None
        result["rmse"] = numeric_rmse(pred_vals, gold_vals)
        result["details"]["total_cells"] = total_cells
        result["details"]["correct_cells"] = correct_cells

    elif qid in ("Q3","Q4"):
        # customer-level lists. We'll match by customer_id
        gold_lookup = {row["customer_id"]: row for row in gold_answer}
        pred_lookup = {row.get("customer_id"): row for row in model_rows}
        total_cells = 0; correct_cells = 0
        pred_vals = []; gold_vals = []
        for cid, gold_row in gold_lookup.items():
            for nc in numeric_cols:
                total_cells += 1
                gold_val = safe_num(gold_row.get(nc, 0.0))
                pred_row = pred_lookup.get(cid)
                if pred_row is None:
                    continue
                pred_val = safe_num(pred_row.get(nc, float("nan")))
                pred_vals.append(pred_val); gold_vals.append(gold_val)
                if math.isfinite(pred_val) and abs(pred_val - gold_val) <= NUM_TOL:
                    correct_cells += 1
        result["accuracy"] = (correct_cells / total_cells) if total_cells>0 else None
        result["rmse"] = numeric_rmse(pred_vals, gold_vals)
        result["details"]["total_cells"] = total_cells
        result["details"]["correct_cells"] = correct_cells

    elif qid in ("Q5","Q6"):
        # top-k tasks: gold_answer is a list of top-k rows (product_id...). We compute precision@k
        k = schema.get("constraints", {}).get("top_k", 5)
        gold_set = set([r["product_id"] for r in gold_answer[:k]])
        pred_set = []
        # model may include rank; but we only need the product ids
        for r in model_rows[:k]:
            pid = r.get("product_id")
            if pid:
                pred_set.append(pid)
        pred_set = set(pred_set)
        if len(pred_set)==0:
            precision_at_k = 0.0
        else:
            precision_at_k = len(pred_set & gold_set) / float(k)
        result["accuracy"] = precision_at_k
        # RMSE over numeric column (revenue or qty) if present and product matched by id
        pred_map = {r.get("product_id"): r for r in model_rows}
        pred_vals=[]; gold_vals=[]
        for g in gold_answer[:k]:
            pid = g["product_id"]
            gold_num = safe_num(g.get(numeric_cols[0]) if numeric_cols else 0.0)
            pred_row = pred_map.get(pid)
            if pred_row:
                pred_num = safe_num(pred_row.get(numeric_cols[0], float("nan")))
                pred_vals.append(pred_num); gold_vals.append(gold_num)
        result["rmse"] = numeric_rmse(pred_vals, gold_vals) if pred_vals else None
        result["details"]["gold_top_k"] = list(gold_set)
        result["details"]["pred_top_k"] = list(pred_set)

    elif qid in ("Q7","Q8"):
        # scalar: single-row table with one numeric column
        if len(model_rows)==0:
            result["accuracy"] = 0.0
            result["rmse"] = None
        else:
            mval = safe_num(model_rows[0].get(list(model_rows[0].keys())[0], float("nan")))
            gold_val = safe_num(gold_answer)
            result["accuracy"] = 1.0 if math.isfinite(mval) and abs(mval - gold_val) <= NUM_TOL else 0.0
            result["rmse"] = numeric_rmse([mval], [gold_val])
            result["details"]["pred"] = mval
            result["details"]["gold"] = gold_val

    elif qid == "Q9":
        # category-level revenues: match by category string
        gold_lookup = {row["category"]: row for row in gold_answer}
        pred_lookup = {row.get("category"): row for row in model_rows}
        total_cells=0; correct_cells=0; pred_vals=[]; gold_vals=[]
        for cat, gold_row in gold_lookup.items():
            total_cells += 1
            gval = safe_num(gold_row.get("revenue", 0.0))
            pred_row = pred_lookup.get(cat)
            if pred_row:
                pval = safe_num(pred_row.get("revenue", float("nan")))
                pred_vals.append(pval); gold_vals.append(gval)
                if math.isfinite(pval) and abs(pval - gval) <= NUM_TOL:
                    correct_cells += 1
        result["accuracy"] = (correct_cells / total_cells) if total_cells>0 else None
        result["rmse"] = numeric_rmse(pred_vals, gold_vals)
        result["details"]["total_cells"]=total_cells
        result["details"]["correct_cells"]=correct_cells

    elif qid == "Q10":
        # average order value per customer
        gold_lookup = {row["customer_id"]: row for row in gold_answer}
        pred_lookup = {row.get("customer_id"): row for row in model_rows}
        total_cells=0; correct_cells=0; pred_vals=[]; gold_vals=[]
        for cid, gold_row in gold_lookup.items():
            total_cells += 1
            gval = safe_num(gold_row.get("average_order_value", 0.0))
            pred_row = pred_lookup.get(cid)
            if pred_row:
                pval = safe_num(pred_row.get("average_order_value", float("nan")))
                pred_vals.append(pval); gold_vals.append(gval)
                if math.isfinite(pval) and abs(pval - gval) <= NUM_TOL:
                    correct_cells += 1
        result["accuracy"] = (correct_cells / total_cells) if total_cells>0 else None
        result["rmse"] = numeric_rmse(pred_vals, gold_vals)
        result["details"]["total_cells"]=total_cells
        result["details"]["correct_cells"]=correct_cells

    else:
        result["schema_ok"] = False
        result["schema_errors"].append("Unknown QID")
    return result

# ----------------------------
# Experiment logging: write / read session-wise logs (one txt per question)
# ----------------------------
def _experiment_log_path(experiment_dir: str, session_id: str, qid: str) -> str:
    return os.path.join(experiment_dir, session_id, f"{qid}.txt")


def _read_experiment_log_output(experiment_dir: str, session_id: str, qid: str) -> Optional[str]:
    """If experiment/<session_id>/<qid>.txt exists, return the OUTPUT section content; else None."""
    path = _experiment_log_path(experiment_dir, session_id, qid)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if "---OUTPUT---" in text:
            return text.split("---OUTPUT---", 1)[1].strip()
    except Exception:
        return None
    return None


def _write_experiment_log(experiment_dir: str, session_id: str, qid: str, prompt: str, model_output: str) -> None:
    """Write one log file: experiment/<session_id>/<qid>.txt with INPUT and OUTPUT sections."""
    session_log_dir = os.path.join(experiment_dir, session_id)
    os.makedirs(session_log_dir, exist_ok=True)
    path = _experiment_log_path(experiment_dir, session_id, qid)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"session_id={session_id}\nqid={qid}\n\n")
        f.write("---INPUT---\n")
        f.write(prompt)
        f.write("\n\n---OUTPUT---\n")
        f.write(model_output)
    return path


# ----------------------------
# High-level evaluation loop for one session
# ----------------------------
def evaluate_session_with_model(
    session: Dict[str, Any],
    verbose: bool = False,
    experiment_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    For each question in QUESTION_SCHEMAS:
      - Build prompt + transcript
      - Call model
      - Optionally write experiment log to experiment_dir/<session_id>/<qid>.txt
      - Parse JSON array
      - Compare to gold (compute accuracy & RMSE)
    Returns a dict of per-question evaluations.
    """
    # transcript lines
    transcript = session["transcript"]
    session_id = session["session_id"]
    session_results = {"session_id": session_id, "per_question": []}
    if "gold_answers" not in session:
        raise ValueError("Session must include 'gold_answers' mapping QIDs to gold answers. Add them when generating sessions.")
    gold_answers = session["gold_answers"]

    for qid, schema in QUESTION_SCHEMAS.items():
        prompt = build_prompt(schema, transcript)
        # If this question was already run (log file exists), reuse its output and skip the API call
        if experiment_dir:
            existing = _read_experiment_log_output(experiment_dir, session_id, qid)
            if existing is not None:
                raw_out = existing
                if verbose:
                    print(f"  {qid}: using cached output (already run)")
            else:
                json_schema = _question_schema_to_json_schema(schema)
                raw_out = call_model_api(prompt, response_json_schema=json_schema)
                _write_experiment_log(experiment_dir, session_id, qid, prompt, raw_out)
        else:
            json_schema = _question_schema_to_json_schema(schema)
            raw_out = call_model_api(prompt, response_json_schema=json_schema)
        json_rows = extract_json_array_from_text(raw_out)
        # basic fallback: if model returns object instead of array, try to wrap
        if isinstance(json_rows, dict):
            json_rows = [json_rows]
        # validate & compare
        res = compare_tables_and_score({"qid": qid, **schema}, json_rows, gold_answers[qid])
        res["model_raw_output"] = raw_out[:2000]  # keep short snippet
        res["model_rows"] = json_rows
        session_results["per_question"].append(res)
        if verbose:
            print(f"Q {qid}: acc={res['accuracy']}, rmse={res['rmse']}, schema_ok={res['schema_ok']}")
        # small delay to avoid rate limit
        time.sleep(0.2)
    return session_results

# ----------------------------
# Utilities: compute gold answers from events (adapt / paste compute_answers_from_events code)
# ----------------------------
def compute_gold_answers_from_events(events: List[Dict[str,Any]], product_catalog: List[Dict[str,Any]]) -> Dict[str,Any]:
    # replicate the logic from your compute_answers_from_events previously
    # (This function must produce exactly the same structures used by the comparator.)
    # For brevity we call into a simplified aggregator: assume you already have a function in dataset_tools.
    # You should paste the 'compute_answers_from_events' here (omitted for brevity).
    raise NotImplementedError("Paste your compute_answers_from_events implementation here so gold answers can be computed.")

# ----------------------------
# Results file: avg by session and overall
# ----------------------------
def _safe_mean(values: List[Optional[float]]) -> Optional[float]:
    """Mean of numeric values; ignores None and NaN."""
    valid = [v for v in values if v is not None and math.isfinite(v)]
    if not valid:
        return None
    return sum(valid) / len(valid)


def write_results_file(all_results: List[Dict[str, Any]], out_path: str) -> None:
    """Write results file with avg numbers by session and overall."""
    rows = []
    for sess in all_results:
        sid = sess["session_id"]
        for qres in sess["per_question"]:
            rows.append({
                "session_id": sid,
                "qid": qres["qid"],
                "schema_ok": qres["schema_ok"],
                "accuracy": qres["accuracy"],
                "rmse": qres["rmse"],
            })
    df = pd.DataFrame(rows)

    # Per-session averages
    session_agg = df.groupby("session_id").agg(
        avg_accuracy=("accuracy", lambda s: _safe_mean(s.tolist())),
        avg_rmse=("rmse", lambda s: _safe_mean(s.tolist())),
        n_questions=("qid", "count"),
    ).reset_index()

    # Overall averages (all session–question pairs)
    all_acc = [r["accuracy"] for r in rows if r["accuracy"] is not None and math.isfinite(r["accuracy"])]
    all_rmse = [r["rmse"] for r in rows if r["rmse"] is not None and math.isfinite(r["rmse"])]
    overall_avg_accuracy = sum(all_acc) / len(all_acc) if all_acc else None
    overall_avg_rmse = sum(all_rmse) / len(all_rmse) if all_rmse else None

    lines = [
        "=== EVALUATION RESULTS ===",
        "",
        "--- By session ---",
        session_agg.to_string(index=False),
        "",
        "--- Overall (all sessions, all questions) ---",
        f"mean accuracy: {overall_avg_accuracy if overall_avg_accuracy is not None else 'N/A'}",
        f"mean RMSE:     {overall_avg_rmse if overall_avg_rmse is not None else 'N/A'}",
        f"total (session, question) pairs: {len(rows)}",
        "",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # Also save per-session and flat CSV next to it
    base = os.path.splitext(out_path)[0]
    session_agg.to_csv(f"{base}_by_session.csv", index=False)
    df.to_csv(f"{base}_detail.csv", index=False)
    print(f"Wrote {out_path}, {base}_by_session.csv, {base}_detail.csv")


# ----------------------------
# Example main loop (load from gold_questions_answers.json; write experiment logs + results)
# ----------------------------
if __name__ == "__main__":
    # Load sessions with gold answers (from gold_questions_answers.json)
    if os.path.exists(GOLD_QA_JSON):
        with open(GOLD_QA_JSON, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        print(f"Loaded {len(sessions)} sessions from {GOLD_QA_JSON}")
    else:
        if not os.path.exists(SESSIONS_JSONL):
            raise FileNotFoundError(f"Neither {GOLD_QA_JSON} nor {SESSIONS_JSONL} found. Run generate_gold_qa.py first.")
        sessions = []
        with open(SESSIONS_JSONL, "r", encoding="utf-8") as fr:
            for line in fr:
                sessions.append(json.loads(line))
        for s in sessions:
            if "gold_answers" not in s:
                raise RuntimeError("Sessions from JSONL lack gold_answers. Use gold_questions_answers.json (run generate_gold_qa.py).")

    os.makedirs(EXPERIMENT_DIR, exist_ok=True)

    all_results = []
    for s in sessions:
        print("Evaluating", s["session_id"])
        res = evaluate_session_with_model(s, verbose=True, experiment_dir=EXPERIMENT_DIR)
        all_results.append(res)

    # Summary CSV (legacy location)
    rows = []
    for sess in all_results:
        for qres in sess["per_question"]:
            rows.append({
                "session_id": sess["session_id"],
                "qid": qres["qid"],
                "schema_ok": qres["schema_ok"],
                "accuracy": qres["accuracy"],
                "rmse": qres["rmse"],
            })
    pd.DataFrame(rows).to_csv(os.path.join(_SCRIPT_DIR, "model_eval_summary.csv"), index=False)

    # Results file: avg by session + overall
    results_path = os.path.join(EXPERIMENT_DIR, "results.txt")
    write_results_file(all_results, results_path)
    print("Done.")

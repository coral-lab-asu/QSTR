import json
import math
import os
import argparse
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional

import numpy as np

SETTING_TO_PRED_KEY = {
    # SQL settings: evaluate executed SQL output
    "CTX_Q_TO_SQL": "pred_result",
    "CTX_SCHEMA_Q_TO_SQL": "pred_result",
    "SCHEMA_Q_TO_SQL": "pred_result",
    # Table setting: evaluate model-returned table
    "CTX_Q_TO_TABLE": "pred_answer",
}

ALL_SETTINGS = list(SETTING_TO_PRED_KEY.keys())


# -----------------------
# IO
# -----------------------
def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


# Helper functions for best-effort extraction from dicts
def _first_str(d: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _first_any(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return None



def build_dataset_map(dataset_path: str) -> Dict[str, Dict[str, Any]]:
    """Map record_id -> metadata used for eval + error inspection.

    Stored fields (best-effort based on dataset schema):
      - primary_key: list|None
      - gold_answer: dict
      - question: str|None
      - gold_sql: str|None
      - db_id: str|None
      - any extra passthrough fields that can help debugging
    """
    m: Dict[str, Dict[str, Any]] = {}
    for item in read_jsonl(dataset_path):
        rid = item.get("record_id")
        if not rid:
            continue

        pk = item.get("primary_key")
        if pk is not None and not isinstance(pk, list):
            pk = None
        if isinstance(pk, list):
            pk = [str(c) for c in pk]

        ans = item.get("answer")
        if not isinstance(ans, dict):
            ans = {"columns": [], "rows": []}

        # Best-effort extraction of question + SQL across common dataset schemas
        question = _first_str(item, ["question", "nl_question", "prompt", "input", "query", "text"])
        gold_sql = _first_str(item, ["gold_sql", "sql", "ground_truth_sql", "gt_sql", "query_sql"])
        db_id = _first_str(item, ["db_id", "database", "db", "schema_id"])

        # Keep a small amount of extra context if present
        extra = {
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
        }

        m[rid] = {
            "primary_key": pk,
            "gold_answer": ans,
            **extra,
        }
    return m


# -----------------------
# Table helpers
# -----------------------
def answer_to_cols_rows(answer: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    cols = [str(c) for c in (answer.get("columns") or [])]
    rows = answer.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    return cols, rows


def build_col_index(cols: List[str]) -> Dict[str, int]:
    return {c: i for i, c in enumerate(cols)}


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float, np.integer, np.floating)):
        try:
            if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
                return None
        except Exception:
            pass
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None
    return None


def looks_numeric_column(cols: List[str], rows: List[List[Any]], col: str, sample_n: int = 50) -> bool:
    idx = build_col_index(cols)
    if col not in idx:
        return False
    i = idx[col]
    n = 0
    for r in rows[:sample_n]:
        if i >= len(r):
            continue
        if to_float(r[i]) is not None:
            n += 1
    return n > 0


# -----------------------
# Cell normalization for content matching
# -----------------------
def _normalize_numeric_for_signature(v: float, decimals: int = 2) -> Any:
    """Normalize numeric values for content matching.

    This reduces brittle mismatches like 3 vs 3.0 or 2.0000001 vs 2.0.
    """
    try:
        if math.isnan(v) or math.isinf(v):
            return None
    except Exception:
        pass

    # Round to a fixed number of decimals for stable stringification
    vr = round(float(v), decimals)

    # If it is effectively an integer after rounding, store as int
    if abs(vr - round(vr)) < 10 ** (-decimals):
        return int(round(vr))
    return vr


def normalize_cell_for_signature(x: Any, decimals: int = 2) -> Any:
    """Normalize a cell value for table_signature content matching.

    - Strips strings
    - Converts numeric-like values to normalized numbers
    - Maps NaN/Inf to None
    """
    if x is None:
        return None

    # Normalize strings (trim whitespace)
    if isinstance(x, str):
        s = x.strip()
        # Try numeric conversion for numeric-like strings
        fv = to_float(s)
        if fv is not None:
            return _normalize_numeric_for_signature(fv, decimals=decimals)
        return s

    # Normalize ints / floats / numpy numeric types
    fv = to_float(x)
    if fv is not None:
        return _normalize_numeric_for_signature(fv, decimals=decimals)

    return x


def normalize_pk_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, np.integer)):
        return int(v)
    fv = to_float(v)
    if fv is not None:
        return fv
    return v


def pk_tuple_list(cols: List[str], rows: List[List[Any]], pk_cols: List[str]) -> Optional[List[Tuple[Any, ...]]]:
    idx = build_col_index(cols)
    if any(c not in idx for c in pk_cols):
        return None
    out = []
    for r in rows:
        try:
            out.append(tuple(normalize_pk_value(r[idx[c]]) for c in pk_cols))
        except Exception:
            continue
    return out


def table_signature(answer: Dict[str, Any]) -> Tuple[int, int, List[str]]:
    cols, rows = answer_to_cols_rows(answer)
    nrows = len(rows)
    ncols = len(cols)

    # Normalize each row by normalizing cells and JSON-dumping the cell list;
    # treat as multiset by sorting.
    norm_rows: List[str] = []
    for r in rows:
        if not isinstance(r, list):
            continue
        norm_r = [normalize_cell_for_signature(v) for v in r]
        norm_rows.append(json.dumps(norm_r, ensure_ascii=False, sort_keys=True))
    norm_rows.sort()
    return nrows, ncols, norm_rows


def exact_table_match(gold: Dict[str, Any], pred: Dict[str, Any]) -> Dict[str, Any]:
    gr, gc, gh = table_signature(gold)
    pr, pc, ph = table_signature(pred)
    return {
        "row_match": gr == pr,
        "col_match": gc == pc,
        "content_match": gh == ph,
        "exact_match": (gr == pr) and (gc == pc) and (gh == ph),
    }


# -----------------------
# PK metrics
# -----------------------
def compute_pk_metrics(gold: Dict[str, Any], pred: Dict[str, Any], pk_cols: List[str]) -> Dict[str, Any]:
    gcols, grows = answer_to_cols_rows(gold)
    pcols, prows = answer_to_cols_rows(pred)

    pk_present = all(c in pcols for c in pk_cols)

    g_tups = pk_tuple_list(gcols, grows, pk_cols)
    p_tups = pk_tuple_list(pcols, prows, pk_cols)

    if g_tups is None:
        return {
            "pk_present": pk_present,
            "pk_eval_skipped": True,
            "pk_recall": None,
            "pk_precision": None,
            "pk_f1": None,
            "pk_exact_set_match": None,
            "gold_pk_count": None,
            "pred_pk_count": None,
        }

    gold_set = set(g_tups)
    pred_set = set(p_tups) if p_tups is not None else set()

    inter = gold_set & pred_set
    gold_n = len(gold_set)
    pred_n = len(pred_set)
    inter_n = len(inter)

    recall = (inter_n / gold_n) if gold_n else 1.0
    precision = (inter_n / pred_n) if pred_n else (1.0 if gold_n == 0 else 0.0)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "pk_present": pk_present,
        "pk_eval_skipped": False,
        "pk_recall": recall,
        "pk_precision": precision,
        "pk_f1": f1,
        "pk_exact_set_match": (gold_set == pred_set),
        "gold_pk_count": gold_n,
        "pred_pk_count": pred_n,
    }


# -----------------------
# Numeric error metrics (aligned by PK if possible)
# -----------------------
def align_rows_by_pk_or_order(
    gold: Dict[str, Any],
    pred: Dict[str, Any],
    pk_cols: Optional[List[str]],
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    gcols, grows = answer_to_cols_rows(gold)
    pcols, prows = answer_to_cols_rows(pred)
    gidx = build_col_index(gcols)
    pidx = build_col_index(pcols)

    common_cols = [c for c in gcols if c in pidx]

    def row_to_dict(cols, idx_map, r):
        d = {}
        for c in cols:
            i = idx_map[c]
            d[c] = r[i] if i < len(r) else None
        return d

    if pk_cols:
        g_tups = pk_tuple_list(gcols, grows, pk_cols)
        p_tups = pk_tuple_list(pcols, prows, pk_cols)
        if g_tups is not None and p_tups is not None:
            g_map = {}
            for r, t in zip(grows, g_tups):
                g_map[t] = row_to_dict(common_cols, gidx, r)
            p_map = {}
            for r, t in zip(prows, p_tups):
                p_map[t] = row_to_dict(common_cols, pidx, r)

            keys = sorted(set(g_map.keys()) & set(p_map.keys()))
            return common_cols, [g_map[k] for k in keys], [p_map[k] for k in keys]

    # fallback: row-order
    m = min(len(grows), len(prows))
    return (
        common_cols,
        [row_to_dict(common_cols, gidx, grows[i]) for i in range(m)],
        [row_to_dict(common_cols, pidx, prows[i]) for i in range(m)],
    )


def compute_numeric_metrics(gold: Dict[str, Any], pred: Dict[str, Any], pk_cols: Optional[List[str]]) -> Dict[str, Any]:
    gcols, grows = answer_to_cols_rows(gold)
    pcols, prows = answer_to_cols_rows(pred)

    common_cols = [c for c in gcols if c in set(pcols)]
    numeric_cols = [c for c in common_cols if looks_numeric_column(gcols, grows, c) or looks_numeric_column(pcols, prows, c)]

    if not numeric_cols:
        return {"numeric_eval_skipped": True, "per_column": {}, "macro": {}}

    _, gold_rows, pred_rows = align_rows_by_pk_or_order(gold, pred, pk_cols)

    per_col = {}
    maes, rmses, counts = [], [], []

    for c in numeric_cols:
        errs = []
        for gr, pr in zip(gold_rows, pred_rows):
            gv = to_float(gr.get(c))
            pv = to_float(pr.get(c))
            if gv is None or pv is None:
                continue
            errs.append(pv - gv)

        if not errs:
            per_col[c] = {"n": 0, "mae": None, "rmse": None, "bias": None}
            continue

        arr = np.array(errs, dtype=float)
        mae = float(np.mean(np.abs(arr)))
        rmse = float(np.sqrt(np.mean(arr ** 2)))
        bias = float(np.mean(arr))

        per_col[c] = {"n": int(arr.size), "mae": mae, "rmse": rmse, "bias": bias}

        maes.append(mae)
        rmses.append(rmse)
        counts.append(arr.size)

    # weighted macro
    total_n = int(sum(counts))
    if total_n > 0:
        w_mae = sum(m * n for m, n in zip(maes, counts)) / total_n
        w_rmse = sum(r * n for r, n in zip(rmses, counts)) / total_n
    else:
        w_mae, w_rmse = None, None

    return {
        "numeric_eval_skipped": False,
        "per_column": per_col,
        "macro": {
            "weighted_mae": float(w_mae) if w_mae is not None else None,
            "weighted_rmse": float(w_rmse) if w_rmse is not None else None,
            "total_numeric_pairs": total_n,
        },
    }



# -----------------------
# Main evaluation
# -----------------------
def evaluate_predictions_core(dataset_path: str, predictions_path: str) -> Dict[str, Any]:
    """Evaluate a single dataset+predictions pair and return a structured result.

    The returned dict includes:
      - setting_to_pred_key
      - summary (rates/averages)
      - per_record
      - agg (raw counts/sums used to aggregate)
    """
    preds = read_jsonl(predictions_path)
    ds_map = build_dataset_map(dataset_path)

    # group by record_id -> setting -> entry
    by_rid = defaultdict(dict)
    for p in preds:
        rid = p.get("record_id")
        setting = p.get("setting")
        if not rid or not setting:
            continue
        if setting not in SETTING_TO_PRED_KEY:
            continue
        by_rid[rid][setting] = p

    # aggregates (raw counts/sums)
    agg = {
        s: {
            # counts
            "n_total": 0,          # total records encountered for this setting (including missing preds)
            "n": 0,                # evaluated records for this setting (pred present + gold present)
            "missing_pred_n": 0,   # records where pred output is missing / invalid

            # table match counts (only for evaluated records)
            "exact_match_n": 0,
            "row_match_n": 0,
            "col_match_n": 0,
            "content_match_n": 0,

            # PK aggregates (only for evaluated records where PK eval runs)
            "pk_eval_n": 0,
            "pk_exact_n": 0,
            "pk_recall_sum": 0.0,

            # numeric aggregates (only for evaluated records where numeric eval runs)
            "num_eval_n": 0,
            "rmse_sum": 0.0,
            "mae_sum": 0.0,
        }
        for s in ALL_SETTINGS
    }

    per_record: List[Dict[str, Any]] = []

    for rid, settings_map in by_rid.items():
        for setting, entry in settings_map.items():
            # Gold + PK come from dataset.jsonl (predictions may not carry these fields)
            ds = ds_map.get(rid, {})
            gold = entry.get("gold_answer")
            if not isinstance(gold, dict):
                gold = ds.get("gold_answer")
            if not isinstance(gold, dict):
                # cannot evaluate without gold
                continue

            pk_cols = ds.get("primary_key")
            if pk_cols is not None and not isinstance(pk_cols, list):
                pk_cols = None
            if pk_cols:
                pk_cols = [str(c) for c in pk_cols]

            pred_key = SETTING_TO_PRED_KEY[setting]
            pred_tbl = entry.get(pred_key)
            if not isinstance(pred_tbl, dict):
                # no pred output available: count toward total + missing, but do not include in evaluated denom
                agg[setting]["n_total"] += 1
                agg[setting]["missing_pred_n"] += 1
                meta = ds_map.get(rid, {})
                per_record.append({
                    "record_id": rid,
                    "setting": setting,
                    "question": meta.get("question"),
                    "gold_sql": meta.get("gold_sql"),
                    "gold_answer": gold,
                    "pred_sql": entry.get("pred_sql") or entry.get("predicted_sql") or entry.get("sql"),
                    "pred_value": None,
                    "used_pred_key": pred_key,
                    "missing_pred": True,
                })
                continue

            ex = exact_table_match(gold, pred_tbl)
            agg[setting]["exact_match_n"] += 1 if ex["exact_match"] else 0
            agg[setting]["row_match_n"] += 1 if ex["row_match"] else 0
            agg[setting]["col_match_n"] += 1 if ex["col_match"] else 0
            agg[setting]["content_match_n"] += 1 if ex["content_match"] else 0

            pk_metrics = compute_pk_metrics(gold, pred_tbl, pk_cols) if pk_cols else {
                "pk_present": None,
                "pk_eval_skipped": True,
                "pk_recall": None,
                "pk_precision": None,
                "pk_f1": None,
                "pk_exact_set_match": None,
                "gold_pk_count": None,
                "pred_pk_count": None,
            }
            num_metrics = compute_numeric_metrics(gold, pred_tbl, pk_cols)

            # aggregate
            agg[setting]["n_total"] += 1
            agg[setting]["n"] += 1

            if not pk_metrics["pk_eval_skipped"]:
                agg[setting]["pk_eval_n"] += 1
                agg[setting]["pk_exact_n"] += 1 if pk_metrics["pk_exact_set_match"] else 0
                agg[setting]["pk_recall_sum"] += float(pk_metrics["pk_recall"] or 0.0)

            if not num_metrics["numeric_eval_skipped"]:
                agg[setting]["num_eval_n"] += 1
                rmse = num_metrics["macro"].get("weighted_rmse")
                mae = num_metrics["macro"].get("weighted_mae")
                if rmse is not None:
                    agg[setting]["rmse_sum"] += float(rmse)
                if mae is not None:
                    agg[setting]["mae_sum"] += float(mae)

            meta = ds_map.get(rid, {})
            per_record.append({
                "record_id": rid,
                "setting": setting,
                "question": meta.get("question"),
                "gold_sql": meta.get("gold_sql"),
                "gold_answer": gold,
                "pred_sql": entry.get("pred_sql") or entry.get("predicted_sql") or entry.get("sql"),
                "pred_value": pred_tbl,
                "used_pred_key": pred_key,
                "primary_key": pk_cols,
                "missing_pred": False,
                "pk_metrics": pk_metrics,
                "numeric_metrics": num_metrics,
                "table_match": ex,
            })

    # finalize summary
    summary = {"per_setting": {}}
    for s in ALL_SETTINGS:
        n = agg[s]["n"]
        n_total = agg[s]["n_total"]
        missing_n = agg[s]["missing_pred_n"]
        pk_n = agg[s]["pk_eval_n"]
        num_n = agg[s]["num_eval_n"]

        summary["per_setting"][s] = {
            "n": n,
            "n_total": n_total,
            "missing_pred_n": missing_n,
            "coverage_rate": (n / n_total) if n_total else 0.0,
            "table_exact_match_rate": (agg[s]["exact_match_n"] / n) if n else 0.0,
            "row_match_rate": (agg[s]["row_match_n"] / n) if n else 0.0,
            "col_match_rate": (agg[s]["col_match_n"] / n) if n else 0.0,
            "content_match_rate": (agg[s]["content_match_n"] / n) if n else 0.0,
            "pk_eval_n": pk_n,
            "pk_exact_set_match_rate": (agg[s]["pk_exact_n"] / pk_n) if pk_n else 0.0,
            "pk_recall_avg": (agg[s]["pk_recall_sum"] / pk_n) if pk_n else 0.0,
            "numeric_eval_n": num_n,
            "avg_weighted_rmse": (agg[s]["rmse_sum"] / num_n) if num_n else 0.0,
            "avg_weighted_mae": (agg[s]["mae_sum"] / num_n) if num_n else 0.0,
        }

    return {
        "setting_to_pred_key": SETTING_TO_PRED_KEY,
        "summary": summary,
        "per_record": per_record,
        "agg": agg,
    }


def evaluate_predictions(dataset_path: str, predictions_path: str, out_path: str) -> None:
    out = evaluate_predictions_core(dataset_path, predictions_path)

    base = os.path.splitext(out_path)[0]
    samplewise_path = base + ".samplewise.json"
    aggregated_path = base + ".aggregated.json"

    # 1) Samplewise file: all per-record entries + settings metadata
    samplewise = {
        "dataset": dataset_path,
        "predictions": predictions_path,
        "settings": {
            "setting_to_pred_key": out.get("setting_to_pred_key"),
            "all_settings": ALL_SETTINGS,
        },
        "records": out.get("per_record", []),
    }

    # 2) Aggregated file: summary + raw agg used for aggregation
    aggregated = {
        "dataset": dataset_path,
        "predictions": predictions_path,
        "settings": {
            "setting_to_pred_key": out.get("setting_to_pred_key"),
            "all_settings": ALL_SETTINGS,
        },
        "summary": out.get("summary"),
        "agg": out.get("agg"),
    }

    with open(samplewise_path, "w", encoding="utf-8") as f:
        json.dump(samplewise, f, ensure_ascii=False, indent=2)
    with open(aggregated_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, ensure_ascii=False, indent=2)

    print("✅ Wrote:", samplewise_path)
    print("✅ Wrote:", aggregated_path)
    print(json.dumps(aggregated.get("summary", {}), indent=2))
# -----------------------
# ROI-suite helpers
# -----------------------
def _merge_aggs(aggs: List[Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Merge a list of per-setting agg dicts by summing raw counts/sums."""
    merged = {
        s: {
            "n_total": 0,
            "n": 0,
            "missing_pred_n": 0,
            "exact_match_n": 0,
            "row_match_n": 0,
            "col_match_n": 0,
            "content_match_n": 0,
            "pk_eval_n": 0,
            "pk_exact_n": 0,
            "pk_recall_sum": 0.0,
            "num_eval_n": 0,
            "rmse_sum": 0.0,
            "mae_sum": 0.0,
        }
        for s in ALL_SETTINGS
    }
    for agg in aggs:
        for s in ALL_SETTINGS:
            a = agg.get(s, {})
            merged[s]["n_total"] += int(a.get("n_total", 0))
            merged[s]["missing_pred_n"] += int(a.get("missing_pred_n", 0))
            merged[s]["n"] += int(a.get("n", 0))
            merged[s]["exact_match_n"] += int(a.get("exact_match_n", 0))
            merged[s]["row_match_n"] += int(a.get("row_match_n", 0))
            merged[s]["col_match_n"] += int(a.get("col_match_n", 0))
            merged[s]["content_match_n"] += int(a.get("content_match_n", 0))
            merged[s]["pk_eval_n"] += int(a.get("pk_eval_n", 0))
            merged[s]["pk_exact_n"] += int(a.get("pk_exact_n", 0))
            merged[s]["pk_recall_sum"] += float(a.get("pk_recall_sum", 0.0))
            merged[s]["num_eval_n"] += int(a.get("num_eval_n", 0))
            merged[s]["rmse_sum"] += float(a.get("rmse_sum", 0.0))
            merged[s]["mae_sum"] += float(a.get("mae_sum", 0.0))
    return merged


def _summary_from_agg(agg: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    summary = {"per_setting": {}}
    for s in ALL_SETTINGS:
        n = agg[s]["n"]
        n_total = agg[s].get("n_total", n)
        missing_n = agg[s].get("missing_pred_n", 0)
        pk_n = agg[s]["pk_eval_n"]
        num_n = agg[s]["num_eval_n"]
        summary["per_setting"][s] = {
            "n": n,
            "n_total": n_total,
            "missing_pred_n": missing_n,
            "coverage_rate": (n / n_total) if n_total else 0.0,
            "table_exact_match_rate": (agg[s]["exact_match_n"] / n) if n else 0.0,
            "row_match_rate": (agg[s]["row_match_n"] / n) if n else 0.0,
            "col_match_rate": (agg[s]["col_match_n"] / n) if n else 0.0,
            "content_match_rate": (agg[s]["content_match_n"] / n) if n else 0.0,
            "pk_eval_n": pk_n,
            "pk_exact_set_match_rate": (agg[s]["pk_exact_n"] / pk_n) if pk_n else 0.0,
            "pk_recall_avg": (agg[s]["pk_recall_sum"] / pk_n) if pk_n else 0.0,
            "numeric_eval_n": num_n,
            "avg_weighted_rmse": (agg[s]["rmse_sum"] / num_n) if num_n else 0.0,
            "avg_weighted_mae": (agg[s]["mae_sum"] / num_n) if num_n else 0.0,
        }
    return summary


# Helper for an empty agg dict (for fallback)
def _empty_agg() -> Dict[str, Dict[str, Any]]:
    return {
        s: {
            "n_total": 0,
            "n": 0,
            "missing_pred_n": 0,
            "exact_match_n": 0,
            "row_match_n": 0,
            "col_match_n": 0,
            "content_match_n": 0,
            "pk_eval_n": 0,
            "pk_exact_n": 0,
            "pk_recall_sum": 0.0,
            "num_eval_n": 0,
            "rmse_sum": 0.0,
            "mae_sum": 0.0,
        }
        for s in ALL_SETTINGS
    }


def _find_latest_predictions_jsonl(split_dir: str) -> Optional[str]:
    """Find the latest predictions.jsonl under split_dir.

    Supports either:
      - split_dir/predictions.jsonl
      - split_dir/<timestamp>/predictions.jsonl (chooses latest by folder name, fallback to mtime)
    """
    direct = os.path.join(split_dir, "predictions.jsonl")
    if os.path.exists(direct):
        return direct

    if not os.path.isdir(split_dir):
        return None

    candidates: List[Tuple[str, float]] = []
    try:
        for name in os.listdir(split_dir):
            sub = os.path.join(split_dir, name)
            if not os.path.isdir(sub):
                continue
            p = os.path.join(sub, "predictions.jsonl")
            if os.path.exists(p):
                try:
                    mtime = os.path.getmtime(p)
                except Exception:
                    mtime = 0.0
                candidates.append((p, mtime))
    except Exception:
        return None

    if not candidates:
        return None

    # Prefer lexicographically latest parent folder name if possible (works for YYYYMMDD_HHMMSS)
    def parent_name(path: str) -> str:
        return os.path.basename(os.path.dirname(path))

    try:
        candidates.sort(key=lambda x: (parent_name(x[0]), x[1]))
        return candidates[-1][0]
    except Exception:
        candidates.sort(key=lambda x: x[1])
        return candidates[-1][0]

def evaluate_roi_suite(roi_config_path: str, predictions_root: str, out_dir: str, write_per_record: bool = False) -> None:
    """Evaluate all ROI split datasets listed under analysis_paths.

    Assumptions:
      - roi_config_path is a JSON containing `analysis_paths` mapping split_name -> dataset_jsonl
      - predictions_root contains per-split subfolders with `predictions.jsonl` inside.
        (e.g., .../roi_splits/<split_name>/predictions.jsonl)
    """
    with open(roi_config_path, "r", encoding="utf-8") as f:
        roi_cfg = json.load(f)

    analysis_paths = roi_cfg.get("analysis_paths") or {}
    if not isinstance(analysis_paths, dict) or not analysis_paths:
        raise RuntimeError(f"ROI config has no analysis_paths dict: {roi_config_path}")

    os.makedirs(out_dir, exist_ok=True)

    per_split_summary: Dict[str, Any] = {}
    aggs: List[Tuple[str, Dict[str, Dict[str, Any]]]] = []
    all_records: List[Dict[str, Any]] = []

    for split_name, dataset_path in analysis_paths.items():
        if not dataset_path or not isinstance(dataset_path, str):
            print(f"[SKIP] {split_name}: invalid dataset path: {dataset_path}")
            continue
        if not os.path.exists(dataset_path):
            print(f"[SKIP] {split_name}: dataset not found: {dataset_path}")
            continue
        split_pred_dir = os.path.join(predictions_root, split_name)
        pred_path = _find_latest_predictions_jsonl(split_pred_dir)
        if not pred_path or not os.path.exists(pred_path):
            print(f"[SKIP] {split_name}: predictions not found under: {split_pred_dir}")
            continue

        print(f"\n=== EVAL ROI SPLIT: {split_name} ===")
        print(f"Dataset:     {dataset_path}")
        print(f"Predictions: {pred_path}")
        run_folder = os.path.basename(os.path.dirname(pred_path))
        if run_folder != split_name:
            print(f"Run folder:  {run_folder}")

        out = evaluate_predictions_core(dataset_path, pred_path)
        aggs.append((split_name, out["agg"]))
        # Append all per_record entries, tagging with split_name
        for r in out.get("per_record", []):
            rr = dict(r)
            rr["split_name"] = split_name
            all_records.append(rr)
        per_split_summary[split_name] = out["summary"]

    # Merge all splits
    merged_agg = _merge_aggs([a for _, a in aggs])
    merged_summary = _summary_from_agg(merged_agg)

    suite_samplewise_path = os.path.join(out_dir, "roi_suite.samplewise.json")
    suite_aggregated_path = os.path.join(out_dir, "roi_suite.aggregated.json")

    suite_samplewise = {
        "roi_config": roi_config_path,
        "predictions_root": predictions_root,
        "settings": {
            "setting_to_pred_key": SETTING_TO_PRED_KEY,
            "all_settings": ALL_SETTINGS,
        },
        "records": all_records,
    }

    suite_aggregated = {
        "roi_config": roi_config_path,
        "predictions_root": predictions_root,
        "settings": {
            "setting_to_pred_key": SETTING_TO_PRED_KEY,
            "all_settings": ALL_SETTINGS,
        },
        "summary": merged_summary,
        "per_split_summary": per_split_summary,
        "agg": merged_agg,
    }

    with open(suite_samplewise_path, "w", encoding="utf-8") as f:
        json.dump(suite_samplewise, f, ensure_ascii=False, indent=2)

    with open(suite_aggregated_path, "w", encoding="utf-8") as f:
        json.dump(suite_aggregated, f, ensure_ascii=False, indent=2)

    print("\n✅ Wrote ROI suite samplewise:", suite_samplewise_path)
    print("✅ Wrote ROI suite aggregated:", suite_aggregated_path)
    print(json.dumps(merged_summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()

    # Single-file mode (backwards compatible)
    ap.add_argument("--dataset", default="output/dataset_runs/v1/dataset.jsonl")
    ap.add_argument("--predictions", default="", help="Path to runs.../predictions.jsonl")
    ap.add_argument("--out", default="evaluation_pk_rmse.json")

    # ROI suite mode
    ap.add_argument("--roi_config", default="", help="Path to ROI JSON config containing analysis_paths")
    ap.add_argument(
        "--predictions_root",
        default="",
        help="Root folder containing per-split subfolders with predictions.jsonl (e.g., .../roi_splits)",
    )
    ap.add_argument(
        "--roi_out_dir",
        default="",
        help="Where to write per-split evaluations and the aggregated ROI suite summary",
    )
    ap.add_argument(
        "--write_per_record",
        action="store_true",
        help="Include per_record in each per-split output JSON (can be large)",
    )

    args = ap.parse_args()

    # ROI suite mode
    if args.roi_config:
        if not args.predictions_root:
            raise RuntimeError("--predictions_root is required when using --roi_config")
        roi_out_dir = args.roi_out_dir or os.path.join(args.predictions_root, "..", "eval")
        evaluate_roi_suite(args.roi_config, args.predictions_root, roi_out_dir, write_per_record=args.write_per_record)

    # Single-file mode
    else:
        if not args.predictions:
            raise RuntimeError("--predictions is required unless --roi_config is provided")
        evaluate_predictions(args.dataset, args.predictions, args.out)


# python src/eval/evaluate_settings.py \
#   --roi_config data/output/dataset_runs/roi_test/roi_config.json \
#   --predictions_root data/runs_sql_table_settings/roi_splits \
#   --roi_out_dir runs_sql_table_settings/roi_eval \
#   --write_per_record \
#   --out evaluation_pk_rmse.json
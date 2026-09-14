import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.eval.table_metrics_evaluator import TableMetricsEvaluator  # noqa: E402


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def read_dataset(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".jsonl"):
        return read_jsonl(path)
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "records" in obj:
        return obj["records"]
    if isinstance(obj, list):
        return obj
    raise ValueError(f"Unsupported dataset format: {path}")


def build_dataset_map(dataset: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    m: Dict[str, Dict[str, Any]] = {}
    for item in dataset:
        rid = item.get("record_id")
        if not rid:
            continue
        ans = item.get("answer") or {}
        if not isinstance(ans, dict):
            ans = {"columns": [], "rows": []}
        pk = item.get("primary_key")
        if not isinstance(pk, list):
            pk = None
        m[rid] = {
            "answer": ans,
            "primary_key": pk,
            "question": item.get("question"),
        }
    return m


def _rows_from_list_of_dicts(rows: List[Dict[str, Any]], cols: List[str]) -> List[List[Any]]:
    out = []
    for r in rows:
        out.append([r.get(c) for c in cols])
    return out


def normalize_pred_table(pred: Any) -> Optional[Dict[str, Any]]:
    if isinstance(pred, dict):
        if "columns" in pred and "rows" in pred:
            return {"columns": pred.get("columns") or [], "rows": pred.get("rows") or []}
        # Some runners may emit {"table":[{...},...]}
        if "table" in pred and isinstance(pred["table"], list):
            t = pred["table"]
            if len(t) == 0:
                return {"columns": [], "rows": []}
            if isinstance(t[0], dict):
                cols = list(t[0].keys())
                return {"columns": cols, "rows": _rows_from_list_of_dicts(t, cols)}
    if isinstance(pred, list):
        # list of row dicts
        if len(pred) == 0:
            return {"columns": [], "rows": []}
        if isinstance(pred[0], dict):
            cols = list(pred[0].keys())
            return {"columns": cols, "rows": _rows_from_list_of_dicts(pred, cols)}
    return None


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description="Evaluate table predictions against dataset GT.")
    ap.add_argument("--dataset", required=True, help="Path to dataset (json/jsonl)")
    ap.add_argument("--predictions", required=True, help="Path to predictions jsonl")
    ap.add_argument("--pred-key", default="pred_table", help="Key in predictions for the table")
    ap.add_argument("--require-success", action="store_true", help="Only evaluate records with success==True")
    ap.add_argument("--success-key", default="success", help="Key for success flag in predictions")
    ap.add_argument("--out-samplewise", default="baseline-results/eval.samplewise.jsonl")
    ap.add_argument("--out-summary", default="baseline-results/eval.summary.json")
    args = ap.parse_args()

    ensure_dir(os.path.dirname(args.out_samplewise))
    ensure_dir(os.path.dirname(args.out_summary))

    dataset = read_dataset(args.dataset)
    ds_map = build_dataset_map(dataset)
    preds = read_jsonl(args.predictions)

    agg = {
        "n_total": 0,
        "n_eval": 0,
        "missing_pred_n": 0,
        "exact_match_n": 0,
        "row_match_n": 0,
        "col_match_n": 0,
        "content_match_n": 0,
        "pk_eval_n": 0,
        "pk_exact_n": 0,
        "pk_precision_sum": 0.0,
        "pk_recall_sum": 0.0,
        "pk_cell_eval_n": 0,
        "pk_cell_acc_sum": 0.0,
        "num_eval_n": 0,
        "rmse_sum": 0.0,
        "mae_sum": 0.0,
    }

    per_record: List[Dict[str, Any]] = []

    for p in preds:
        rid = p.get("record_id")
        if not rid or rid not in ds_map:
            continue
        if args.require_success and not p.get(args.success_key, False):
            continue

        agg["n_total"] += 1
        pred_raw = p.get(args.pred_key)
        pred_tbl = normalize_pred_table(pred_raw)
        if pred_tbl is None:
            agg["missing_pred_n"] += 1
            per_record.append(
                {
                    "record_id": rid,
                    "missing_pred": True,
                    "pred_key": args.pred_key,
                }
            )
            continue

        gold = ds_map[rid]["answer"]
        pk = ds_map[rid]["primary_key"]

        out = TableMetricsEvaluator.compare_tables(gold, pred_tbl, primary_key=pk)
        agg["n_eval"] += 1
        tm = out["table_match"]
        agg["exact_match_n"] += 1 if tm.get("exact_match") else 0
        agg["row_match_n"] += 1 if tm.get("row_match") else 0
        agg["col_match_n"] += 1 if tm.get("col_match") else 0
        agg["content_match_n"] += 1 if tm.get("content_match") else 0

        pkm = out["pk_metrics"]
        if not pkm.get("pk_eval_skipped"):
            agg["pk_eval_n"] += 1
            agg["pk_exact_n"] += 1 if pkm.get("pk_exact_set_match") else 0
            agg["pk_precision_sum"] += float(pkm.get("pk_precision") or 0.0)
            agg["pk_recall_sum"] += float(pkm.get("pk_recall") or 0.0)

        pkcm = out["pk_cell_metrics"]
        if not pkcm.get("pk_cell_eval_skipped"):
            agg["pk_cell_eval_n"] += 1
            agg["pk_cell_acc_sum"] += float(pkcm.get("cell_acc") or 0.0)

        nm = out["numeric_metrics"]
        if not nm.get("numeric_eval_skipped"):
            agg["num_eval_n"] += 1
            rmse = nm["macro"].get("weighted_rmse")
            mae = nm["macro"].get("weighted_mae")
            agg["rmse_sum"] += float(rmse) if rmse is not None else 0.0
            agg["mae_sum"] += float(mae) if mae is not None else 0.0

        per_record.append(
            {
                "record_id": rid,
                "question": ds_map[rid].get("question"),
                "pred_table": pred_tbl,
                "gold_table": gold,
                "table_match": tm,
                "pk_metrics": pkm,
                "pk_cell_metrics": pkcm,
                "numeric_metrics": nm,
            }
        )

    summary = {
        "n_total": agg["n_total"],
        "n_eval": agg["n_eval"],
        "missing_pred_n": agg["missing_pred_n"],
        "exact_match_rate": (agg["exact_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "row_match_rate": (agg["row_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "col_match_rate": (agg["col_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "content_match_rate": (agg["content_match_n"] / agg["n_eval"]) if agg["n_eval"] else 0.0,
        "pk_exact_rate": (agg["pk_exact_n"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_precision_avg": (agg["pk_precision_sum"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_recall_avg": (agg["pk_recall_sum"] / agg["pk_eval_n"]) if agg["pk_eval_n"] else None,
        "pk_cell_acc_avg": (agg["pk_cell_acc_sum"] / agg["pk_cell_eval_n"]) if agg["pk_cell_eval_n"] else None,
        "rmse_avg": (agg["rmse_sum"] / agg["num_eval_n"]) if agg["num_eval_n"] else None,
        "mae_avg": (agg["mae_sum"] / agg["num_eval_n"]) if agg["num_eval_n"] else None,
    }

    with open(args.out_samplewise, "w", encoding="utf-8") as f:
        for r in per_record:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(args.out_summary, "w", encoding="utf-8") as f:
        json.dump(
            {
                "dataset": args.dataset,
                "predictions": args.predictions,
                "pred_key": args.pred_key,
                "require_success": args.require_success,
                "summary": summary,
                "agg": agg,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

import argparse
import json
import os
from typing import Optional
from typing import Any, Dict, List

from src.eval import evaluate_settings as eval_base


SETTING = "SCHEMA_Q_TO_SQL"
PRED_KEY = "pred_result"
ROUND_DECIMALS = 2


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _nulls_to_zero_table(answer: Dict[str, Any]) -> Dict[str, Any]:
    cols = answer.get("columns") or []
    rows = answer.get("rows") or []
    norm_rows: List[List[Any]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        norm_rows.append([0 if cell is None else cell for cell in row])
    return {
        "columns": [str(c) for c in cols],
        "rows": norm_rows,
    }


def _round_numeric(value: Any, decimals: int = ROUND_DECIMALS) -> Any:
    fv: Optional[float] = eval_base.to_float(value)
    if fv is None:
        return value
    return round(float(fv), decimals)


def _normalize_table_for_eval(answer: Dict[str, Any]) -> Dict[str, Any]:
    cols = [str(c) for c in (answer.get("columns") or [])]
    rows = answer.get("rows") or []
    norm_rows: List[List[Any]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        norm_rows.append([_round_numeric(0 if cell is None else cell) for cell in row])
    return {
        "columns": cols,
        "rows": norm_rows,
    }


def _exact_table_match_2dp(gold: Dict[str, Any], pred: Dict[str, Any]) -> Dict[str, Any]:
    gr, gc, gh = eval_base.table_signature(gold)
    pr, pc, ph = eval_base.table_signature(pred)
    return {
        "row_match": gr == pr,
        "col_match": gc == pc,
        "content_match": gh == ph,
        "exact_match": (gr == pr) and (gc == pc) and (gh == ph),
    }


def _compute_pk_metrics_2dp(gold: Dict[str, Any], pred: Dict[str, Any], pk_cols: List[str]) -> Dict[str, Any]:
    gcols, grows = eval_base.answer_to_cols_rows(gold)
    pcols, prows = eval_base.answer_to_cols_rows(pred)

    pk_present = all(c in pcols for c in pk_cols)

    def _pk_tuple_list_rounded(cols: List[str], rows: List[List[Any]], keys: List[str]):
        idx = eval_base.build_col_index(cols)
        if any(c not in idx for c in keys):
            return None
        out = []
        for r in rows:
            try:
                out.append(tuple(_round_numeric(r[idx[c]]) for c in keys))
            except Exception:
                continue
        return out

    g_tups = _pk_tuple_list_rounded(gcols, grows, pk_cols)
    p_tups = _pk_tuple_list_rounded(pcols, prows, pk_cols)

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


def _compute_numeric_metrics_2dp(gold: Dict[str, Any], pred: Dict[str, Any], pk_cols: Optional[List[str]]) -> Dict[str, Any]:
    gcols, grows = eval_base.answer_to_cols_rows(gold)
    pcols, prows = eval_base.answer_to_cols_rows(pred)

    common_cols = [c for c in gcols if c in set(pcols)]
    numeric_cols = [c for c in common_cols if eval_base.looks_numeric_column(gcols, grows, c) or eval_base.looks_numeric_column(pcols, prows, c)]

    if not numeric_cols:
        return {"numeric_eval_skipped": True, "per_column": {}, "macro": {}}

    _, gold_rows, pred_rows = eval_base.align_rows_by_pk_or_order(gold, pred, pk_cols)

    per_col = {}
    maes, rmses, counts = [], [], []

    for c in numeric_cols:
        errs = []
        for gr, pr in zip(gold_rows, pred_rows):
            gv = eval_base.to_float(gr.get(c))
            pv = eval_base.to_float(pr.get(c))
            if gv is None or pv is None:
                continue
            gv = round(float(gv), ROUND_DECIMALS)
            pv = round(float(pv), ROUND_DECIMALS)
            errs.append(pv - gv)

        if not errs:
            per_col[c] = {"n": 0, "mae": None, "rmse": None, "bias": None}
            continue

        arr = eval_base.np.array(errs, dtype=float)
        mae = float(eval_base.np.mean(eval_base.np.abs(arr)))
        rmse = float(eval_base.np.sqrt(eval_base.np.mean(arr ** 2)))
        bias = float(eval_base.np.mean(arr))

        per_col[c] = {"n": int(arr.size), "mae": mae, "rmse": rmse, "bias": bias}
        maes.append(mae)
        rmses.append(rmse)
        counts.append(arr.size)

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


def _empty_agg() -> Dict[str, Dict[str, Any]]:
    return {
        SETTING: {
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
    }


def _summary_from_agg(agg: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    s = agg[SETTING]
    n = s["n"]
    n_total = s["n_total"]
    missing_n = s["missing_pred_n"]
    pk_n = s["pk_eval_n"]
    num_n = s["num_eval_n"]

    return {
        "per_setting": {
            SETTING: {
                "n": n,
                "n_total": n_total,
                "missing_pred_n": missing_n,
                "coverage_rate": (n / n_total) if n_total else 0.0,
                "table_exact_match_rate": (s["exact_match_n"] / n) if n else 0.0,
                "row_match_rate": (s["row_match_n"] / n) if n else 0.0,
                "col_match_rate": (s["col_match_n"] / n) if n else 0.0,
                "content_match_rate": (s["content_match_n"] / n) if n else 0.0,
                "pk_eval_n": pk_n,
                "pk_exact_set_match_rate": (s["pk_exact_n"] / pk_n) if pk_n else 0.0,
                "pk_recall_avg": (s["pk_recall_sum"] / pk_n) if pk_n else 0.0,
                "numeric_eval_n": num_n,
                "avg_weighted_rmse": (s["rmse_sum"] / num_n) if num_n else 0.0,
                "avg_weighted_mae": (s["mae_sum"] / num_n) if num_n else 0.0,
            }
        }
    }


def evaluate_predictions_core(predictions_path: str) -> Dict[str, Any]:
    rows = read_json(predictions_path)
    if not isinstance(rows, list):
        raise ValueError(f"Expected a JSON list at {predictions_path}, got {type(rows)}")

    agg = _empty_agg()
    per_record: List[Dict[str, Any]] = []

    for idx, entry in enumerate(rows):
        if not isinstance(entry, dict):
            continue

        rid = entry.get("record_id") or entry.get("item_id") or f"r{idx}"
        gold = entry.get("ground_truth_table")
        if not isinstance(gold, dict):
            continue
        gold = _normalize_table_for_eval(_nulls_to_zero_table(gold))

        pk_cols = entry.get("primary_key")
        if pk_cols is not None and not isinstance(pk_cols, list):
            pk_cols = None
        if pk_cols:
            pk_cols = [str(c) for c in pk_cols]

        pred_tbl = entry.get(PRED_KEY)
        agg[SETTING]["n_total"] += 1

        if not isinstance(pred_tbl, dict):
            agg[SETTING]["missing_pred_n"] += 1
            per_record.append({
                "record_id": rid,
                "setting": SETTING,
                "question": entry.get("question"),
                "gold_sql": entry.get("gold_sql") or entry.get("original_sql") or entry.get("sql"),
                "gold_answer": gold,
                "pred_sql": entry.get("pred_sql"),
                "pred_value": None,
                "used_pred_key": PRED_KEY,
                "missing_pred": True,
                "exec_ok": entry.get("exec_ok"),
                "exec_error": entry.get("exec_error"),
            })
            continue
        pred_tbl = _normalize_table_for_eval(_nulls_to_zero_table(pred_tbl))

        ex = _exact_table_match_2dp(gold, pred_tbl)
        pk_metrics = _compute_pk_metrics_2dp(gold, pred_tbl, pk_cols) if pk_cols else {
            "pk_present": None,
            "pk_eval_skipped": True,
            "pk_recall": None,
            "pk_precision": None,
            "pk_f1": None,
            "pk_exact_set_match": None,
            "gold_pk_count": None,
            "pred_pk_count": None,
        }
        num_metrics = _compute_numeric_metrics_2dp(gold, pred_tbl, pk_cols)

        agg[SETTING]["n"] += 1
        agg[SETTING]["exact_match_n"] += 1 if ex["exact_match"] else 0
        agg[SETTING]["row_match_n"] += 1 if ex["row_match"] else 0
        agg[SETTING]["col_match_n"] += 1 if ex["col_match"] else 0
        agg[SETTING]["content_match_n"] += 1 if ex["content_match"] else 0

        if not pk_metrics["pk_eval_skipped"]:
            agg[SETTING]["pk_eval_n"] += 1
            agg[SETTING]["pk_exact_n"] += 1 if pk_metrics["pk_exact_set_match"] else 0
            agg[SETTING]["pk_recall_sum"] += float(pk_metrics["pk_recall"] or 0.0)

        if not num_metrics["numeric_eval_skipped"]:
            agg[SETTING]["num_eval_n"] += 1
            rmse = num_metrics["macro"].get("weighted_rmse")
            mae = num_metrics["macro"].get("weighted_mae")
            if rmse is not None:
                agg[SETTING]["rmse_sum"] += float(rmse)
            if mae is not None:
                agg[SETTING]["mae_sum"] += float(mae)

        per_record.append({
            "record_id": rid,
            "setting": SETTING,
            "question": entry.get("question"),
            "gold_sql": entry.get("gold_sql") or entry.get("original_sql") or entry.get("sql"),
            "gold_answer": gold,
            "pred_sql": entry.get("pred_sql"),
            "pred_value": pred_tbl,
            "used_pred_key": PRED_KEY,
            "primary_key": pk_cols,
            "missing_pred": False,
            "exec_ok": entry.get("exec_ok"),
            "exec_error": entry.get("exec_error"),
            "pk_metrics": pk_metrics,
            "numeric_metrics": num_metrics,
            "table_match": ex,
        })

    return {
        "setting_to_pred_key": {SETTING: PRED_KEY},
        "summary": _summary_from_agg(agg),
        "per_record": per_record,
        "agg": agg,
    }


def evaluate_predictions(predictions_path: str, out_path: str) -> None:
    out = evaluate_predictions_core(predictions_path)

    base = os.path.splitext(out_path)[0]
    samplewise_path = base + ".samplewise.json"
    aggregated_path = base + ".aggregated.json"
    content_mismatch_path = base + ".content_mismatch.txt"

    samplewise = {
        "predictions": predictions_path,
        "settings": {
            "setting_to_pred_key": out.get("setting_to_pred_key"),
            "all_settings": [SETTING],
        },
        "records": out.get("per_record", []),
    }

    aggregated = {
        "predictions": predictions_path,
        "settings": {
            "setting_to_pred_key": out.get("setting_to_pred_key"),
            "all_settings": [SETTING],
        },
        "summary": out.get("summary"),
        "agg": out.get("agg"),
    }

    with open(samplewise_path, "w", encoding="utf-8") as f:
        json.dump(samplewise, f, ensure_ascii=False, indent=2)
    with open(aggregated_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, ensure_ascii=False, indent=2)
    with open(content_mismatch_path, "w", encoding="utf-8") as f:
        mismatch_rows = [
            r for r in out.get("per_record", [])
            if not r.get("missing_pred")
            and isinstance(r.get("table_match"), dict)
            and (r["table_match"].get("content_match") is False)
        ]
        for i, r in enumerate(mismatch_rows, start=1):
            f.write(f"Case {i}\n")
            f.write(f"item_id: {r.get('record_id')}\n")
            f.write(f"question: {r.get('question')}\n")
            f.write(f"gnd_truth_sql: {r.get('gold_sql')}\n")
            f.write(
                "gnd_truth_table:\n"
                f"{json.dumps(r.get('gold_answer'), ensure_ascii=False, indent=2)}\n"
            )
            f.write(f"pred_sql: {r.get('pred_sql')}\n")
            f.write(
                "pred_table:\n"
                f"{json.dumps(r.get('pred_value'), ensure_ascii=False, indent=2)}\n"
            )
            f.write("\n" + "=" * 80 + "\n\n")

    print("Wrote:", samplewise_path)
    print("Wrote:", aggregated_path)
    print("Wrote:", content_mismatch_path)
    print(json.dumps(aggregated.get("summary", {}), indent=2))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--predictions",
        default="data/data_final/test_generated_sql_nl.schema_q_to_sql_predictions.json",
        help="Path to the SCHEMA_Q_TO_SQL predictions JSON file.",
    )
    ap.add_argument(
        "--out",
        default="data/data_final/test_generated_sql_nl.schema_q_to_sql_eval.json",
        help="Base output path used to derive .samplewise.json and .aggregated.json files.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    evaluate_predictions(args.predictions, args.out)


if __name__ == "__main__":
    main()


# python -m src.eval.evaluate_schema_q_to_sql_predictions \
#   --predictions data/data_final/test_generated_sql_nl.schema_q_to_sql_predictions.json \
#   --out data/data_final/test_generated_sql_nl.schema_q_to_sql_eval.json

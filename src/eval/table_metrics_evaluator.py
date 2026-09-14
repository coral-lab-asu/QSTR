import math
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.eval import evaluate_schema_q_to_sql_predictions as schema_eval


class TableMetricsEvaluator:
    """Compare two in-memory tables using the same metrics as SCHEMA_Q_TO_SQL eval.

    Required input table format for both `gold_table` and `pred_table`:

    ```python
    {
        "columns": ["col_a", "col_b", ...],
        "rows": [
            [value_a1, value_b1, ...],
            [value_a2, value_b2, ...],
        ],
    }
    ```

    Notes:
    - `columns` must be a list of column names in row order.
    - `rows` must be a list of row-lists aligned to `columns`.
    - `None` values are normalized to `0`, matching the existing evaluator.
    - Numeric values are rounded to 2 decimals before comparison, matching
      `src/eval/evaluate_schema_q_to_sql_predictions.py`.
    - `primary_key` is optional. If provided, it must be a list of column names.
    - PK and numeric metrics use a surname-aware row alignment path so surface
      forms like "Ben Duckett" and "Duckett" can still align.
    """

    _UNMATCHED_COST = 5.0
    _MISMATCH_COST = 10.0

    @staticmethod
    def _is_zeroish_cell(value: Any, numeric_tol: float = 0.2) -> bool:
        if value is None:
            return True
        numeric = schema_eval.eval_base.to_float(value)
        if numeric is not None:
            return abs(float(numeric)) <= numeric_tol
        return False

    @staticmethod
    def _row_to_dict(cols: Sequence[str], row: Sequence[Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for i, col in enumerate(cols):
            out[str(col)] = row[i] if i < len(row) else None
        return out

    @classmethod
    def _canonical_pk_value(cls, value: Any) -> Any:
        fv = schema_eval.eval_base.to_float(value)
        if fv is not None:
            return schema_eval._round_numeric(fv)
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        s = value.strip().lower()
        if not s:
            return ""
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        parts = [p for p in s.split() if p]
        if not parts:
            return ""
        # Use surname / final token for multi-token person names.
        return parts[-1]

    @classmethod
    def _canonical_pk_tuple(cls, row: Dict[str, Any], pk_cols: Sequence[str]) -> Tuple[Any, ...]:
        return tuple(cls._canonical_pk_value(row.get(c)) for c in pk_cols)

    @classmethod
    def _pk_similarity_cost(cls, gold_row: Dict[str, Any], pred_row: Dict[str, Any], pk_cols: Sequence[str]) -> float:
        gold_key = cls._canonical_pk_tuple(gold_row, pk_cols)
        pred_key = cls._canonical_pk_tuple(pred_row, pk_cols)
        if gold_key == pred_key:
            return 0.0

        total = 0.0
        for gv, pv in zip(gold_key, pred_key):
            if gv == pv:
                continue
            if isinstance(gv, str) and isinstance(pv, str) and gv and pv:
                total += 1.0 - SequenceMatcher(None, gv, pv).ratio()
            else:
                total += 1.0
        return total / max(1, len(pk_cols))

    @classmethod
    def _hungarian(cls, cost: List[List[float]]) -> List[Tuple[int, int]]:
        n = len(cost)
        m = len(cost[0]) if n else 0
        if n == 0 or m == 0:
            return []

        # Hungarian algorithm for rectangular matrices (1-indexed implementation).
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

    @classmethod
    def _aligned_row_pairs(
        cls,
        gold: Dict[str, Any],
        pred: Dict[str, Any],
        pk_cols: Optional[List[str]],
    ) -> Dict[str, Any]:
        gcols, grows = schema_eval.eval_base.answer_to_cols_rows(gold)
        pcols, prows = schema_eval.eval_base.answer_to_cols_rows(pred)
        common_cols = [c for c in gcols if c in set(pcols)]

        gold_rows = [cls._row_to_dict(common_cols, r) for r in grows if isinstance(r, list)]
        pred_rows = [cls._row_to_dict(common_cols, r) for r in prows if isinstance(r, list)]

        if not pk_cols:
            m = min(len(gold_rows), len(pred_rows))
            return {
                "method": "row_order",
                "common_cols": common_cols,
                "gold_rows": gold_rows[:m],
                "pred_rows": pred_rows[:m],
                "matched_pairs": [{"gold_index": i, "pred_index": i, "cost": 0.0} for i in range(m)],
                "unmatched_gold_indices": list(range(m, len(gold_rows))),
                "unmatched_pred_indices": list(range(m, len(pred_rows))),
            }

        size = max(len(gold_rows), len(pred_rows))
        if size == 0:
            return {
                "method": "surname_hungarian",
                "common_cols": common_cols,
                "gold_rows": [],
                "pred_rows": [],
                "matched_pairs": [],
                "unmatched_gold_indices": [],
                "unmatched_pred_indices": [],
            }

        cost = [[cls._UNMATCHED_COST for _ in range(size)] for _ in range(size)]
        for i in range(len(gold_rows)):
            for j in range(len(pred_rows)):
                sim_cost = cls._pk_similarity_cost(gold_rows[i], pred_rows[j], pk_cols)
                cost[i][j] = sim_cost if sim_cost < 1.0 else cls._MISMATCH_COST

        assignments = cls._hungarian(cost)
        matched_pairs: List[Dict[str, Any]] = []
        matched_gold = set()
        matched_pred = set()
        aligned_gold_rows: List[Dict[str, Any]] = []
        aligned_pred_rows: List[Dict[str, Any]] = []

        for gi, pj in assignments:
            if gi >= len(gold_rows) or pj >= len(pred_rows):
                continue
            c = cost[gi][pj]
            if c >= cls._UNMATCHED_COST:
                continue
            matched_pairs.append({"gold_index": gi, "pred_index": pj, "cost": c})
            matched_gold.add(gi)
            matched_pred.add(pj)
            aligned_gold_rows.append(gold_rows[gi])
            aligned_pred_rows.append(pred_rows[pj])

        return {
            "method": "surname_hungarian",
            "common_cols": common_cols,
            "gold_rows": aligned_gold_rows,
            "pred_rows": aligned_pred_rows,
            "matched_pairs": matched_pairs,
            "unmatched_gold_indices": [i for i in range(len(gold_rows)) if i not in matched_gold],
            "unmatched_pred_indices": [j for j in range(len(pred_rows)) if j not in matched_pred],
        }

    @classmethod
    def _compute_pk_metrics_aligned(
        cls,
        gold: Dict[str, Any],
        pred: Dict[str, Any],
        pk_cols: List[str],
    ) -> Dict[str, Any]:
        gcols, grows = schema_eval.eval_base.answer_to_cols_rows(gold)
        pcols, prows = schema_eval.eval_base.answer_to_cols_rows(pred)
        pk_present = all(c in pcols for c in pk_cols)
        if any(c not in gcols for c in pk_cols):
            return {
                "pk_present": pk_present,
                "pk_eval_skipped": True,
                "pk_recall": None,
                "pk_precision": None,
                "pk_f1": None,
                "pk_exact_set_match": None,
                "gold_pk_count": None,
                "pred_pk_count": None,
                "alignment_method": "surname_hungarian",
            }

        aligned = cls._aligned_row_pairs(gold, pred, pk_cols)
        gold_n = len(grows)
        pred_n = len(prows)
        inter_n = len(aligned["matched_pairs"])
        recall = (inter_n / gold_n) if gold_n else 1.0
        precision = (inter_n / pred_n) if pred_n else (1.0 if gold_n == 0 else 0.0)
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        exact = inter_n == gold_n == pred_n and not aligned["unmatched_gold_indices"] and not aligned["unmatched_pred_indices"]
        return {
            "pk_present": pk_present,
            "pk_eval_skipped": False,
            "pk_recall": recall,
            "pk_precision": precision,
            "pk_f1": f1,
            "pk_exact_set_match": exact,
            "gold_pk_count": gold_n,
            "pred_pk_count": pred_n,
            "alignment_method": aligned["method"],
            "matched_pk_n": inter_n,
            "unmatched_gold_n": len(aligned["unmatched_gold_indices"]),
            "unmatched_pred_n": len(aligned["unmatched_pred_indices"]),
        }

    @classmethod
    def _compute_numeric_metrics_aligned(
        cls,
        gold: Dict[str, Any],
        pred: Dict[str, Any],
        pk_cols: Optional[List[str]],
    ) -> Dict[str, Any]:
        gcols, grows = schema_eval.eval_base.answer_to_cols_rows(gold)
        pcols, prows = schema_eval.eval_base.answer_to_cols_rows(pred)
        common_cols = [c for c in gcols if c in set(pcols)]
        numeric_cols = [
            c
            for c in common_cols
            if schema_eval.eval_base.looks_numeric_column(gcols, grows, c)
            or schema_eval.eval_base.looks_numeric_column(pcols, prows, c)
        ]
        if not numeric_cols:
            return {"numeric_eval_skipped": True, "per_column": {}, "macro": {}, "alignment_method": None}

        aligned = cls._aligned_row_pairs(gold, pred, pk_cols)
        gold_rows = aligned["gold_rows"]
        pred_rows = aligned["pred_rows"]

        per_col: Dict[str, Dict[str, Any]] = {}
        maes: List[float] = []
        rmses: List[float] = []
        counts: List[int] = []
        overcount_total = 0
        undercount_total = 0

        for c in numeric_cols:
            errs = []
            for gr, pr in zip(gold_rows, pred_rows):
                gv = schema_eval.eval_base.to_float(gr.get(c))
                pv = schema_eval.eval_base.to_float(pr.get(c))
                if gv is None or pv is None:
                    continue
                gv = round(float(gv), schema_eval.ROUND_DECIMALS)
                pv = round(float(pv), schema_eval.ROUND_DECIMALS)
                errs.append(pv - gv)

            if not errs:
                per_col[c] = {"n": 0, "mae": None, "rmse": None, "bias": None}
                continue

            arr = schema_eval.eval_base.np.array(errs, dtype=float)
            mae = float(schema_eval.eval_base.np.mean(schema_eval.eval_base.np.abs(arr)))
            rmse = float(schema_eval.eval_base.np.sqrt(schema_eval.eval_base.np.mean(arr ** 2)))
            bias = float(schema_eval.eval_base.np.mean(arr))
            overcount_n = int(schema_eval.eval_base.np.sum(arr > 0))
            undercount_n = int(schema_eval.eval_base.np.sum(arr < 0))
            overcount_total += overcount_n
            undercount_total += undercount_n
            per_col[c] = {
                "n": int(arr.size),
                "mae": mae,
                "rmse": rmse,
                "bias": bias,
                "overcount_n": overcount_n,
                "undercount_n": undercount_n,
                "Overcount%": float(100.0 * overcount_n / arr.size),
                "Undercount%": float(100.0 * undercount_n / arr.size),
            }
            maes.append(mae)
            rmses.append(rmse)
            counts.append(arr.size)

        total_n = int(sum(counts))
        if total_n > 0:
            weighted_mae = sum(m * n for m, n in zip(maes, counts)) / total_n
            weighted_rmse = sum(r * n for r, n in zip(rmses, counts)) / total_n
        else:
            weighted_mae = None
            weighted_rmse = None

        return {
            "numeric_eval_skipped": False,
            "per_column": per_col,
            "macro": {
                "weighted_mae": float(weighted_mae) if weighted_mae is not None else None,
                "weighted_rmse": float(weighted_rmse) if weighted_rmse is not None else None,
                "total_numeric_pairs": total_n,
                "overcount_n": overcount_total,
                "undercount_n": undercount_total,
                "Overcount%": float(100.0 * overcount_total / total_n) if total_n else None,
                "Undercount%": float(100.0 * undercount_total / total_n) if total_n else None,
            },
            "alignment_method": aligned["method"],
            "matched_row_pairs": len(aligned["matched_pairs"]),
            "unmatched_gold_n": len(aligned["unmatched_gold_indices"]),
            "unmatched_pred_n": len(aligned["unmatched_pred_indices"]),
        }

    @classmethod
    def _compute_pk_cell_metrics_aligned(
        cls,
        gold: Dict[str, Any],
        pred: Dict[str, Any],
        pk_cols: Optional[List[str]],
        numeric_tol: float = 0.2,
    ) -> Dict[str, Any]:
        if not pk_cols:
            return {
                "cell_acc": None,
                "correct_cells": 0,
                "total_cells": 0,
                "pk_cell_eval_skipped": True,
            }

        gcols, _ = schema_eval.eval_base.answer_to_cols_rows(gold)
        pcols, _ = schema_eval.eval_base.answer_to_cols_rows(pred)
        if any(c not in gcols for c in pk_cols) or any(c not in pcols for c in pk_cols):
            return {
                "cell_acc": None,
                "correct_cells": 0,
                "total_cells": 0,
                "pk_cell_eval_skipped": True,
            }

        aligned = cls._aligned_row_pairs(gold, pred, pk_cols)
        eval_cols = [c for c in aligned["common_cols"] if c not in set(pk_cols)]
        if not eval_cols:
            return {
                "cell_acc": None,
                "correct_cells": 0,
                "total_cells": 0,
                "pk_cell_eval_skipped": True,
            }

        correct_cells = 0
        total_cells = 0
        for gold_row, pred_row in zip(aligned["gold_rows"], aligned["pred_rows"]):
            for col in eval_cols:
                gv = gold_row.get(col)
                pv = pred_row.get(col)
                total_cells += 1

                if gv is None and pv is None:
                    correct_cells += 1
                    continue
                if gv is None or pv is None:
                    continue

                gv_num = schema_eval.eval_base.to_float(gv)
                pv_num = schema_eval.eval_base.to_float(pv)
                if gv_num is not None and pv_num is not None:
                    if abs(float(pv_num) - float(gv_num)) <= numeric_tol:
                        correct_cells += 1
                    continue

                gv_norm = str(gv).strip().lower()
                pv_norm = str(pv).strip().lower()
                if gv_norm == pv_norm:
                    correct_cells += 1

        if total_cells == 0:
            return {
                "cell_acc": None,
                "correct_cells": 0,
                "total_cells": 0,
                "zero_null_metrics": {
                    "accuracy": None,
                    "precision": None,
                    "recall": None,
                    "tp": 0,
                    "fp": 0,
                    "fn": 0,
                    "tn": 0,
                    "gold_zero_null_n": 0,
                    "pred_zero_null_n": 0,
                    "eval_cell_n": 0,
                    "zero_null_eval_skipped": True,
                },
                "pk_cell_eval_skipped": True,
            }

        tp = 0
        fp = 0
        fn = 0
        tn = 0
        for gold_row, pred_row in zip(aligned["gold_rows"], aligned["pred_rows"]):
            for col in eval_cols:
                gold_is_zero = cls._is_zeroish_cell(gold_row.get(col), numeric_tol=numeric_tol)
                pred_is_zero = cls._is_zeroish_cell(pred_row.get(col), numeric_tol=numeric_tol)
                if gold_is_zero and pred_is_zero:
                    tp += 1
                elif gold_is_zero and not pred_is_zero:
                    fn += 1
                elif not gold_is_zero and pred_is_zero:
                    fp += 1
                else:
                    tn += 1

        zero_eval_n = tp + fp + fn + tn
        zero_accuracy = ((tp + tn) / zero_eval_n) if zero_eval_n else None
        zero_precision = (tp / (tp + fp)) if (tp + fp) else None
        zero_recall = (tp / (tp + fn)) if (tp + fn) else None

        return {
            "cell_acc": (100.0 * correct_cells / total_cells),
            "correct_cells": correct_cells,
            "total_cells": total_cells,
            "zero_null_metrics": {
                "accuracy": zero_accuracy,
                "precision": zero_precision,
                "recall": zero_recall,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "gold_zero_null_n": tp + fn,
                "pred_zero_null_n": tp + fp,
                "eval_cell_n": zero_eval_n,
                "zero_null_eval_skipped": False,
            },
            "pk_cell_eval_skipped": False,
        }

    @classmethod
    def compare_tables(
        cls,
        gold_table: Dict[str, Any],
        pred_table: Dict[str, Any],
        primary_key: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(gold_table, dict):
            raise TypeError(f"gold_table must be a dict, got {type(gold_table)}")
        if not isinstance(pred_table, dict):
            raise TypeError(f"pred_table must be a dict, got {type(pred_table)}")

        pk_cols: Optional[List[str]] = None
        if primary_key is not None:
            if not isinstance(primary_key, list):
                raise TypeError(f"primary_key must be a list or None, got {type(primary_key)}")
            pk_cols = [str(c) for c in primary_key]

        gold = schema_eval._normalize_table_for_eval(schema_eval._nulls_to_zero_table(gold_table))
        pred = schema_eval._normalize_table_for_eval(schema_eval._nulls_to_zero_table(pred_table))

        table_match = schema_eval._exact_table_match_2dp(gold, pred)
        pk_metrics_surface = schema_eval._compute_pk_metrics_2dp(gold, pred, pk_cols) if pk_cols else {
            "pk_present": None,
            "pk_eval_skipped": True,
            "pk_recall": None,
            "pk_precision": None,
            "pk_f1": None,
            "pk_exact_set_match": None,
            "gold_pk_count": None,
            "pred_pk_count": None,
        }
        numeric_metrics_surface = schema_eval._compute_numeric_metrics_2dp(gold, pred, pk_cols)
        pk_metrics = cls._compute_pk_metrics_aligned(gold, pred, pk_cols) if pk_cols else pk_metrics_surface
        numeric_metrics = cls._compute_numeric_metrics_aligned(gold, pred, pk_cols)
        pk_cell_metrics = cls._compute_pk_cell_metrics_aligned(gold, pred, pk_cols)

        agg = schema_eval._empty_agg()
        agg[schema_eval.SETTING]["n_total"] = 1
        agg[schema_eval.SETTING]["n"] = 1
        agg[schema_eval.SETTING]["exact_match_n"] = 1 if table_match["exact_match"] else 0
        agg[schema_eval.SETTING]["row_match_n"] = 1 if table_match["row_match"] else 0
        agg[schema_eval.SETTING]["col_match_n"] = 1 if table_match["col_match"] else 0
        agg[schema_eval.SETTING]["content_match_n"] = 1 if table_match["content_match"] else 0

        if not pk_metrics["pk_eval_skipped"]:
            agg[schema_eval.SETTING]["pk_eval_n"] = 1
            agg[schema_eval.SETTING]["pk_exact_n"] = 1 if pk_metrics["pk_exact_set_match"] else 0
            agg[schema_eval.SETTING]["pk_recall_sum"] = float(pk_metrics["pk_recall"] or 0.0)

        if not numeric_metrics["numeric_eval_skipped"]:
            agg[schema_eval.SETTING]["num_eval_n"] = 1
            rmse = numeric_metrics["macro"].get("weighted_rmse")
            mae = numeric_metrics["macro"].get("weighted_mae")
            agg[schema_eval.SETTING]["rmse_sum"] = float(rmse) if rmse is not None else 0.0
            agg[schema_eval.SETTING]["mae_sum"] = float(mae) if mae is not None else 0.0

        return {
            "setting_to_pred_key": {schema_eval.SETTING: schema_eval.PRED_KEY},
            "gold_table": gold,
            "pred_table": pred,
            "primary_key": pk_cols,
            "table_match": table_match,
            "pk_metrics": pk_metrics,
            "pk_cell_metrics": pk_cell_metrics,
            "numeric_metrics": numeric_metrics,
            "pk_metrics_surface": pk_metrics_surface,
            "numeric_metrics_surface": numeric_metrics_surface,
            "summary": schema_eval._summary_from_agg(agg),
            "agg": agg,
        }

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.eval.table_metrics_evaluator import TableMetricsEvaluator  # noqa: E402


def main() -> None:
    gold = {
        "columns": ["batsman", "strike_rate_after_high_bowler_concession"],
        "rows": [
            ["Duckett", 100.0],
            ["Archer", 83.33333587646484],
            ["Livingstone", 69.23076629638672],
            ["Root", 67.74193572998047],
            ["Overton", 55.0],
            ["Brook", 50.0],
            ["Mahmood", 50.0],
            ["Buttler", 48.83720779418945],
            ["Rashid", 22.22222137451172],
        ],
    }
    pred = {
        "columns": ["batsman", "strike_rate_after_high_bowler_concession"],
        "rows": [
            ["Ben Duckett", 114.28],
            ["Joe Root", 84.09],
            ["Harry Brook", 65.51],
            ["Liam Livingstone", 60],
            ["Jamie Overton", 55],
            ["Jofra Archer", 80.64],
            ["Jos Buttler", 48.83],
            ["Adil Rashid", 22.22],
        ],
    }

    out = TableMetricsEvaluator.compare_tables(gold, pred, primary_key=["batsman"])
    print(json.dumps(
        {
            "table_match": out["table_match"],
            "pk_metrics": out["pk_metrics"],
            "pk_metrics_surface": out["pk_metrics_surface"],
            "numeric_metrics": out["numeric_metrics"],
            "numeric_metrics_surface": out["numeric_metrics_surface"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()

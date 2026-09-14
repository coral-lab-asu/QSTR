import json
import pytest
from src.benchmark_data import read_dataset


def test_full_context_fallback_and_ids(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{"question": "Total?", "context": "", "context_full": "One run.",
                                 "answer": {"columns": ["total"], "rows": [[1]]}}]))
    row = read_dataset(path)[0]
    assert row["context"] == "One run."
    assert row["record_id"] == "benchmark-0"
    assert row["sample_id"] == 0


def test_raw_query_bank_rejected(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text('[{"question": "Total?", "sql": "SELECT 1"}]')
    with pytest.raises(ValueError, match="prepare_benchmark"):
        read_dataset(path)


def test_preparation_excludes_incorrect_answers(tmp_path):
    from scripts.prepare_benchmark import prepare
    csv = tmp_path / "match.csv"
    csv.write_text('overs,commentary,runs\n0.1,One run,1\n')
    path = tmp_path / "input.json"
    base = {"question": "Total?", "match_path": str(csv), "sql": "SELECT SUM(runs) AS total FROM df",
            "item_id": "same"}
    rows = [dict(base, ground_truth_table={"columns": ["total"], "rows": [[n]]}) for n in (1.0,99.0,1.0)]
    path.write_text(json.dumps(rows))
    output = tmp_path / "prepared.jsonl"
    report = prepare(path, output)
    assert report["accepted"] == 2
    assert report["excluded"][0]["index"] == 1
    prepared = read_dataset(output)
    assert [r["sample_id"] for r in prepared] == [0,2]
    assert len({r["record_id"] for r in prepared}) == 2
    assert all(r["context"] for r in prepared)
    # Exercise the evaluator CLI with synthetic perfect predictions. This
    # checks serialization and ID joins, not model quality.
    import subprocess
    import sys
    from pathlib import Path
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text("\n".join(json.dumps({"record_id": r["record_id"], "pred_table": r["answer"]}) for r in prepared))
    summary = tmp_path / "summary.json"
    subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "baseline-scripts/eval_table_predictions.py"),
                    "--dataset", str(output), "--predictions", str(predictions),
                    "--out-summary", str(summary), "--out-samplewise", str(tmp_path / "scores.jsonl")], check=True)
    result = json.loads(summary.read_text())
    assert result["summary"]["n_eval"] == 2
    assert result["summary"]["exact_match_rate"] == 1.0

import json
import tempfile
import unittest
from pathlib import Path

from pipelines.cmt2.pipeline.dataset_pipeline import deduplicate_records, load_records, write_records


class DatasetPipelineTests(unittest.TestCase):
    def test_jsonl_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            rows = [{"record_id": "a", "sql": "select 1"}, {"record_id": "b", "sql": "select 2"}]
            write_records(path, rows)
            loaded, envelope = load_records(path)
            self.assertEqual(rows, loaded)
            self.assertEqual({}, envelope)

    def test_json_envelope_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.json"
            rows = [{"item_id": 1, "answer": {"columns": ["x"], "rows": [[1]]}}]
            write_records(path, rows, envelope={"final": [], "failed": []})
            loaded, envelope = load_records(path)
            self.assertEqual(rows, loaded)
            self.assertIn("failed", envelope)

    def test_deduplicates_same_source_and_answer(self):
        rows = [
            {"record_id": "first", "match_path": "game.csv", "answer": {"columns": ["x"], "rows": [[1]]}},
            {"record_id": "duplicate", "match_path": "game.csv", "answer": {"columns": ["x"], "rows": [[1]]}},
            {"record_id": "other-source", "match_path": "other.csv", "answer": {"columns": ["x"], "rows": [[1]]}},
        ]
        kept, removed = deduplicate_records(rows)
        self.assertEqual(["first", "other-source"], [row["record_id"] for row in kept])
        self.assertEqual(1, len(removed))


if __name__ == "__main__":
    unittest.main()

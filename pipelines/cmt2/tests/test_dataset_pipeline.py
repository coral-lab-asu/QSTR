import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

from pipelines.cmt2.pipeline.dataset_pipeline import (
    answer_signature,
    deduplicate_records,
    is_read_only_sql,
    load_records,
    validate_records,
    write_records,
)


CMT2_ROOT = Path(__file__).resolve().parents[1]
HAS_PIPELINE_DEPS = importlib.util.find_spec("duckdb") is not None and importlib.util.find_spec("pandas") is not None


class DatasetPipelineTests(unittest.TestCase):
    def test_answer_signature_treats_rows_as_a_multiset(self):
        first = {"columns": ["x"], "rows": [[1], [2]]}
        reversed_rows = {"columns": ["x"], "rows": [[2], [1]]}
        self.assertEqual(answer_signature(first), answer_signature(reversed_rows))

    def test_legacy_serialized_list_fields_are_normalized(self):
        from pipelines.cmt2.generate_questions import normalize_list_field

        self.assertEqual([], normalize_list_field("[]"))
        self.assertEqual(["bowler", "batsman"], normalize_list_field("['bowler', 'batsman']"))
        self.assertEqual(["question one", "question two"], normalize_list_field('["question one", "question two"]'))
        self.assertEqual(["single value"], normalize_list_field("single value"))

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

    def test_read_only_sql_guard(self):
        self.assertTrue(is_read_only_sql("SELECT SUM(x) FROM df;"))
        self.assertTrue(is_read_only_sql("SELECT REPLACE(commentary, 'a', 'b') FROM df"))
        self.assertTrue(is_read_only_sql("WITH totals AS (SELECT SUM(x) AS n FROM df) SELECT n FROM totals"))
        self.assertFalse(is_read_only_sql("DELETE FROM df"))
        self.assertFalse(is_read_only_sql("SELECT * FROM df; DROP TABLE df"))
        self.assertFalse(is_read_only_sql("SELECT * FROM read_csv_auto('private.csv')"))

    @unittest.skipUnless(HAS_PIPELINE_DEPS, "duckdb and pandas are required for the integration smoke test")
    def test_generation_validation_and_deduplication_smoke(self):
        from pipelines.cmt2.generate_questions import PipelineConfig, generate_dataset

        fixture_csv = CMT2_ROOT / "examples" / "smoke_match.csv"
        fixture_templates = CMT2_ROOT / "examples" / "smoke_templates.py"
        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            def generate(output_dir: str):
                return generate_dataset(
                    PipelineConfig(
                        templates_paths=[str(fixture_templates)],
                        matches_glob=str(fixture_csv),
                        output_dir=output_dir,
                        max_matches=1,
                        total_examples=3,
                        samples_per_template_per_match=1,
                        seed=42,
                        context_max_chars=0,
                        answer_max_rows=0,
                        drop_zeroish=False,
                        write_analysis_jsonls=False,
                        roi_stratify=False,
                        roi_bucket_mode="random",
                    )
                )

            first = generate(first_tmp)
            second = generate(second_tmp)
            first_rows, _ = load_records(first["dataset_path_no_overs"])
            second_rows, _ = load_records(second["dataset_path_no_overs"])

            self.assertEqual(3, len(first_rows))
            self.assertEqual(
                [row["record_id"] for row in first_rows],
                [row["record_id"] for row in second_rows],
            )
            report = validate_records(first_rows)
            self.assertEqual(3, report["valid_records"])

            unsafe = dict(first_rows[0], sql="DELETE FROM df")
            unsafe_report = validate_records([unsafe])
            self.assertEqual(1, unsafe_report["invalid_records"])
            self.assertIn("read-only", unsafe_report["records"][0]["error"])

            mismatched = dict(first_rows[0], answer={"columns": ["total_runs"], "rows": [[999]]})
            mismatch_report = validate_records([mismatched])
            self.assertEqual(1, mismatch_report["invalid_records"])
            self.assertFalse(mismatch_report["records"][0]["answer_match"])

            legacy = dict(first_rows[0])
            legacy["ground_truth_table"] = legacy.pop("answer")
            legacy_report = validate_records([legacy])
            self.assertEqual(1, legacy_report["valid_records"])
            self.assertTrue(legacy_report["records"][0]["answer_checked"])
            legacy["ground_truth_table"] = {"columns": ["total_runs"], "rows": [[999]]}
            self.assertEqual(1, validate_records([legacy])["invalid_records"])

            kept, removed = deduplicate_records(first_rows)
            self.assertEqual(2, len(kept))
            self.assertEqual(1, len(removed))


if __name__ == "__main__":
    unittest.main()

import unittest
import json
import tempfile
from pathlib import Path

import pandas as pd

from src.core.generate_questions_split import SplitConfig, extract_row_indices_from_query, generate_split_dataset


class GenerateQuestionsSplitProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame(
            {
                "overs": [0.1, 0.2, 6.1, 7.1, 10.2],
                "bowler": ["A", "A", "B", "B", "A"],
                "batsman": ["X", "Y", "X", "Y", "X"],
                "batsman_runs": [1, 2, 3, 4, 6],
                "batsman_fours": [0, 0, 0, 1, 0],
                "batsman_sixes": [0, 0, 0, 0, 1],
                "batsman_bowls_faced": [1, 1, 1, 1, 1],
                "bowler_runs_given": [1, 2, 3, 4, 6],
                "bowler_wickets": [0, 1, 0, 1, 0],
                "bowler_bowls_done": [1, 2, 1, 2, 3],
                "commentary": ["a", "b", "c", "d", "e"],
            }
        )

    def test_where_only_provenance(self) -> None:
        q = "SELECT bowler, batsman_runs FROM df WHERE CEIL(overs) <= 6 ORDER BY batsman_runs DESC"
        out = extract_row_indices_from_query(q, self.df, None)
        self.assertTrue(out["provenance_supported"])
        self.assertEqual(out["row_indices_contributing"], [0, 1])
        self.assertEqual(out["output_row_provenance"], [[1], [0]])
        self.assertEqual([s["node_type"] for s in out["provenance_steps"]], ["scan", "filter_where", "project", "order_by", "query"])
        self.assertEqual(out["step_row_progression"]["num_steps"], 3)
        self.assertEqual(out["step_row_progression"]["max_row_count"], 2)
        self.assertEqual(out["step_row_progression"]["steps"][0]["node_type"], "filter_where")
        self.assertEqual(out["step_row_progression"]["steps"][0]["row_indices"], [0, 1])
        self.assertEqual(out["step_row_progression"]["steps"][1]["node_type"], "project")

    def test_group_by_and_having_provenance(self) -> None:
        q = (
            "SELECT bowler, SUM(batsman_runs) AS runs "
            "FROM df WHERE CEIL(overs) <= 11 "
            "GROUP BY bowler HAVING SUM(batsman_runs) > 5 "
            "ORDER BY runs DESC"
        )
        out = extract_row_indices_from_query(q, self.df, None)
        self.assertTrue(out["provenance_supported"])
        self.assertEqual(out["row_indices_contributing"], [0, 1, 2, 3, 4])
        self.assertEqual(len(out["output_row_provenance"]), 2)
        self.assertEqual(sorted(out["output_row_provenance"][0]), [0, 1, 4])
        self.assertEqual(sorted(out["output_row_provenance"][1]), [2, 3])

    def test_aggregate_without_group_by_omits_group_step_from_progression(self) -> None:
        q = (
            "SELECT SUM(batsman_runs) AS total_runs_scored "
            "FROM df WHERE batsman = 'X' AND bowler = 'A'"
        )
        out = extract_row_indices_from_query(q, self.df, None)
        self.assertTrue(out["provenance_supported"])
        node_types = [step["node_type"] for step in out["step_row_progression"]["steps"]]
        self.assertEqual(node_types, ["filter_where", "project"])

    def test_cte_provenance(self) -> None:
        q = (
            "WITH base AS ("
            "SELECT bowler, batsman_runs FROM df WHERE CEIL(overs) <= 6"
            ") "
            "SELECT bowler, SUM(batsman_runs) AS runs FROM base GROUP BY bowler ORDER BY runs DESC"
        )
        out = extract_row_indices_from_query(q, self.df, None)
        self.assertTrue(out["provenance_supported"])
        self.assertIsNone(out["provenance_error"])
        self.assertTrue(any(step["label"] == "cte:base" for step in out["provenance_steps"]))
        self.assertEqual(out["row_indices_contributing"], [0, 1])

    def test_unsupported_join_falls_back_cleanly(self) -> None:
        q = (
            "SELECT a.bowler, a.batsman_runs "
            "FROM df AS a JOIN df AS b ON a.bowler = b.bowler"
        )
        out = extract_row_indices_from_query(q, self.df, None)
        self.assertFalse(out["provenance_supported"])
        self.assertTrue(out["provenance_error"])
        self.assertEqual(out["row_indices_contributing"], [])
        self.assertEqual(out["provenance_steps"], [])

    def test_unsupported_window_falls_back_cleanly(self) -> None:
        q = "SELECT batsman, ROW_NUMBER() OVER (ORDER BY overs) AS row_num FROM df"
        out = extract_row_indices_from_query(q, self.df, None)
        self.assertFalse(out["provenance_supported"])
        self.assertEqual(out["provenance_error"], "window_not_supported")
        self.assertEqual(out["row_indices_contributing"], [])

    def test_generate_split_dataset_emits_primary_key_and_sample_idx(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matches_dir = tmp / "matches"
            matches_dir.mkdir()
            output_dir = tmp / "out"

            df = pd.DataFrame(
                {
                    "overs": [0.1, 0.2],
                    "bowler": ["A", "A"],
                    "batsman": ["X", "Y"],
                    "batsman_runs": [1, 2],
                    "commentary": ["ball one", "ball two"],
                }
            )
            match_path = matches_dir / "match.csv"
            df.to_csv(match_path, index=False)

            templates = [
                {
                    "template_id": 1,
                    "idx": "m0",
                    "item_id": "m0",
                    "question": "List batsman runs.",
                    "sql": "SELECT batsman, batsman_runs FROM df ORDER BY batsman_runs DESC",
                    "variables": [],
                    "primary_key": ["batsman"],
                }
            ]
            templates_path = tmp / "templates.json"
            templates_path.write_text(json.dumps(templates), encoding="utf-8")

            result = generate_split_dataset(
                SplitConfig(
                    templates_paths=[str(templates_path)],
                    matches_glob=str(matches_dir / "*.csv"),
                    output_dir=str(output_dir),
                    seed=1,
                    context_max_chars=0,
                    answer_max_rows=0,
                    drop_zeroish=False,
                    max_zeroish_frac=1.0,
                    max_init_attempts=1,
                    split_num_matches=1,
                    min_match_rows=0,
                    split_templates_per_match=1,
                    split_inits_per_template_per_match=1,
                    temporal_all_phrases=False,
                    split_use_base_question_only=True,
                    cover_all_templates_once=False,
                )
            )

            payload = json.loads(Path(result["dataset_path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(payload["records"]), 1)
            rec = payload["records"][0]
            self.assertEqual(rec["primary_key"], ["batsman"])
            self.assertEqual(rec["sample_idx"], 0)


if __name__ == "__main__":
    unittest.main()

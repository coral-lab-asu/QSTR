import tempfile
import unittest
from pathlib import Path

from pipelines.synthetic_data.synData.generate_op_sequence import demo_generate_and_save


class SyntheticPipelineTests(unittest.TestCase):
    def test_seeded_generation_is_reproducible_and_writes_to_requested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            first_path, first_dir, first_sessions = demo_generate_and_save(
                out_dir=first_tmp,
                num_sessions=2,
                seed=12345,
            )
            second_path, second_dir, second_sessions = demo_generate_and_save(
                out_dir=second_tmp,
                num_sessions=2,
                seed=12345,
            )

            self.assertEqual(first_sessions, second_sessions)
            self.assertEqual(Path(first_tmp), Path(first_dir))
            self.assertEqual(Path(second_tmp), Path(second_dir))
            self.assertEqual(Path(first_path).read_bytes(), Path(second_path).read_bytes())
            self.assertNotIn("generated_at", first_sessions[0])


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.engine.metrics import record_metrics


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.run_path = self.root / "run"
        self.round_dir = self.run_path / "01-unit" / "rounds" / "1"
        self.round_dir.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_records_counts_and_last_input_token_value(self):
        (self.round_dir / "implement.events.jsonl").write_text(
            '{"type":"item.completed"}\n'
            '{"type":"item.started"}\n'
            '{"type":"item.completed","input_tokens":17}\n'
            '{"type":"turn.completed","usage":{"input_tokens":1234}}\n'
        )
        (self.round_dir / "diff.patch").write_text(
            "diff --git a/a b/a\n+---\n diff --git should not count\n"
            "diff --git a/b b/b\n"
        )
        with patch("harness.engine.metrics.time.time", return_value=1060):
            record_metrics(self.run_path, "01-unit", 2, self.round_dir, 1000)
        self.assertEqual(
            (self.run_path / "metrics.tsv").read_text(),
            "01-unit\t2\t1\t2\t2\t1234\n",
        )

    def test_missing_files_and_missing_matches_are_zero(self):
        with patch("harness.engine.metrics.time.time", return_value=1059):
            record_metrics(self.run_path, "unit", 1, self.round_dir, 1000)
        self.assertEqual(
            (self.run_path / "metrics.tsv").read_text(),
            "unit\t1\t0\t0\t0\t0\n",
        )

    def test_existing_files_without_matching_records_are_zero(self):
        (self.round_dir / "implement.events.jsonl").write_text(
            '{"type":"item.started","usage":{"cached_input_tokens":5}}\n'
        )
        (self.round_dir / "diff.patch").write_text("--- a/file\n+++ b/file\n")
        with patch("harness.engine.metrics.time.time", return_value=1059):
            record_metrics(self.run_path, "unit", 1, self.round_dir, 1000)
        self.assertEqual(
            (self.run_path / "metrics.tsv").read_text(),
            "unit\t1\t0\t0\t0\t0\n",
        )

    def test_appends_records(self):
        (self.run_path / "metrics.tsv").write_text("prior\tline\n")
        with patch("harness.engine.metrics.time.time", return_value=1060):
            record_metrics(self.run_path, "unit", 1, self.round_dir, 1000)
        self.assertEqual(
            (self.run_path / "metrics.tsv").read_text(),
            "prior\tline\nunit\t1\t1\t0\t0\t0\n",
        )


if __name__ == "__main__":
    unittest.main()

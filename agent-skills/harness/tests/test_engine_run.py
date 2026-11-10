import tempfile
import unittest
from pathlib import Path

from harness.engine.run import RunDir, RunError, Settings, valid_name, valid_pause


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.settings = Settings("gpt-6-luna", "high", "")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_name_matches_bash_pattern(self):
        for name in ("run-1", "A_b.c", "0"):
            self.assertTrue(valid_name(name))
        for name in ("", ".", "..", "bad/name", "has space", "é"):
            self.assertFalse(valid_name(name))

    def test_valid_pause_matches_bash_pattern(self):
        for pause in ("none", "each", "2", "2,4", "01,0"):
            self.assertTrue(valid_pause(pause))
        for pause in ("", "Each", "1,", ",1", "1,,2", "1, 2"):
            self.assertFalse(valid_pause(pause))

    def test_create_writes_run_files_and_exact_status_header(self):
        run = RunDir.create(self.root, "sample", "/repo/path", self.settings, "2,4")

        self.assertEqual(run.path, self.root / "sample")
        self.assertEqual(run.name, "sample")
        self.assertEqual(run.repo, "/repo/path")
        self.assertEqual(run.settings, self.settings)
        self.assertEqual(run.pause, "2,4")
        self.assertEqual((run.path / "repo").read_text(), "/repo/path\n")
        self.assertEqual((run.path / "pause").read_text(), "2,4\n")
        self.assertEqual((run.path / "settings").read_text(), "gpt-6-luna high \n")
        self.assertEqual((run.path / "status.log").read_text(), "time\tevent\n")

    def test_create_rejects_bad_name_and_existing_folder(self):
        with self.assertRaisesRegex(RunError, r"^bad run name: \.\.$"):
            RunDir.create(self.root, "..", "/repo", self.settings, "none")

        existing = self.root / "exists"
        existing.mkdir()
        with self.assertRaisesRegex(
            RunError,
            r"^run already exists: .*exists \(finish it, or resume it\)$",
        ):
            RunDir.create(self.root, "exists", "/repo", self.settings, "none")

    def test_load_reads_values_and_reports_invalid_or_missing_run(self):
        run = RunDir.create(self.root, "sample", "/repo/path", self.settings, "each")
        loaded = RunDir.load(self.root, "sample")
        self.assertEqual(loaded.repo, "/repo/path")
        self.assertEqual(loaded.settings, self.settings)
        self.assertEqual(loaded.pause, "each")

        with self.assertRaisesRegex(RunError, "^bad run name: a/b$"):
            RunDir.load(self.root, "a/b")
        with self.assertRaisesRegex(RunError, "^no such run: .*/missing$"):
            RunDir.load(self.root, "missing")

        (run.path / "settings").unlink()
        self.assertIsNone(RunDir.load(self.root, "sample").settings)

    def test_save_settings_and_set_pause_keep_bash_formats(self):
        run = RunDir.create(self.root, "sample", "/repo", self.settings, "none")
        settings = Settings("model", "effort", "review")
        run.save_settings(settings)
        run.set_pause("each")
        self.assertEqual((run.path / "settings").read_text(), "model effort review\n")
        self.assertEqual((run.path / "pause").read_text(), "each\n")
        self.assertEqual(RunDir.load(self.root, "sample").settings, settings)

    def test_reviewer_model_and_backend_persist_on_a_second_line_and_old_files_still_load(self):
        run = RunDir.create(self.root, "sample", "/repo", self.settings, "none")
        settings = Settings("model", "effort", "", "claude-haiku-5-5", "claude")
        run.save_settings(settings)
        self.assertEqual(
            (run.path / "settings").read_text(),
            "model effort \nreview_model=claude-haiku-5-5 review_backend=claude\n",
        )
        self.assertEqual(RunDir.load(self.root, "sample").settings, settings)
        (run.path / "settings").write_text("model effort review\n")
        self.assertEqual(
            RunDir.load(self.root, "sample").settings,
            Settings("model", "effort", "review", "", "", "0", "reviewer"),
        )

    def test_takeover_settings_round_trip_every_combination_and_keep_exact_file_text(self):
        run = RunDir.create(self.root, "sample", "/repo", self.settings, "none")
        expected_text = {
            ("0", "reviewer", False): "model effort review\n",
            ("0", "reviewer", True): (
                "model effort review\nreview_model=haiku review_backend=claude\n"
            ),
            ("2", "reviewer", False): "model effort review\ntakeover_after=2\n",
            ("2", "reviewer", True): (
                "model effort review\nreview_model=haiku review_backend=claude takeover_after=2\n"
            ),
            ("0", "none", False): "model effort review\ntakeover_review=none\n",
            ("0", "none", True): (
                "model effort review\nreview_model=haiku review_backend=claude takeover_review=none\n"
            ),
            ("2", "none", False): (
                "model effort review\ntakeover_after=2 takeover_review=none\n"
            ),
            ("2", "none", True): (
                "model effort review\nreview_model=haiku review_backend=claude "
                "takeover_after=2 takeover_review=none\n"
            ),
        }
        for (after, review, has_reviewer), expected in expected_text.items():
            with self.subTest(after=after, review=review, has_reviewer=has_reviewer):
                reviewer = ("haiku", "claude") if has_reviewer else ("", "")
                settings = Settings("model", "effort", "review", *reviewer, after, review)
                run.save_settings(settings)
                self.assertEqual((run.path / "settings").read_text(), expected)
                self.assertEqual(RunDir.load(self.root, "sample").settings, settings)

    def test_old_three_field_settings_file_loads_takeover_defaults(self):
        run = RunDir.create(self.root, "sample", "/repo", self.settings, "none")
        (run.path / "settings").write_text("old effort review\n")
        self.assertEqual(
            RunDir.load(self.root, "sample").settings,
            Settings("old", "effort", "review", "", "", "0", "reviewer"),
        )

    def test_note_appends_local_timestamp_and_event(self):
        run = RunDir.create(self.root, "sample", "/repo", self.settings, "none")
        run.note("start run")
        run.note("done run")
        lines = (run.path / "status.log").read_text().splitlines()
        self.assertEqual(lines[0], "time\tevent")
        self.assertRegex(lines[1], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\tstart run$")
        self.assertRegex(lines[2], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\tdone run$")

    def test_done_markers(self):
        run = RunDir.create(self.root, "sample", "/repo", self.settings, "none")
        self.assertFalse(run.is_done("S1"))
        run.mark_done("S1")
        self.assertTrue((run.path / ".done-S1").is_file())
        self.assertTrue(run.is_done("S1"))

    def test_pause_here_each_list_none_empty_and_paused_marker(self):
        run = RunDir.create(self.root, "each", "/repo", self.settings, "each")
        self.assertTrue(run.pause_here(1))
        run.mark_paused(1)
        self.assertTrue((run.path / ".paused-S1").is_file())
        self.assertFalse(run.pause_here(1))

        run.set_pause("2,4")
        self.assertTrue(run.pause_here(2))
        self.assertFalse(run.pause_here(3))
        run.set_pause("none")
        self.assertFalse(run.pause_here(2))
        run.set_pause("")
        self.assertFalse(run.pause_here(2))


if __name__ == "__main__":
    unittest.main()

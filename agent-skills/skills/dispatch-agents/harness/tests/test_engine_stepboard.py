import pathlib
import tempfile
import unittest

from harness.engine.stepboard import render_steps


class StepboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = pathlib.Path(self.temp.name) / "sample"
        self.run.mkdir()
        self.specs = ["one|First|01-first|a b|out.md", "two|Second|02-second||"]

    def tearDown(self):
        self.temp.cleanup()

    def board(self):
        return render_steps(self.run, self.specs, "Run", "12:34")

    def test_nothing_started(self):
        expected = "Run sample · início --:-- → agora 12:34\n\n○ First\n    ○ a\n    ○ b\n○ Second\n"
        self.assertEqual(expected, self.board())

    def test_first_step_running_and_agents_with_or_without_output(self):
        (self.run / "status.log").write_text("time\tevent\n2026-01-02T11:00:00\tstart one launch\n", encoding="utf-8")
        (self.run / "01-first/a").mkdir(parents=True)
        (self.run / "01-first/a/out.md").write_text("done", encoding="utf-8")
        (self.run / "01-first/b").mkdir(parents=True)
        expected = ("Run sample · início 11:00 → agora 12:34\n\n◐ First\n"
                    "    ✓ a\n    ◐ b\n○ Second\n")
        self.assertEqual(expected, self.board())

    def test_stopped_step_is_crossed_and_following_steps_remain_pending(self):
        (self.run / "status.log").write_text("time\tevent\n2026-01-02T11:00:00\tSTOPPED at one: broken\n", encoding="utf-8")
        expected = "Run sample · início 11:00 → agora 12:34\n\n✗ First\n    ○ a\n    ○ b\n○ Second\n"
        self.assertEqual(expected, self.board())

    def test_all_done(self):
        (self.run / ".done-one").touch()
        (self.run / ".done-two").touch()
        expected = "Run sample · início --:-- → agora 12:34\n\n✓ First\n    ○ a\n    ○ b\n✓ Second\n"
        self.assertEqual(expected, self.board())

    def test_agents_report_failure(self):
        (self.run / "01-first/a").mkdir(parents=True)
        (self.run / "01-first/a/out.md").write_text("output", encoding="utf-8")
        (self.run / "01-first/b").mkdir(parents=True)
        (self.run / "01-first/b/failed").touch()
        expected = "Run sample · início --:-- → agora 12:34\n\n○ First\n    ✓ a\n    ✗ b\n○ Second\n"
        self.assertEqual(expected, self.board())


if __name__ == "__main__":
    unittest.main()

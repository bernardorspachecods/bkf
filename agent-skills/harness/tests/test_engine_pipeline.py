import contextlib
import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from pathlib import Path

from harness.cli import main as cli_main
from harness.engine.run import RunDir, RunError
from harness.engine.pipeline import _check_reviewer, _check_takeover, _options, main


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.runs = self.root / "runs"
        self.definition = self.root / "workflow.py"
        self.definition.write_text(textwrap.dedent("""
            from pathlib import Path
            from harness.engine.agentstep import run_agent_step
            from harness.gate import run_gate
            from harness.engine.workflow import Step, Stop, Workflow

            class Work(Workflow):
                name = "tiny"
                command = "tiny-run.sh"
                usage_start = "usage: start [-p checkpoints] <name>"
                repo_hint = "run start inside a repository"
                def validate_start(self, args):
                    if args and args[0] == "bad":
                        from harness.engine.run import RunError
                        raise RunError("bad argument")
                def validate_resume(self, run):
                    if (run.path / "refuse-resume").exists():
                        from harness.engine.run import RunError
                        raise RunError("resume refused")
                def start(self, ctx, args):
                    (ctx.run.path / "input").write_text("\\n".join(args) + "\\n")
                    if args == ["crash"]:
                        (ctx.run.path / "crash-step").touch()
                    if args == ["stop"]:
                        (ctx.run.path / "stop").touch()
                    ctx.note("start " + ctx.run.name)
                def steps(self, ctx):
                    def first(ctx):
                        prompt = ctx.run.path / "agent-prompt.md"
                        prompt.write_text("do the step\\n")
                        result = run_agent_step(
                            ctx.run, "agent step", ctx.repo, str(prompt),
                            str(ctx.run.path / "agent"), ctx.settings.model,
                            ctx.settings.effort, "workspace-write", None,
                            "agent failed with exit=<exit>",
                        )
                        if not result.ok:
                            raise Stop(result.reason)
                    def second(ctx):
                        if (ctx.run.path / "crash-step").exists():
                            raise RuntimeError("workflow broke")
                        if (ctx.run.path / "stop").exists():
                            raise Stop("cause remains")
                        result = run_gate(ctx.repo, 10, ctx.run.path / "gate", ["test -d .git"])
                        if result["red"]:
                            raise Stop("gate failed")
                        (ctx.run.path / "second").write_text("ok\\n")
                    return [Step(1, "agent step", first), Step(2, "gate step", second)]
                def regression(self, ctx, label):
                    (ctx.run.path / "regression-calls").open("a").write(label + "\\n")
                    if (ctx.run.path / "regression-red").exists():
                        return "regression red after " + label
                    return None
                def final_step(self, ctx):
                    def finish(ctx):
                        (ctx.run.path / "report.md").write_text("ready\\n")
                    return Step("final", "review", finish)
                def board(self, ctx):
                    return "BOARD\\n"
                def ready_path(self, ctx):
                    return str(ctx.run.path / "report.md")
                def finish(self, ctx):
                    return None

            WORKFLOW = Work()
        """), encoding="utf-8")
        self.env = {"HARNESS_RUNS_DIR": str(self.runs)}
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        codex = self.bin_dir / "codex"
        codex.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "out = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
            "out.write_text('agent completed\\n')\n",
            encoding="utf-8",
        )
        codex.chmod(0o755)
        self.env["PATH"] = str(self.bin_dir) + os.pathsep + os.environ.get("PATH", "")

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, cwd=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        previous = os.getcwd()
        os.chdir(cwd or self.repo)
        try:
            with patch.dict(os.environ, self.env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(str(self.definition), list(args))
        finally:
            os.chdir(previous)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_full_run_and_status_board_finish(self):
        code, out, err = self.call("start", "sample", "input")
        run = self.runs / "sample"
        self.assertEqual(code, 0)
        self.assertEqual(out, "Run folder: {0}\nREADY: {0}/report.md\nSee {0}/status.log\n".format(run))
        self.assertIn("BOARD\n", err)
        self.assertTrue((run / ".done-S1").is_file())
        self.assertTrue((run / ".done-S2").is_file())
        self.assertTrue((run / ".done-report").is_file())
        self.assertFalse((run / ".lock").exists())
        self.assertIn("start step 1: agent step (gpt-6-luna high)", (run / "status.log").read_text())
        self.assertIn("READY: report at {0}/report.md".format(run), (run / "status.log").read_text())
        self.assertEqual(self.call("status", "sample")[1], (run / "status.log").read_text())
        self.assertEqual(self.call("board", "sample")[1], "BOARD\n")
        self.assertEqual(self.call("finish", "--discard", "sample")[1], "Removed {0}\n".format(run))

    def test_start_uses_takeover_defaults_and_accepts_an_explicit_zero(self):
        self.assertEqual(self.call("start", "defaults")[0], 0)
        defaults = RunDir.load(self.runs, "defaults").settings
        self.assertEqual((defaults.takeover_after, defaults.takeover_review), ("2", "reviewer"))

        self.assertEqual(self.call("start", "--takeover-after", "0", "never")[0], 0)
        never = RunDir.load(self.runs, "never").settings
        self.assertEqual((never.takeover_after, never.takeover_review), ("0", "reviewer"))

    def test_resume_keeps_stored_takeover_values_or_replaces_them_when_given(self):
        self.assertEqual(self.call("start", "--takeover-after", "1", "--takeover-review", "none", "resume-settings")[0], 0)
        self.assertEqual(self.call("resume", "resume-settings")[0], 0)
        run = RunDir.load(self.runs, "resume-settings")
        self.assertEqual((run.settings.takeover_after, run.settings.takeover_review), ("1", "none"))

        self.assertEqual(
            self.call("resume", "--takeover-after", "2", "--takeover-review", "reviewer", "resume-settings")[0],
            0,
        )
        run = RunDir.load(self.runs, "resume-settings")
        self.assertEqual((run.settings.takeover_after, run.settings.takeover_review), ("2", "reviewer"))

    def test_start_and_resume_validate_takeover_options(self):
        for value in ("-1", "x", "1.5", ""):
            with self.subTest(option="--takeover-after", value=value):
                code, _, err = self.call("start", "--takeover-after", value, "invalid-after")
                self.assertEqual(code, 1)
                self.assertIn("bad --takeover-after:", err)
        code, _, err = self.call("start", "--takeover-review", "fast", "invalid-review")
        self.assertEqual(code, 1)
        self.assertIn("bad --takeover-review: fast", err)

        self.assertEqual(self.call("start", "validation-resume")[0], 0)
        for option, value in (("--takeover-after", "x"), ("--takeover-review", "fast")):
            with self.subTest(resume_option=option, value=value):
                code, _, err = self.call("resume", option, value, "validation-resume")
                self.assertEqual(code, 1)
                self.assertIn("bad " + option, err)

    def test_pause_resume_and_stopped_resume(self):
        code, out, _ = self.call("start", "-p", "each", "paused")
        self.assertEqual(code, 3)
        self.assertIn("PAUSED after step 1 (agent step).", out)
        self.assertEqual(self.call("resume", "-p", "none", "paused")[0], 0)
        code, out, _ = self.call("start", "stopped", "stop")
        self.assertEqual(code, 1)
        self.assertIn("STOPPED at step 2 (gate step): cause remains", out)
        (self.runs / "stopped" / "stop").unlink()
        code, _, _ = self.call("resume", "stopped")
        self.assertEqual(code, 0)
        self.assertTrue((self.runs / "stopped" / ".done-S2").is_file())
        self.assertTrue((self.runs / "stopped" / "second").is_file())

    def test_regression_runs_at_checkpoints_and_before_the_final_review_and_stops_when_red(self):
        code, out, _ = self.call("start", "-p", "1", "reg")
        run = self.runs / "reg"
        self.assertEqual(code, 3)
        self.assertEqual((run / "regression-calls").read_text(), "S1\n")
        self.assertEqual(self.call("resume", "reg")[0], 0)
        self.assertEqual((run / "regression-calls").read_text(), "S1\nfinal\n")

        code, out, _ = self.call("start", "-p", "none", "red", "stop")
        (self.runs / "red" / "regression-red").touch()
        (self.runs / "red" / "stop").unlink()
        code, out, _ = self.call("resume", "red")
        self.assertEqual(code, 1)
        self.assertIn("STOPPED at the regression check after final: regression red after final", out)
        self.assertFalse((self.runs / "red" / ".done-report").exists())
        (self.runs / "red" / "regression-red").unlink()
        self.assertEqual(self.call("resume", "red")[0], 0)

    def test_a_red_regression_at_a_checkpoint_is_retried_on_resume_without_rerunning_the_step(self):
        run = self.runs / "cp"
        self.call("start", "-p", "none", "cp", "stop")
        (run / "stop").unlink()
        (run / "pause").write_text("2\n")
        (run / "regression-red").touch()
        self.assertEqual(self.call("resume", "cp")[0], 1)
        self.assertTrue((run / ".done-S2").is_file())
        self.assertFalse((run / ".paused-S2").exists())
        (run / "regression-red").unlink()
        self.assertEqual(self.call("resume", "cp")[0], 3)
        self.assertTrue((run / ".paused-S2").is_file())

    def test_say_reaches_the_resumed_run_and_is_removed_after_it(self):
        self.call("start", "talk", "stop")
        run = self.runs / "talk"
        (run / "stop").unlink()
        code, _, err = self.call("resume", "--say", "the table exists now", "talk")
        self.assertEqual(code, 0)
        self.assertIn("the coordinator says: the table exists now", (run / "status.log").read_text())
        self.assertFalse((run / "say.md").exists())
        note = self.root / "note.txt"
        note.write_text("from a file\n", encoding="utf-8")
        self.call("resume", "--say-file", str(note), "talk")
        self.assertIn("the coordinator says: from a file", (run / "status.log").read_text())
        code, _, err = self.call("resume", "--say", "a", "--say-file", str(note), "talk")
        self.assertEqual(code, 1)
        self.assertIn("use --say or --say-file, not both", err)

    def test_finish_requires_ready_file(self):
        self.call("start", "unfinished", "stop")
        code, _, err = self.call("finish", "unfinished")
        self.assertEqual(code, 1)
        self.assertIn("there is no final review in this run: nothing to keep", err)

    def test_existing_run_refused_and_bad_usage(self):
        self.call("start", "dup")
        code, _, err = self.call("start", "dup")
        self.assertEqual(code, 1)
        self.assertIn("run already exists:", err)
        code, _, err = self.call("unknown")
        self.assertEqual(code, 1)
        self.assertIn("usage: tiny-run.sh start|resume|close|status|board|finish ...", err)

    def test_close_requires_a_unit_waiting_for_takeover(self):
        self.call("start", "no-takeover")
        code, _, err = self.call("close", "no-takeover")
        self.assertEqual(code, 1)
        self.assertIn("no unit of no-takeover is waiting for a takeover", err)

    def test_close_marks_waiting_units_and_reuses_resume_path(self):
        self.call("start", "waiting")
        run = self.runs / "waiting"
        unit = run / "01-unit"
        unit.mkdir()
        (unit / "takeover").write_text("problems.md\n", encoding="utf-8")
        code, _, err = self.call("close", "waiting")
        self.assertEqual(code, 0, err)
        self.assertEqual((unit / "closing").read_text(), "\n")
        self.assertTrue(run.joinpath("status.log").read_text().count("\tresume\n") >= 1)

    def test_resume_lock_and_finish_lock(self):
        run = self.runs / "locked"
        self.call("start", "locked")
        (run / ".lock").write_text(str(os.getpid()) + "\n", encoding="ascii")
        active_process = subprocess.CompletedProcess([], 0, stdout="harness\n")
        with patch("harness.engine.lock.subprocess.run", return_value=active_process):
            code, _, err = self.call("finish", "locked")
            self.assertEqual(code, 1)
            self.assertIn("finish it when it stops", err)
            code, _, err = self.call("resume", "locked")
            self.assertEqual(code, 1)
            self.assertIn("already being worked on", err)
        (run / ".lock").unlink()

    def test_resume_asks_the_workflow_to_validate_before_it_continues(self):
        self.call("start", "refused", "stop")
        (self.runs / "refused" / "refuse-resume").touch()
        before = (self.runs / "refused" / "status.log").read_text()
        code, _, err = self.call("resume", "refused")
        self.assertEqual(code, 1)
        self.assertIn("resume refused", err)
        self.assertEqual((self.runs / "refused" / "status.log").read_text(), before)

    def test_step_stop_is_not_marked_done(self):
        self.call("start", "stopped", "stop")
        self.assertFalse((self.runs / "stopped" / ".done-S2").exists())

    def test_cli_run_dispatches_to_definition(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        previous = os.getcwd()
        os.chdir(self.repo)
        try:
            with patch.dict(os.environ, self.env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli_main(["run", str(self.definition), "start", "cli"])
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0)
        self.assertIn("READY:", stdout.getvalue())


class ReviewerOptionTests(unittest.TestCase):
    def test_options_read_the_reviewers_model_and_backend(self):
        options, rest = _options(
            ["--review-model", "haiku", "--review-backend", "claude", "-r", "low", "name"],
            {"review_model": "", "review_backend": "", "review_effort": ""},
        )
        self.assertEqual((options["review_model"], options["review_backend"], options["review_effort"]),
                         ("haiku", "claude", "low"))
        self.assertEqual(rest, ["name"])

    def test_options_read_takeover_values(self):
        options, rest = _options(["--takeover-after", "1", "--takeover-review", "none", "name"])
        self.assertEqual((options["takeover_after"], options["takeover_review"]), ("1", "none"))
        self.assertEqual(rest, ["name"])

    def test_takeover_validation_rejects_bad_values_and_accepts_supported_values(self):
        for value in ("-1", "x", "1.5", ""):
            with self.subTest(after=value), self.assertRaisesRegex(RunError, "bad --takeover-after"):
                _check_takeover(value, "reviewer")
        with self.assertRaisesRegex(RunError, "bad --takeover-review: fast"):
            _check_takeover("1", "fast")
        for value in ("0", "1", "2"):
            _check_takeover(value, "reviewer")
            _check_takeover(value, "none")

    def test_a_reviewer_backend_needs_its_own_model_and_a_known_backend(self):
        _check_reviewer("", "")
        _check_reviewer("some-model", "")
        with self.assertRaisesRegex(RunError, "--review-backend needs --review-model"):
            _check_reviewer("", "claude")
        with self.assertRaisesRegex(RunError, "bad --review-backend: nope"):
            _check_reviewer("m", "nope")


if __name__ == "__main__":
    unittest.main()

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
from harness.engine.pipeline import main


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
        self.assertIn("usage: tiny-run.sh start|resume|status|board|finish ...", err)

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


if __name__ == "__main__":
    unittest.main()

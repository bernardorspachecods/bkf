"""Integration tests for the review workflow using a fake Codex executable."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "review-run.sh"


_FAKE_CODEX = r'''#!/usr/bin/env python3
import os
import pathlib
import sys

args = sys.argv[1:]
directory = pathlib.Path(args[args.index("-C") + 1])
last_message = pathlib.Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
state = pathlib.Path(os.environ["FAKE_STATE"])
counter = state / ("calls-" + directory.parent.name + "-" + directory.name)
counter.write_text(str(int(counter.read_text() if counter.exists() else "0") + 1), encoding="utf-8")
if os.environ.get("FAKE_QUOTA") and not (state / "quota-done").exists() and " review" in prompt:
    (state / "quota-done").write_text("failed\n", encoding="utf-8")
    print('{"error":{"message":"hit your usage limit; try again at tomorrow"}}')
    raise SystemExit(1)
if os.environ.get("FAKE_FAIL_ONCE") and "Standards review" in prompt:
    marker = state / "failed-once"
    if not marker.exists():
        marker.write_text("failed\n", encoding="utf-8")
        raise SystemExit(1)
if prompt.startswith("# Brief: check"):
    (directory / "checked.md").write_text("No findings.\n", encoding="utf-8")
elif prompt.startswith("# Brief:"):
    (directory / "report.md").write_text("No findings.\n", encoding="utf-8")
else:
    raise SystemExit("unexpected prompt")
last_message.write_text("fake response\n", encoding="utf-8")
print('{"type":"turn.completed"}')
'''


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._git("init", "-q", str(self.repo))
        self._git("-C", str(self.repo), "config", "user.email", "test@example.com")
        self._git("-C", str(self.repo), "config", "user.name", "test")
        (self.repo / "change.txt").write_text("base\n", encoding="utf-8")
        self._git("-C", str(self.repo), "add", "change.txt")
        self._git("-C", str(self.repo), "commit", "-qm", "init")
        (self.repo / "change.txt").write_text("base\nchange\n", encoding="utf-8")
        self.spec = self.root / "spec.md"
        self.spec.write_text("# Spec\n\nReview this change.\n", encoding="utf-8")
        self.standards = self.root / "standards.md"
        self.standards.write_text("# Standards\n\nKeep it clear.\n", encoding="utf-8")
        self.empty = self.root / "empty.md"
        self.empty.write_text("", encoding="utf-8")
        self.guides = self.root / "guides"
        self.guides.mkdir()
        for guide in ("code-review-axis.md", "code-review-check.md"):
            (self.guides / guide).write_text("guide\n", encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        codex = self.bin / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        self.state = self.root / "state"
        self.state.mkdir()
        self.runs = self.root / "runs"
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + self.env.get("PATH", ""),
            "REVIEW_RUNS_DIR": str(self.runs),
            "REVIEW_GUIDES": str(self.guides),
            "REVIEW_IN_PLACE": "1",
            "FAKE_STATE": str(self.state),
        })

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args):
        return subprocess.run(["git"] + list(args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def call(self, *args, env=None):
        return subprocess.run(
            [str(SCRIPT)] + list(args), cwd=str(self.repo),
            env=env or self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, check=False,
        )

    def start(self, name="run", *options, env=None):
        return self.call("start", *options, name, "working-tree", env=env)

    def test_full_run_report_matches_shell_text_and_gate_is_recorded(self):
        result = self.start("full", "-m", "fake-model", "-e", "medium", "-s", str(self.spec),
                            "-d", str(self.standards), "-g", "echo gate-output")
        run = self.runs / "full"
        self.assertEqual(result.returncode, 0, result.stderr)
        report = (run / "report.md").read_text(encoding="utf-8")
        gate = (run / "00-input" / "gate.md").read_text(encoding="utf-8")
        expected = (
            "# Code review\n\nTarget: working-tree\n\n"
            "> The checkers confirm the findings below against the diff. They do not show what the reviewers missed: a clean axis is not a clean diff.\n\n"
            "## Gate\n\n"
            "The harness ran these commands in {0}, outside any agent.\n"
            "Gate target: HEAD {1} of the repository.\n\n"
            "Result: all green (1 commands).\n\n"
            "#### `echo gate-output`\n\nexit code: 0\n\n~~~~\ngate-output\n~~~~\n\n"
            "## Standards\n\nNo findings.\n\n## Spec\n\nNo findings.\n\n"
        ).format(Path(self._git("-C", str(self.repo), "rev-parse", "--show-toplevel").stdout.decode().strip()),
                 self._git("-C", str(self.repo), "rev-parse", "--short", "HEAD").stdout.decode().strip())
        self.assertEqual(report, expected)
        self.assertIn("gate-output", gate)
        self.assertEqual((run / "settings").read_text(encoding="utf-8"), "fake-model medium \n")
        self.assertEqual((run / "01-review" / "standards" / "brief.md").read_text(encoding="utf-8"),
                         self.shell_axis_brief("Standards", Path(self._git("-C", str(self.repo), "rev-parse", "--show-toplevel").stdout.decode().strip()), self.guides, commits=False, standards=True))

    def shell_axis_brief(self, title, repo, guides, commits=False, standards=False):
        return (
            "# Brief: {0} review\n\n## What to review\nThe diff is `diff.patch` in the current directory (read-only){1}.\n"
            "\n## Gate\nThe script ran the repository's own checks before you started: their commands, output and exit codes are in `gate.md` here (read-only). Take them as given.\n"
            "\n## Criteria\n{2}\n"
            "\n## The repository\nIt is at {3}. Open it read-only to see the code around the diff. Change nothing in it.\n"
            "\n## Role\nOpen and follow the role guide: {4}/code-review-axis.md (read-only), the section \"{0}\". You are not the author of the change.\n"
            "\n## Rules\n- Write your report to report.md in the current directory. Write nothing else.\n"
            "- Open only files in the current directory, the repository and the role guide. Other folders under the run folder are not for you.\n"
            "- Do not run git commands that change state.\n"
        ).format(title, ", and the commits in `commits.txt`" if commits else "",
                 "The documented standards are the files in `standards/` here (read-only)." if standards else "The originating spec is `spec.md` here (read-only).",
                 repo, guides)

    def test_spec_only_and_no_gate_report_gap(self):
        result = self.start("spec-only", "-s", str(self.spec))
        report = (self.runs / "spec-only" / "report.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No gate commands were given, so no checks were run. This is a gap, not a pass.", report)
        self.assertIn("## Standards\n\nNot run: no standards sources were given.", report)
        self.assertIn("## Spec\n\nNo findings.", report)

    def test_standards_only_uses_the_matching_brief_and_report_text(self):
        result = self.start("standards-only", "-d", str(self.standards))
        run = self.runs / "standards-only"
        self.assertEqual(result.returncode, 0, result.stderr)
        report = (run / "report.md").read_text(encoding="utf-8")
        self.assertIn("## Standards\n\nNo findings.", report)
        self.assertIn("## Spec\n\nNot run: no spec available.", report)
        self.assertEqual((run / "02-check" / "standards" / "brief.md").read_text(encoding="utf-8"), (
            "# Brief: check of the Standards findings\n\n## Inputs (read-only, in the current directory)\n"
            "- diff.patch: the diff under review\n- standards/: the documented standards\n"
            "- gate.md: the repository's own checks, run by the script before the review\n"
            "- reports/: the findings of the reviewer(s) of this axis\n\n## The repository\n"
            "It is at {0}. Open it read-only to see the code around a hunk. Change nothing in it.\n"
            "\n## Role\nOpen and follow the role guide: {1}/code-review-check.md (read-only). You are not the author of the findings.\n"
            "\n## Rules\n- Write your result to checked.md in the current directory. Write nothing else.\n"
            "- Open only files in the current directory, the repository and the role guide.\n"
            "- Do not run git commands that change state.\n"
        ).format(Path(self._git("-C", str(self.repo), "rev-parse", "--show-toplevel").stdout.decode().strip()), self.guides))

    def test_two_reviewers_and_checker_report_both(self):
        result = self.start("second", "-s", str(self.spec), "-d", str(self.standards), "-2")
        run = self.runs / "second"
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in ("01-review/standards-2/report.md", "01-review/spec-2/report.md",
                     "02-check/standards/reports/reviewer-2.md", "02-check/spec/reports/reviewer-2.md"):
            self.assertTrue((run / path).is_file(), path)

    def test_red_gate_does_not_stop_and_is_in_report(self):
        result = self.start("red", "-s", str(self.spec), "-g", "echo red-output; exit 3", "-g", "true")
        report = (self.runs / "red" / "report.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Result: RED, 1 of 2 commands failed.", report)
        self.assertIn("exit code: 3", report)
        self.assertIn("red-output", report)

    def test_revision_range_is_pinned_and_reported(self):
        self._git("-C", str(self.repo), "add", "change.txt")
        self._git("-C", str(self.repo), "commit", "-qm", "feature")
        result = self.call("start", "-s", str(self.spec), "-g", "true", "range", "HEAD~1..HEAD")
        run = self.runs / "range"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((run / "00-input" / "target").read_text(), "HEAD~1..HEAD\n")
        self.assertTrue((run / "00-input" / "commits.txt").is_file())
        self.assertIn("revision range", (run / "00-input" / "gate.md").read_text())

    def test_failed_agent_resume_retries_only_missing_axis(self):
        environment = dict(self.env, FAKE_FAIL_ONCE="1")
        result = self.start("resume", "-s", str(self.spec), "-d", str(self.standards), env=environment)
        run = self.runs / "resume"
        self.assertEqual(result.returncode, 1)
        self.assertFalse((run / "01-review" / "standards" / "report.md").exists())
        self.assertTrue((run / "01-review" / "spec" / "report.md").is_file())
        self.assertEqual((self.state / "calls-01-review-spec").read_text(), "1")
        resumed = self.call("resume", "resume", env=self.env)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertTrue((run / "report.md").is_file())
        self.assertEqual((self.state / "calls-01-review-spec").read_text(), "1")
        self.assertEqual((self.state / "calls-01-review-standards").read_text(), "2")

    def test_quota_is_reported_and_finish_keeps_or_discards_record(self):
        environment = dict(self.env, FAKE_QUOTA="1")
        result = self.start("quota", "-s", str(self.spec), env=environment)
        self.assertEqual(result.returncode, 1)
        self.assertIn("QUOTA: tomorrow", (self.runs / "quota" / "status.log").read_text())
        environment = dict(self.env)
        self.assertEqual(self.start("kept", "-s", str(self.spec), env=environment).returncode, 0)
        kept = self.call("finish", "kept")
        self.assertEqual(kept.returncode, 0, kept.stderr)
        self.assertTrue((self.repo / "records" / "reviews" / "kept" / "report.md").is_file())
        self.assertFalse((self.runs / "kept").exists())
        self.assertEqual(self.start("discard", "-s", str(self.spec), env=environment).returncode, 0)
        discarded = self.call("finish", "--discard", "discard")
        self.assertEqual(discarded.returncode, 0, discarded.stderr)
        self.assertFalse((self.runs / "discard").exists())

    def test_board_and_status(self):
        result = self.start("board", "-s", str(self.spec), "-d", str(self.standards))
        self.assertEqual(result.returncode, 0, result.stderr)
        board = self.call("board", "board")
        status = self.call("status", "board")
        self.assertEqual(board.returncode, 0)
        self.assertIn("✓ Revisores", board.stdout)
        self.assertIn("✓ Verificação", board.stdout)
        self.assertIn("READY:", status.stdout)

    def test_every_start_refusal(self):
        usage = self.call("start")
        self.assertEqual(usage.returncode, 1)
        self.assertIn("usage: start", usage.stderr)
        cases = [
            (("start", "bad/name", "working-tree"), "bad run name"),
            (("start", "missing-spec", "working-tree", "-s", str(self.root / "missing.md")), "missing or empty spec"),
            (("start", "empty-spec", "working-tree", "-s", str(self.empty)), "missing or empty spec"),
            (("start", "missing-std", "working-tree", "-d", str(self.root / "missing.md")), "missing or empty standards file"),
            (("start", "empty-std", "working-tree", "-d", str(self.empty)), "missing or empty standards file"),
            (("start", "no-criteria", "working-tree"), "no criteria"),
            (("start", "bad-ref", "not-a-ref", "-s", str(self.spec)), "git diff not-a-ref failed"),
        ]
        for args, message in cases:
            with self.subTest(message=message):
                result = self.call(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        empty_repo = self.root / "empty-repo"
        empty_repo.mkdir()
        self._git("init", "-q", str(empty_repo))
        self._git("-C", str(empty_repo), "config", "user.email", "t@t")
        self._git("-C", str(empty_repo), "config", "user.name", "t")
        (empty_repo / "base").write_text("x\n")
        self._git("-C", str(empty_repo), "add", "base")
        self._git("-C", str(empty_repo), "commit", "-qm", "init")
        empty_result = subprocess.run([str(SCRIPT), "start", "-s", str(self.spec), "empty-diff", "working-tree"],
                                      cwd=str(empty_repo), env=self.env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, universal_newlines=True, check=False)
        self.assertIn("diff for working-tree is empty", empty_result.stderr)
        no_codex_bin = self.root / "no-codex-bin"
        no_codex_bin.mkdir()
        for executable in ("bash", "python3", "dirname", "env"):
            (no_codex_bin / executable).symlink_to(shutil.which(executable))
        no_codex = dict(self.env, PATH=str(no_codex_bin))
        result = self.call("start", "-s", str(self.spec), "no-codex", "working-tree", env=no_codex)
        self.assertIn("codex not found", result.stderr)
        no_guides = dict(self.env, REVIEW_GUIDES=str(self.root / "missing-guides"))
        result = self.call("start", "-s", str(self.spec), "no-guides", "working-tree", env=no_guides)
        self.assertIn("no role guides at", result.stderr)
        outside = subprocess.run([str(SCRIPT), "start", "-s", str(self.spec), "outside", "working-tree"],
                                 cwd=str(self.root), env=self.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True, check=False)
        self.assertIn("run start inside the repository under review", outside.stderr)
        existing = self.start("existing", "-s", str(self.spec))
        self.assertEqual(existing.returncode, 0, existing.stderr)
        repeated = self.start("existing", "-s", str(self.spec))
        self.assertIn("run already exists", repeated.stderr)


if __name__ == "__main__":
    unittest.main()

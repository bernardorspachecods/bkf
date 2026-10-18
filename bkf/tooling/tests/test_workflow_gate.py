from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import workflow_gate


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True
    )


class GateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        git(self.repo, "init", "-q")
        (self.repo / "seed.txt").write_text("seed")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "seed")

    def gate(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                status = workflow_gate.main([*arguments, str(self.repo)])
            except SystemExit as exc:
                status = int(exc.code)
        return status, out.getvalue(), err.getvalue()

    def test_passes_when_changes_are_inside_scope_and_checks_succeed(self) -> None:
        (self.repo / "out").mkdir()
        (self.repo / "out" / "a.md").write_text("a")
        status, output, _ = self.gate("--base", "HEAD", "--allow", "out/a.md", "--check", "true")
        self.assertEqual(status, 0)
        self.assertIn("gate: pass", output)

    def test_untracked_file_outside_scope_fails(self) -> None:
        (self.repo / "a.md").write_text("a")
        (self.repo / "stray.md").write_text("x")
        status, output, _ = self.gate("--base", "HEAD", "--allow", "a.md")
        self.assertEqual(status, 1)
        self.assertIn("scope: fail - outside the allowed files: stray.md", output)

    def test_modified_tracked_file_outside_scope_fails(self) -> None:
        (self.repo / "seed.txt").write_text("changed")
        status, output, _ = self.gate("--base", "HEAD", "--allow", "a.md")
        self.assertEqual(status, 1)
        self.assertIn("seed.txt", output)

    def test_committed_change_is_seen_against_base(self) -> None:
        (self.repo / "a.md").write_text("a")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "work")
        status, _, _ = self.gate("--base", "HEAD~1", "--allow", "a.md")
        self.assertEqual(status, 0)

    def test_branch_that_wrote_nothing_fails_unless_allowed(self) -> None:
        status, output, _ = self.gate("--base", "HEAD", "--allow", "a.md")
        self.assertEqual(status, 1)
        self.assertIn("nonempty: fail", output)
        status, _, _ = self.gate("--base", "HEAD", "--allow", "a.md", "--allow-empty")
        self.assertEqual(status, 0)

    def test_failing_check_fails_the_gate_with_its_output(self) -> None:
        (self.repo / "a.md").write_text("a")
        status, output, _ = self.gate("--base", "HEAD", "--allow", "a.md", "--check", "echo missing 2 verdicts; exit 3")
        self.assertEqual(status, 1)
        self.assertIn("exit 3: missing 2 verdicts", output)

    def test_check_timeout_fails(self) -> None:
        (self.repo / "a.md").write_text("a")
        status, output, _ = self.gate(
            "--base", "HEAD", "--allow", "a.md", "--check", "sleep 5", "--timeout", "1"
        )
        self.assertEqual(status, 1)
        self.assertIn("no result after 1 seconds", output)

    def test_unknown_base_is_a_usage_error(self) -> None:
        status, _, error = self.gate("--base", "nope", "--allow", "a.md")
        self.assertEqual(status, 2)
        self.assertIn("bkf gate:", error)

    def test_allow_is_required(self) -> None:
        status, _, _ = self.gate("--base", "HEAD")
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HARNESS_DIR = pathlib.Path(__file__).resolve().parents[1]


class PrepareCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.tree = self.root / "tree"
        self.tree.mkdir()
        self.run = self.root / "run"
        self.run.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def declare(self, commands):
        (self.repo / ".plan-run.json").write_text(
            json.dumps({"worktree": {"prepare": commands}}), encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "declare"], check=True)

    def run_cli(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(HARNESS_DIR)
        return subprocess.run(
            [
                sys.executable, "-m", "harness", "prepare", "--run", str(self.run),
                "--repo", str(self.repo), "--tree", str(self.tree),
            ],
            cwd=str(HARNESS_DIR), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def test_prepare_runs_declared_command_and_prints_note(self):
        self.declare(["echo prepared > marker.txt"])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.tree / "marker.txt").read_text(), "prepared\n")
        self.assertIn(b"worktree.prepare: 1 command(s) passed", result.stdout)

    def test_prepare_failure_returns_one_and_prints_the_error(self):
        self.declare(["exit 7"])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"preparing the worktree failed", result.stderr)


if __name__ == "__main__":
    unittest.main()

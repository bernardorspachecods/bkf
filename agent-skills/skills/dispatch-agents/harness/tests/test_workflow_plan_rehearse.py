import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT.parent / "scripts" / "plan-run.sh"


class PlanRehearseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "t"], check=True)
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "init"], check=True)

        self.plan_dir = self.root / "plan"
        self.plan_dir.mkdir()
        (self.plan_dir / "first.md").write_text(
            "```gate\ntrue\nfalse\n```\n", encoding="utf-8"
        )
        (self.plan_dir / "second.md").write_text(
            "```gate\ntest -f missing.txt\n```\n", encoding="utf-8"
        )
        self.plan = self.plan_dir / "plan.txt"
        self.plan.write_text("first.md\nsecond.md\n", encoding="utf-8")

        self.output_root = self.root / "temporary-outputs"
        self.output_root.mkdir()
        self.runs = self.root / "runs"

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args):
        environ = os.environ.copy()
        environ.update({
            "TMPDIR": str(self.output_root),
            "PLAN_RUNS_DIR": str(self.runs),
        })
        return subprocess.run(
            [str(SCRIPT)] + list(args),
            cwd=str(self.repo),
            env=environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )

    def test_rehearse_reports_every_gate_and_leaves_checkout_untouched(self):
        result = self.call("rehearse", str(self.plan))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            "PASS first true\n"
            "FAIL first false (exit 1)\n"
            "FAIL second test -f missing.txt (exit 1)\n"
            "Lines that fail here are expected only for behavior the unit itself creates; read the others before start.\n",
        )
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(self.repo), "status", "--porcelain"], text=True
        ), "")
        self.assertEqual(list(self.output_root.glob("plan-rehearse-*")), [])
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.runs.exists())

    def test_rehearse_missing_plan_is_usage_error(self):
        result = self.call("rehearse", str(self.plan_dir / "missing.txt"))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("missing plan file", result.stderr)

    def test_rehearse_without_plan_is_usage_error(self):
        result = self.call("rehearse")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage: rehearse <plan.txt>", result.stderr)


if __name__ == "__main__":
    unittest.main()

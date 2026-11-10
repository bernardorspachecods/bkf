import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "plan-unit.sh"

# A fake `codex` that records how it was called and answers from FAKE_VERDICTS, one verdict per review.
_FAKE_CODEX = '''#!/usr/bin/env python3
import json, os, pathlib, sys

args = sys.argv[1:]
output = pathlib.Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
state = pathlib.Path(os.environ["FAKE_STATE"])
count = len(list(state.glob("prompt-*.md"))) + 1
(state / "prompt-{0}.md".format(count)).write_text(prompt, encoding="utf-8")
(state / "args-{0}.json".format(count)).write_text(json.dumps(args), encoding="utf-8")
thread_id = args[-2] if "resume" in args else "thread-{0}".format(count)
verdicts = json.loads(os.environ["FAKE_VERDICTS"])
verdict = verdicts[min(count, len(verdicts)) - 1]
output.write_text("## What I checked\\n\\n- patch\\n- prompt\\n- result\\n\\n## Problems\\n\\nfix the thing\\n\\n"
                  "VERDICT: " + verdict + "\\n", encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": thread_id}))
print('{"type":"turn.completed","usage":{"input_tokens":1}}')
'''


class PlanUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.repo)] + command, check=True)
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "init"], check=True)
        self.out = root / "units"
        self.state = root / "state"
        self.state.mkdir()
        guides = root / "guides"
        guides.mkdir()
        (guides / "plan-review.md").write_text("guide\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        codex = bin_dir / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(bin_dir) + os.pathsep + self.env["PATH"], "FAKE_STATE": str(self.state),
            "PLAN_GUIDES": str(guides), "FAKE_VERDICTS": json.dumps(["pass"]),
        })
        self.brief = root / "unit.md"

    def write_brief(self, gate=None):
        text = "## Result\nChange seed.\n"
        if gate:
            text += "\n```gate\n{0}\n```\n".format(gate)
        self.brief.write_text(text, encoding="utf-8")

    def plan_unit(self, *args):
        return subprocess.run(
            [str(SCRIPT)] + list(args), cwd=str(self.repo), env=self.env, capture_output=True, text=True
        )

    def begin(self, *extra):
        result = self.plan_unit("begin", str(self.brief), "--dir", str(self.out), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)

    def check(self, *extra, unit=None):
        args = ["check", str(self.brief), "--dir", str(self.out)]
        if unit:
            args.extend(["--unit", unit])
        return self.plan_unit(*(args + list(extra)))

    def implement(self, text="changed\n"):
        (self.repo / "seed.txt").write_text(text, encoding="utf-8")

    def reviews(self):
        return sorted(self.state.glob("prompt-*.md"))

    def test_passing_gate_then_a_separate_reviewer_on_its_own_model_gives_pass(self):
        self.write_brief(gate="grep -q changed seed.txt")
        self.begin()
        self.implement()
        result = self.check("--review-model", "haiku-x", "-r", "low")
        self.assertEqual((result.returncode, "VERDICT: pass" in result.stdout), (0, True), result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        args = json.loads((self.state / "args-1.json").read_text())
        self.assertEqual(args[args.index("-m") + 1], "haiku-x")
        self.assertIn('model_reasoning_effort="low"', args)
        self.assertEqual(args[args.index("-s") + 1], "read-only")
        prompt = self.reviews()[0].read_text()
        self.assertIn("Change seed.", prompt)
        self.assertIn("+changed", (self.out / "unit" / "rounds" / "1" / "diff.patch").read_text())

    def test_a_failing_gate_sends_the_unit_back_without_starting_a_reviewer(self):
        self.write_brief(gate="grep -q never-there seed.txt")
        self.begin()
        self.implement()
        result = self.check("--review-model", "haiku-x")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("VERDICT: back", result.stdout)
        self.assertEqual(self.reviews(), [])
        problems = (self.out / "unit" / "rounds" / "1" / "problems.md").read_text()
        self.assertIn("The gate failed: 1 of 1", problems)

    def test_same_unit_resumes_reviewer_with_continuation_and_previous_problems(self):
        self.env["FAKE_VERDICTS"] = json.dumps(["back", "pass"])
        self.write_brief()
        self.begin()
        self.implement()
        first = self.check("--review-model", "m")
        self.assertEqual(first.returncode, 1, first.stdout)
        self.implement("changed again\n")
        second = self.check("--review-model", "m")
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(len(self.reviews()), 2)
        first_args = json.loads((self.state / "args-1.json").read_text())
        second_args = json.loads((self.state / "args-2.json").read_text())
        self.assertNotIn("resume", first_args)
        self.assertIn("-C", first_args)
        self.assertIn("resume", second_args)
        self.assertNotIn("-C", second_args)
        self.assertEqual(second_args[-2], "thread-1")
        self.assertIn("fix the thing", self.reviews()[1].read_text())
        self.assertNotIn("Change seed.", self.reviews()[1].read_text())
        self.assertNotIn("fix the thing", self.reviews()[0].read_text())

    def test_a_different_unit_starts_a_fresh_reviewer_conversation(self):
        self.write_brief()
        self.begin()
        self.implement()
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        self.begin("--unit", "another")
        self.assertEqual(self.check("--review-model", "m", unit="another").returncode, 0)
        args = json.loads((self.state / "args-2.json").read_text())
        self.assertNotIn("resume", args)
        self.assertIn("-C", args)

    def test_begin_restart_drops_the_reviewer_conversation(self):
        self.write_brief()
        self.begin()
        self.implement()
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        self.implement("changed again\n")
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        self.begin("--restart")
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        args = json.loads((self.state / "args-3.json").read_text())
        self.assertNotIn("resume", args)
        self.assertIn("-C", args)

    def test_escalate_and_brief_verdicts_stop_with_exit_two(self):
        for verdict in ("escalate", "brief"):
            with self.subTest(verdict=verdict):
                for path in self.state.iterdir():
                    path.unlink()
                self.env["FAKE_VERDICTS"] = json.dumps([verdict])
                self.write_brief()
                self.plan_unit("begin", str(self.brief), "--dir", str(self.out), "--restart")
                result = self.check("--review-model", "m")
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_gate_only_runs_the_gate_and_writes_the_diff_without_a_reviewer(self):
        self.write_brief(gate="true")
        self.begin()
        self.implement()
        result = self.check("--gate-only")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("VERDICT", result.stdout)
        self.assertEqual(self.reviews(), [])
        self.assertTrue((self.out / "unit" / "rounds" / "1" / "diff.patch").is_file())

    def test_begin_does_not_overwrite_a_unit_unless_restarted(self):
        self.write_brief()
        self.begin()
        again = self.plan_unit("begin", str(self.brief), "--dir", str(self.out))
        self.assertEqual(again.returncode, 3)
        self.assertIn("already begun", again.stderr)
        restarted = self.plan_unit("begin", str(self.brief), "--dir", str(self.out), "--restart")
        self.assertEqual(restarted.returncode, 0, restarted.stderr)

    def test_errors_exit_three(self):
        self.write_brief()
        no_begin = self.check("--review-model", "m")
        self.assertEqual(no_begin.returncode, 3)
        self.assertIn("run begin first", no_begin.stderr)
        self.begin()
        no_model = self.check()
        self.assertEqual(no_model.returncode, 3)
        self.assertIn("--review-model is required", no_model.stderr)


if __name__ == "__main__":
    unittest.main()

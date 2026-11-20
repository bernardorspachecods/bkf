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

_FAKE_BKF = '''#!/usr/bin/env python3
import json, os, pathlib, sys

with (pathlib.Path(os.environ["FAKE_STATE"]) / "bkf.log").open("a") as log:
    print(json.dumps(sys.argv[1:]), file=log)
if os.environ.get("FAKE_BKF_FAIL"):
    sys.exit("store unavailable")
'''

CARD = "t20261120-143005-a3f1"


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
        (guides / "agentic-work-review.md").write_text("guide\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        codex = bin_dir / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        bkf = bin_dir / "bkf"
        bkf.write_text(_FAKE_BKF, encoding="utf-8")
        bkf.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(bin_dir) + os.pathsep + self.env["PATH"], "FAKE_STATE": str(self.state),
            "PLAN_GUIDES": str(guides), "FAKE_VERDICTS": json.dumps(["pass"]), "HARNESS_BACKEND": "codex",
            "BKF_TASKS_DIR": str(root / "tasks"), "BKF_TASK": "t20261120-143005-0000", "FAKE_BKF_FAIL": "",
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

    def gate(self, *extra, unit=None):
        args = ["gate", str(self.brief), "--dir", str(self.out)]
        if unit:
            args.extend(["--unit", unit])
        return self.plan_unit(*(args + list(extra)))

    def reviews(self):
        return sorted(self.state.glob("prompt-*.md"))

    def counted_gate(self, check="grep -q changed seed.txt", log="gate-runs.log"):
        """A gate command that appends a line to a log outside the checkout each time it really runs."""
        return 'echo run >> "{0}"; {1}'.format(self.state / log, check)

    def runs(self, log="gate-runs.log"):
        path = self.state / log
        return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0

    def receipt(self):
        return self.out / "unit" / "receipt" / "receipt.json"

    def link_card(self):
        (self.out / "unit" / "task").write_text(CARD + "\n", encoding="utf-8")

    def card_calls(self):
        log = self.state / "bkf.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.is_file() else []

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
        self.assertEqual(self.card_calls(), [])

    def test_a_failing_gate_sends_the_unit_back_without_starting_a_reviewer(self):
        self.write_brief(gate="grep -q never-there seed.txt")
        self.begin()
        self.link_card()
        self.implement()
        result = self.check("--review-model", "haiku-x")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("VERDICT: back", result.stdout)
        self.assertEqual(self.reviews(), [])
        problems = (self.out / "unit" / "rounds" / "1" / "problems.md").read_text()
        self.assertIn("The gate failed: 1 of 1", problems)
        self.assertEqual(self.card_calls(), [])

    def test_same_unit_resumes_reviewer_with_continuation_and_previous_problems(self):
        self.env["FAKE_VERDICTS"] = json.dumps(["back", "pass"])
        self.write_brief()
        self.begin()
        self.link_card()
        self.implement()
        first = self.check("--review-model", "m")
        self.assertEqual(first.returncode, 1, first.stdout)
        self.assertEqual(self.card_calls(), [])
        self.implement("changed again\n")
        second = self.check("--review-model", "m")
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(self.card_calls(), [["task", "done", CARD]])
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
                self.begin("--restart")
                self.link_card()
                result = self.check("--review-model", "m")
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(self.card_calls(), [["task", "fail", CARD, "--note", "escalated"]])

    def test_gate_only_runs_the_gate_and_writes_the_diff_without_a_reviewer(self):
        self.write_brief(gate="true")
        self.begin()
        self.link_card()
        self.implement()
        result = self.check("--gate-only")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("VERDICT", result.stdout)
        self.assertEqual(self.reviews(), [])
        self.assertTrue((self.out / "unit" / "rounds" / "1" / "diff.patch").is_file())
        self.assertEqual(self.card_calls(), [])

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
        self.link_card()
        no_model = self.check()
        self.assertEqual(no_model.returncode, 3)
        self.assertIn("--review-model is required", no_model.stderr)
        self.assertEqual(self.card_calls(), [])

    def test_missing_review_verdict_leaves_the_card_alone(self):
        self.env["FAKE_VERDICTS"] = json.dumps(["invalid"])
        self.write_brief()
        self.begin()
        self.link_card()
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertEqual(self.card_calls(), [])

    def test_close_records_a_manual_review(self):
        self.write_brief(gate="true")
        self.begin()
        self.link_card()
        self.assertEqual(self.check("--gate-only").returncode, 0)
        close = ("close", str(self.brief), "--dir", str(self.out), "--as")
        for args in (("done",), ("failed",), ("failed", "--note", "needs a decision")):
            with self.subTest(args=args):
                result = self.plan_unit(*close, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.card_calls(), [
            ["task", "done", CARD],
            ["task", "fail", CARD],
            ["task", "fail", CARD, "--note", "needs a decision"],
        ])

    def test_close_without_a_card_does_nothing(self):
        self.write_brief()
        self.begin()
        result = self.plan_unit("close", str(self.brief), "--dir", str(self.out), "--as", "done")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.card_calls(), [])

    def test_task_failure_warns_without_changing_review_or_close_exit_codes(self):
        self.write_brief()
        self.begin()
        self.link_card()
        self.env["FAKE_VERDICTS"] = json.dumps(["pass", "escalate"])
        self.env["FAKE_BKF_FAIL"] = "1"
        for result, code in (
            (self.check("--review-model", "m"), 0),
            (self.check("--review-model", "m"), 2),
            (self.plan_unit("close", str(self.brief), "--dir", str(self.out), "--as", "done"), 0),
        ):
            with self.subTest(code=code):
                self.assertEqual(result.returncode, code, result.stdout)
                self.assertIn("warning", result.stderr.lower())
                self.assertIn("store unavailable", result.stderr)

    def test_green_receipt_makes_check_skip_the_gate(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        receipt = self.gate()
        self.assertEqual((receipt.returncode, receipt.stdout.strip()), (0, "receipt: pass (1 command(s))"), receipt.stderr)
        self.assertEqual(self.runs(), 1)
        data = json.loads(self.receipt().read_text(encoding="utf-8"))
        self.assertEqual((data["commands"], data["red"]), ([self.counted_gate()], 0))
        self.assertRegex(data["tree"], r"^[0-9a-f]+$")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (receipt, 1 command(s))", result.stdout)
        self.assertEqual(self.runs(), 1)
        self.assertIn(str(self.out / "unit" / "receipt" / "gate" / "gate.md"), self.reviews()[0].read_text())

    def test_edit_after_gate_makes_check_run_the_gate_again(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.implement("changed again\n")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        self.assertEqual(self.runs(), 2)

    def test_changed_gate_command_in_the_brief_makes_check_run_the_gate_again(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.write_brief(gate=self.counted_gate(log="other.log"))
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        self.assertEqual((self.runs(), self.runs("other.log")), (1, 1))

    def test_red_receipt_never_makes_check_skip_the_gate(self):
        self.write_brief(gate=self.counted_gate(check="grep -q never-there seed.txt"))
        self.begin()
        self.implement()
        receipt = self.gate()
        self.assertEqual((receipt.returncode, receipt.stdout.strip()), (1, "receipt: FAIL (1 of 1)"), receipt.stderr)
        self.assertEqual(json.loads(self.receipt().read_text(encoding="utf-8"))["red"], 1)
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("VERDICT: back", result.stdout)
        self.assertEqual(self.runs(), 2)
        self.assertEqual(self.reviews(), [])

    def test_failing_gate_in_check_deletes_an_old_receipt(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.implement("other\n")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse(self.receipt().exists())

    def test_gate_needs_begin_first(self):
        self.write_brief(gate="true")
        result = self.gate()
        self.assertEqual(result.returncode, 3)
        self.assertIn("run begin first", result.stderr)

    def test_green_receipt_also_skips_the_gate_with_gate_only(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        result = self.check("--gate-only")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (receipt, 1 command(s))", result.stdout)
        self.assertNotIn("VERDICT", result.stdout)
        self.assertEqual((self.runs(), self.reviews()), (1, []))

    def test_unreadable_receipt_is_ignored_and_the_gate_runs(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.receipt().write_text("{not json", encoding="utf-8")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        self.assertEqual(self.runs(), 2)

    def test_gate_without_gate_commands_writes_no_receipt(self):
        self.write_brief()
        self.begin()
        self.implement()
        result = self.gate()
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "receipt: none (no gate commands)"), result.stderr)
        self.assertFalse(self.receipt().exists())


if __name__ == "__main__":
    unittest.main()

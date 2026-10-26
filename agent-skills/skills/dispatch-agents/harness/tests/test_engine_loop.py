import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.engine.run import RunDir, Settings
from harness.engine.loop import run_unit_loop


class Limits:
    max_rounds = 3
    max_gate_rounds = 3
    gate_timeout = 10
    min_checked = 1


class Hooks:
    def __init__(self):
        self.progress_lines = []
        self.entered = []
        self.implement_calls = []
        self.review_calls = []
        self.commands = None

    def implement_prompt(self, brief, round_number, resumed, previous_problems, previous_handoff):
        self.implement_calls.append((round_number, resumed, previous_problems, previous_handoff))
        return "IMPLEMENT {0} resumed={1}\n".format(round_number, resumed)

    def review_prompt(self, brief, patch, previous_problems, attempt, gate_file):
        self.review_calls.append((brief, patch, previous_problems, attempt, gate_file))
        return "# Review\nREVIEW attempt={0} gate={1}\n".format(attempt, gate_file)

    def gate_commands(self, brief):
        if self.commands is not None:
            return self.commands
        return ["test -f ready"] if "gate" in Path(brief).read_text() else []

    def progress(self, text):
        self.progress_lines.append(text)

    class Around:
        def __init__(self, hooks, checkout, unit, base, brief):
            self.hooks = hooks
            self.checkout = checkout
            self.unit = unit
            self.base = base
            self.brief = brief

        def __enter__(self):
            self.hooks.entered.append(("enter", self.unit))
            (Path(self.checkout) / ".around-implement").write_text("inside\n", encoding="utf-8")

        def __exit__(self, *args):
            self.hooks.entered.append(("exit", self.unit))
            (Path(self.checkout) / ".around-implement").unlink()

    def around_implement(self, checkout, unit, base, brief):
        return self.Around(self, checkout, unit, base, brief)


class UnitLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Harness Test")
        self.git("config", "user.email", "harness@example.invalid")
        (self.checkout / "tracked.txt").write_text("base\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.run = RunDir.create(
            self.root / "runs", "sample", str(self.checkout), Settings("model", "high", "review"), "none"
        )
        self.unit_dir = self.run.path / "01-unit"
        self.source_brief = self.root / "source-brief.md"
        self.source_brief.write_text("# Unit\n", encoding="utf-8")
        self.hooks = Hooks()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.install_codex()
        self.path_patch = patch.dict(os.environ, {
            "PATH": str(self.bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_VERDICT": "pass",
            "FAKE_IMPL": "change",
            "FAKE_GATE_READY_ROUND": "0",
        })
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.checkout)] + list(args), check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()

    def install_codex(self):
        self.fake = self.bin_dir / "codex"
        self.fake.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, re, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "prompt = sys.stdin.read()\n"
            "output = cwd / sys.argv[sys.argv.index('-o') + 1]\n"
            "if prompt.startswith('# Review'):\n"
            " if (cwd / '.around-implement').exists(): sys.exit(92)\n"
            " verdicts = os.environ.get('FAKE_VERDICTS', os.environ.get('FAKE_VERDICT', 'pass')).split(',')\n"
            " n = int(output.parent.name) - 1\n"
            " verdict = verdicts[min(n, len(verdicts)-1)]\n"
            " if os.environ.get('FAKE_REVIEW') == 'unusable': output.write_text('no review\\n')\n"
            " else:\n"
            "  checked = '## What I checked\\n- diff\\n\\n'\n"
            "  output.write_text(checked + '## Problems\\n' + os.environ.get('FAKE_PROBLEM_FILES', 'none') + '\\n\\nVERDICT: ' + verdict + '\\n')\n"
            "else:\n"
            " if not (cwd / '.around-implement').exists(): sys.exit(91)\n"
            " match = re.search(r'IMPLEMENT ([0-9]+)', prompt)\n"
            " n = int(match.group(1)) if match else 1\n"
            " mode = os.environ.get('FAKE_IMPL', 'change')\n"
            " if mode == 'fail':\n"
            "  if os.environ.get('FAKE_QUOTA') == '1': print('{\"message\":\"hit your usage limit; try again at tomorrow\"}')\n"
            "  sys.exit(7)\n"
            " if mode != 'no-handoff':\n"
            "  output.write_text('BLOCKED: ' + os.environ['FAKE_BLOCKED'] + '\\n' if os.environ.get('FAKE_BLOCKED') else 'handoff round ' + str(n) + '\\n')\n"
            " if mode == 'change': (cwd / 'tracked.txt').write_text('changed\\n')\n"
            " if os.environ.get('FAKE_GATE_READY_ROUND') and n >= int(os.environ['FAKE_GATE_READY_ROUND']) > 0: (cwd / 'ready').write_text('ok')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        self.fake.chmod(0o755)

    def run_loop(self, limits=None, base_from=None):
        return run_unit_loop(
            self.run, "01-unit", self.checkout, source_brief=self.source_brief,
            hooks=self.hooks, settings=self.run.settings, tier="fast",
            limits=limits or Limits(), step=1, base_from=base_from,
        )

    def notes(self):
        return [line.split("\t", 1)[1] for line in (self.run.path / "status.log").read_text().splitlines()[1:]]

    def test_green_round_writes_files_status_notes_and_progress(self):
        result = self.run_loop()
        self.assertTrue(result.ok)
        rd = self.unit_dir / "rounds" / "1"
        self.assertEqual((self.unit_dir / "status").read_text(), "passed\n")
        self.assertEqual((self.unit_dir / "brief.md").read_text(), "# Unit\n")
        self.assertEqual((rd / "implement-prompt.md").read_text(), "IMPLEMENT 1 resumed=0\n")
        self.assertEqual(sorted(path.name for path in rd.iterdir()), [
            "diff.patch", "handoff.md", "implement-prompt.md", "implement.events.jsonl",
            "implement.last-message.md", "implement.stderr.log", "problems.md",
            "review-prompt.md", "review.events.jsonl", "review.last-message.md",
            "review.stderr.log", "verdict",
        ])
        self.assertEqual((rd / "handoff.md").read_text(), "handoff round 1\n")
        self.assertEqual((self.unit_dir / "handoff.md").read_text(), "handoff round 1\n")
        self.assertEqual((self.unit_dir / "final.patch").read_text(), (rd / "diff.patch").read_text())
        self.assertEqual(self.notes(), ["01-unit round 1: implement", "01-unit round 1: review", "01-unit: round 1: verdict pass"])
        self.assertEqual(self.hooks.progress_lines, [
            "S1 unidade 01-unit · ronda 1 · implementação",
            "S1 unidade 01-unit · ronda 1 · revisão",
            "S1 unidade 01-unit · ronda 1 · passou",
        ])
        self.assertEqual(self.hooks.entered, [("enter", "01-unit"), ("exit", "01-unit")])

    def test_blocked_handoff_stops_before_diff_gate_and_review(self):
        self.source_brief.write_text("# Unit\n```gate\nfalse\n```\n", encoding="utf-8")
        os.environ["FAKE_BLOCKED"] = "the gate command cannot pass here"
        self.addCleanup(lambda: os.environ.pop("FAKE_BLOCKED", None))
        result = self.run_loop()
        round_dir = self.unit_dir / "rounds" / "1"
        handoff = round_dir / "handoff.md"

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: blocked by the implementer: the gate command cannot pass here (see {0})".format(handoff))
        self.assertEqual((self.unit_dir / "status").read_text(), "blocked\n")
        self.assertFalse((round_dir / "diff.patch").exists())
        self.assertFalse((round_dir / "gate.md").exists())
        self.assertFalse((round_dir / "review-prompt.md").exists())
        self.assertIn(result.reason, (self.run.path / "status.log").read_text())
        self.assertEqual(self.hooks.progress_lines[-1], "S1 unidade 01-unit · ronda 1 · bloqueada")

    def test_brief_verdict_escalates_with_brief_reason(self):
        os.environ["FAKE_VERDICT"] = "brief"
        result = self.run_loop()
        problems = self.unit_dir / "rounds" / "1" / "problems.md"

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: the reviewer says the brief is the problem (see {0})".format(problems))
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")
        self.assertEqual(self.hooks.progress_lines[-1], "S1 unidade 01-unit · ronda 1 · escalada")

    def test_gate_failure_then_pass_counts_separately_and_keeps_gate_problems_text(self):
        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        os.environ["FAKE_GATE_READY_ROUND"] = "2"
        result = self.run_loop()
        self.assertTrue(result.ok)
        one = self.unit_dir / "rounds" / "1"
        self.assertEqual((one / "verdict").read_text(), "back\n")
        self.assertEqual((one / "problems.md").read_text(), "## What I checked\n\n- The script ran the brief's gate in the checkout; a command failed, so no reviewer ran (a failing command is not a matter of opinion).\n- The results are in gate.md of this round.\n- Each failing command below must pass.\n\n## Problems\n\n" + (one / "gate.md").read_text() + "\nVERDICT: back\n")
        self.assertFalse((one / "review-prompt.md").exists())
        self.assertEqual((self.unit_dir / "rounds" / "2" / "review-prompt.md").read_text(),
                         "# Review\nREVIEW attempt=1 gate={0}\n".format(self.unit_dir / "rounds" / "2" / "gate.md"))
        self.assertEqual(self.notes()[:4], [
            "01-unit round 1: implement", "01-unit round 1: gate",
            "01-unit: round 1: gate failed (see {0})".format(one / "gate.md"),
            "01-unit round 2: implement",
        ])
        self.assertEqual(self.notes(), [
            "01-unit round 1: implement", "01-unit round 1: gate",
            "01-unit: round 1: gate failed (see {0})".format(one / "gate.md"),
            "01-unit round 2: implement", "01-unit round 2: gate",
            "01-unit round 2: gate passed", "01-unit round 2: review",
            "01-unit: round 2: verdict pass",
        ])
        self.assertEqual(self.hooks.progress_lines, [
            "S1 unidade 01-unit · ronda 1 · implementação",
            "S1 unidade 01-unit · ronda 1 · gate FAIL",
            "S1 unidade 01-unit · ronda 2 · implementação",
            "S1 unidade 01-unit · ronda 2 · gate PASS",
            "S1 unidade 01-unit · ronda 2 · revisão",
            "S1 unidade 01-unit · ronda 2 · passou",
        ])

    def test_round_caps_are_independent_for_gate_failures_and_review_backs(self):
        class TwoCaps(Limits):
            max_rounds = 1
            max_gate_rounds = 2

        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        os.environ["FAKE_GATE_READY_ROUND"] = "0"
        result = self.run_loop(TwoCaps())
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: the gate fails the same way in two rounds in a row (test -f ready); the brief may ask for something that cannot pass at this step (see {0})".format(self.unit_dir / "rounds" / "2" / "gate.md"))
        self.assertEqual(len(list((self.unit_dir / "rounds").iterdir())), 2)

    def test_gate_always_red_escalates_at_gate_cap_without_reviewing(self):
        class OneGateRound(Limits):
            max_gate_rounds = 1

        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        result = self.run_loop(OneGateRound())
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: the gate still fails after 1 rounds (see {0})".format(self.unit_dir / "rounds" / "1" / "gate.md"))
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")
        self.assertFalse((self.unit_dir / "rounds" / "1" / "review-prompt.md").exists())

    def test_flaky_gate_passes_on_one_repeat(self):
        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        self.hooks.commands = [
            "n=$(cat .gate-count 2>/dev/null || echo 0); n=$((n+1)); echo $n >.gate-count; "
            "if [ $n -eq 1 ]; then echo 'FAIL 123 /tmp/run-123/test.py'; exit 1; fi"
        ]
        result = self.run_loop()
        self.assertTrue(result.ok)
        self.assertEqual(len(list((self.unit_dir / "rounds").iterdir())), 1)
        self.assertTrue((self.unit_dir / "rounds" / "1" / "gate-repeat" / "gate.md").exists())
        self.assertTrue(any(
            "gate was red once and green on repeat (flaky): " + self.hooks.commands[0] in note
            for note in self.notes()
        ))

    def test_flaky_gate_does_not_count_as_previous_failed_round(self):
        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        os.environ["FAKE_VERDICTS"] = "back,back"
        self.hooks.commands = [
            "n=$(cat .gate-count 2>/dev/null || echo 0); n=$((n+1)); echo $n >.gate-count; "
            "if [ $n -eq 4 ]; then exit 0; fi; "
            "echo 'FAIL 123 /tmp/same'; exit 1"
        ]
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("gate fails the same way in two rounds in a row", result.reason)
        self.assertIn(str(self.unit_dir / "rounds" / "4" / "gate.md"), result.reason)
        self.assertEqual(len(list((self.unit_dir / "rounds").iterdir())), 4)

    def test_same_gate_failure_twice_escalates_early(self):
        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        self.hooks.commands = ["echo 'FAIL test_a.py:123'; exit 1"]
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("fails the same way in two rounds in a row (" + self.hooks.commands[0] + ")", result.reason)
        self.assertEqual(len(list((self.unit_dir / "rounds").iterdir())), 2)
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")

    def test_different_gate_failures_in_two_rounds_do_not_stop_as_repeated(self):
        class TwoGateRounds(Limits):
            max_gate_rounds = 2

        self.source_brief.write_text("# Unit\n gate\n", encoding="utf-8")
        self.hooks.commands = [
            "n=$(cat .gate-count 2>/dev/null || echo 0); n=$((n+1)); echo $n >.gate-count; "
            "if [ $n -le 2 ]; then echo 'FAIL test_a.py'; else echo 'FAIL test_b.py'; fi; exit 1"
        ]
        result = self.run_loop(TwoGateRounds())
        self.assertFalse(result.ok)
        self.assertIn("gate still fails after 2 rounds", result.reason)
        self.assertNotIn("fails the same way", result.reason)

    def test_same_review_files_twice_escalates(self):
        os.environ["FAKE_VERDICTS"] = "back,back"
        os.environ["FAKE_PROBLEM_FILES"] = "- Fix `src/a.py`"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("reviewer sent the unit back twice for the same files (src/a.py)", result.reason)
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")

    def test_different_review_files_do_not_stop_as_repeated(self):
        os.environ["FAKE_VERDICTS"] = "back,back,back"
        os.environ["FAKE_PROBLEM_FILES"] = "- Fix `src/a.py`"
        # The fake reviewer changes the file on each call when requested.
        self.fake.write_text(self.fake.read_text().replace(
            "os.environ.get('FAKE_PROBLEM_FILES', 'none')",
            "os.environ.get('FAKE_PROBLEM_FILES', 'none').replace('src/a.py', 'src/' + str(n) + '.py')"
        ), encoding="utf-8")
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("round cap 3 reached", result.reason)
        self.assertNotIn("same files", result.reason)

    def test_reviewer_back_then_pass_preserves_previous_problem_paths(self):
        os.environ["FAKE_VERDICTS"] = "back,pass"
        result = self.run_loop()
        self.assertTrue(result.ok)
        self.assertEqual((self.unit_dir / "rounds" / "2" / "implement-prompt.md").read_text(), "IMPLEMENT 2 resumed=0\n")
        self.assertEqual(self.hooks.progress_lines[1:], [
            "S1 unidade 01-unit · ronda 1 · revisão",
            "S1 unidade 01-unit · ronda 1 · devolvida",
            "S1 unidade 01-unit · ronda 2 · implementação",
            "S1 unidade 01-unit · ronda 2 · revisão",
            "S1 unidade 01-unit · ronda 2 · passou",
        ])
        self.assertEqual(self.notes()[2], "01-unit: round 1: verdict back")
        previous_round = str(self.unit_dir / "rounds" / "1")
        self.assertEqual(self.hooks.implement_calls[1], (
            2, 0, previous_round + "/problems.md", previous_round + "/handoff.md"
        ))
        self.assertEqual(self.hooks.review_calls[1][2], previous_round + "/problems.md")

    def test_reviewer_back_at_max_rounds_escalates(self):
        class OneReview(Limits):
            max_rounds = 1

        os.environ["FAKE_VERDICT"] = "back"
        result = self.run_loop(OneReview())
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: round cap 1 reached (see {0})".format(self.unit_dir / "rounds" / "1" / "problems.md"))
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")
        self.assertEqual(self.hooks.progress_lines[-2:], [
            "S1 unidade 01-unit · ronda 1 · devolvida",
            "S1 unidade 01-unit · ronda 1 · escalada",
        ])

    def test_reviewer_escalate_stops_with_exact_reason(self):
        os.environ["FAKE_VERDICT"] = "escalate"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: the reviewer escalated (see {0})".format(self.unit_dir / "rounds" / "1" / "problems.md"))
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")

    def test_empty_diff_stops_after_metrics_and_handoff(self):
        os.environ["FAKE_IMPL"] = "no-change"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: the diff is empty after round 1, so nothing was changed")
        self.assertTrue((self.run.path / "metrics.tsv").exists())
        self.assertTrue((self.unit_dir / "rounds" / "1" / "handoff.md").exists())
        self.assertFalse((self.unit_dir / "rounds" / "1" / "review-prompt.md").exists())

    def test_implementer_failures_are_quota_aware(self):
        os.environ["FAKE_IMPL"] = "fail"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: implementer exit=7 (see {0}/implement.stderr.log)".format(self.unit_dir / "rounds" / "1"))
        self.run = RunDir.create(
            self.root / "runs", "quota", str(self.checkout), Settings("model", "high", "review"), "none"
        )
        self.unit_dir = self.run.path / "02-unit"
        self.run_loop = lambda limits=None, base_from=None: run_unit_loop(
            self.run, "02-unit", self.checkout, source_brief=self.source_brief,
            hooks=self.hooks, settings=self.run.settings, tier="fast",
            limits=limits or Limits(), step=1, base_from=base_from,
        )
        os.environ["FAKE_QUOTA"] = "1"
        quota_result = self.run_loop()
        self.assertFalse(quota_result.ok)
        self.assertEqual(quota_result.reason, "02-unit: usage limit reached. QUOTA: tomorrow (see {0}/rounds/1/implement.events.jsonl)".format(self.unit_dir))

    def test_missing_handoff_stops_with_exact_reason(self):
        os.environ["FAKE_IMPL"] = "no-handoff"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: implementer left no handoff")

    def test_three_unusable_reviews_stop_with_review_reason(self):
        os.environ["FAKE_REVIEW"] = "unusable"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: the reviewer left no usable review after 3 attempts (see {0})".format(self.unit_dir / "rounds" / "1" / "review.last-message.md"))
        self.assertEqual(self.notes()[-3:], [
            "01-unit: review attempt 1 was not usable",
            "01-unit: review attempt 2 was not usable",
            "01-unit: review attempt 3 was not usable",
        ])

    def test_resume_moves_old_rounds_and_sets_resumed_prompt_flag(self):
        class OneReview(Limits):
            max_rounds = 1

        os.environ["FAKE_VERDICT"] = "back"
        first = self.run_loop(OneReview())
        self.assertFalse(first.ok)
        os.environ["FAKE_VERDICT"] = "pass"
        second = self.run_loop()
        self.assertTrue(second.ok)
        attempts = list(self.unit_dir.glob("rounds.attempt-*"))
        self.assertEqual(len(attempts), 1)
        self.assertTrue((attempts[0] / "1" / "problems.md").exists())
        self.assertEqual((self.unit_dir / "rounds" / "1" / "implement-prompt.md").read_text(), "IMPLEMENT 1 resumed=1\n")

    def test_resume_uses_supplied_base_file_when_present(self):
        class OneReview(Limits):
            max_rounds = 1

        os.environ["FAKE_VERDICT"] = "back"
        self.assertFalse(self.run_loop(OneReview()).ok)
        replacement = self.root / "replacement-base"
        replacement.write_text(self.git("rev-parse", "HEAD^{tree}") + "\n", encoding="utf-8")
        os.environ["FAKE_VERDICT"] = "pass"
        result = self.run_loop(base_from=replacement)
        self.assertTrue(result.ok)
        self.assertEqual((self.unit_dir / "base").read_text(), replacement.read_text())
        self.assertEqual((self.unit_dir / "base-format").read_text(), "tree\n")


if __name__ == "__main__":
    unittest.main()

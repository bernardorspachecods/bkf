import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.engine.run import RunDir, Settings
from harness.engine.integration import run_integration
from harness.engine.review import ReviewResult
from harness.engine.loop import run_review_round, run_unit_loop


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

    def implement_prompt(self, brief, round_number, resumed, previous_problems, previous_handoff,
                         last_review_problems=None):
        self.implement_calls.append((round_number, resumed, previous_problems, previous_handoff,
                                     last_review_problems))
        text = "IMPLEMENT {0} resumed={1}\n".format(round_number, resumed)
        if last_review_problems:
            text += "previous={0} last_review={1}\n".format(previous_problems, last_review_problems)
        return text

    def review_prompt(self, brief, patch, previous_problems, attempt, gate_file,
                      last_review_problems=None):
        self.review_calls.append((brief, patch, previous_problems, attempt, gate_file,
                                  last_review_problems))
        text = "# Review\nREVIEW attempt={0} gate={1}\n".format(attempt, gate_file)
        if last_review_problems:
            text += "last_review={0}\n".format(last_review_problems)
        return text

    def review_continuation(self, brief, brief_changed, patch, previous_problems, attempt, gate_file,
                            last_review_problems, delta_patch=None):
        if delta_patch is None:
            return None
        self.review_continuations = getattr(self, "review_continuations", [])
        self.review_continuations.append(delta_patch)
        self.continuation_gate_files = getattr(self, "continuation_gate_files", [])
        self.continuation_gate_files.append(gate_file)
        return "# Continue review\npatch={0}\ndelta={1}\n".format(patch, delta_patch)

    def gate_commands(self, brief):
        if self.commands is not None:
            return self.commands
        return ["test -f ready"] if "gate" in Path(brief).read_text() else []

    premises = ()

    def premise_commands(self, brief):
        return list(self.premises)

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
            "HARNESS_SHM_MIN_FREE": "0",
            "FAKE_ARG_LOG": str(self.root / "codex-args.log"),
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
            "import json, os, pathlib, re, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1]) if '-C' in sys.argv else pathlib.Path.cwd()\n"
            "prompt = sys.stdin.read()\n"
            "output = cwd / sys.argv[sys.argv.index('-o') + 1]\n"
            "if os.environ.get('FAKE_ARG_LOG'): open(os.environ['FAKE_ARG_LOG'], 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
            "print(json.dumps({'type': 'thread.started', 'thread_id': 'fake-thread'}))\n"
            "if prompt.startswith('# Review') or prompt.startswith('# Continue review'):\n"
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

    def test_review_round_runs_on_the_reviewers_own_model_and_backend(self):
        cases = (
            (Settings("impl-model", "high", "low"), ("impl-model", None)),
            (Settings("impl-model", "high", "low", "rev-model", "claude"), ("rev-model", "claude")),
        )
        for settings, (model, backend) in cases:
            with self.subTest(model=model):
                round_dir = self.unit_dir / "rounds" / "1"
                round_dir.mkdir(parents=True, exist_ok=True)
                with patch("harness.engine.loop.run_review", return_value=ReviewResult("pass", "")) as review:
                    run_review_round(self.run, "01-unit", str(self.checkout), str(round_dir), self.hooks, settings,
                                     "fast", Limits(), "", "", "01-unit")
                self.assertEqual(review.call_args.args[5], model)
                self.assertEqual(review.call_args.args[6], "low")
                self.assertEqual(review.call_args.kwargs["backend"], backend)

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

    def test_a_false_premise_stops_before_any_implementer_is_launched(self):
        self.hooks.premises = ["test -f missing-file"]
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("the premise `test -f missing-file` is false at this unit's start", result.reason)
        self.assertIn("no implementer was launched", result.reason)
        self.assertEqual((self.unit_dir / "status").read_text(), "blocked\n")
        self.assertEqual(self.hooks.implement_calls, [])
        self.assertTrue((self.unit_dir / "premise" / "gate-1.log").is_file())

    def test_exhausted_shared_memory_stops_before_any_implementer_is_launched(self):
        with patch("harness.engine.loop.shm_problem", return_value="only 1 of 32 segments are free"):
            result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "01-unit: not started, only 1 of 32 segments are free")
        self.assertEqual((self.unit_dir / "status").read_text(), "blocked\n")
        self.assertEqual(self.hooks.implement_calls, [])

    def test_a_true_premise_lets_the_unit_run(self):
        self.hooks.premises = ["test -f tracked.txt"]
        self.assertTrue(self.run_loop().ok)

    def test_a_retried_unit_gets_the_earlier_handoff_in_its_first_round(self):
        os.environ["FAKE_BLOCKED"] = "the brief was wrong"
        self.addCleanup(lambda: os.environ.pop("FAKE_BLOCKED", None))
        self.assertFalse(self.run_loop().ok)
        os.environ.pop("FAKE_BLOCKED")
        self.hooks.implement_calls.clear()
        self.assertTrue(self.run_loop().ok)
        round_number, resumed, previous_problems, previous_handoff, _ = self.hooks.implement_calls[0]
        self.assertEqual((round_number, resumed, previous_problems), (1, 1, ""))
        self.assertEqual(Path(previous_handoff), self.unit_dir / "handoff.md")

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
            2, 0, previous_round + "/problems.md", previous_round + "/handoff.md", None
        ))
        self.assertEqual(self.hooks.review_calls[1][2], previous_round + "/problems.md")

    def test_gate_failure_does_not_forget_last_review_problems(self):
        self.source_brief.write_text("# Unit\n```gate\n./check-round.sh\n```\n", encoding="utf-8")
        check = self.checkout / "check-round.sh"
        check.write_text("#!/bin/sh\n[ \"$(cat current-round)\" != 2 ]\n", encoding="utf-8")
        check.chmod(0o755)
        self.hooks.commands = ["./check-round.sh"]
        os.environ["FAKE_VERDICTS"] = "back,pass"
        self.fake.write_text(self.fake.read_text().replace(
            "if mode == 'change': (cwd / 'tracked.txt').write_text('changed\\n')",
            "if mode == 'change': (cwd / 'tracked.txt').write_text('changed\\n')\n"
            " (cwd / 'current-round').write_text(str(n))"
        ), encoding="utf-8")
        result = self.run_loop()

        self.assertTrue(result.ok, result.reason)
        review_problems = str(self.unit_dir / "rounds" / "1" / "problems.md")
        gate_problems = str(self.unit_dir / "rounds" / "2" / "problems.md")
        third_implement = self.hooks.implement_calls[2]
        third_review = self.hooks.review_calls[1]
        self.assertEqual(third_implement[2], gate_problems)
        self.assertEqual(third_implement[4], review_problems)
        self.assertIn(review_problems, (self.unit_dir / "rounds" / "3" / "implement-prompt.md").read_text())
        self.assertIn(gate_problems, (self.unit_dir / "rounds" / "3" / "implement-prompt.md").read_text())
        self.assertEqual(third_review[2], review_problems)
        self.assertIn(review_problems, (self.unit_dir / "rounds" / "3" / "review-prompt.md").read_text())
        self.assertEqual(third_review[4], str(self.unit_dir / "rounds" / "3" / "gate.md"))

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

    def test_takeover_after_two_backs_precedes_repeat_files_and_round_cap(self):
        self.run.settings = Settings("model", "high", "review", "", "", "2", "reviewer")
        os.environ["FAKE_VERDICTS"] = "back,back,pass"
        os.environ["FAKE_PROBLEM_FILES"] = "src/a.py"
        result = self.run_loop()
        problems = self.unit_dir / "rounds" / "2" / "problems.md"
        self.assertFalse(result.ok)
        self.assertEqual((self.unit_dir / "status").read_text(), "takeover\n")
        self.assertEqual((self.unit_dir / "takeover").read_text(), str(problems) + "\n")
        self.assertTrue((self.unit_dir / "takeover-base").is_file())
        for expected in (str(problems), str(self.checkout), str(self.unit_dir / "brief.md"), "close sample"):
            self.assertIn(expected, result.reason)
        self.assertEqual(len(self.hooks.implement_calls), 2)

    def test_takeover_after_one_back(self):
        self.run.settings = Settings("model", "high", "review", "", "", "1", "reviewer")
        os.environ["FAKE_VERDICT"] = "back"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual((self.unit_dir / "status").read_text(), "takeover\n")
        self.assertEqual(len(self.hooks.implement_calls), 1)

    def test_escalate_does_not_become_takeover(self):
        self.run.settings = Settings("model", "high", "review", "", "", "2", "reviewer")
        os.environ["FAKE_VERDICT"] = "escalate"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual((self.unit_dir / "status").read_text(), "escalated\n")
        self.assertFalse((self.unit_dir / "takeover").exists())

    def _make_takeover(self, review="reviewer"):
        self.run.settings = Settings("model", "high", "review", "", "", "1", review)
        os.environ["FAKE_VERDICT"] = "back"
        result = self.run_loop()
        self.assertFalse(result.ok)
        os.environ["FAKE_VERDICT"] = "pass"
        os.environ.pop("FAKE_VERDICTS", None)
        self.hooks.progress_lines.clear()

    def test_close_resumes_reviewer_with_delta_and_finishes(self):
        self._make_takeover()
        (self.checkout / "tracked.txt").write_text("coordinator fix\n", encoding="utf-8")
        (self.unit_dir / "closing").touch()
        result = self.run_loop()
        close_dir = self.unit_dir / "close" / "1"
        self.assertTrue(result.ok, result.reason)
        self.assertEqual((self.unit_dir / "status").read_text(), "passed\n")
        self.assertEqual((self.unit_dir / "closed-by-coordinator").read_text(), "reviewed: yes\n")
        self.assertFalse((self.unit_dir / "takeover").exists())
        self.assertFalse((self.unit_dir / "closing").exists())
        self.assertIn(" resume --skip-git-repo-check", (self.root / "codex-args.log").read_text())
        self.assertIn(" fake-thread -", (self.root / "codex-args.log").read_text())
        self.assertIn("delta.patch", (close_dir / "review-continue.md").read_text())
        self.assertTrue((close_dir / "delta.patch").is_file())

    def test_close_tells_the_reviewer_about_a_gate_only_when_the_brief_has_one(self):
        self._make_takeover()
        (self.checkout / "tracked.txt").write_text("coordinator fix\n", encoding="utf-8")
        (self.unit_dir / "closing").touch()
        self.assertTrue(self.run_loop().ok)
        self.assertEqual(self.hooks.continuation_gate_files, [""])

    def test_close_without_reviewer_finishes_reviewed_no(self):
        self._make_takeover(review="none")
        (self.checkout / "tracked.txt").write_text("coordinator fix\n", encoding="utf-8")
        (self.unit_dir / "closing").touch()
        args_before = (self.root / "codex-args.log").read_text()
        result = self.run_loop()
        self.assertTrue(result.ok, result.reason)
        self.assertEqual((self.unit_dir / "closed-by-coordinator").read_text(), "reviewed: no\n")
        self.assertEqual((self.root / "codex-args.log").read_text(), args_before)

    def test_close_without_delta_stays_in_takeover_without_gate(self):
        self._make_takeover()
        (self.unit_dir / "closing").touch()
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("nothing changed since the takeover", result.reason)
        self.assertEqual((self.unit_dir / "status").read_text(), "takeover\n")
        self.assertTrue((self.unit_dir / "takeover").exists())
        self.assertFalse((self.unit_dir / "closing").exists())
        self.assertFalse((self.unit_dir / "close/1/gate").exists())

    def test_close_gate_failure_stays_in_takeover_without_review(self):
        self._make_takeover()
        self.hooks.commands = ["false"]
        (self.checkout / "tracked.txt").write_text("coordinator fix\n", encoding="utf-8")
        (self.unit_dir / "closing").touch()
        before_reviews = sum("-s read-only" in line for line in (self.root / "codex-args.log").read_text().splitlines())
        result = self.run_loop()
        after_reviews = sum("-s read-only" in line for line in (self.root / "codex-args.log").read_text().splitlines())
        self.assertFalse(result.ok)
        self.assertIn("gate failed after the takeover", result.reason)
        self.assertIn(str(self.unit_dir / "close/1/gate"), result.reason)
        self.assertEqual((self.unit_dir / "status").read_text(), "takeover\n")
        self.assertTrue((self.unit_dir / "takeover").exists())
        self.assertFalse((self.unit_dir / "closing").exists())
        self.assertEqual(after_reviews, before_reviews)

    def test_close_back_starts_a_new_takeover(self):
        self._make_takeover()
        old_base = (self.unit_dir / "takeover-base").read_text()
        (self.checkout / "tracked.txt").write_text("second coordinator fix\n", encoding="utf-8")
        (self.unit_dir / "closing").touch()
        os.environ["FAKE_VERDICT"] = "back"
        result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertEqual((self.unit_dir / "status").read_text(), "takeover\n")
        self.assertEqual((self.unit_dir / "takeover").read_text(), str(self.unit_dir / "close/1/problems.md") + "\n")
        self.assertNotEqual((self.unit_dir / "takeover-base").read_text(), old_base)

    def test_plain_resume_of_takeover_removes_marker_and_implements(self):
        self._make_takeover()
        result = self.run_loop()
        self.assertTrue(result.ok, result.reason)
        self.assertFalse((self.unit_dir / "takeover").exists())
        self.assertEqual(len(self.hooks.implement_calls), 2)

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


class IntegrationLoopMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Harness Test")
        self.git("config", "user.email", "harness@example.invalid")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        check = self.repo / "check-round.sh"
        check.write_text("#!/bin/sh\n[ \"$(cat current-round 2>/dev/null)\" != 2 ]\n", encoding="utf-8")
        check.chmod(0o755)
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.run = RunDir.create(
            self.root / "runs", "sample", str(self.repo),
            Settings("model", "high", "review"), "none",
        )
        units = self.run.path / "00-input" / "units"
        units.mkdir(parents=True)
        (self.run.path / "00-input" / "goal.md").write_text("Goal\n", encoding="utf-8")
        (units / "01-unit.md").write_text("# Unit\n", encoding="utf-8")
        unit_dir = self.run.path / "01-unit"
        unit_dir.mkdir()
        (unit_dir / "brief.md").write_text("# Unit\n", encoding="utf-8")
        (unit_dir / "final.patch").write_text(
            "diff --git a/unit.txt b/unit.txt\nnew file mode 100644\n"
            "index 0000000..f2e2f19\n--- /dev/null\n+++ b/unit.txt\n"
            "@@ -0,0 +1 @@\n+from unit\n",
            encoding="utf-8",
        )
        self.implement_prompts = []
        self.review_prompts = []

        class IntegrationHooks:
            def __init__(inner):
                inner.progress_lines = []

            def integration_brief(inner, run_path, units, goal_text):
                return "Integration brief\n"

            def integrate_prompt(inner, brief, failed, previous_problems, previous_handoff,
                                 last_review_problems=None):
                previous_text = Path(previous_problems).read_text() if previous_problems else ""
                last_review_text = Path(last_review_problems).read_text() if last_review_problems else ""
                return "INTEGRATE previous={0} last_review={1}\n{2}{3}".format(
                    previous_problems, last_review_problems or "", previous_text, last_review_text
                )

            def review_prompt(inner, brief, patch, previous_problems, attempt, gate_file,
                              last_review_problems=None):
                inner_review = (previous_problems, gate_file, last_review_problems)
                self.review_prompts.append(inner_review)
                review_text = Path(last_review_problems).read_text() if last_review_problems else ""
                return "REVIEW previous={0} last_review={1} gate={2}\n{3}".format(
                    previous_problems, last_review_problems or "", gate_file, review_text
                )

            def gate_commands(inner, brief):
                return inner.commands if getattr(inner, "commands", None) is not None else ["./check-round.sh"]

            def progress(inner, text):
                inner.progress_lines.append(text)

        self.hooks = IntegrationHooks()

        class IntegrationLimits:
            max_rounds = 3
            max_gate_rounds = 3
            gate_timeout = 10
            min_checked = 1

        self.limits = IntegrationLimits()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo)] + list(args), check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()

    def integration(self):
        return run_integration(
            self.run, self.repo, 1, ["01-unit"], hooks=self.hooks,
            settings=self.run.settings, tier="fast", limits=self.limits,
            goal_path=self.run.path / "00-input" / "goal.md",
            brief_check=lambda run_path, units: None,
            brief_differs=lambda run_path, unit: False,
            gate_differs=lambda run_path, unit: False,
        )

    def _integration_agent(self, calls):
        def integrate(run, label, directory, prompt_file, out_prefix, *args, **kwargs):
            calls.append(prompt_file)
            (self.repo / "integrated.txt").write_text("integrated {0}\n".format(len(calls)), encoding="utf-8")
            Path(out_prefix + ".last-message.md").write_text("handoff\n", encoding="utf-8")
            return type("Step", (), {"ok": True, "reason": ""})()
        return integrate

    @staticmethod
    def _reviewer(verdicts, calls):
        def review(run, label, checkout, round_dir, hooks, settings, tier, limits,
                   previous, gate_file, progress, last_review_problems=None, delta_patch=None):
            calls.append((round_dir, delta_patch))
            verdict = verdicts.pop(0) if verdicts else "pass"
            Path(round_dir, "problems.md").write_text(
                "## What I checked\n- combined diff\n\n## Problems\n- Fix `src/integration.py`.\n\nVERDICT: {0}\n".format(verdict),
                encoding="utf-8",
            )
            Path(round_dir, "verdict").write_text(verdict + "\n", encoding="utf-8")
            return verdict, ""
        return review

    def test_integration_takeover_after_two_backs_precedes_repeat_files_and_round_cap(self):
        self.run.settings = Settings("model", "high", "review", "", "", "2", "reviewer")
        class TwoRounds(self.limits.__class__):
            max_rounds = 2
        self.limits = TwoRounds()
        (self.run.path / "01-unit" / "final.patch").write_text("not a patch\n", encoding="utf-8")
        integrations, reviews = [], []
        with patch("harness.engine.integration.run_agent_step", side_effect=self._integration_agent(integrations)), patch(
            "harness.engine.integration.run_review_round", side_effect=self._reviewer(["back", "back", "pass"], reviews)
        ):
            result = self.integration()
        directory = self.run.path / "S1-integration"
        problems = directory / "rounds" / "2" / "problems.md"
        self.assertFalse(result.ok)
        self.assertEqual((directory / "status").read_text(), "takeover\n")
        self.assertEqual((directory / "takeover").read_text(), str(problems) + "\n")
        self.assertTrue((directory / "takeover-base").is_file())
        for expected in (str(problems), str(self.repo), str(directory / "brief.md"), "close sample"):
            self.assertIn(expected, result.reason)
        self.assertEqual(len(reviews), 2)
        self.assertEqual(len(integrations), 2)

    def test_integration_takeover_after_one_back_and_escalate_never_take_over(self):
        for verdict, expected_status in (("back", "takeover\n"), ("escalate", "escalated\n")):
            with self.subTest(verdict=verdict):
                self.run = RunDir.create(
                    self.root / "runs", "sample-" + verdict, str(self.repo),
                    Settings("model", "high", "review", "", "", "1", "reviewer"), "none",
                )
                units = self.run.path / "00-input" / "units"
                units.mkdir(parents=True)
                (self.run.path / "00-input" / "goal.md").write_text("Goal\n", encoding="utf-8")
                (units / "01-unit.md").write_text("# Unit\n", encoding="utf-8")
                unit = self.run.path / "01-unit"
                unit.mkdir()
                (unit / "brief.md").write_text("# Unit\n", encoding="utf-8")
                (unit / "final.patch").write_text((self.root / "runs/sample/01-unit/final.patch").read_text())
                integrations, reviews = [], []
                with patch("harness.engine.integration.run_agent_step", side_effect=self._integration_agent(integrations)), patch(
                    "harness.engine.integration.run_review_round", side_effect=self._reviewer([verdict], reviews)
                ):
                    result = self.integration()
                directory = self.run.path / "S1-integration"
                self.assertFalse(result.ok)
                self.assertEqual((directory / "status").read_text(), expected_status)
                self.assertEqual(len(integrations), 0 if verdict == "back" else 1)
                self.assertEqual((directory / "takeover").exists(), verdict == "back")

    def test_takeover_after_zero_keeps_the_integration_round_cap(self):
        class OneRound(self.limits.__class__):
            max_rounds = 1
        self.limits = OneRound()
        self.run.settings = Settings("model", "high", "review", "", "", "0", "reviewer")
        reviews = []
        with patch("harness.engine.integration.run_review_round", side_effect=self._reviewer(["back"], reviews)):
            result = self.integration()
        directory = self.run.path / "S1-integration"
        self.assertFalse(result.ok)
        self.assertIn("round cap 1 reached", result.reason)
        self.assertEqual((directory / "status").read_text(), "escalated\n")
        self.assertFalse((directory / "takeover").exists())

    def _prepare_manual_integration_takeover(self, review="reviewer"):
        self.run.settings = Settings("model", "high", "review", "", "", "2", review)
        directory = self.run.path / "S1-integration"
        directory.mkdir()
        from harness.engine.diffbase import snapshot_base, snapshot_tree
        snapshot_base(directory, self.repo)
        (directory / "takeover-base").write_text(snapshot_tree(self.repo) + "\n", encoding="utf-8")
        (directory / "takeover").write_text(str(directory / "rounds/1/problems.md") + "\n", encoding="utf-8")
        (directory / "status").write_text("takeover\n", encoding="utf-8")
        (directory / "brief.md").write_text("Integration brief\n", encoding="utf-8")
        problems = directory / "rounds/1/problems.md"
        problems.parent.mkdir(parents=True)
        problems.write_text("review problems\n", encoding="utf-8")
        (self.repo / "coordinator.txt").write_text("correction for {0}\n".format(self.run.name), encoding="utf-8")
        (directory / "closing").touch()
        return directory

    def test_integration_close_resumes_reviewer_with_delta_and_finishes(self):
        directory = self._prepare_manual_integration_takeover()
        reviews = []
        with patch("harness.engine.loop.run_review_round", side_effect=self._reviewer(["pass"], reviews)) as reviewer:
            result = self.integration()
        close_dir = directory / "close/1"
        self.assertTrue(result.ok, result.reason)
        self.assertEqual((directory / "status").read_text(), "passed\n")
        self.assertEqual((directory / "closed-by-coordinator").read_text(), "reviewed: yes\n")
        self.assertFalse((directory / "takeover").exists())
        self.assertFalse((directory / "closing").exists())
        reviewer.assert_called_once()
        self.assertEqual(reviews[0][1], str(close_dir / "delta.patch"))
        self.assertTrue((close_dir / "delta.patch").is_file())

    def test_integration_close_without_reviewer_finishes_reviewed_no(self):
        directory = self._prepare_manual_integration_takeover(review="none")
        with patch("harness.engine.loop.run_review_round") as reviewer:
            result = self.integration()
        self.assertTrue(result.ok, result.reason)
        self.assertEqual((directory / "closed-by-coordinator").read_text(), "reviewed: no\n")
        reviewer.assert_not_called()

    def test_integration_close_gate_failure_empty_delta_and_back_stay_in_takeover(self):
        cases = ("gate", "empty", "back")
        for case in cases:
            with self.subTest(case=case):
                run_name = "close-" + case
                self.run = RunDir.create(
                    self.root / "runs", run_name, str(self.repo),
                    Settings("model", "high", "review", "", "", "2", "reviewer"), "none",
                )
                units = self.run.path / "00-input/units"
                units.mkdir(parents=True)
                (self.run.path / "00-input/goal.md").write_text("Goal\n", encoding="utf-8")
                (units / "01-unit.md").write_text("# Unit\n", encoding="utf-8")
                unit = self.run.path / "01-unit"
                unit.mkdir()
                (unit / "brief.md").write_text("# Unit\n", encoding="utf-8")
                (unit / "final.patch").write_text((self.root / "runs/sample/01-unit/final.patch").read_text())
                directory = self._prepare_manual_integration_takeover()
                old_base = (directory / "takeover-base").read_text()
                self.hooks.commands = []
                if case == "empty":
                    (self.repo / "coordinator.txt").unlink()
                    from harness.engine.diffbase import snapshot_tree
                    (directory / "takeover-base").write_text(snapshot_tree(self.repo) + "\n", encoding="utf-8")
                elif case == "gate":
                    self.hooks.commands = ["false"]
                reviews = []
                with patch("harness.engine.loop.run_review_round", side_effect=self._reviewer(["back"], reviews)) as reviewer:
                    result = self.integration()
                self.assertFalse(result.ok)
                self.assertEqual((directory / "status").read_text(), "takeover\n")
                self.assertTrue((directory / "takeover").is_file())
                if case == "gate":
                    reviewer.assert_not_called()
                    self.assertIn("gate failed after the takeover", result.reason)
                elif case == "empty":
                    reviewer.assert_not_called()
                    self.assertIn("nothing changed since the takeover", result.reason)
                else:
                    self.assertNotEqual((directory / "takeover-base").read_text(), old_base)
                    self.assertEqual((directory / "takeover").read_text(), str(directory / "close/1/problems.md") + "\n")

    def test_plain_resume_of_integration_takeover_removes_marker_and_integrates_again(self):
        directory = self._prepare_manual_integration_takeover()
        (directory / "closing").unlink()
        (self.run.path / "01-unit" / "final.patch").write_text("not a patch\n", encoding="utf-8")
        integrations, reviews = [], []
        with patch("harness.engine.integration.run_agent_step", side_effect=self._integration_agent(integrations)), patch(
            "harness.engine.integration.run_review_round", side_effect=self._reviewer(["pass"], reviews)
        ):
            result = self.integration()
        self.assertTrue(result.ok, result.reason)
        self.assertFalse((directory / "takeover").exists())
        self.assertEqual(len(integrations), 1)

    def test_gate_failure_does_not_forget_integration_review_problems(self):
        review_calls = []

        def integrate(run, label, directory, prompt_file, out_prefix, *args, **kwargs):
            prompt = Path(prompt_file).read_text(encoding="utf-8")
            self.implement_prompts.append(prompt)
            round_number = int(Path(prompt_file).parent.name)
            (self.repo / "current-round").write_text(str(round_number), encoding="utf-8")
            (self.repo / "integrated.txt").write_text("integrated {0}\n".format(round_number), encoding="utf-8")
            Path(out_prefix + ".last-message.md").write_text("integrated\n", encoding="utf-8")
            return type("Step", (), {"ok": True, "reason": ""})()

        def review(run, label, checkout, round_dir, build_prompt, *args, **kwargs):
            prompt = build_prompt(1)
            Path(round_dir, "review-prompt.md").write_text(prompt, encoding="utf-8")
            verdict = "back" if not review_calls else "pass"
            review_calls.append(verdict)
            problems = (
                "## What I checked\n\n- The filter\n\n## Problems\n\n"
                "- Keep the organization filter in `src/filter.py`.\n\nVERDICT: {0}\n"
            ).format(verdict)
            Path(round_dir, "problems.md").write_text(problems, encoding="utf-8")
            return ReviewResult(verdict, "")

        with patch("harness.engine.integration.run_agent_step", side_effect=integrate), patch(
            "harness.engine.loop.run_review", side_effect=review
        ):
            result = run_integration(
                self.run, self.repo, 1, ["01-unit"], hooks=self.hooks,
                settings=self.run.settings, tier="fast", limits=self.limits,
                goal_path=self.run.path / "00-input" / "goal.md",
                brief_check=lambda run_path, units: None,
                brief_differs=lambda run_path, unit: False,
                gate_differs=lambda run_path, unit: False,
            )

        self.assertTrue(result.ok, result.reason)
        directory = self.run.path / "S1-integration"
        review_problems = str(directory / "rounds" / "1" / "problems.md")
        gate_problems = str(directory / "rounds" / "2" / "problems.md")
        self.assertEqual(len(self.implement_prompts), 2)
        third_implement = (directory / "rounds" / "3" / "integrate-prompt.md").read_text()
        third_review = (directory / "rounds" / "3" / "review-prompt.md").read_text()
        self.assertIn(review_problems, third_implement)
        self.assertIn(gate_problems, third_implement)
        self.assertIn("Keep the organization filter", third_implement)
        self.assertEqual(self.review_prompts[1][0], review_problems)
        self.assertEqual(self.review_prompts[1][1], str(directory / "rounds" / "3" / "gate.md"))
        self.assertEqual(self.review_prompts[1][2], review_problems)
        self.assertIn(review_problems, third_review)
        self.assertIn("Keep the organization filter", third_review)


if __name__ == "__main__":
    unittest.main()

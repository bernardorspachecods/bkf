import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "workflows"))

from harness.engine.agentstep import StepResult
from harness.engine.integration import run_integration
from harness.engine.run import RunDir, Settings
import plan_inputs


class Limits:
    max_rounds = 1
    max_gate_rounds = 2
    gate_timeout = 5
    min_checked = 1


class Hooks:
    def __init__(self):
        self.progress_lines = []
        self.commands = []

    def integration_brief(self, run_path, units, goal_text):
        return plan_inputs.integration_brief(run_path, units, goal_text)

    def integrate_prompt(self, brief, failed, previous_problems, previous_handoff):
        return plan_inputs.integrate_prompt(
            "guides", brief, failed, previous_problems, previous_handoff
        )

    def review_prompt(self, brief, diff, problems, attempt, gate_file):
        return "REVIEW " + Path(brief).read_text(encoding="utf-8")

    def gate_commands(self, brief):
        return self.commands

    def progress(self, text):
        self.progress_lines.append(text)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Harness Test")
        self.git("config", "user.email", "harness@example.invalid")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.run = RunDir.create(
            self.root / "runs", "sample", str(self.repo),
            Settings("model", "high", "review"), "none",
        )
        input_dir = self.run.path / "00-input" / "units"
        input_dir.mkdir(parents=True)
        (self.run.path / "00-input" / "goal.md").write_text(
            "Goal note\n\n```gate\nfalse\n```\n", encoding="utf-8"
        )
        (input_dir / "01-unit.md").write_text("# Unit\n", encoding="utf-8")
        (self.run.path / "01-unit").mkdir()
        (self.run.path / "01-unit" / "brief.md").write_text("# Unit\n", encoding="utf-8")
        (self.run.path / "01-unit" / "final.patch").write_text(
            "diff --git a/unit.txt b/unit.txt\nnew file mode 100644\n"
            "index 0000000..f2e2f19\n--- /dev/null\n+++ b/unit.txt\n@@ -0,0 +1 @@\n+from unit\n",
            encoding="utf-8",
        )
        self.hooks = Hooks()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo)] + list(args), check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()

    def run_loop(self):
        return run_integration(
            self.run, self.repo, 1, ["01-unit"], hooks=self.hooks,
            settings=self.run.settings, tier="fast", limits=Limits(),
            goal_path=self.run.path / "00-input" / "goal.md",
            brief_check=plan_inputs.check_briefs,
            brief_differs=plan_inputs.brief_differs,
            gate_differs=plan_inputs.gate_differs,
        )

    def test_resume_skips_applied_patch_and_keeps_original_base(self):
        seen = []

        def reviewer(run, label, checkout, round_dir, hooks, settings, tier,
                     limits, previous, gate_file, progress):
            seen.append(round_dir)
            verdict = "back" if len(seen) == 1 else "pass"
            Path(round_dir, "problems.md").write_text("review\n", encoding="utf-8")
            Path(round_dir, "verdict").write_text(verdict + "\n", encoding="utf-8")
            return verdict, ""

        with patch("harness.engine.integration.run_review_round", side_effect=reviewer), patch(
            "harness.engine.integration.run_agent_step", return_value=StepResult(True, "", None)
        ) as integrator:
            first = self.run_loop()
            self.assertFalse(first.ok)
            base = (self.run.path / "S1-integration" / "base").read_text(encoding="utf-8")
            second = self.run_loop()
            integrator.assert_not_called()

        self.assertTrue(second.ok)
        self.assertEqual((self.repo / "unit.txt").read_text(encoding="utf-8"), "from unit\n")
        self.assertEqual((self.run.path / "S1-integration" / "base").read_text(encoding="utf-8"), base)
        self.assertTrue((self.run.path / "S1-integration" / ".applied-01-unit").is_file())
        self.assertEqual(len(list((self.run.path / "S1-integration").glob("rounds.attempt-*"))), 1)
        self.assertIn("Goal note", (self.run.path / "S1-integration" / "brief.md").read_text(encoding="utf-8"))
        self.assertIn("``` gate", (self.run.path / "S1-integration" / "brief.md").read_text(encoding="utf-8"))

    def test_blocked_integrator_stops_before_diff_gate_and_review(self):
        (self.run.path / "01-unit" / "final.patch").write_text("not a patch\n", encoding="utf-8")

        def integrator(run, label, directory, prompt_file, out_prefix, *args):
            Path(out_prefix + ".last-message.md").write_text(
                "BLOCKED: the combined brief requires an impossible command\n", encoding="utf-8"
            )
            return StepResult(True, "", None)

        with patch("harness.engine.integration.run_agent_step", side_effect=integrator) as agent, patch(
            "harness.engine.integration.run_review_round"
        ) as reviewer:
            result = self.run_loop()

        directory = self.run.path / "S1-integration"
        round_dir = directory / "rounds" / "1"
        handoff = round_dir / "handoff.md"
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "S1-integration: blocked by the implementer: the combined brief requires an impossible command (see {0})".format(handoff))
        self.assertEqual((directory / "status").read_text(), "blocked\n")
        self.assertFalse((round_dir / "diff.patch").exists())
        self.assertFalse((round_dir / "gate.md").exists())
        self.assertFalse((round_dir / "review-prompt.md").exists())
        self.assertIn(result.reason, (self.run.path / "status.log").read_text(encoding="utf-8"))
        self.assertEqual(self.hooks.progress_lines[-1], "S1 integração · ronda 1 · bloqueada")
        agent.assert_called_once()
        reviewer.assert_not_called()

    def test_brief_verdict_escalates_with_brief_reason(self):
        with patch("harness.engine.integration.run_review_round", return_value=("brief", "")):
            result = self.run_loop()

        directory = self.run.path / "S1-integration"
        problems = directory / "rounds" / "1" / "problems.md"
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "S1-integration: the reviewer says the brief is the problem (see {0})".format(problems))
        self.assertEqual((directory / "status").read_text(), "escalated\n")
        self.assertEqual(self.hooks.progress_lines[-1], "S1 integração · ronda 1 · escalada")

    def test_goal_is_snapshotted_before_integrator_runs(self):
        goal = self.run.path / "00-input" / "goal.md"
        goal.write_text("START-GOAL\n", encoding="utf-8")
        patch_path = self.run.path / "01-unit" / "final.patch"
        patch_path.write_text("not a git patch\n", encoding="utf-8")

        def integrator(run, label, directory, prompt_file, out_prefix, *args):
            goal.write_text("LATE-GOAL\n", encoding="utf-8")
            (self.repo / "integrated.txt").write_text("combined\n", encoding="utf-8")
            Path(out_prefix + ".last-message.md").write_text("handoff\n", encoding="utf-8")
            return StepResult(True, "", None)

        def reviewer(run, label, checkout, round_dir, hooks, settings, tier,
                     limits, previous, gate_file, progress):
            Path(round_dir, "problems.md").write_text("review\n", encoding="utf-8")
            Path(round_dir, "verdict").write_text("pass\n", encoding="utf-8")
            return "pass", ""

        with patch("harness.engine.integration.run_agent_step", side_effect=integrator), patch(
            "harness.engine.integration.run_review_round", side_effect=reviewer
        ):
            result = self.run_loop()

        self.assertTrue(result.ok)
        brief = (self.run.path / "S1-integration" / "brief.md").read_text(encoding="utf-8")
        self.assertIn("START-GOAL", brief)
        self.assertNotIn("LATE-GOAL", brief)

    def test_changed_gate_is_noted_before_integration(self):
        current = self.run.path / "00-input" / "units" / "01-unit.md"
        current.write_text("# Unit\n\n```gate\nfalse\n```\n", encoding="utf-8")
        (self.run.path / "01-unit" / "brief.md").write_text(
            "# Unit\n\n```gate\ntrue\n```\n", encoding="utf-8"
        )

        with patch("harness.engine.integration.run_review_round", return_value=("pass", "")), patch(
            "harness.engine.integration.run_agent_step",
            return_value=StepResult(True, "", None),
        ):
            result = self.run_loop()

        self.assertTrue(result.ok)
        status_log = (self.run.path / "status.log").read_text(encoding="utf-8")
        self.assertIn(
            "S1-integration: the gate of 01-unit was changed after it passed",
            status_log,
        )

    def test_missing_brief_stops_before_creating_integration_base(self):
        brief = self.run.path / "00-input" / "units" / "01-unit.md"
        brief.unlink()

        result = self.run_loop()

        self.assertFalse(result.ok)
        self.assertEqual(
            result.reason,
            "S1-integration: 01-unit: the current brief {0} is missing or empty".format(brief),
        )
        self.assertFalse((self.run.path / "S1-integration" / "base").exists())

    def test_missing_or_empty_goal_stops_before_creating_integration_base(self):
        goal = self.run.path / "00-input" / "goal.md"
        for value in (None, ""):
            with self.subTest(value=value):
                if value is None:
                    goal.unlink()
                else:
                    goal.write_text(value, encoding="utf-8")

                result = self.run_loop()

                self.assertFalse(result.ok)
                self.assertEqual(
                    result.reason,
                    "S1-integration: the goal {0} is missing or empty".format(goal),
                )
                self.assertFalse((self.run.path / "S1-integration" / "base").exists())
                goal.write_text("Goal note\n", encoding="utf-8")

    def test_goal_is_in_integrator_and_review_prompts_but_not_unit_prompt(self):
        goal = self.run.path / "00-input" / "goal.md"
        goal.write_text("GOAL-PROMPT-MARKER\n", encoding="utf-8")
        patch_path = self.run.path / "01-unit" / "final.patch"
        patch_path.write_text("not a git patch\n", encoding="utf-8")
        prompts = {}

        def integrator(run, label, directory, prompt_file, out_prefix, *args):
            prompts["integrator"] = Path(prompt_file).read_text(encoding="utf-8")
            (self.repo / "integrated.txt").write_text("combined\n", encoding="utf-8")
            Path(out_prefix + ".last-message.md").write_text("handoff\n", encoding="utf-8")
            return StepResult(True, "", None)

        def reviewer(run, label, checkout, round_dir, hooks, settings, tier,
                     limits, previous, gate_file, progress):
            prompt = hooks.review_prompt(
                Path(round_dir).parent.parent / "brief.md",
                Path(round_dir) / "diff.patch",
                previous,
                1,
                gate_file,
            )
            prompts["review"] = prompt
            Path(round_dir, "review-prompt.md").write_text(prompt, encoding="utf-8")
            Path(round_dir, "problems.md").write_text("review\n", encoding="utf-8")
            Path(round_dir, "verdict").write_text("pass\n", encoding="utf-8")
            return "pass", ""

        with patch("harness.engine.integration.run_agent_step", side_effect=integrator), patch(
            "harness.engine.integration.run_review_round", side_effect=reviewer
        ):
            result = self.run_loop()

        self.assertTrue(result.ok)
        self.assertIn("GOAL-PROMPT-MARKER", prompts["integrator"])
        self.assertIn("GOAL-PROMPT-MARKER", prompts["review"])
        unit_prompt = plan_inputs.implement_prompt(
            "guides", self.run.path / "01-unit" / "brief.md", 1, 0, "", ""
        )
        unit_review_prompt = plan_inputs.review_prompt(
            "guides", self.run.path / "01-unit" / "brief.md", "diff.patch", "", 1, ""
        )
        self.assertNotIn("GOAL-PROMPT-MARKER", unit_prompt)
        self.assertNotIn("GOAL-PROMPT-MARKER", unit_review_prompt)

    def test_integrator_quota_is_returned_with_integration_context(self):
        patch_path = self.run.path / "01-unit" / "final.patch"
        patch_path.write_text("not a git patch\n", encoding="utf-8")
        quota_reason = "S1-integration: usage limit reached. QUOTA: retry tomorrow"
        with patch(
            "harness.engine.integration.run_agent_step",
            return_value=StepResult(False, quota_reason, "retry tomorrow"),
        ) as integrator:
            result = self.run_loop()

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, quota_reason)
        integrator.assert_called_once()
        notes = (self.run.path / "status.log").read_text(encoding="utf-8")
        self.assertIn("S1-integration: apply the diffs", notes)
        self.assertEqual((self.run.path / "S1-integration" / "status").read_text(encoding="utf-8"), "integrating round 1\n")

    def test_gate_failure_runs_integrator_and_retries_gate(self):
        self.hooks.commands = ["test -e ready"]
        prompt_calls = []

        def integrator(run, label, directory, prompt_file, out_prefix, *args):
            prompt_calls.append(Path(prompt_file).read_text(encoding="utf-8"))
            (self.repo / "ready").write_text("yes\n", encoding="utf-8")
            Path(out_prefix + ".last-message.md").write_text("handoff\n", encoding="utf-8")
            return StepResult(True, "", None)

        def reviewer(run, label, checkout, round_dir, hooks, settings, tier,
                     limits, previous, gate_file, progress):
            Path(round_dir, "problems.md").write_text("review\n", encoding="utf-8")
            Path(round_dir, "verdict").write_text("pass\n", encoding="utf-8")
            return "pass", ""

        with patch("harness.engine.integration.run_agent_step", side_effect=integrator), patch(
            "harness.engine.integration.run_review_round", side_effect=reviewer
        ):
            result = self.run_loop()

        self.assertTrue(result.ok)
        self.assertEqual(len(prompt_calls), 1)
        self.assertIn("Each failing command below must pass", prompt_calls[0])
        self.assertIn("Your handoff from the previous round", prompt_calls[0])
        self.assertIn("Each failing command below must pass", (self.run.path / "S1-integration/rounds/1/problems.md").read_text(encoding="utf-8"))
        self.assertTrue((self.run.path / "S1-integration/rounds/2/integrate-prompt.md").is_file())
        self.assertEqual(self.hooks.progress_lines[:4], [
            "S1 integração · ronda 1 · aplicar diffs",
            "S1 integração · ronda 1 · gate FAIL",
            "S1 integração · ronda 2 · integrar",
            "S1 integração · ronda 2 · gate PASS",
        ])

    def _integrator(self, run, label, directory, prompt_file, out_prefix, *args):
        (self.repo / "integrated.txt").write_text(Path(prompt_file).read_text() + "\n", encoding="utf-8")
        Path(out_prefix + ".last-message.md").write_text("handoff\n", encoding="utf-8")
        return StepResult(True, "", None)

    def _reviewer(self, files="none", verdict="back"):
        def review(run, label, checkout, round_dir, hooks, settings, tier,
                   limits, previous, gate_file, progress):
            Path(round_dir, "problems.md").write_text(
                "## What I checked\n- diff\n\n## Problems\n" + files + "\n",
                encoding="utf-8",
            )
            Path(round_dir, "verdict").write_text(verdict + "\n", encoding="utf-8")
            return verdict, ""
        return review

    def test_flaky_gate_passes_on_one_repeat(self):
        self.hooks.commands = [
            "n=$(cat .gate-count 2>/dev/null || echo 0); n=$((n+1)); echo $n >.gate-count; "
            "if [ $n -eq 1 ]; then echo 'FAIL 1 /tmp/a'; exit 1; fi"
        ]
        with patch("harness.engine.integration.run_review_round", return_value=("pass", "")):
            result = self.run_loop()
        self.assertTrue(result.ok)
        notes = (self.run.path / "status.log").read_text(encoding="utf-8")
        self.assertIn("gate was red once and green on repeat (flaky): " + self.hooks.commands[0], notes)
        self.assertTrue((self.run.path / "S1-integration/rounds/1/gate-repeat/gate.md").is_file())

    def test_same_gate_failure_twice_stops_early(self):
        self.hooks.commands = ["echo 'ERROR test_a.py:123'; exit 1"]
        with patch("harness.engine.integration.run_agent_step", side_effect=self._integrator):
            result = self.run_loop()
        self.assertFalse(result.ok)
        self.assertIn("gate fails the same way in two rounds in a row", result.reason)
        self.assertEqual((self.run.path / "S1-integration/status").read_text(), "escalated\n")

    def test_different_gate_failures_do_not_stop_as_repeated(self):
        class TwoGateRounds(Limits):
            max_gate_rounds = 2
        self.hooks.commands = [
            "n=$(cat .gate-count 2>/dev/null || echo 0); n=$((n+1)); echo $n >.gate-count; "
            "if [ $n -le 2 ]; then echo 'ERROR test_a.py'; else echo 'ERROR test_b.py'; fi; exit 1"
        ]
        with patch("harness.engine.integration.run_agent_step", side_effect=self._integrator):
            result = run_integration(
                self.run, self.repo, 1, ["01-unit"], hooks=self.hooks,
                settings=self.run.settings, tier="fast", limits=TwoGateRounds(),
                goal_path=self.run.path / "00-input" / "goal.md",
                brief_check=plan_inputs.check_briefs, brief_differs=plan_inputs.brief_differs,
                gate_differs=plan_inputs.gate_differs,
            )
        self.assertFalse(result.ok)
        self.assertIn("gate still fails after 2 rounds", result.reason)
        self.assertNotIn("same way", result.reason)

    def test_same_review_files_twice_stops(self):
        class ThreeRounds(Limits):
            max_rounds = 3
        with patch("harness.engine.integration.run_agent_step", side_effect=self._integrator), patch(
            "harness.engine.integration.run_review_round", side_effect=self._reviewer("- Fix `src/a.py`")
        ):
            result = run_integration(
                self.run, self.repo, 1, ["01-unit"], hooks=self.hooks,
                settings=self.run.settings, tier="fast", limits=ThreeRounds(),
                goal_path=self.run.path / "00-input" / "goal.md",
                brief_check=plan_inputs.check_briefs, brief_differs=plan_inputs.brief_differs,
                gate_differs=plan_inputs.gate_differs,
            )
        self.assertFalse(result.ok)
        self.assertIn("reviewer sent the unit back twice for the same files (src/a.py)", result.reason)

    def test_different_review_files_do_not_stop_as_repeated(self):
        class TwoRounds(Limits):
            max_rounds = 2
        calls = []
        def changing_reviewer(*args):
            calls.append(len(calls))
            files = "- Fix `src/a.py`" if len(calls) == 1 else "- Fix `src/b.py`"
            return self._reviewer(files)(*args)
        with patch("harness.engine.integration.run_agent_step", side_effect=self._integrator), patch(
            "harness.engine.integration.run_review_round", side_effect=changing_reviewer
        ):
            result = run_integration(
                self.run, self.repo, 1, ["01-unit"], hooks=self.hooks,
                settings=self.run.settings, tier="fast", limits=TwoRounds(),
                goal_path=self.run.path / "00-input" / "goal.md",
                brief_check=plan_inputs.check_briefs, brief_differs=plan_inputs.brief_differs,
                gate_differs=plan_inputs.gate_differs,
            )
        self.assertFalse(result.ok)
        self.assertIn("round cap 2 reached", result.reason)
        self.assertNotIn("same files", result.reason)


if __name__ == "__main__":
    unittest.main()

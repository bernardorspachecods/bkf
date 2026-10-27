import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from harness.engine.run import RunError
import plan_inputs


class PlanInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_parse_plan_comments_relative_paths_and_unit_names(self):
        brief = self.write("inputs/one.md", "brief\n")
        plan = self.write("inputs/plan.txt", "# ignored\n\n one.md # inline comment\n")
        self.assertEqual(plan_inputs.parse_plan(plan), [[("one", str(brief))]])

    def test_parse_plan_keeps_multiple_briefs_in_one_group_step(self):
        one = self.write("one.md", "one\n")
        two = self.write("two.md", "two\n")
        plan = self.write("plan.txt", "one.md two.md\n")
        self.assertEqual(plan_inputs.parse_plan(plan), [[("one", str(one)), ("two", str(two))]])

    def test_parse_plan_rejects_missing_empty_bad_name_and_empty_plan(self):
        plan = self.write("plan.txt", "missing.md\n")
        with self.assertRaisesRegex(RunError, "^missing or empty unit brief: missing.md$"):
            plan_inputs.parse_plan(plan)
        self.write("empty.md", "")
        self.write("plan.txt", "empty.md\n")
        with self.assertRaisesRegex(RunError, "^missing or empty unit brief: empty.md$"):
            plan_inputs.parse_plan(plan)
        self.write("bad name.md", "brief\n")
        self.write("plan.txt", "bad name.md\n")
        with self.assertRaisesRegex(RunError, "^missing or empty unit brief: bad$"):
            plan_inputs.parse_plan(plan)
        self.write("bad@name.md", "brief\n")
        self.write("plan.txt", "bad@name.md\n")
        with self.assertRaisesRegex(RunError, r"^bad unit name \(from the file name\): bad@name.md$"):
            plan_inputs.parse_plan(plan)
        self.write("plan.txt", " # only a comment\n\n")
        with self.assertRaisesRegex(RunError, "^plan.txt has no step$"):
            plan_inputs.parse_plan(plan)

    def test_write_inputs_copies_goal_briefs_and_order(self):
        goal = self.write("goal.md", "goal\n")
        first = self.write("one.md", "one brief\n")
        second = self.write("two.md", "two brief\n")
        run = self.root / "run"
        plan_inputs.write_inputs(run, goal, [[("first", first)], [("second", second)]])
        self.assertEqual((run / "00-input" / "goal.md").read_text(), "goal\n")
        self.assertEqual((run / "00-input" / "order").read_text(), "01-first\n02-second\n")
        self.assertEqual((run / "00-input" / "units" / "01-first.md").read_text(), "one brief\n")
        self.assertEqual((run / "00-input" / "units" / "02-second.md").read_text(), "two brief\n")

    def test_gate_commands_reads_two_blocks_ignores_untagged_and_deduplicates(self):
        brief = self.write(
            "brief.md",
            """```text
ignored command
```
```gate
  alpha  

 # skip this
beta
```
```gate
alpha
gamma
```
""",
        )
        self.assertEqual(plan_inputs.gate_commands([brief]), ["alpha", "beta", "gamma"])

    def test_gates_command_for_plan_formats_commands_and_missing_gate_status(self):
        gated = self.write("gated.md", "```gate\ncheck\n\n# comment\nother\n```\n")
        plain = self.write("plain.md", "No gate\n")
        plan = self.write("plan.txt", "gated.md\nplain.md\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = plan_inputs.gates_command([str(plan)])
        self.assertEqual(status, 1)
        self.assertEqual(output.getvalue(), "gated\n  $ check\n  $ other\n\nplain\n  NO GATE: only a reviewer checks this unit\n\n")

    def test_gates_command_for_run(self):
        runs = self.root / "runs"
        run = runs / "sample"
        (run / "00-input" / "units").mkdir(parents=True)
        (run / "00-input" / "order").write_text("01-alpha\n02-beta\n")
        (run / "00-input" / "units" / "01-alpha.md").write_text("```gate\ncheck\n```\n")
        (run / "00-input" / "units" / "02-beta.md").write_text("No gate\n")
        output = io.StringIO()
        with patch.dict(os.environ, {"PLAN_RUNS_DIR": str(runs)}):
            with contextlib.redirect_stdout(output):
                status = plan_inputs.gates_command(["sample"])
        self.assertEqual(status, 1)
        self.assertEqual(output.getvalue(), "01-alpha\n  $ check\n\n02-beta\n  NO GATE: only a reviewer checks this unit\n\n")

    def test_brief_helpers_detect_current_difference_and_preserve_text(self):
        run = self.root / "run"
        current = run / "00-input" / "units" / "01-unit.md"
        received = run / "01-unit" / "brief.md"
        current.parent.mkdir(parents=True)
        received.parent.mkdir(parents=True)
        current.write_text("Current brief\n```gate\nnew-check\n```\n")
        received.write_text("Received brief\n```gate\nold-check\n```\n")
        self.assertEqual(plan_inputs.brief_current(run, "01-unit"), str(current))
        self.assertTrue(plan_inputs.brief_differs(run, "01-unit"))
        self.assertTrue(plan_inputs.gate_differs(run, "01-unit"))
        self.assertEqual(
            plan_inputs.print_unit_brief(run, "01-unit", "####"),
            "Current brief\n```gate\nnew-check\n```\n\n\n#### Brief received by the implementer (differs from the current one)\n\n"
            "The current brief defines the intent. The copy below is what the implementer received. Judge against the current brief. "
            "If the unit meets the copy but not the current brief, say so: the deviation comes from the change of brief, not from the unit. "
            "If it fails both, the unit failed.\n\nReceived brief\n```gate\nold-check\n```\n",
        )

    def test_implement_prompts_match_bash_for_first_resumed_and_returned_rounds(self):
        brief = self.write("brief.md", "Do the work.\n")
        gate_brief = self.write("gated.md", "Do the work.\n```gate\ncheck\n```\n")
        expected_base = (
            "Do the work.\n\n\n---\n## Role\nOpen and follow the role guide: /guides/plan-implementation.md (read-only). "
            "It says how to work inside the brief, what to verify and what the handoff holds.\n\n## Rules\n"
            "- The current directory is the repository: do the work here.\n"
            "- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n"
            "- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.\n"
        )
        blocked_sentence = "\nIf the brief cannot be followed because a command cannot pass at this step or a rule forbids what the result requires, make your last line `BLOCKED: <the sentence of the brief that conflicts and what you saw>` instead of repeating the attempt.\n"
        self.assertEqual(plan_inputs.implement_prompt("/guides", brief, 1, False, "", ""), expected_base + blocked_sentence)
        self.assertNotIn(".plan-porteiro/ponte", plan_inputs.implement_prompt("/guides", brief, 1, False, "", ""))
        self.assertEqual(
            plan_inputs.implement_prompt("/guides", gate_brief, 1, False, "", ""),
            expected_base.replace("Do the work.\n", "Do the work.\n```gate\ncheck\n```\n")
            + "- The brief has a `gate`. After you finish, the script runs those commands itself and sends the work back, without a review, if any fails. Run them yourself first when you can.\n"
            + blocked_sentence,
        )
        self.assertEqual(
            plan_inputs.implement_prompt("/guides", brief, 1, True, "", ""),
            expected_base + "\nAn earlier attempt at this unit was stopped. The checkout may already hold its work. Judge it against the brief, keep what is right and fix the rest.\n" + blocked_sentence,
        )
        problems = self.write("problems.md", "Fix this.\n")
        handoff = self.write("handoff.md", "I changed it.\n")
        self.assertEqual(
            plan_inputs.implement_prompt("/guides", brief, 2, False, problems, handoff),
            expected_base + "\nThe script's gate or a reviewer sent your work back. The work from the earlier round is in the checkout. Fix the problems below and only those, keeping what was fine, and verify again.\n\nProblems from the gate or the review:\n\nFix this.\n\n\nYour handoff from the previous round, for you to resume from:\n\nI changed it.\n\n" + blocked_sentence,
        )

    def test_review_prompt_matches_bash(self):
        brief = self.write("brief.md", "Do the work.\n")
        previous = self.write("problems.md", "Fix it.\n")
        expected = (
            "# Review\n\n## The brief\n\nDo the work.\n\n\n---\n## Inputs (read-only)\n- The diff, new files included: /patch\n"
            "- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.\n"
            "- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.\n"
            "- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.\n"
            "\n## Role\nOpen and follow the role guide: /guides/plan-review.md (read-only). You are not the author of the work.\n"
            "\nThe problems you listed in the previous round are below. The work was corrected; check whether they are gone.\n\nFix it.\n\n"
            "\n---\nYour final message is the review, and nothing else. Begin it with a section headed \"## What I checked\": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:\n"
            "VERDICT: pass\nVERDICT: back\nVERDICT: escalate\n"
            'Your previous attempt left no usable review (no "## What I checked" section, or no verdict line). Follow the form this time.\n'
            "The reviewer may end with `VERDICT: brief` when the diff is fine but the brief asks for something contradictory or impossible.\n"
        )
        self.assertEqual(plan_inputs.review_prompt("/guides", brief, "/patch", previous, 2, "/gate.md"), expected)

    def test_blocked_and_brief_sentences_are_in_unit_and_integration_prompts(self):
        brief = self.write("brief.md", "Do the work.\n")
        blocked = "make your last line `BLOCKED: <the sentence of the brief that conflicts and what you saw>` instead of repeating the attempt."
        brief_verdict = "The reviewer may end with `VERDICT: brief` when the diff is fine but the brief asks for something contradictory or impossible."

        unit_implement = plan_inputs.implement_prompt("/guides", brief, 1, False, "", "")
        integration_implement = plan_inputs.integrate_prompt("/guides", brief, "", "", "")
        unit_review = plan_inputs.review_prompt("/guides", brief, "/patch", "", 1, "")
        integration_review = plan_inputs.integration_review_prompt("/guides", brief, "/patch", "", 1, "")

        self.assertIn(blocked, unit_implement)
        self.assertIn(blocked, integration_implement)
        self.assertIn(brief_verdict, unit_review)
        self.assertIn(brief_verdict, integration_review)

    def test_report_prompt_matches_bash(self):
        run = self.root / "run"
        units = run / "00-input" / "units"
        units.mkdir(parents=True)
        (run / "00-input" / "goal.md").write_text("Reach the goal.\n")
        (run / "00-input" / "order").write_text("01-unit\n")
        (units / "01-unit.md").write_text("Do the work.\n")
        expected = (
            "# Final review of the plan\n\n## The goal\n\nReach the goal.\n\n\n## The unit briefs, in order\n"
            "\n### 01-unit\n\nDo the work.\n\n\n## Inputs (read-only)\n- The diff of the whole plan, new files included: {0}/cumulative.patch\n"
            "- The reviews of each unit and of each parallel group: {0}/01-unit/rounds/*/problems.md {0}/S*-integration/rounds/*/problems.md\n"
            "- The repository is your current directory. Open it read-only. Do not change anything. Do not open the handoffs.\n"
            "\n## Role\nOpen and follow the role guide: /guides/plan-review.md (read-only), section \"The final review\". You are not the author of the work.\n"
            "\n---\nYour final message is the report, and nothing else.\n"
        ).format(run)
        self.assertEqual(plan_inputs.report_prompt(run, "/guides"), expected)

    def test_guides_path_uses_override_or_the_skill_roles_folder(self):
        self.assertEqual(plan_inputs.guides_path({"PLAN_GUIDES": "/custom"}), "/custom")
        self.assertEqual(
            plan_inputs.guides_path({}),
            str(Path(plan_inputs.__file__).resolve().parents[1] / "roles"),
        )


if __name__ == "__main__":
    unittest.main()

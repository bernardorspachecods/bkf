import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

from harness.engine.run import RunError
from plan_test_support import PlanRunFixture, _WORKFLOW


class PlanWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PlanRunFixture(self)

    def tearDown(self):
        self.fixture.close()

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = self.fixture.call(*args)
        return code, output.getvalue(), errors.getvalue()

    def test_one_unit_runs_to_final_report(self):
        self.fixture.add_brief("unit")
        plan = self.fixture.write_plan("unit.md")
        code, out, err = self.call("start", "--in-place", "sample", str(self.fixture.goal), str(plan))
        run = self.fixture.runs / "sample"

        self.assertEqual(code, 0)
        self.assertEqual(out, "Run folder: {0}\nREADY: {0}/report.md\nSee {0}/status.log\n".format(run))
        self.assertIn("[plan] S1 início · unidade 01-unit", err)
        for path in (
            "00-input/goal.md", "00-input/units/01-unit.md", "00-input/order",
            "plan-base/base", "01-unit/brief.md", "01-unit/base", "01-unit/final.patch",
            "01-unit/rounds/1/implement-prompt.md", "01-unit/rounds/1/diff.patch",
            "report-prompt.md", "report.md", "state-after-S1", "cumulative.patch", "status.log",
        ):
            self.assertTrue((run / path).is_file(), path)
        self.assertEqual((run / "00-input/order").read_text(), "01-unit\n")
        self.assertEqual((run / "01-unit/status").read_text(), "passed\n")
        self.assertTrue((run / ".done-S1").is_file())
        self.assertTrue((run / ".done-report").is_file())
        status_events = [line.split("\t", 1)[1] for line in (run / "status.log").read_text().splitlines()[1:]]
        self.assertEqual(status_events, [
            "start sample (gpt-6-luna xhigh, review xhigh, max 3 rounds, 1 step(s), 1 unit(s), repo {0})".format(self.fixture.repo.resolve()),
            "unit 01-unit has no gate: only a reviewer checks it",
            "no .plan-run.json at HEAD: the bridge will run only gate commands unless an untracked copy is in the checkout; commit it so changes to it are reviewed like code",
            "start step 1: 01-unit (gpt-6-luna xhigh)",
            "01-unit round 1: implement",
            "01-unit round 1: review",
            "01-unit: round 1: verdict pass",
            "done step 1",
            "start final review (gpt-6-luna xhigh)",
            "done final review",
            "READY: report at {0}/report.md".format(run),
        ])
        self.assertEqual((run / "report.md").read_text(), "Final report\n")
        self.assertIn("diff --git a/seed.txt b/seed.txt", (run / "cumulative.patch").read_text())
        self.assertEqual((self.fixture.state / "review-efforts").read_text(), "model_reasoning_effort=xhigh\n")

    def test_second_unit_patch_is_based_on_first_units_state(self):
        self.fixture.add_brief("first")
        self.fixture.add_brief("second")
        plan = self.fixture.write_plan("first.md", "second.md")
        self.fixture.env["FAKE_IMPLS"] = json.dumps({
            "1": "echo first >> seed.txt; echo first-created > first.txt",
            "2": "test -f first.txt && echo second > second.txt",
        })

        code, _, _ = self.call("start", "sequence", str(self.fixture.goal), str(plan))
        run = self.fixture.runs / "sequence"
        self.assertEqual(code, 0)
        patch = (run / "02-second/rounds/1/diff.patch").read_text()
        self.assertIn("second.txt", patch)
        self.assertNotIn("first-created", patch)
        self.assertNotIn("first.txt", patch)
        self.assertEqual((run / "state-after-S1").read_text(), (run / "02-second/base").read_text())

    def test_failing_gate_stops_before_review(self):
        self.fixture.add_brief("unit", "## Result\nChange it.\n\n```gate\nfalse\n```\n")
        plan = self.fixture.write_plan("unit.md")
        self.fixture.env["PLAN_MAX_GATE_ROUNDS"] = "1"
        code, out, _ = self.call("start", "red", str(self.fixture.goal), str(plan))
        run = self.fixture.runs / "red"

        self.assertEqual(code, 1)
        self.assertIn("STOPPED at step 1 (01-unit): 01-unit: the gate still fails after 1 rounds", out)
        self.assertFalse((self.fixture.state / "reviews").exists())
        self.assertEqual((run / "01-unit/status").read_text(), "escalated\n")
        self.assertIn("exit code: 1", (run / "01-unit/rounds/1/gate.md").read_text())

    def test_pause_and_resume_continues_to_report(self):
        self.fixture.add_brief("unit")
        plan = self.fixture.write_plan("unit.md")
        code, out, _ = self.call("start", "-p", "each", "paused", str(self.fixture.goal), str(plan))
        run = self.fixture.runs / "paused"
        self.assertEqual(code, 3)
        self.assertIn("PAUSED after step 1 (01-unit).", out)
        self.assertTrue((run / ".paused-S1").exists())

        code, out, _ = self.call("resume", "-p", "none", "paused")
        self.assertEqual(code, 0)
        self.assertIn("READY:", out)
        self.assertEqual((self.fixture.state / "implementations").read_text(), "1")

    def test_missing_current_brief_stops_before_final_review(self):
        self.fixture.add_brief("unit")
        plan = self.fixture.write_plan("unit.md")
        self.fixture.env["FAKE_REMOVE_BRIEF_ON_REVIEW"] = str(self.fixture.runs / "briefs/00-input/units/01-unit.md")
        code, out, _ = self.call("start", "briefs", str(self.fixture.goal), str(plan))

        self.assertEqual(code, 1)
        self.assertIn("STOPPED at the final review: 01-unit: the current brief", out)
        run = self.fixture.runs / "briefs"
        self.assertFalse((run / "report.md").exists())
        self.assertEqual((self.fixture.state / "reviews").read_text(), "1")

    def test_several_briefs_on_one_line_run_through_group_integration(self):
        self.fixture.add_brief("one")
        self.fixture.add_brief("two")
        plan = self.fixture.write_plan("one.md two.md")
        code, out, _ = self.call("start", "group", str(self.fixture.goal), str(plan))
        run = self.fixture.runs / "group"
        self.assertEqual(code, 0)
        self.assertIn("READY:", out)
        self.assertEqual((run / "00-input/order").read_text(), "01-one 02-two\n")
        self.assertTrue((run / ".group-ready-S1").exists())
        self.assertTrue((run / ".done-01-one").exists())
        self.assertTrue((run / ".done-02-two").exists())
        self.assertTrue((run / ".done-S1-integration").exists())
        self.assertFalse((run / "worktrees").exists())

    def test_group_resume_preserves_unit_diff_base(self):
        self.fixture.add_brief("one")
        self.fixture.add_brief("two")
        plan = self.fixture.write_plan("one.md two.md")
        bases = []
        attempts = {}

        def run_unit_loop(_run, unit, checkout, **kwargs):
            if unit == "01-one":
                base = kwargs["base_from"].read_text(encoding="utf-8")
                bases.append(base)
                attempts[unit] = attempts.get(unit, 0) + 1
                if attempts[unit] == 1:
                    (checkout / "failed-attempt.txt").write_text("keep in diff\n", encoding="utf-8")
                    return SimpleNamespace(ok=False, reason="first attempt failed")
            return SimpleNamespace(ok=True, reason="")

        from harness.engine import pipeline
        workflow = pipeline._load_workflow(_WORKFLOW)
        with patch.dict(workflow.steps.__func__.__globals__, {"run_unit_loop": run_unit_loop}), \
                patch("harness.engine.pipeline._load_workflow", return_value=workflow):
            code, out, _ = self.call("start", "group-resume", str(self.fixture.goal), str(plan))
            self.assertEqual(code, 1)
            self.assertIn("first attempt failed", out)
            code, out, _ = self.call("resume", "group-resume")

        self.assertEqual(code, 0)
        self.assertIn("READY:", out)
        self.assertEqual(len(bases), 2)
        self.assertEqual(bases[0], bases[1])

    def test_start_refuses_brief_lint_errors_unless_allowed(self):
        self.fixture.add_brief(
            "unit", "## Criteria\n- The handoff proves it worked.\n## Gate\n```gate\necho ok\n```\n"
        )
        plan = self.fixture.write_plan("unit.md")
        code, _, errors = self.call("start", "lint", str(self.fixture.goal), str(plan))
        self.assertEqual(code, 1)
        self.assertIn("brief lint found 1 error(s)", errors)
        self.assertIn("unit: Criteria must not use the handoff as proof", errors)
        from harness.engine.pipeline import _load_workflow
        workflow = _load_workflow(_WORKFLOW)
        with patch.dict("os.environ", {"PLAN_ALLOW_LINT_ERRORS": "1"}):
            workflow.validate_start([str(self.fixture.goal), str(plan)])

    def test_resume_refuses_a_corrected_brief_that_has_a_lint_error(self):
        from harness.engine.pipeline import _load_workflow
        workflow = _load_workflow(_WORKFLOW)
        run = self.fixture.root / "run"
        units = run / "00-input" / "units"
        units.mkdir(parents=True)
        (run / "00-input" / "order").write_text("01-unit\n", encoding="utf-8")
        (units / "01-unit.md").write_text(
            "## Criteria\n- The handoff proves it worked.\n", encoding="utf-8"
        )
        run_dir = mock.Mock(path=run, checkout=str(self.fixture.root))
        with self.assertRaises(RunError) as error:
            workflow.validate_resume(run_dir)
        self.assertIn("01-unit: Criteria must not use the handoff as proof", str(error.exception))
        with patch.dict("os.environ", {"PLAN_ALLOW_LINT_ERRORS": "1"}):
            workflow.validate_resume(run_dir)
        (run / ".done-01-unit").touch()
        workflow.validate_resume(run_dir)

    def test_validate_start_messages(self):
        self.fixture.add_brief("unit")
        plan = self.fixture.write_plan("unit.md")
        empty_goal = self.fixture.root / "empty-goal.md"
        empty_goal.write_text("", encoding="utf-8")
        empty_plan = self.fixture.root / "empty-plan.txt"
        empty_plan.write_text("", encoding="utf-8")
        cases = (
            (("start", "missing-goal", str(self.fixture.root / "missing.md"), str(plan)), "missing or empty goal:"),
            (("start", "empty-goal", str(empty_goal), str(plan)), "missing or empty goal:"),
            (("start", "missing-plan", str(self.fixture.goal), str(self.fixture.root / "missing.txt")), "missing or empty plan:"),
            (("start", "empty-plan", str(self.fixture.goal), str(empty_plan)), "missing or empty plan:"),
        )
        for args, expected in cases:
            with self.subTest(expected=expected):
                code, _, errors = self.call(*args)
                self.assertEqual(code, 1)
                self.assertIn(expected, errors)
        with patch.dict("os.environ", {"PATH": ""}):
            with self.assertRaises(RunError) as error:
                from harness.engine.pipeline import _load_workflow
                workflow = _load_workflow(_WORKFLOW)
                workflow.validate_start([str(self.fixture.goal), str(plan)])
        self.assertIn("codex not found", str(error.exception))
        environment = dict(self.fixture.env)
        environment["PLAN_GUIDES"] = str(self.fixture.root / "missing-guides")
        with patch.dict("os.environ", environment):
            with self.assertRaises(RunError) as error:
                from harness.engine.pipeline import _load_workflow
                workflow = _load_workflow(_WORKFLOW)
                workflow.validate_start([str(self.fixture.goal), str(plan)])
        self.assertIn("no role guides at {0} (set PLAN_GUIDES)".format(environment["PLAN_GUIDES"]), str(error.exception))


if __name__ == "__main__":
    unittest.main()

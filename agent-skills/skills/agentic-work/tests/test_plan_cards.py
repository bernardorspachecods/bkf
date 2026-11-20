"""Task cards of plan runs: the run's card, and one card per unit under it, through the `bkf` shim."""
import contextlib
import io
import shutil
import unittest
from pathlib import Path

from plan_test_support import PlanRunFixture


class UnitEndedWithoutACardTests(unittest.TestCase):
    def test_a_unit_that_ended_before_it_started_gets_no_card(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        import plan_cards

        with tempfile.TemporaryDirectory() as temp:
            run = SimpleNamespace(path=Path(temp) / "run", repo=temp, name="run")
            run.path.mkdir()
            with patch.object(plan_cards, "_bkf", return_value="") as bkf:
                plan_cards.unit_ended(run, "01-unit", "blocked", "premise failed")
            bkf.assert_not_called()
            self.assertFalse((run.path / "01-unit" / "task").exists())


class PlanCardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PlanRunFixture(self)
        self.addCleanup(self.fixture.close)
        self.run = self.fixture.runs / "sample"

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = self.fixture.call(*args)
        return code, output.getvalue(), errors.getvalue()

    def start(self, name, *options, plan_lines=("unit.md",)):
        plan = self.fixture.write_plan(*plan_lines)
        return self.call("start", *options, name, str(self.fixture.goal), str(plan))

    def cards(self):
        return {card["title"]: card for card in self.fixture.cards()}

    def test_one_unit_run_to_ready_has_a_run_card_waiting_for_its_owner_and_no_unit_card(self):
        self.fixture.add_brief("unit")
        code, out, err = self.start("sample")

        self.assertEqual(code, 0, err)
        cards = self.cards()
        run_card = cards["plan sample"]
        self.assertEqual((run_card["status"], run_card["kind"]), ("working", "unit"))
        self.assertEqual(run_card["attention"]["reason"], "paused")
        self.assertIsNone(run_card["parent"])
        tree = str(self.run / "tree")
        self.assertEqual(run_card["worktree"], {"path": tree, "branch": "plan/sample", "head": None})
        self.assertEqual(run_card["run_dir"], str(self.run))
        self.assertEqual((self.run / "task").read_text(encoding="utf-8"), run_card["id"] + "\n")
        # The passed unit's card is closed: its id is still in its folder, but no card carries it any more.
        unit_id = (self.run / "01-unit" / "task").read_text(encoding="utf-8").strip()
        self.assertNotIn(unit_id, [card["id"] for card in self.fixture.cards()])
        self.assertNotIn("01-unit", cards)
        self.assertNotIn("task card", err)

    def test_a_takeover_leaves_the_unit_escalated_and_the_run_stopped(self):
        self.fixture.add_brief("unit")
        self.fixture.env["FAKE_REVIEW_VERDICTS"] = '["back"]'
        code, _, _ = self.start("takeover", "--takeover-after", "1")

        self.assertEqual(code, 1)
        cards = self.cards()
        self.assertEqual(cards["01-unit"]["attention"]["reason"], "escalated")
        self.assertEqual(cards["01-unit"]["attention"]["note"], "takeover")
        self.assertEqual(cards["01-unit"]["status"], "working")
        self.assertEqual(cards["plan takeover"]["attention"]["note"], "stopped")

    def test_a_reviewer_escalation_is_an_escalated_unit(self):
        self.fixture.add_brief("unit")
        self.fixture.env["FAKE_REVIEW_VERDICTS"] = '["escalate"]'
        code, _, _ = self.start("escalated")

        self.assertEqual(code, 1)
        self.assertEqual(self.cards()["01-unit"]["attention"]["note"], "escalated")

    def test_a_gate_that_fails_the_same_way_stops_with_an_escalated_unit(self):
        self.fixture.add_brief("unit", "## Result\nImplement it.\n\n```gate\nfalse\n```\n")
        code, _, _ = self.start("gate")

        self.assertEqual(code, 1)
        cards = self.cards()
        self.assertEqual(cards["01-unit"]["attention"]["note"], "escalated")
        self.assertEqual(cards["plan gate"]["attention"]["note"], "stopped")

    def test_a_failed_unit_is_failed_and_started_again_on_resume(self):
        self.fixture.add_brief("unit")
        self.fixture.env["FAKE_IMPLS"] = '{"1": "exit 3"}'
        code, _, _ = self.start("failing")

        self.assertEqual(code, 1)
        cards = self.cards()
        unit_card = cards["01-unit"]
        self.assertEqual(unit_card["status"], "failed")
        self.assertIn("implementer exit=3", unit_card["note"])
        self.assertEqual(unit_card["parent"], cards["plan failing"]["id"])
        self.assertEqual(unit_card["run_dir"], str(self.fixture.runs / "failing" / "01-unit"))
        self.assertEqual(cards["plan failing"]["attention"]["note"], "stopped")

        self.fixture.env["FAKE_IMPLS"] = "{}"
        code, _, err = self.call("resume", "failing")

        self.assertEqual(code, 0, err)
        cards = self.cards()
        self.assertNotIn("01-unit", cards)
        run_attention = cards["plan failing"]["attention"]
        self.assertEqual((cards["plan failing"]["status"], run_attention["reason"]), ("working", "paused"))

    def test_a_pause_is_an_attention_that_resume_clears(self):
        self.fixture.add_brief("unit")
        code, _, _ = self.start("paused", "-p", "each")

        self.assertEqual(code, 3)
        self.assertEqual(self.cards()["plan paused"]["attention"]["reason"], "paused")
        code, _, err = self.call("resume", "-p", "none", "paused")

        self.assertEqual(code, 0, err)
        cards = self.cards()
        self.assertEqual(cards["plan paused"]["attention"]["reason"], "paused")
        self.assertEqual(cards["plan paused"]["status"], "working")

    def test_a_group_run_has_one_card_per_unit_without_a_branch(self):
        self.fixture.add_brief("a", "## Result\nCreate A.\n\nUNIT-A-REVIEW-MARKER\n")
        self.fixture.add_brief("b", "## Result\nCreate B.\n\nUNIT-B-REVIEW-MARKER\n")
        self.fixture.env["FAKE_IMPLS_BY_PROMPT"] = '{"UNIT-A-REVIEW-MARKER":"echo A > a.txt","UNIT-B-REVIEW-MARKER":"echo B > b.txt"}'
        code, _, err = self.start("group", plan_lines=("a.md b.md",))

        self.assertEqual(code, 0, err)
        cards = self.cards()
        self.assertEqual(sorted(cards), ["plan group"])
        self.assertEqual(cards["plan group"]["attention"]["reason"], "paused")

    def test_finish_closes_the_cards_and_the_records_keep_no_task_files(self):
        self.fixture.add_brief("unit")
        self.assertEqual(self.start("kept")[0], 0)
        self.assertEqual(sorted(card["title"] for card in self.fixture.cards()), ["plan kept"])

        code, _, err = self.call("finish", "kept")

        self.assertEqual(code, 0, err)
        self.assertEqual(self.fixture.cards(), [])
        record = self.fixture.repo / "records" / "plans" / "kept"
        self.assertTrue((record / "report.md").is_file())
        self.assertFalse((record / "task").exists())
        self.assertFalse((record / "01-unit" / "task").exists())

    def test_discard_deletes_the_run_card_and_its_unit_cards(self):
        self.fixture.add_brief("unit")
        self.assertEqual(self.start("dropped")[0], 0)
        self.assertEqual(len(self.fixture.cards()), 1)

        code, _, err = self.call("finish", "--discard", "dropped")

        self.assertEqual(code, 0, err)
        self.assertEqual(self.fixture.cards(), [])
        self.assertFalse(self.run.exists())

    def test_a_refused_start_leaves_no_cards(self):
        self.fixture.add_brief("unit")
        (self.fixture.repo / "seed.txt").write_text("changed\n", encoding="utf-8")
        code, _, err = self.start("refused")

        self.assertEqual(code, 1)
        self.assertIn("uncommitted", err)
        self.assertEqual(self.fixture.cards(), [])

    def test_without_bkf_the_run_result_is_the_same_and_one_warning_is_printed(self):
        self.fixture.add_brief("unit")
        (self.fixture.bin / "bkf").unlink()
        self.fixture.env["PATH"] = str(self.fixture.bin) + ":/usr/bin:/bin"
        if shutil.which("bkf", path=self.fixture.env["PATH"]) is not None:
            self.skipTest("a bkf is installed in the system folders")
        code, out, err = self.start("nobkf")

        self.assertEqual(code, 0, err)
        run = self.fixture.runs / "nobkf"
        self.assertEqual(out, "Run folder: {0}\nREADY: {0}/report.md\nSee {0}/status.log\n".format(run))
        self.assertEqual(err.count("plan: task card:"), 2)
        self.assertIn("bkf is not available", err)
        self.assertEqual((run / "01-unit" / "status").read_text(), "passed\n")
        self.assertIn("READY: report at", (run / "status.log").read_text(encoding="utf-8"))

    def test_a_failing_bkf_prints_one_warning_per_call_and_the_run_goes_on(self):
        self.fixture.add_brief("unit")
        shim = self.fixture.bin / "bkf"
        shim.write_text("#!/bin/sh\necho 'bkf task: refused' >&2\nexit 1\n", encoding="utf-8")
        code, out, err = self.start("refusing")

        self.assertEqual(code, 0, err)
        self.assertIn("READY:", out)
        self.assertEqual(err.count("plan: task card:"), 2)
        self.assertEqual((self.fixture.runs / "refusing" / "01-unit" / "status").read_text(), "passed\n")


if __name__ == "__main__":
    unittest.main()

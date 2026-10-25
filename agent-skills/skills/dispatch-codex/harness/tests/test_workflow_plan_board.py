"""Board and record behavior for sequential plan runs."""
import contextlib
import io
import unittest
from unittest.mock import patch

from harness.engine.run import RunDir, Settings, RunError
from harness.engine.pipeline import _load_workflow
from plan_test_support import PlanRunFixture, _WORKFLOW


WORKFLOW = _load_workflow(_WORKFLOW)


class PlanBoardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PlanRunFixture(self)
        self.run_path = self.fixture.runs / "board"
        self.run_path.mkdir(parents=True)
        (self.run_path / "00-input" / "units").mkdir(parents=True)
        (self.run_path / "00-input" / "order").write_text("01-alpha\n02-beta\n", encoding="utf-8")
        self.run = RunDir(self.run_path, str(self.fixture.repo.resolve()), Settings("m", "e", ""), "")
        (self.run_path / "status.log").write_text(
            "time\tevent\n2026-10-23T09:10:00\tstart board (m e)\n", encoding="utf-8"
        )

    def tearDown(self):
        self.fixture.close()

    def ctx(self):
        from harness.engine.workflow import Context
        return Context(self.run, WORKFLOW)

    def unit(self, unit, status="implementing round 1", rounds=1, verdict=None, gate=None):
        directory = self.run_path / unit
        round_path = directory / "rounds" / str(rounds)
        round_path.mkdir(parents=True, exist_ok=True)
        (directory / "status").write_text(status + "\n", encoding="utf-8")
        if verdict:
            (round_path / "verdict").write_text(verdict + "\n", encoding="utf-8")
        if gate:
            (round_path / "gate.md").write_text(gate, encoding="utf-8")

    def board(self):
        with patch("plan_board._now_time", return_value="10:11"):
            return WORKFLOW.board(self.ctx())

    def assert_board(self, alpha, beta, final="  ○ Revisão final  pendente\n"):
        expected = (
            "Plano board · 2 unidades · início 09:10 → agora 10:11\n\n"
            "Passo 1\n" + alpha + "\n"
            "Passo 2\n" + beta + "\n"
            + final
        )
        self.assertEqual(self.board(), expected)

    def test_board_pending_rows_and_padding(self):
        expected = (
            "Plano board · 2 unidades · início 09:10 → agora 10:11\n\n"
            "Passo 1\n  ○ 01-alpha       pendente\n\n"
            "Passo 2\n  ○ 02-beta        pendente\n\n"
            "  ○ Revisão final  pendente\n"
        )
        self.assertEqual(self.board(), expected)

    def test_board_implementation_review_red_gate_pass_and_escalated(self):
        self.unit("01-alpha", "reviewing round 1")
        self.assert_board(
            "  ◐ 01-alpha       revisão · ronda 1\n",
            "  ○ 02-beta        pendente\n",
        )
        self.unit("02-beta", "implementing round 2", rounds=2, verdict="back",
                  gate="Result: RED\n")
        (self.run_path / ".done-S1").touch()
        self.assert_board(
            "  ✓ 01-alpha       passou · 1 ronda\n",
            "  ↩ 02-beta        gate falhou · ronda 3 a implementar\n",
        )
        (self.run_path / "02-beta/status").write_text("escalated\n", encoding="utf-8")
        self.assert_board(
            "  ✓ 01-alpha       passou · 1 ronda\n",
            "  ✗ 02-beta        escalada\n",
        )

    def test_board_red_gate_return_and_final_review_states(self):
        self.unit("01-alpha", "implementing round 2", rounds=2)
        (self.run_path / "01-alpha/rounds/1").mkdir(parents=True)
        (self.run_path / "01-alpha/rounds/1/verdict").write_text("back\n", encoding="utf-8")
        (self.run_path / "01-alpha/rounds/1/gate.md").write_text("Result: RED\n", encoding="utf-8")
        self.unit("02-beta", "reviewing round 1")
        self.run.note("STOPPED at the final review: pending")
        self.assert_board(
            "  ↩ 01-alpha       gate falhou · ronda 2 a implementar\n",
            "  ◐ 02-beta        revisão · ronda 1\n",
            "  ✗ Revisão final  parou\n",
        )

    def test_board_other_unit_and_final_states(self):
        self.unit("01-alpha", "implementing round 1")
        self.unit("02-beta", "gate round 1")
        self.assert_board(
            "  ◐ 01-alpha       implementação · ronda 1\n",
            "  ◐ 02-beta        gate · ronda 1\n",
        )

        self.unit("02-beta", "reviewing round 1")
        self.assert_board(
            "  ◐ 01-alpha       implementação · ronda 1\n",
            "  ◐ 02-beta        revisão · ronda 1\n",
        )

        (self.run_path / "01-alpha/rounds/1/verdict").write_text("back\n", encoding="utf-8")
        (self.run_path / "01-alpha/rounds/1/gate.md").write_text("green\n", encoding="utf-8")
        self.unit("01-alpha", "implementing round 2", rounds=2)
        self.assert_board(
            "  ↩ 01-alpha       devolvida · ronda 2 a implementar\n",
            "  ◐ 02-beta        revisão · ronda 1\n",
        )

        self.unit("02-beta", "passed", verdict="pass")
        self.assert_board(
            "  ↩ 01-alpha       devolvida · ronda 2 a implementar\n",
            "  ✓ 02-beta        passou · 1 ronda\n",
        )
        (self.run_path / "01-alpha/rounds/3").mkdir()
        self.unit("01-alpha", "implementing round 3", rounds=3)
        self.run.note("STOPPED at step 1: held")
        self.assert_board(
            "  ✗ 01-alpha       parou · ronda 3\n",
            "  ✓ 02-beta        passou · 1 ronda\n",
        )

        self.run.note("start final review (m e)")
        self.assert_board(
            "  ✗ 01-alpha       parou · ronda 3\n",
            "  ✓ 02-beta        passou · 1 ronda\n",
            "  ◐ Revisão final  revisão\n",
        )
        (self.run_path / "report.md").write_text("done\n", encoding="utf-8")
        self.assert_board(
            "  ✗ 01-alpha       parou · ronda 3\n",
            "  ✓ 02-beta        passou · 1 ronda\n",
            "  ✓ Revisão final  passou\n",
        )

    def test_real_run_progress_and_board_command_show_the_board(self):
        self.fixture.add_brief("unit")
        plan = self.fixture.write_plan("unit.md")
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = self.fixture.call("start", "live-board", str(self.fixture.goal), str(plan))
        self.assertEqual(code, 0)
        self.assertIn("Plano live-board · 1 unidades · início ", errors.getvalue())
        self.assertIn("Passo 1\n  ◐ 01-unit", errors.getvalue())
        board_output, board_errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(board_output), contextlib.redirect_stderr(board_errors):
            code = self.fixture.call("board", "live-board")
        self.assertEqual(code, 0)
        self.assertIn("Revisão final", board_output.getvalue())
        self.assertEqual(board_errors.getvalue(), "")

    def test_finish_copies_filtered_record_writes_summary_and_removes_run(self):
        (self.run_path / "report.md").write_text("review\n", encoding="utf-8")
        (self.run_path / "00-input" / "goal.md").write_text("goal\n", encoding="utf-8")
        rounds = self.run_path / "01-alpha" / "rounds" / "1"
        rounds.mkdir(parents=True)
        (rounds / "verdict").write_text("pass\n", encoding="utf-8")
        (self.run_path / "02-beta" / "rounds" / "1").mkdir(parents=True)
        (self.run_path / "02-beta" / "rounds" / "1" / "verdict").write_text("back\n", encoding="utf-8")
        (self.run_path / "metrics.tsv").write_text("01-alpha\t1\t2\t3\t4\t1500\n", encoding="utf-8")
        for name in ("raw.events.jsonl", "raw.stderr.log", "x.last-message.md", ".hidden", "a.attempt-1",
                     "untracked-x.txt", "base", "plan-base", "x.worktree.log", "repo", "pause", "settings",
                     "status", "status.log"):
            (self.run_path / name).write_text("excluded\n", encoding="utf-8")
        (self.fixture.repo / "AGENTS.md").write_text("Repository instructions.\n", encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), patch(
            "plan_board._repo_root", return_value=str(self.fixture.repo.resolve())
        ):
            WORKFLOW.finish(self.ctx())
        destination = self.fixture.repo.resolve() / "records" / "plans" / "board"
        self.assertFalse(self.run_path.exists())
        self.assertTrue((destination / "report.md").is_file())
        self.assertTrue((destination / "metrics.tsv").is_file())
        self.assertFalse(any((destination / name).exists() for name in (
            "raw.events.jsonl", "raw.stderr.log", "x.last-message.md", ".hidden", "a.attempt-1",
            "untracked-x.txt", "base", "plan-base", "x.worktree.log", "repo", "pause", "settings",
            "status", "status.log",
        )))
        summary = (destination / "status.md").read_text(encoding="utf-8")
        self.assertEqual(summary, (
            "# Plan summary\n\nRun: board\n\n| Step | Unit | Rounds | Last verdict |\n|---|---|---|---|\n"
            "| 1 | 01-alpha | 1 | pass |\n| 2 | 02-beta | 1 | back |\n"
            "\n## Implementation rounds\n\n| Unit | Round | Minutes | Steps | Files | Input tokens (k) |\n"
            "|---|---|---|---|---|---|\n| 01-alpha | 1 | 2 | 3 | 4 | 1 |\n"
            "\nThe final review is in report.md.\n"
        ))
        self.assertTrue(output.getvalue().startswith("Kept in "))
        self.assertIn("Note: {0}/AGENTS.md does not mention records/.".format(self.fixture.repo.resolve()), output.getvalue())

    def test_finish_refuses_existing_destination(self):
        (self.run_path / "report.md").write_text("review\n", encoding="utf-8")
        destination = self.fixture.repo.resolve() / "records" / "plans" / "board"
        destination.mkdir(parents=True)
        with patch("plan_board._repo_root", return_value=str(self.fixture.repo.resolve())):
            with self.assertRaisesRegex(RunError, "already exists: {0}".format(destination)):
                WORKFLOW.finish(self.ctx())
        self.assertTrue(self.run_path.exists())

    def test_finish_refuses_run_without_final_review(self):
        destination = self.fixture.repo.resolve() / "records" / "plans" / "board"
        with patch("plan_board._repo_root", return_value=str(self.fixture.repo.resolve())):
            with self.assertRaisesRegex(RunError, "there is no final review in this run: nothing to keep"):
                WORKFLOW.finish(self.ctx())
        self.assertTrue(self.run_path.exists())
        self.assertFalse(destination.exists())

        (self.run_path / "report.md").write_text("", encoding="utf-8")
        with patch("plan_board._repo_root", return_value=str(self.fixture.repo.resolve())):
            with self.assertRaisesRegex(RunError, "there is no final review in this run: nothing to keep"):
                WORKFLOW.finish(self.ctx())
        self.assertTrue(self.run_path.exists())
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()

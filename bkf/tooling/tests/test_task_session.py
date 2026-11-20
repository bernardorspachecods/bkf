"""Tests task_session through the task hook: one card per interactive Claude session in tmux, and its life."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import task_hook
import task_store
import task_tmux
from task_store import Task
from task_tmux import Result


SESSION = "sess-1"
PANE = "%7"
WINDOW = Result(0, "main\t@3\tAgentic work\n", "")


class FakeTmux:
    """Answers the one display-message the session needs; records each call."""

    def __init__(self, result: Result = WINDOW) -> None:
        self.result = result
        self.calls: list[list[str]] = []

    def __call__(self, args, stdin=None) -> Result:
        self.calls.append(list(args))
        return self.result


class TaskSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.store = base / "tasks"
        self.repo = base / "work" / "agentic"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.plain = base / "plain"
        self.plain.mkdir()
        self.tmux = FakeTmux()
        patcher = patch.object(task_tmux, "default_runner", self.tmux)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env = {
            "BKF_TASKS_DIR": str(self.store), "HOME": self.tmp.name,
            "CLAUDE_CODE_ENTRYPOINT": "cli", "TMUX_PANE": PANE,
        }

    def fire(self, event: str, *, environ: dict | None = None, cwd: Path | None = None, **fields: object) -> str:
        data = {"hook_event_name": event, "session_id": SESSION, "cwd": str(cwd or self.repo), **fields}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = task_hook.run(environ=self.env if environ is None else environ, stream=io.StringIO(json.dumps(data)))
        self.assertEqual(code, 0)
        return output.getvalue()

    def cards(self) -> list[Task]:
        return task_store.list_tasks(self.store).tasks

    def card(self) -> Task:
        tasks = self.cards()
        self.assertEqual(len(tasks), 1)
        return tasks[0]

    def start(self) -> Task:
        self.fire("SessionStart", source="startup")
        return self.card()

    def test_interactive_session_in_tmux_gets_one_working_card(self) -> None:
        self.assertEqual(self.fire("SessionStart", source="startup"), "")
        card = self.card()
        self.assertEqual((card.kind, card.status, card.source), ("task", "working", "session"))
        self.assertEqual(card.repo, task_store.repo_identity(self.repo))
        self.assertEqual(card.title, "Agentic work")
        self.assertEqual(card.session["agent"], "claude")
        self.assertEqual((card.session["tmux_session"], card.session["tmux_window"]), ("main", "@3"))

    def test_title_falls_back_to_the_repository_folder_without_tmux(self) -> None:
        self.tmux.result = Result(1, "", "no server running")
        self.start()
        self.assertEqual(self.card().title, "agentic")
        self.assertIsNone(self.card().session["tmux_window"])

    def test_no_card_for_sdk_cli_outside_tmux_or_outside_git(self) -> None:
        self.fire("SessionStart", environ={**self.env, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli"})
        self.fire("SessionStart", environ={k: v for k, v in self.env.items() if k != "TMUX_PANE"})
        self.fire("SessionStart", cwd=self.plain)
        self.assertEqual(self.cards(), [])
        self.assertFalse((self.store / ".sessions").exists())
        self.assertEqual(self.tmux.calls, [])

    def test_outside_git_reads_no_store_at_all(self) -> None:
        with patch.object(task_store, "session_link", side_effect=AssertionError("store read")):
            self.fire("SessionStart", cwd=self.plain)
        self.assertFalse(self.store.exists())

    def test_resume_reuses_the_card_and_moves_a_done_card_back_to_working(self) -> None:
        card = self.start()
        task_store.update(self.store, card.id, task_store.mark_done)
        self.tmux.result = Result(0, "main\t@9\tAgentic work\n", "")
        self.fire("SessionStart", source="resume")
        self.fire("SessionStart", source="compact")
        again = self.card()
        self.assertEqual((again.id, again.status), (card.id, "working"))
        self.assertEqual(again.session["tmux_window"], "@9")

    def test_two_starts_with_one_session_id_make_one_card(self) -> None:
        self.start()
        self.fire("SessionStart", source="startup")
        self.assertEqual(len(self.cards()), 1)

    def test_a_stale_link_gets_a_new_card_on_start(self) -> None:
        card = self.start()
        task_store.delete(self.store, card.id)
        self.fire("SessionStart", source="resume")
        new = self.card()
        self.assertNotEqual(new.id, card.id)
        self.assertEqual(task_store.session_link(self.store, SESSION)["task"], new.id)

    def test_first_prompt_names_the_card_and_later_prompts_do_not(self) -> None:
        self.start()
        self.fire("UserPromptSubmit", prompt="Fix the parser\nand the lexer too")
        self.assertEqual(self.card().title, "Fix the parser and the lexer too")
        self.fire("UserPromptSubmit", prompt="Now the docs")
        self.assertEqual(self.card().title, "Fix the parser and the lexer too")

    def test_title_from_a_prompt_is_one_line_of_at_most_120_characters(self) -> None:
        self.start()
        self.fire("UserPromptSubmit", prompt="x" * 300)
        self.assertEqual(self.card().title, "x" * 120)

    def test_an_empty_first_prompt_keeps_the_default_title_for_the_next(self) -> None:
        self.start()
        self.fire("UserPromptSubmit", prompt="   ")
        self.assertEqual(self.card().title, "Agentic work")
        self.fire("UserPromptSubmit", prompt="Real task")
        self.assertEqual(self.card().title, "Real task")

    def test_a_title_someone_set_is_not_replaced_by_a_prompt(self) -> None:
        card = self.start()
        task_store.update(self.store, card.id, lambda task: setattr(task, "title", "My own name"))
        self.fire("UserPromptSubmit", prompt="Something else")
        self.assertEqual(self.card().title, "My own name")

    def test_session_end_marks_a_working_card_done_and_keeps_the_link(self) -> None:
        card = self.start()
        self.fire("SessionEnd", reason="other")
        self.assertEqual(self.card().status, "done")
        self.assertEqual(task_store.session_link(self.store, SESSION)["task"], card.id)

    def test_resume_after_session_end_reuses_the_card(self) -> None:
        card = self.start()
        self.fire("SessionEnd", reason="other")
        self.tmux.result = Result(0, "main\t@9\tAgentic work\n", "")
        self.fire("SessionStart", source="resume")
        again = self.card()
        self.assertEqual((again.id, again.status), (card.id, "working"))
        self.assertEqual(again.session["tmux_window"], "@9")
        self.fire("SessionEnd", reason="other")
        self.assertEqual(self.card().status, "done")

    def test_session_end_takes_a_card_in_review_to_done(self) -> None:
        card = self.start()
        task_store.update(self.store, card.id, task_store.mark_ready)
        self.fire("SessionEnd", reason="other")
        self.assertEqual(self.card().status, "done")

    def test_session_end_leaves_a_card_someone_else_moved(self) -> None:
        card = self.start()
        task_store.update(self.store, card.id, task_store.mark_failed)
        self.fire("SessionEnd", reason="other")
        self.assertEqual(self.card().status, "failed")
        self.assertIsNotNone(task_store.session_link(self.store, SESSION))

    def test_a_stale_link_does_nothing_on_turn_events(self) -> None:
        card = self.start()
        task_store.delete(self.store, card.id)
        self.fire("Stop")
        self.fire("UserPromptSubmit", prompt="hello")
        self.fire("SessionEnd", reason="other")
        self.assertEqual(self.cards(), [])
        self.assertEqual(task_store.session_link(self.store, SESSION)["task"], card.id)

    def test_turn_events_set_and_clear_the_mark_on_the_session_card(self) -> None:
        self.start()
        self.fire("Stop")
        self.assertEqual(self.card().attention["note"], "waiting for your reply")
        self.fire("PermissionRequest", tool_name="Bash")
        self.assertEqual(self.card().attention["note"], "waiting for your approval")
        self.fire("PostToolUse", tool_name="Bash")
        self.assertIsNone(self.card().attention)

    def test_session_with_task_variable_never_touches_the_index(self) -> None:
        task = task_store.create(self.store, repo="/repo", title="Launched")
        task_store.update(self.store, task.id, task_store.start)
        bound = {**self.env, "BKF_TASK": task.id}
        self.fire("SessionStart", environ=bound)
        self.fire("Stop", environ=bound)
        self.fire("SessionEnd", environ=bound, reason="other")
        self.fire("UserPromptSubmit", environ=bound, prompt="A prompt")
        self.assertFalse((self.store / ".sessions").exists())
        self.assertEqual([card.id for card in self.cards()], [task.id])
        self.assertEqual(self.card().title, "Launched")

    def test_session_end_prints_nothing_for_a_launched_task(self) -> None:
        task = task_store.create(self.store, repo="/repo", title="Launched")
        task_store.update(self.store, task.id, task_store.start)
        output = self.fire("SessionEnd", environ={**self.env, "BKF_TASK": task.id}, reason="other")
        self.assertEqual(output, "")

    def test_session_cards_are_not_reported_as_unreadable(self) -> None:
        self.start()
        self.fire("SessionEnd", reason="other")
        listing = task_store.list_tasks(self.store)
        self.assertEqual(listing.unreadable, [])
        self.assertEqual(len(listing.tasks), 1)

    def test_invalid_session_ids_are_ignored(self) -> None:
        for bad in ("../escape", "", ".hidden"):
            data = {"hook_event_name": "SessionStart", "session_id": bad, "cwd": str(self.repo)}
            with contextlib.redirect_stdout(io.StringIO()):
                task_hook.run(environ=self.env, stream=io.StringIO(json.dumps(data)))
        self.assertEqual(self.cards(), [])
        self.assertFalse((self.store / ".sessions").exists())

    def test_ineligible_sessions_do_not_read_their_input(self) -> None:
        class Unreadable(io.StringIO):
            def read(self, size: int = -1) -> str:
                raise AssertionError("the hook read its input")

        for environ in (
            {"BKF_TASKS_DIR": str(self.store), "HOME": self.tmp.name, "CLAUDE_CODE_ENTRYPOINT": "sdk-cli", "TMUX_PANE": PANE},
            {"BKF_TASKS_DIR": str(self.store), "HOME": self.tmp.name, "CLAUDE_CODE_ENTRYPOINT": "cli"},
        ):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(task_hook.run(environ=environ, stream=Unreadable("")), 0)
            self.assertEqual(output.getvalue(), "")
        self.assertFalse(self.store.exists())

    def test_garbage_input_exits_zero(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(task_hook.run(environ=self.env, stream=io.StringIO("{not json")), 0)
        self.assertEqual(self.cards(), [])

    def test_title_rule_is_one_line_of_at_most_120_characters(self) -> None:
        self.assertIsNone(task_store.title_from_text("  \n  "))
        self.assertEqual(task_store.title_from_text("a\n b  "), "a  b")
        self.assertEqual(len(task_store.title_from_text("y" * 500) or ""), 120)


if __name__ == "__main__":
    unittest.main()

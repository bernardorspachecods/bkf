from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import bkf_cli
import bkf_launch
import task_store
import task_tmux
import task_worktree
from task_tmux import TmuxError, Window


GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
}
PARENT_ID = "t20260101-000000-abcd"


def make_repo(path: Path) -> None:
    path.mkdir(parents=True)
    env = {**os.environ, **GIT_IDENTITY}
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "--allow-empty", "-m", "init"],
                   check=True, env=env)


class FakeWindows:
    """Stands in for task_tmux.open_window: records each call and answers with a fixed window."""

    def __init__(self, *, needs_attach: bool = False, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.needs_attach = needs_attach
        self.error = error

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return Window(session="fake-session", window_id="@7", needs_attach=self.needs_attach)


class FakeSessions:
    """Stands in for task_tmux.default_runner: answers the tmux and repository calls of --session-name, never a real server."""

    def __init__(self, *, server: bool = False, listing: str = "") -> None:
        self.calls: list[list[str]] = []
        self.server = server
        self.listing = listing

    def __call__(self, args, stdin=None):
        args = list(args)
        self.calls.append(args)
        if args[0] == "git":  # every directory is its own repository here
            return task_tmux.Result(0, args[2] + "/.git\n", "")
        tmux_args = args[3:] if args[1] == "-L" else args[1:]
        if tmux_args[0] == "has-session" or not self.server:
            return task_tmux.Result(1, "", "no server running")
        return task_tmux.Result(0, self.listing, "")


class LaunchTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(os.path.realpath(directory.name))
        self.store = self.root / "store"
        self.repo = self.root / "repo"
        make_repo(self.repo)
        self.plain = self.root / "plain"
        self.plain.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("claude", "codex"):
            script = self.bin / name
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            script.chmod(0o755)
        self.original_path = os.environ.get("PATH", "")
        environment = patch.dict(os.environ, {
            "BKF_TASKS_DIR": str(self.store),
            "PATH": f"{self.bin}{os.pathsep}{self.original_path}",
        })
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("BKF_TASK", "BKF_DELEGATED", "TMUX", "TMUX_PANE", "BKF_TMUX_SOCKET"):
            os.environ.pop(name, None)
        self.windows = FakeWindows()
        opener = patch("task_tmux.open_window", self.windows)
        opener.start()
        self.addCleanup(opener.stop)
        self.sessions = FakeSessions()
        sessions = patch("task_tmux.default_runner", self.sessions)
        sessions.start()
        self.addCleanup(sessions.stop)
        self.tempdir = self.root / "tmp"
        self.tempdir.mkdir()
        temp = patch.object(tempfile, "tempdir", str(self.tempdir))
        temp.start()
        self.addCleanup(temp.stop)

    def launch(self, *arguments: str, stdin: str = "") -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch("sys.stdin", io.StringIO(stdin)):
            try:
                status = bkf_cli.main(["launch", *arguments])
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def write(self, name: str, text: str) -> str:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def cards(self) -> list[task_store.Task]:
        return task_store.list_tasks(self.store).tasks

    def only_card(self) -> task_store.Task:
        cards = self.cards()
        self.assertEqual(len(cards), 1)
        return cards[0]

    def command(self) -> str:
        return self.windows.calls[-1]["command"]

    def assertRefused(self, status: int, stderr: str, message: str) -> None:
        self.assertEqual(status, 1)
        self.assertTrue(stderr.startswith("bkf launch: "), stderr)
        self.assertEqual(stderr.count("\n"), 1)
        self.assertIn(message, stderr)
        self.assertEqual(self.windows.calls, [])

    # Command lines.

    def test_claude_command_with_every_option(self) -> None:
        prompt = self.write("p.md", "Hello\n")
        status, _, error = self.launch(
            "claude", "--dir", str(self.plain), "--no-task", "--prompt-file", prompt,
            "--model", "opus", "--effort", "high", "--name", "n", "--permission-mode", "plan",
        )
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(
            self.command(),
            f'claude --name n --permission-mode plan --model opus --effort high "$(cat {shlex.quote(prompt)})"',
        )

    def test_claude_command_without_a_prompt(self) -> None:
        self.assertEqual(self.launch("claude", "--dir", str(self.plain), "--no-task")[0], 0)
        self.assertEqual(self.command(), "claude")
        self.assertNotIn("--remote-control", self.command())

    def test_remote_control_is_placed_before_model(self) -> None:
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--no-task",
                                       "--permission-mode", "plan", "--remote-control", "--model", "opus")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(self.command(), "claude --permission-mode plan --remote-control --model opus")

    def test_codex_command(self) -> None:
        prompt = self.write("p.md", "Hello\n")
        status, _, _ = self.launch("codex", "--dir", str(self.plain), "--no-task", "--prompt-file", prompt,
                                   "--model", "gpt-x", "--effort", "high")
        self.assertEqual(status, 0)
        effort = shlex.quote('model_reasoning_effort="high"')
        self.assertEqual(self.command(), f'codex -m gpt-x -c {effort} "$(cat {shlex.quote(prompt)})"')

    def test_values_are_shell_quoted(self) -> None:
        self.launch("claude", "--dir", str(self.plain), "--no-task", "--model", "a b;rm", "--name", "x'y")
        self.assertEqual(self.command(), "claude --name 'x'\"'\"'y' --model 'a b;rm'")

    def test_relative_prompt_path_becomes_absolute(self) -> None:
        self.write("rel.md", "Hi\n")
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        self.launch("claude", "--dir", str(self.plain), "--no-task", "--prompt-file", "rel.md")
        self.assertIn(shlex.quote(str(self.root / "rel.md")), self.command())

    def test_claude_only_options_are_usage_errors_for_codex(self) -> None:
        for arguments in (("--name", "n"), ("--permission-mode", "plan"), ("--remote-control",)):
            with self.subTest(arguments=arguments):
                status, _, error = self.launch("codex", "--dir", str(self.plain), "--no-task", *arguments)
                self.assertEqual(status, 2)
                if arguments == ("--remote-control",):
                    self.assertIn("--remote-control works only with claude", error)
        self.assertEqual(self.windows.calls, [])

    # Title, kind, parent and body of a new card.

    def test_title_fallbacks(self) -> None:
        long_line = "x" * 100
        cases = [
            (("--title", "Given", "--window", "w", "--name", "n"), "", "Given", "w"),
            (("--window", "w", "--name", "n"), "", "w", "w"),
            (("--name", "n"), "", "n", None),
            ((), "\n\n  First line here  \nsecond\n", "First line here", None),
            ((), long_line + "\nmore", "x" * 80, None),
            ((), "", "session", None),
        ]
        for extra, prompt, title, window in cases:
            with self.subTest(title=title):
                for card in self.cards():
                    task_store.delete(self.store, card.id)
                arguments = ["claude", "--dir", str(self.plain), "--prompt-file", "-", *extra]
                status, _, error = self.launch(*arguments, stdin=prompt)
                self.assertEqual((status, error), (0, ""))
                self.assertEqual(self.only_card().title, title)
                self.assertEqual(self.windows.calls[-1]["window_name"], window or title)

    def test_kind_and_parent_defaults(self) -> None:
        self.launch("claude", "--dir", str(self.plain), "--no-task")
        self.launch("claude", "--dir", str(self.plain), "--title", "a")
        self.assertEqual(self.only_card().kind, "handoff")
        self.assertIsNone(self.only_card().parent)
        task_store.delete(self.store, self.only_card().id)

        with patch.dict(os.environ, {"BKF_TASK": PARENT_ID}):
            self.launch("claude", "--dir", str(self.plain), "--title", "child")
        self.assertEqual(self.only_card().parent, PARENT_ID)
        task_store.delete(self.store, self.only_card().id)

        with patch.dict(os.environ, {"BKF_TASK": PARENT_ID}):
            self.launch("claude", "--dir", str(self.plain), "--title", "orphan", "--no-parent")
        self.assertIsNone(self.only_card().parent)
        task_store.delete(self.store, self.only_card().id)

        self.launch("codex", "--dir", str(self.plain), "--title", "explicit", "--kind", "task",
                    "--parent", PARENT_ID, "--worktree", "none")
        card = self.only_card()
        self.assertEqual((card.kind, card.parent), ("task", PARENT_ID))

    def test_body_file_becomes_the_body(self) -> None:
        body = self.write("body.md", "Body text\n")
        self.launch("claude", "--dir", str(self.plain), "--title", "b", "--body-file", body)
        self.assertEqual(self.only_card().body, "Body text\n")

    # Worktree.

    def test_task_kind_gets_a_worktree_and_runs_in_it(self) -> None:
        status, _, error = self.launch("claude", "--dir", str(self.repo), "--title", "Make it",
                                       "--kind", "task")
        self.assertEqual((status, error), (0, ""))
        card = self.only_card()
        self.assertTrue(os.path.isdir(card.worktree["path"]))
        self.assertEqual(self.windows.calls[-1]["directory"], card.worktree["path"])
        self.assertEqual(card.worktree["path"], str(self.repo / ".claude" / "worktrees" /
                                                    task_worktree.slug("Make it", card.id)))

    def test_handoff_and_explicit_none_run_in_dir(self) -> None:
        self.launch("claude", "--dir", str(self.repo), "--title", "h")
        self.assertEqual(self.windows.calls[-1]["directory"], os.path.abspath(self.repo))
        self.assertIsNone(self.only_card().worktree)
        task_store.delete(self.store, self.only_card().id)
        self.launch("claude", "--dir", str(self.repo), "--title", "t", "--kind", "task", "--worktree", "none")
        self.assertIsNone(self.only_card().worktree)

    def test_auto_on_a_handoff_card_creates_a_worktree(self) -> None:
        self.launch("claude", "--dir", str(self.repo), "--title", "h", "--worktree", "auto")
        self.assertTrue(os.path.isdir(self.only_card().worktree["path"]))

    def test_non_git_folder_falls_back_to_none_silently(self) -> None:
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--title", "t", "--kind", "task")
        self.assertEqual((status, error), (0, ""))
        self.assertIsNone(self.only_card().worktree)
        self.assertEqual(self.windows.calls[-1]["directory"], str(self.plain))

    def test_no_task_has_no_worktree_even_for_a_git_folder(self) -> None:
        self.launch("claude", "--dir", str(self.repo), "--no-task")
        self.assertEqual(self.windows.calls[-1]["directory"], str(self.repo))
        self.assertEqual(self.cards(), [])

    # Existing cards.

    def test_task_launch_on_a_todo_card_records_the_session(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="Todo card")
        status, out, error = self.launch("codex", "--dir", str(self.plain), "--task", card.id,
                                         "--worktree", "none", "--model", "m", "--effort", "e",
                                         "--reviewer", "r")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(out.splitlines()[0], card.id)
        loaded = task_store.read(self.store, card.id)
        self.assertEqual(loaded.status, "working")
        self.assertEqual(loaded.session, {
            "agent": "codex", "model": "m", "effort": "e", "reviewer": "r",
            "tmux_session": "fake-session", "tmux_window": "@7",
        })

    def test_failed_card_with_its_worktree_reuses_it(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="Again", kind="task")
        self.assertEqual(self.launch("claude", "--dir", str(self.plain), "--task", card.id)[0], 0)
        first = task_store.read(self.store, card.id).worktree["path"]
        task_store.update(self.store, card.id, lambda task: task_store.mark_failed(task, exit=1))
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--task", card.id)
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(self.windows.calls[-1]["directory"], first)
        self.assertEqual(task_store.read(self.store, card.id).status, "working")

    def test_failed_card_without_a_worktree_gets_one(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="Late", kind="task")
        task_store.update(self.store, card.id, lambda task: task_store.start(task))
        task_store.update(self.store, card.id, lambda task: task_store.mark_failed(task, exit=1))
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--task", card.id)
        self.assertEqual((status, error), (0, ""))
        path = task_store.read(self.store, card.id).worktree["path"]
        self.assertTrue(os.path.isdir(path))
        self.assertEqual(self.windows.calls[-1]["directory"], path)

    def test_task_refusals_write_nothing(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="Busy")
        task_store.update(self.store, card.id, lambda task: task_store.start(task))
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--task", card.id)
        self.assertRefused(status, error, "is working; a launch needs a todo or failed task")
        self.assertEqual(len(self.cards()), 1)

        status, _, error = self.launch("claude", "--dir", str(self.plain), "--task", "t20260101-000000-zzzz")
        self.assertRefused(status, error, "no task")
        self.assertEqual(len(self.cards()), 1)

    # Refusals and usage errors.

    def test_refusals_before_the_card_exist(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        with patch.dict(os.environ, {"PATH": f"{empty}:/usr/bin:/bin"}):
            status, _, error = self.launch("claude", "--dir", str(self.plain), "--title", "t")
        self.assertRefused(status, error, "claude is not installed or not on PATH")
        self.assertEqual(self.cards(), [])

        status, _, error = self.launch("claude", "--dir", str(self.root / "missing"), "--title", "t")
        self.assertRefused(status, error, "--dir is not a folder")
        self.assertEqual(self.cards(), [])

        status, _, error = self.launch("claude", "--dir", str(self.plain), "--title", "t",
                                       "--prompt-file", str(self.root / "nope.md"))
        self.assertRefused(status, error, "no prompt file")
        self.assertEqual(self.cards(), [])

    def test_usage_errors_exit_two_and_write_nothing(self) -> None:
        prompt = self.write("u.md", "x")
        cases = [
            ("claude", "--dir", str(self.plain), "--no-task", "--kind", "task"),
            ("claude", "--dir", str(self.plain), "--task", PARENT_ID, "--title", "t"),
            ("claude", "--dir", str(self.plain), "--task", PARENT_ID, "--no-task"),
            ("claude", "--dir", str(self.plain), "--no-task", "--worktree", "auto"),
            ("claude", "--dir", str(self.plain), "--title", "t", "--parent", PARENT_ID, "--no-parent"),
            ("claude", "--dir", str(self.plain), "--title", "t", "--prompt-file", "-", "--body-file", "-"),
            ("claude", "--dir", str(self.plain), "--title", "t", "--size", "abc"),
            ("claude", "--dir", str(self.plain), "--title", "t", "--kind", "bogus"),
            ("claude", "--dir", str(self.plain), "--title", "t", "--prompt-file", prompt, "--worktree", "x"),
            ("--dir", str(self.plain), "--title", "t"),
            ("nope", "--dir", str(self.plain), "--title", "t"),
            ("claude", "--title", "t"),
            ("--session-name", "--dir", str(self.plain), "--model", "m"),
            ("--session-name", "--dir", str(self.plain), "--remote-control"),
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                status, _, _ = self.launch(*arguments)
                self.assertEqual(status, 2)
        self.assertFalse(self.store.exists())
        self.assertEqual(self.windows.calls, [])

    def test_session_name_prints_the_repository_session_and_launches_nothing(self) -> None:
        status, out, error = self.launch("--session-name", "--dir", str(self.repo))
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(out, task_tmux.repo_session_name(task_store.repo_identity(self.repo)) + "\n")
        self.assertEqual(self.windows.calls, [])
        self.assertFalse(self.store.exists())

        status, _, error = self.launch("--session-name", "--dir", str(self.root / "missing"))
        self.assertEqual(status, 1)
        self.assertIn("--dir is not a folder", error)

    def test_session_name_prints_the_session_where_the_repository_has_windows(self) -> None:
        legacy = "agentic-agentic-66d44a"
        self.sessions.server = True
        self.sessions.listing = "\n".join([
            "\t".join(["main", "1", "@1", "0", str(self.plain)]),
            "\t".join([legacy, "0", "@5", "2", str(self.repo)]),
        ]) + "\n"
        status, out, error = self.launch("--session-name", "--dir", str(self.repo))
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(out, legacy + "\n")
        self.assertEqual(self.windows.calls, [])
        self.assertIn(["tmux", "list-panes", "-a", "-F", task_tmux.PANE_FORMAT], self.sessions.calls)

    def test_session_name_ignores_a_session_with_a_name_tmux_targets_refuse(self) -> None:
        self.sessions.server = True
        self.sessions.listing = "\t".join(["Agentic", "3", "@5", "0", str(self.repo)]) + "\n"
        status, out, _ = self.launch("--session-name", "--dir", str(self.repo))
        self.assertEqual((status, out),
                         (0, task_tmux.repo_session_name(task_store.repo_identity(self.repo)) + "\n"))

    def test_session_name_applies_the_socket_of_the_environment_to_list_panes(self) -> None:
        self.sessions.server = True
        with patch.dict(os.environ, {"BKF_TMUX_SOCKET": "sock-x"}):
            status, _, _ = self.launch("--session-name", "--dir", str(self.repo))
        self.assertEqual(status, 0)
        self.assertIn(["tmux", "-L", "sock-x", "list-panes", "-a", "-F", task_tmux.PANE_FORMAT],
                      self.sessions.calls)

    # What the window receives and the output.

    def test_card_after_success_is_working_with_session_and_worktree(self) -> None:
        prompt = self.write("first.md", "Do the thing\n")
        status, out, error = self.launch("claude", "--dir", str(self.repo), "--prompt-file", prompt,
                                         "--kind", "task", "--title", "Do it", "--model", "opus",
                                         "--no-attach")
        self.assertEqual((status, error), (0, ""))
        card = self.only_card()
        loaded = task_store.read(self.store, card.id)
        self.assertEqual(loaded.status, "working")
        self.assertEqual(loaded.session, {
            "agent": "claude", "model": "opus", "effort": None, "reviewer": None,
            "tmux_session": "fake-session", "tmux_window": "@7",
            "claude_session_id": shlex.split(self.command())[self.command().split().index("--session-id") + 1],
        })
        self.assertEqual(shlex.split(self.command())[1], "--session-id")
        self.assertEqual(str(uuid.UUID(loaded.session["claude_session_id"])), loaded.session["claude_session_id"])
        self.assertEqual(loaded.worktree["path"], card.worktree["path"])
        self.assertEqual(loaded.worktree["branch"], f"task/{task_worktree.slug('Do it', card.id)}")
        self.assertEqual(out.splitlines(), [card.id, "fake-session:@7"])

    def test_launch_session_id_is_passed_to_claude_and_recorded_on_the_card(self) -> None:
        prompt = self.write("first.md", "Do the thing\n")
        self.launch("claude", "--dir", str(self.repo), "--prompt-file", prompt, "--kind", "task", "--title", "Do it")
        card = self.only_card()
        session_id = task_store.read(self.store, card.id).session["claude_session_id"]
        command = shlex.split(self.command())
        self.assertEqual(command[1:3], ["--session-id", session_id])
        self.assertEqual(str(uuid.UUID(session_id)), session_id)

    def test_the_prompt_is_copied_to_the_card_and_the_window_reads_the_copy(self) -> None:
        prompt = self.write("first.md", "Do the thing\n")
        self.launch("claude", "--dir", str(self.plain), "--title", "p", "--prompt-file", prompt)
        card = self.only_card()
        copy = self.store / card.id / "prompt.md"
        self.assertEqual(copy.read_text(encoding="utf-8"), "Do the thing\n")
        command = shlex.split(self.command())
        self.assertEqual(command[0], "claude")
        self.assertEqual(command[1], "--session-id")
        self.assertEqual(str(uuid.UUID(command[2])), command[2])
        self.assertEqual(command[3], f"$(cat {shlex.quote(str(copy.absolute()))})")

    def test_standard_input_with_a_card_is_saved_as_the_prompt(self) -> None:
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--title", "s",
                                       "--prompt-file", "-", stdin="From stdin\n")
        self.assertEqual((status, error), (0, ""))
        card = self.only_card()
        self.assertEqual(task_store.read_prompt(self.store, card.id), "From stdin\n")

    def test_standard_input_without_a_card_goes_to_a_kept_temporary_file(self) -> None:
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--no-task",
                                       "--prompt-file", "-", stdin="Kept text\n")
        self.assertEqual((status, error), (0, ""))
        command = self.command()
        path = command.split("$(cat ", 1)[1][:-2]
        self.assertTrue(path.startswith(str(self.tempdir)), path)
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "Kept text\n")
        self.assertEqual(self.cards(), [])

    def test_no_task_has_no_environment_and_a_task_gets_its_id(self) -> None:
        self.launch("claude", "--dir", str(self.plain), "--no-task")
        environment = self.windows.calls[-1]["environment"]
        self.assertNotIn(bkf_launch.TASK_ENV, environment)
        self.assertNotIn("BKF_DELEGATED", environment)

        self.launch("claude", "--dir", str(self.plain), "--title", "e", "--delegated")
        card = self.only_card()
        environment = self.windows.calls[-1]["environment"]
        self.assertEqual(environment[bkf_launch.TASK_ENV], card.id)
        self.assertEqual(environment["BKF_DELEGATED"], "1")
        self.assertEqual(environment["BKF_TASKS_DIR"], str(self.store))

    def test_window_name_and_size_reach_the_window(self) -> None:
        self.launch("claude", "--dir", str(self.plain), "--no-task", "--window", "W", "--size", "200x50",
                    "--no-attach")
        call = self.windows.calls[-1]
        self.assertEqual((call["window_name"], call["size"], call["attach"]), ("W", (200, 50), False))
        self.assertEqual(call["repo"], task_store.repo_identity(self.plain))

    def test_plain_output_names_the_attach_command_when_needed(self) -> None:
        self.windows.needs_attach = True
        status, out, _ = self.launch("claude", "--dir", str(self.plain), "--no-task")
        self.assertEqual(status, 0)
        self.assertEqual(out.splitlines(), ["fake-session:@7",
                                            "attach with: tmux attach -t =fake-session"])

    def test_json_output(self) -> None:
        status, out, _ = self.launch("claude", "--dir", str(self.repo), "--title", "j", "--kind", "task", "--json")
        self.assertEqual(status, 0)
        card = self.only_card()
        self.assertEqual(json.loads(out), {
            "task": card.id, "session": "fake-session", "window": "@7",
            "worktree": card.worktree["path"], "branch": card.worktree["branch"],
            "needs_attach": False,
        })
        self.assertEqual(json.loads(self.launch("claude", "--dir", str(self.plain), "--no-task", "--json")[1]),
                         {"task": None, "session": "fake-session", "window": "@7", "worktree": None,
                          "branch": None, "needs_attach": False})

    def test_bkf_help_lists_launch(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(bkf_cli.main(["help"]), 0)
        self.assertIn("launch", stdout.getvalue())

    # Failures after the card exists.

    def test_window_failure_leaves_the_card_todo_with_attention_and_the_worktree(self) -> None:
        self.windows.error = TmuxError("tmux new-window failed: no server running")
        status, out, error = self.launch("claude", "--dir", str(self.repo), "--title", "f", "--kind", "task")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(error, "bkf launch: tmux new-window failed: no server running\n")
        card = self.only_card()
        self.assertEqual(card.status, "todo")
        self.assertEqual(card.attention["reason"], "launch-failed")
        self.assertEqual(card.attention["note"], "tmux new-window failed: no server running")
        self.assertTrue(os.path.isdir(card.worktree["path"]))

    def test_worktree_failure_leaves_the_card_todo_with_attention(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="Clash", kind="task")
        blocked = self.repo / ".claude" / "worktrees" / task_worktree.slug(card.title, card.id)
        blocked.mkdir(parents=True)
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--task", card.id)
        self.assertEqual(status, 1)
        self.assertIn("the path exists and is not the worktree", error)
        self.assertEqual(error.count("\n"), 1)
        loaded = task_store.read(self.store, card.id)
        self.assertEqual((loaded.status, loaded.attention["reason"]), ("todo", "launch-failed"))
        self.assertEqual(self.windows.calls, [])

    def test_failed_card_keeps_its_status_and_gets_attention(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="Was failed",
                                 kind="handoff")
        task_store.update(self.store, card.id, lambda task: task_store.start(task))
        task_store.update(self.store, card.id, lambda task: task_store.mark_failed(task, exit=2))
        self.windows.error = TmuxError("tmux new-window failed: boom")
        status, _, error = self.launch("claude", "--dir", str(self.plain), "--task", card.id)
        self.assertEqual(status, 1)
        self.assertEqual(error, "bkf launch: tmux new-window failed: boom\n")
        loaded = task_store.read(self.store, card.id)
        self.assertEqual(loaded.status, "failed")
        self.assertEqual((loaded.attention["reason"], loaded.attention["note"]),
                         ("launch-failed", "tmux new-window failed: boom"))
        self.assertIsNone(loaded.note)


@unittest.skipUnless(shutil.which("tmux"), "tmux is not on PATH")
class RealTmuxLaunchTests(unittest.TestCase):
    """Launches on a throwaway tmux server with fake agents first on PATH; the user's server is never used."""

    def setUp(self) -> None:
        self.socket = f"bkf-launch-test-{uuid.uuid4().hex[:10]}"
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(os.path.realpath(directory.name))
        self.repo = self.root / "repo"
        make_repo(self.repo)
        self.store = self.root / "store"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.record = self.root / "record.json"
        for name in ("claude", "codex"):
            script = self.bin / name
            script.write_text(
                "#!" + sys.executable + "\n"
                "import json, os, sys\n"
                "with open(" + repr(str(self.record)) + ", 'w') as handle:\n"
                "    json.dump({'argv': sys.argv[1:], 'cwd': os.getcwd(), "
                "'task': os.environ.get('BKF_TASK')}, handle)\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
        environment = patch.dict(os.environ, {
            "BKF_TMUX_SOCKET": self.socket,
            "BKF_TASKS_DIR": str(self.store),
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
        })
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("TMUX", "TMUX_PANE", "BKF_TASK"):
            os.environ.pop(name, None)
        self.addCleanup(subprocess.run, ["tmux", "-L", self.socket, "kill-server"],
                        capture_output=True, check=False)

    def launch_json(self, *arguments: str) -> dict:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = bkf_cli.main(["launch", *arguments, "--no-attach", "--json"])
        self.assertEqual(status, 0, stderr.getvalue())
        return json.loads(stdout.getvalue())

    def wait_for_record(self) -> dict:
        for _ in range(150):
            if self.record.exists() and self.record.stat().st_size:
                return json.loads(self.record.read_text(encoding="utf-8"))
            time.sleep(0.1)
        self.fail("the fake agent did not run")

    def test_task_card_runs_in_its_worktree_and_handoff_runs_in_dir(self) -> None:
        prompt = self.root / "prompt.md"
        text = "line one\n'quoted' $HOME `tick` \"double\"\nlast line\n"
        prompt.write_text(text, encoding="utf-8")

        result = self.launch_json("claude", "--dir", str(self.repo), "--prompt-file", str(prompt),
                                  "--kind", "task", "--title", "Real run")
        record = self.wait_for_record()
        self.assertEqual(record["argv"][0], "--session-id")
        self.assertEqual(str(uuid.UUID(record["argv"][1])), record["argv"][1])
        self.assertEqual(record["argv"][2:], [text.rstrip("\n")])
        self.assertEqual(record["cwd"], result["worktree"])
        self.assertEqual(record["task"], result["task"])
        self.assertTrue(result["worktree"].startswith(str(self.repo)))

        shown = self.show(result["task"])
        self.assertEqual(shown["status"], "working")
        self.assertEqual(shown["session"]["tmux_window"], result["window"])
        self.assertEqual(shown["session"]["tmux_session"], result["session"])
        self.assertEqual(shown["session"]["claude_session_id"], record["argv"][1])

        self.record.unlink()
        second = self.launch_json("codex", "--dir", str(self.repo), "--prompt-file", str(prompt))
        record = self.wait_for_record()
        self.assertEqual(record["argv"], [text.rstrip("\n")])
        self.assertEqual(record["cwd"], str(self.repo))
        self.assertEqual(record["task"], second["task"])
        self.assertIsNone(second["worktree"])
        self.assertEqual(self.show(second["task"])["status"], "working")

    def show(self, task_id: str) -> dict:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(bkf_cli.main(["task", "show", task_id, "--json"]), 0)
        return json.loads(stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

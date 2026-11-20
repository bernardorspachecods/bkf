from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import bkf_cli
import task_store
import task_tmux


TOOLING = Path(__file__).resolve().parents[1]
TASK_ID_SHAPE = r"t[0-9]{8}-[0-9]{6}-[0-9a-f]{4}"


class BkfTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.store = self.root / "store"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        environment = patch.dict(os.environ, {"BKF_TASKS_DIR": str(self.store)})
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("BKF_TASK", None)
        os.environ.pop("BKF_TMUX_SOCKET", None)

    def run_task(self, *arguments: str, stdin: str = "") -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch("sys.stdin", io.StringIO(stdin)):
            try:
                status = bkf_cli.main(["task", *arguments])
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def new(self, title: str = "first", *extra: str) -> str:
        status, output, error = self.run_task("new", "--repo", str(self.repo), "--title", title, *extra)
        self.assertEqual((status, error), (0, ""))
        return output.strip()

    def assertRefused(self, status: int, output: str, error: str, message: str = "") -> None:
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertTrue(error.startswith("bkf task: "), error)
        self.assertEqual(error.count("\n"), 1)
        if message:
            self.assertIn(message, error)

    def git(self, cwd: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(cwd), *arguments], capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    # new

    def test_new_prints_the_id_and_stores_a_todo_task(self) -> None:
        task_id = self.new("Write the report", "--source", "https://example.invalid/a")
        self.assertRegex(task_id, rf"^{TASK_ID_SHAPE}$")
        task = task_store.read(self.store, task_id)
        self.assertEqual((task.status, task.kind, task.title, task.source), ("todo", "task", "Write the report", "https://example.invalid/a"))
        self.assertEqual(task.repo, task_store.repo_identity(self.repo))

    def test_new_json_prints_the_task_object(self) -> None:
        status, output, error = self.run_task("new", "--repo", str(self.repo), "--title", "A", "--kind", "unit", "--json")
        self.assertEqual((status, error), (0, ""))
        data = json.loads(output)
        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["kind"], "unit")
        self.assertEqual(data["status"], "todo")

    def test_new_reads_body_from_a_file_and_from_standard_input(self) -> None:
        body_file = self.root / "body.md"
        body_file.write_text("from a file\n", encoding="utf-8")
        from_file = self.new("file", "--body-file", str(body_file))
        self.assertEqual(task_store.read(self.store, from_file).body, "from a file\n")
        status, output, error = self.run_task("new", "--repo", str(self.repo), "--title", "stdin", "--body-file", "-", stdin="from stdin")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(task_store.read(self.store, output.strip()).body, "from stdin")

    def test_new_with_a_missing_body_file_is_refused(self) -> None:
        status, output, error = self.run_task("new", "--repo", str(self.repo), "--title", "x", "--body-file", str(self.root / "missing.md"))
        self.assertRefused(status, output, error)

    def test_new_parent_defaults_to_the_task_window_and_no_parent_overrides_it(self) -> None:
        parent = self.new("parent")
        with patch.dict(os.environ, {"BKF_TASK": parent}):
            child = self.new("child")
            orphan = self.new("orphan", "--no-parent")
            explicit = self.new("explicit", "--parent", parent)
        self.assertEqual(task_store.read(self.store, child).parent, parent)
        self.assertIsNone(task_store.read(self.store, orphan).parent)
        self.assertEqual(task_store.read(self.store, explicit).parent, parent)
        self.assertIsNone(task_store.read(self.store, self.new("plain")).parent)

    def test_new_with_an_invalid_kind_is_a_usage_error(self) -> None:
        status, _, _ = self.run_task("new", "--repo", str(self.repo), "--title", "x", "--kind", "bogus")
        self.assertEqual(status, 2)

    # list

    def test_list_prints_one_line_per_task_and_filters_combine(self) -> None:
        other_repo = self.root / "other"
        other_repo.mkdir()
        first = self.new("alpha")
        status, _, _ = self.run_task("new", "--repo", str(self.repo), "--title", "beta", "--kind", "unit")
        self.assertEqual(status, 0)
        elsewhere = self.run_task("new", "--repo", str(other_repo), "--title", "gamma")[1].strip()
        self.run_task("start", first)

        status, output, error = self.run_task("list")
        self.assertEqual((status, error), (0, ""))
        lines = output.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn(f"{first}  working  task  alpha", lines)
        self.assertTrue(any(line.endswith("  unit  beta") for line in lines), lines)

        _, output, _ = self.run_task("list", "--repo", str(self.repo))
        self.assertEqual(len(output.splitlines()), 2)
        _, output, _ = self.run_task("list", "--repo", str(self.repo), "--status", "todo", "--status", "working")
        self.assertEqual(len(output.splitlines()), 2)
        _, output, _ = self.run_task("list", "--status", "done")
        self.assertEqual(output, "")
        _, output, _ = self.run_task("list", "--kind", "unit")
        self.assertEqual(len(output.splitlines()), 1)
        _, output, _ = self.run_task("list", "--repo", str(self.repo), "--kind", "unit", "--status", "working")
        self.assertEqual(output, "")
        _, output, _ = self.run_task("list", "--repo", str(other_repo), "--status", "todo")
        self.assertIn(elsewhere, output)

    def test_list_parent_filter(self) -> None:
        parent = self.new("parent")
        child = self.new("child", "--parent", parent)
        self.new("other")
        _, output, _ = self.run_task("list", "--parent", parent)
        self.assertEqual(output.splitlines(), [f"{child}  todo  task  child"])

    def test_list_json_has_the_documented_shape_in_creation_order(self) -> None:
        first = self.new("one")
        second = self.new("two")
        status, output, error = self.run_task("list", "--json")
        self.assertEqual((status, error), (0, ""))
        data = json.loads(output)
        self.assertEqual(list(data), ["schema", "store", "generation", "tasks", "unreadable"])
        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["store"], str(self.store))
        self.assertEqual(data["generation"], task_store.generation(self.store))
        self.assertEqual([task["id"] for task in data["tasks"]], [task.id for task in task_store.list_tasks(self.store).tasks])
        self.assertEqual({task["id"] for task in data["tasks"]}, {first, second})
        by_id = {task["id"]: task for task in data["tasks"]}
        self.assertEqual(by_id[first], task_store.read(self.store, first).to_json())
        self.assertEqual(data["unreadable"], [])

    def test_list_reports_unreadable_folders(self) -> None:
        good = self.new("good")
        broken = self.store / "t20000101-000000-dead"
        broken.mkdir(parents=True)
        (broken / "task.json").write_text("{not json", encoding="utf-8")
        status, output, error = self.run_task("list")
        self.assertEqual(status, 0)
        self.assertEqual(output.splitlines(), [f"{good}  todo  task  good"])
        self.assertIn(broken.name, error)
        self.assertTrue(error.startswith("bkf task: "))
        status, output, error = self.run_task("list", "--json")
        data = json.loads(output)
        self.assertEqual(data["unreadable"], [broken.name])
        self.assertEqual(error, "")

    def test_list_of_an_empty_store_prints_nothing(self) -> None:
        self.assertEqual(self.run_task("list"), (0, "", ""))
        data = json.loads(self.run_task("list", "--json")[1])
        self.assertEqual((data["generation"], data["tasks"]), (0, []))

    # show

    def test_show_prints_key_value_lines(self) -> None:
        task_id = self.new("Shown", "--source", "src")
        status, output, error = self.run_task("show", task_id)
        self.assertEqual((status, error), (0, ""))
        lines = output.splitlines()
        self.assertEqual(lines[0], f"id: {task_id}")
        self.assertIn("title: Shown", lines)
        self.assertIn("status: todo", lines)
        self.assertIn("kind: task", lines)
        self.assertIn("parent: -", lines)
        self.assertIn("attention: -", lines)
        self.assertEqual(
            [line.split(":")[0] for line in lines],
            ["id", "title", "status", "kind", "repo", "parent", "worktree", "branch", "tmux window", "attention", "note"],
        )

    def test_show_json_and_default_id_from_the_environment(self) -> None:
        task_id = self.new("env")
        with patch.dict(os.environ, {"BKF_TASK": task_id}):
            status, output, error = self.run_task("show", "--json")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(json.loads(output)["id"], task_id)

    def test_missing_id_is_refused_when_no_environment_task(self) -> None:
        status, output, error = self.run_task("show")
        self.assertRefused(status, output, error, "pass an id")
        status, output, error = self.run_task("close")
        self.assertRefused(status, output, error, "pass an id")

    def test_unknown_task_is_refused(self) -> None:
        status, output, error = self.run_task("show", "t20000101-000000-0000")
        self.assertRefused(status, output, error, "no task")

    # start

    def test_start_records_session_and_worktree_objects(self) -> None:
        task_id = self.new()
        status, output, error = self.run_task(
            "start", task_id, "--agent", "claude", "--model", "m", "--tmux-window", "w1",
            "--worktree", str(self.repo), "--branch", "feature", "--run-dir", "/runs/x",
        )
        self.assertEqual((status, output, error), (0, "", ""))
        task = task_store.read(self.store, task_id)
        self.assertEqual(task.status, "working")
        self.assertEqual(task.session, {
            "agent": "claude", "model": "m", "effort": None, "reviewer": None,
            "tmux_session": None, "tmux_window": "w1",
        })
        self.assertEqual(task.worktree, {"path": str(self.repo), "branch": "feature", "head": None})
        self.assertEqual(task.run_dir, "/runs/x")

    def test_start_without_options_sets_no_objects(self) -> None:
        task_id = self.new()
        self.assertEqual(self.run_task("start", task_id)[0], 0)
        task = task_store.read(self.store, task_id)
        self.assertEqual((task.status, task.session, task.worktree, task.run_dir), ("working", None, None, None))

    def test_start_of_a_working_task_is_a_rerun_that_clears_its_attention(self) -> None:
        task_id = self.new()
        self.run_task("start", task_id)
        self.run_task("attention", task_id, "--set", "paused", "--note", "report")
        self.assertEqual(self.run_task("start", task_id)[0], 0)
        task = task_store.read(self.store, task_id)
        self.assertEqual((task.status, task.attention), ("working", None))

    def test_start_of_an_unknown_task_is_refused(self) -> None:
        status, output, error = self.run_task("start", "t20000101-000000-0000")
        self.assertRefused(status, output, error, "no task")

    def test_start_after_fail_clears_the_exit_status(self) -> None:
        task_id = self.new()
        self.run_task("start", task_id)
        self.assertEqual(self.run_task("fail", task_id, "--exit", "3", "--note", "boom")[0], 0)
        self.assertEqual(self.run_task("start", task_id)[0], 0)
        task = task_store.read(self.store, task_id)
        self.assertEqual((task.status, task.exit), ("working", None))

    # the removed commands, close

    def test_ready_and_done_are_no_longer_commands(self) -> None:
        task_id = self.new()
        for command in ("ready", "done"):
            with self.subTest(command):
                status, output, error = self.run_task(command, task_id)
                self.assertEqual(status, 2)
                self.assertIn("invalid choice", error)

    def test_close_deletes_the_card_from_any_status(self) -> None:
        for status_name in ("todo", "working", "to-merge", "failed"):
            with self.subTest(status_name):
                task_id = self.new()
                if status_name in ("working", "to-merge", "failed"):
                    self.run_task("start", task_id)
                if status_name == "to-merge":
                    task_store.update(self.store, task_id, task_store.enter_merge)
                if status_name == "failed":
                    self.run_task("fail", task_id)
                self.assertEqual(task_store.read(self.store, task_id).status, status_name)
                with patch.dict(os.environ, {"BKF_TASK": task_id}):
                    self.assertEqual(self.run_task("close")[0], 0)
                self.assertFalse((self.store / task_id).exists())

    def test_close_of_an_unknown_task_is_refused(self) -> None:
        status, output, error = self.run_task("close", "t20000101-000000-0000")
        self.assertRefused(status, output, error, "no task")

    def test_a_card_in_to_merge_is_listed_with_its_status(self) -> None:
        task_id = self.new()
        self.run_task("start", task_id)
        task_store.update(self.store, task_id, task_store.enter_merge)
        status, output, error = self.run_task("list", "--status", "to-merge")
        self.assertEqual((status, error), (0, ""))
        self.assertIn(f"{task_id}  to-merge  task  first", output)
        self.assertEqual(self.run_task("list", "--status", "review")[0], 2)

    def test_merge_failed_is_an_attention_reason(self) -> None:
        task_id = self.new()
        self.run_task("start", task_id)
        self.assertEqual(self.run_task("attention", task_id, "--set", "merge-failed", "--note", "why")[0], 0)
        self.assertEqual(task_store.read(self.store, task_id).attention["reason"], "merge-failed")

    # fail, attention, delete

    def test_fail_records_exit_and_note(self) -> None:
        task_id = self.new()
        self.run_task("start", task_id)
        self.assertEqual(self.run_task("fail", task_id, "--exit", "3", "--note", "boom")[0], 0)
        task = task_store.read(self.store, task_id)
        self.assertEqual((task.status, task.exit, task.note), ("failed", 3, "boom"))

    def test_fail_from_todo_is_refused(self) -> None:
        task_id = self.new()
        status, output, error = self.run_task("fail", task_id)
        self.assertRefused(status, output, error, "a task cannot go from todo to failed")

    def test_attention_sets_and_clears(self) -> None:
        task_id = self.new()
        status, _, error = self.run_task("attention", task_id, "--set", "prompt", "--note", "need a call")
        self.assertEqual((status, error), (0, ""))
        task = task_store.read(self.store, task_id)
        self.assertEqual((task.attention["reason"], task.attention["note"]), ("prompt", "need a call"))
        self.assertIn("attention: prompt since", self.run_task("show", task_id)[1])
        self.assertEqual(self.run_task("attention", task_id, "--clear")[0], 0)
        self.assertIsNone(task_store.read(self.store, task_id).attention)

    def test_attention_accepts_the_plan_run_reasons(self) -> None:
        task_id = self.new()
        for reason in ("escalated", "paused"):
            status, _, error = self.run_task("attention", task_id, "--set", reason, "--note", "stopped")
            self.assertEqual((status, error), (0, ""))
            self.assertEqual(task_store.read(self.store, task_id).attention["reason"], reason)

    def test_attention_with_an_unknown_reason_is_refused(self) -> None:
        task_id = self.new()
        status, output, error = self.run_task("attention", task_id, "--set", "bogus")
        self.assertRefused(status, output, error, "unknown attention reason")

    def test_attention_needs_exactly_one_action(self) -> None:
        task_id = self.new()
        self.assertEqual(self.run_task("attention", task_id)[0], 2)
        self.assertEqual(self.run_task("attention", task_id, "--set", "prompt", "--clear")[0], 2)
        self.assertEqual(self.run_task("attention", task_id, "--clear", "--note", "x")[0], 2)

    def test_delete_removes_the_folder_and_refuses_an_unknown_id(self) -> None:
        task_id = self.new()
        self.assertEqual(self.run_task("delete", task_id), (0, "", ""))
        self.assertFalse((self.store / task_id).exists())
        status, output, error = self.run_task("delete", task_id)
        self.assertRefused(status, output, error, "no task")

    def test_help_for_task_shows_its_usage(self) -> None:
        status, output, error = self.run_task("--help")
        self.assertEqual(status, 0)
        self.assertIn("usage: bkf task", output)
        self.assertEqual(error, "")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            try:
                bkf_cli.main(["help", "task"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.assertIn("usage: bkf task", stdout.getvalue())

    # imports and speed, in fresh processes

    def run_fresh(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ, PYTHONPATH=str(TOOLING))
        return subprocess.run(
            [sys.executable, *arguments], capture_output=True, text=True, check=False,
            env=environment, cwd=str(self.root),
        )

    def test_importing_the_cli_does_not_load_heavy_dependencies(self) -> None:
        code = (
            "import sys\n"
            "import bkf_cli, bkf_task\n"
            "heavy = [name for name in ('ruamel', 'markdown_it', 'jsonschema') if name in sys.modules]\n"
            "print(heavy)\n"
        )
        result = self.run_fresh("-c", code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "[]")

    def test_list_json_with_two_hundred_tasks_is_fast(self) -> None:
        for index in range(200):
            task_store.create(self.store, repo=str(self.repo), title=f"task {index}")
        durations = []
        for _ in range(5):
            started = time.perf_counter()
            result = self.run_fresh("-m", "bkf_cli", "task", "list", "--json")
            durations.append(time.perf_counter() - started)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(result.stdout)["tasks"]), 200)
        average_ms = sum(durations) / len(durations) * 1000
        print(f"\nbkf task list --json with 200 tasks: average {average_ms:.0f} ms over 5 runs", file=sys.stderr)
        self.assertLess(average_ms, 300)

    # output

    def windowed(self, session: str = "repo-ab12cd", window: str = "@41", title: str = "watched") -> str:
        task_id = self.new(title)
        status, _, error = self.run_task("start", task_id, f"--tmux-session={session}", f"--tmux-window={window}")
        self.assertEqual((status, error), (0, ""))
        return task_id

    def fake_tmux(self, returncode: int = 0, stdout: str = "screen\n") -> list[list[str]]:
        calls: list[list[str]] = []

        def runner(args, stdin=None):
            calls.append(list(args))
            return task_tmux.Result(returncode, stdout, "" if returncode == 0 else "can't find window")

        patcher = patch.object(task_tmux, "default_runner", runner)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def card_bytes(self, task_id: str) -> bytes:
        return (self.store / task_id / "task.json").read_bytes()

    def test_output_reads_the_visible_screen_and_two_hundred_history_lines_by_default(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux(stdout="line one\nline two\n")
        status, output, error = self.run_task("output", task_id)
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(calls, [["tmux", "capture-pane", "-p", "-S", "-200", "-t", "repo-ab12cd:@41"]])
        self.assertEqual(output, "line one\nline two\n")

    def test_output_uses_the_tmux_socket_of_the_environment(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        with patch.dict(os.environ, {"BKF_TMUX_SOCKET": "throwaway"}):
            status, _, error = self.run_task("output", task_id, "--lines", "50")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(calls, [["tmux", "-L", "throwaway", "capture-pane", "-p", "-S", "-50", "-t", "repo-ab12cd:@41"]])

    def test_output_with_lines_passes_that_history_size(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        status, output, error = self.run_task("output", task_id, "--lines", "50")
        self.assertEqual((status, error, output), (0, "", "screen\n"))
        self.assertEqual(calls, [["tmux", "capture-pane", "-p", "-S", "-50", "-t", "repo-ab12cd:@41"]])

    def test_output_accepts_the_cap_and_refuses_more(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        status, _, error = self.run_task("output", task_id, "--lines", "5000")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(calls[-1][calls[-1].index("-S") + 1], "-5000")
        self.assertRefused(*self.run_task("output", task_id, "--lines", "5001"), "at most 5000")
        self.assertEqual(len(calls), 1)

    def test_output_refuses_lines_that_are_not_positive_integers(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        for value in ("0", "-3", "abc", "1.5", ""):
            with self.subTest(value=value):
                self.assertRefused(*self.run_task("output", task_id, "--lines", value),
                                   "--lines must be a positive integer")
        self.assertEqual(calls, [])

    def test_output_uses_bkf_task_when_the_id_is_omitted(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        with patch.dict(os.environ, {"BKF_TASK": task_id}):
            status, output, error = self.run_task("output")
        self.assertEqual((status, error, output), (0, "", "screen\n"))
        self.assertEqual(calls[0][-1], "repo-ab12cd:@41")

    def test_output_explicit_id_wins_over_bkf_task(self) -> None:
        current = self.windowed(window="@1", title="current")
        other = self.windowed(window="@2", title="other")
        calls = self.fake_tmux()
        with patch.dict(os.environ, {"BKF_TASK": current}):
            status, _, error = self.run_task("output", other)
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(calls[0][-1], "repo-ab12cd:@2")

    def test_output_without_an_id_outside_a_task_is_refused(self) -> None:
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("output"), "no task id")
        self.assertEqual(calls, [])

    def test_output_unknown_task_is_refused(self) -> None:
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("output", "t20000101-000000-0000"), "no task")
        self.assertEqual(calls, [])

    def test_output_task_without_a_window_is_refused(self) -> None:
        task_id = self.new("no window")
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("output", task_id), f"task {task_id} has no window")
        self.assertEqual(calls, [])

    def test_output_task_with_only_a_session_is_refused(self) -> None:
        task_id = self.new("session only")
        self.run_task("start", task_id, "--tmux-session=repo-ab12cd")
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("output", task_id), f"task {task_id} has no window")
        self.assertEqual(calls, [])

    def test_output_closed_window_or_no_tmux_server_is_refused(self) -> None:
        task_id = self.windowed()
        self.fake_tmux(returncode=1)
        self.assertRefused(*self.run_task("output", task_id), f"the window of task {task_id} is closed")

    def test_output_without_tmux_is_refused(self) -> None:
        task_id = self.windowed()
        self.fake_tmux(returncode=127)
        self.assertRefused(*self.run_task("output", task_id), "tmux is not installed")

    def test_output_refuses_hostile_names_before_any_process_starts(self) -> None:
        cases = [
            ("-x", "@41"),           # leading dash
            ("repo", "-@41"),        # leading dash in the window
            ("repo", "@41:0"),       # colon in the window
            ("re\npo", "@41"),       # line break in the session
            ("repo", "@4\n1"),       # line break in the window
            ("re po", "@41"),        # space
        ]
        calls = self.fake_tmux()
        for session, window in cases:
            with self.subTest(session=session, window=window):
                task_id = self.windowed(session=session, window=window, title=f"hostile {len(calls)}")
                self.assertRefused(*self.run_task("output", task_id), "not a tmux session and window name")
        self.assertEqual(calls, [])

    def test_output_never_changes_the_card(self) -> None:
        task_id = self.windowed()
        before = self.card_bytes(task_id)
        generation = task_store.generation(self.store)
        self.fake_tmux()
        self.run_task("output", task_id, "--lines", "10")
        self.assertEqual(self.card_bytes(task_id), before)
        self.assertEqual(task_store.generation(self.store), generation)

    # send

    def test_send_types_the_text_and_then_enter_and_prints_nothing(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        self.assertEqual(self.run_task("send", task_id, "--text", "hello"), (0, "", ""))
        self.assertEqual(calls, [
            ["tmux", "send-keys", "-t", "repo-ab12cd:@41", "-l", "--", "hello"],
            ["tmux", "send-keys", "-t", "repo-ab12cd:@41", "Enter"],
        ])

    def test_send_text_starting_with_a_dash_is_typed_as_text(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        status, output, error = self.run_task("send", task_id, "--text=-rf --help")
        self.assertEqual((status, output, error), (0, "", ""))
        self.assertEqual(calls[0], ["tmux", "send-keys", "-t", "repo-ab12cd:@41", "-l", "--", "-rf --help"])

    def test_send_no_enter_types_the_text_only(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        self.assertEqual(self.run_task("send", task_id, "--text", "draft", "--no-enter"), (0, "", ""))
        self.assertEqual(calls, [["tmux", "send-keys", "-t", "repo-ab12cd:@41", "-l", "--", "draft"]])

    def test_send_multi_line_message_from_a_file_and_from_standard_input(self) -> None:
        task_id = self.windowed()
        message = self.root / "message.txt"
        message.write_text("one\ntwo\n", encoding="utf-8")
        calls = self.fake_tmux()
        self.assertEqual(self.run_task("send", task_id, "--message-file", str(message)), (0, "", ""))
        self.assertEqual([call[-1] for call in calls], ["one", "Enter", "two", "Enter"])
        calls.clear()
        self.assertEqual(self.run_task("send", task_id, "--message-file", "-", stdin="from stdin"), (0, "", ""))
        self.assertEqual([call[-1] for call in calls], ["from stdin", "Enter"])

    def test_send_uses_bkf_task_when_the_id_is_omitted_and_the_socket_of_the_environment(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        with patch.dict(os.environ, {"BKF_TASK": task_id, "BKF_TMUX_SOCKET": "throwaway"}):
            status, _, error = self.run_task("send", "--text", "hi", "--no-enter")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(calls, [["tmux", "-L", "throwaway", "send-keys", "-t", "repo-ab12cd:@41", "-l", "--", "hi"]])

    def test_send_needs_exactly_one_of_text_and_message_file(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        self.assertEqual(self.run_task("send", task_id)[0], 2)
        self.assertEqual(self.run_task("send", task_id, "--text", "a", "--message-file", "-")[0], 2)
        self.assertEqual(calls, [])

    def test_send_missing_message_file_is_refused(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("send", task_id, "--message-file", str(self.root / "missing.txt")),
                           "missing.txt")
        self.assertEqual(calls, [])

    def test_send_empty_or_too_long_text_is_refused(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("send", task_id, "--text", ""), "the message is empty")
        self.assertRefused(*self.run_task("send", task_id, "--text", "x" * 10001), "longer than 10000 characters")
        self.assertEqual(calls, [])

    def test_send_control_characters_are_refused(self) -> None:
        task_id = self.windowed()
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("send", task_id, "--text", "\x1b[A"), "control character")
        self.assertEqual(calls, [])

    def test_send_hostile_window_names_are_refused_before_any_process_starts(self) -> None:
        calls = self.fake_tmux()
        for session, window in (("-x", "@41"), ("repo", "@41:0"), ("re po", "@41"), ("re\npo", "@41")):
            with self.subTest(session=session, window=window):
                task_id = self.windowed(session=session, window=window, title=f"hostile {len(calls)}")
                self.assertRefused(*self.run_task("send", task_id, "--text", "x"), "not a tmux session and window name")
        self.assertEqual(calls, [])

    def test_send_task_without_a_window_is_refused(self) -> None:
        task_id = self.new("no window")
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("send", task_id, "--text", "x"), f"task {task_id} has no window")
        self.assertEqual(calls, [])

    def test_send_closed_window_or_no_tmux_server_is_refused(self) -> None:
        task_id = self.windowed()
        self.fake_tmux(returncode=1)
        self.assertRefused(*self.run_task("send", task_id, "--text", "x"), f"the window of task {task_id} is closed")

    def test_send_without_tmux_is_refused(self) -> None:
        task_id = self.windowed()
        self.fake_tmux(returncode=127)
        self.assertRefused(*self.run_task("send", task_id, "--text", "x"), "tmux is not installed")

    def test_send_without_an_id_outside_a_task_or_for_an_unknown_task_is_refused(self) -> None:
        calls = self.fake_tmux()
        self.assertRefused(*self.run_task("send", "--text", "x"), "no task id")
        self.assertRefused(*self.run_task("send", "t20000101-000000-0000", "--text", "x"), "no task")
        self.assertEqual(calls, [])

    def test_send_never_changes_the_card(self) -> None:
        task_id = self.windowed()
        before = self.card_bytes(task_id)
        generation = task_store.generation(self.store)
        self.fake_tmux()
        self.run_task("send", task_id, "--text", "hello")
        self.assertEqual(self.card_bytes(task_id), before)
        self.assertEqual(task_store.generation(self.store), generation)


if __name__ == "__main__":
    unittest.main()

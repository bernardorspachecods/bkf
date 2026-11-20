from __future__ import annotations

import copy
import json
import multiprocessing
import os
import re
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import task_store
from task_store import (
    CorruptTask, InvalidId, InvalidTransition, InvalidValue, Task, TaskError, UnknownTask,
    clear_attention, create, delete, generation, is_valid_id, list_tasks, mark_done, mark_failed,
    mark_ready, read, read_prompt, repo_identity, set_attention, start, store_dir, update, write_prompt,
)


NOW = datetime(2026, 11, 20, 14, 30, 5, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 20, 15, 0, 0, tzinfo=timezone.utc)
ID_SHAPE = re.compile(r"t[0-9]{8}-[0-9]{6}-[0-9a-f]{4}")


def add_one(store: str, task_id: str, count: int) -> None:
    """Run in a child process: count times, read the note as an integer and write it plus one."""
    def bump(task: Task) -> None:
        task.note = str(int(task.note or "0") + 1)

    for _ in range(count):
        update(Path(store), task_id, bump)


class TempStore(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        self.store = self.root / "tasks"

    def tearDown(self) -> None:
        self._dir.cleanup()

    def make(self, title: str = "A task", **kwargs) -> Task:
        kwargs.setdefault("repo", "/example/repo")
        return create(self.store, title=title, now=NOW, **kwargs)


class StoreDirTests(unittest.TestCase):
    def test_bkf_tasks_dir_wins(self) -> None:
        env = {"BKF_TASKS_DIR": "/x/tasks", "XDG_STATE_HOME": "/y", "HOME": "/home/u"}
        self.assertEqual(store_dir(env), Path("/x/tasks"))

    def test_empty_bkf_tasks_dir_is_ignored(self) -> None:
        env = {"BKF_TASKS_DIR": "", "XDG_STATE_HOME": "/y", "HOME": "/home/u"}
        self.assertEqual(store_dir(env), Path("/y/bkf/tasks"))

    def test_xdg_state_home(self) -> None:
        self.assertEqual(store_dir({"XDG_STATE_HOME": "/y"}), Path("/y/bkf/tasks"))

    def test_empty_xdg_is_ignored(self) -> None:
        env = {"XDG_STATE_HOME": "", "HOME": "/home/u"}
        self.assertEqual(store_dir(env), Path("/home/u/.local/state/bkf/tasks"))

    def test_reading_does_not_create_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = Path(root) / "missing"
            self.assertEqual(list_tasks(store).tasks, [])
            self.assertEqual(generation(store), 0)
            self.assertFalse(store.exists())


class IdTests(TempStore):
    def test_is_valid_id(self) -> None:
        self.assertTrue(is_valid_id("t20261120-143005-a3f1"))
        self.assertTrue(is_valid_id("a" * 64))
        self.assertFalse(is_valid_id("a" * 65))
        self.assertFalse(is_valid_id(""))
        self.assertFalse(is_valid_id("A"))
        self.assertFalse(is_valid_id(".hidden"))
        self.assertFalse(is_valid_id("../x"))
        self.assertFalse(is_valid_id("a_b"))

    def test_created_ids_have_the_documented_shape(self) -> None:
        task = self.make()
        self.assertRegex(task.id, ID_SHAPE)

    def test_outside_ids_are_rejected_before_any_path_is_built(self) -> None:
        outside = self.root / "x"
        outside.mkdir()
        (outside / "task.json").write_text("not json", encoding="utf-8")
        self.make()
        with self.assertRaises(InvalidId):
            read(self.store, "../x")
        with self.assertRaises(InvalidId):
            delete(self.store, "../x")
        with self.assertRaises(InvalidId):
            write_prompt(self.store, "../x", "text")
        with self.assertRaises(InvalidId):
            update(self.store, "../x", lambda task: None)
        self.assertTrue((outside / "task.json").exists())


class RecordTests(TempStore):
    def test_create_and_read_round_trip(self) -> None:
        task = create(
            self.store, repo="/example/repo", title="  Fix\nthe  parser  ", kind="unit", body="Body text.",
            source="https://example.com/a", parent="t20261120-000000-0000", now=NOW,
        )
        loaded = read(self.store, task.id)
        self.assertEqual(loaded, task)
        self.assertEqual(loaded.title, "Fix the  parser")
        self.assertEqual(loaded.kind, "unit")
        self.assertEqual(loaded.status, "todo")
        self.assertEqual(loaded.body, "Body text.")
        self.assertEqual(loaded.source, "https://example.com/a")
        self.assertEqual(loaded.parent, "t20261120-000000-0000")
        self.assertEqual(loaded.created, "2026-11-20T14:30:05Z")
        self.assertEqual(loaded.updated, "2026-11-20T14:30:05Z")
        for name in ("attention", "session", "worktree", "run_dir", "exit", "note"):
            self.assertIsNone(getattr(loaded, name))

    def test_file_on_disk_is_sorted_indented_json(self) -> None:
        task = self.make()
        text = (self.store / task.id / "task.json").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n"))
        data = json.loads(text)
        self.assertEqual(data["schema"], 1)
        self.assertEqual(text, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def test_invalid_create_values_are_refused(self) -> None:
        with self.assertRaises(InvalidValue):
            self.make(kind="bogus")
        with self.assertRaises(InvalidValue):
            self.make(title="   ")
        with self.assertRaises(InvalidValue):
            self.make(repo="two\nlines")
        with self.assertRaises(InvalidValue):
            self.make(parent="../up")
        self.assertEqual(list_tasks(self.store).tasks, [])

    def test_a_corrupt_file_is_unreadable_and_the_good_ones_still_list(self) -> None:
        good = self.make("good")
        bad = self.make("bad")
        self.damage(bad.id, lambda data: data.pop("status"))
        result = list_tasks(self.store)
        self.assertEqual([task.id for task in result.tasks], [good.id])
        self.assertEqual(result.unreadable, [bad.id])
        with self.assertRaises(CorruptTask):
            read(self.store, bad.id)

    def damage(self, task_id: str, change) -> None:
        path = self.store / task_id / "task.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_from_json_rejects_each_kind_of_corrupt_record(self) -> None:
        base = self.make().to_json()
        cases = {
            "wrong schema": lambda data: data.update(schema=2),
            "missing key": lambda data: data.pop("repo"),
            "wrong type": lambda data: data.update(exit="3"),
            "bool exit": lambda data: data.update(exit=True),
            "unknown status": lambda data: data.update(status="started"),
            "unknown kind": lambda data: data.update(kind="other"),
            "id differs from folder": lambda data: data.update(id="t20261120-000000-0000"),
            "bad attention reason": lambda data: data.update(attention={"reason": "sleepy", "since": "2026-11-20T14:30:05Z", "note": None}),
            "bad timestamp": lambda data: data.update(created="2026-11-20 14:30:05"),
            "bad session": lambda data: data.update(session={"agent": "x"}),
            "empty title": lambda data: data.update(title=""),
        }
        for label, change in cases.items():
            with self.subTest(label):
                data = copy.deepcopy(base)
                change(data)
                with self.assertRaises(CorruptTask):
                    Task.from_json(data, base["id"])
        with self.assertRaises(CorruptTask):
            Task.from_json([], base["id"])

    def test_unreadable_json_is_corrupt(self) -> None:
        task = self.make()
        (self.store / task.id / "task.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(CorruptTask):
            read(self.store, task.id)
        self.assertEqual(list_tasks(self.store).unreadable, [task.id])

    def test_missing_task_json_is_corrupt(self) -> None:
        task = self.make()
        (self.store / task.id / "task.json").unlink()
        self.assertEqual(list_tasks(self.store).unreadable, [task.id])

    def test_listing_order_and_ignored_entries(self) -> None:
        first = self.make("first")
        second = self.make("second")
        (self.store / "stray.txt").write_text("x", encoding="utf-8")
        (self.store / ".tmp-leftover").mkdir()
        (self.store / ".tmp-leftover" / "task.json").write_text("{}", encoding="utf-8")
        (self.store / "Not_An_Id").mkdir()
        result = list_tasks(self.store)
        self.assertEqual([task.id for task in result.tasks], sorted([first.id, second.id]))
        self.assertEqual(result.unreadable, [])


class TransitionTests(unittest.TestCase):
    def task(self, status: str) -> Task:
        return Task(
            id="t20261120-143005-a3f1", kind="task", parent=None, repo="/r", title="T", body="",
            source=None, status=status, attention=None, session=None, worktree=None, run_dir=None,
            exit=None, note=None, created="2026-11-20T14:30:05Z", updated="2026-11-20T14:30:05Z",
        )

    def test_start_from_todo_and_failed(self) -> None:
        for status in ("todo", "failed"):
            with self.subTest(status):
                task = self.task(status)
                task.exit = 2
                start(task, session={"agent": "claude"}, worktree={"path": "/w"}, run_dir="/runs/1")
                self.assertEqual(task.status, "working")
                self.assertIsNone(task.exit)
                self.assertEqual(task.session["agent"], "claude")
                self.assertIsNone(task.session["model"])
                self.assertEqual(task.worktree["path"], "/w")
                self.assertEqual(task.run_dir, "/runs/1")

    def test_mark_ready_creates_and_fills_worktree(self) -> None:
        task = self.task("working")
        mark_ready(task, branch="agent/x", head="abc", note="Ready.")
        self.assertEqual(task.status, "review")
        self.assertEqual(task.worktree, {"path": None, "branch": "agent/x", "head": "abc"})
        self.assertEqual(task.note, "Ready.")
        mark_ready(task, head="def")
        self.assertEqual(task.status, "review")
        self.assertEqual(task.worktree["head"], "def")
        self.assertEqual(task.worktree["branch"], "agent/x")

    def test_mark_done_and_mark_failed(self) -> None:
        done = self.task("review")
        set_attention(done, "still", now=NOW)
        mark_done(done)
        self.assertEqual(done.status, "done")
        self.assertIsNone(done.attention)
        failed = self.task("working")
        mark_failed(failed, exit=1, note="boom")
        self.assertEqual((failed.status, failed.exit, failed.note), ("failed", 1, "boom"))

    def test_set_and_clear_attention(self) -> None:
        task = self.task("working")
        set_attention(task, "prompt", note="Needs an answer", now=NOW)
        failed = self.task("failed")
        set_attention(failed, "launch-failed", note="boom", now=NOW)
        self.assertEqual(failed.attention["reason"], "launch-failed")
        with self.assertRaises(InvalidTransition):
            set_attention(self.task("done"), "still", now=NOW)
        self.assertEqual(task.attention, {"reason": "prompt", "since": "2026-11-20T14:30:05Z", "note": "Needs an answer"})
        self.assertEqual(task.status, "working")
        clear_attention(task)
        self.assertIsNone(task.attention)
        with self.assertRaises(InvalidValue):
            set_attention(task, "sleepy", now=NOW)
        set_attention(task, "escalated", note="takeover", now=NOW)
        set_attention(task, "paused", note="after step 2", now=NOW)
        self.assertEqual((task.attention["reason"], task.attention["note"]), ("paused", "after step 2"))

    def test_allowed_and_refused_transitions(self) -> None:
        allowed = [
            (start, "todo", {}), (start, "failed", {}),
            (mark_ready, "working", {}), (mark_ready, "review", {}),
            (mark_done, "working", {}), (mark_done, "review", {}),
            (mark_failed, "working", {}),
        ]
        for function, status, kwargs in allowed:
            with self.subTest(function.__name__, status=status):
                function(self.task(status), **kwargs)
        refused = [
            (start, "working"), (start, "review"), (start, "done"),
            (mark_ready, "todo"), (mark_ready, "done"), (mark_ready, "failed"),
            (mark_done, "todo"), (mark_done, "done"), (mark_done, "failed"),
            (mark_failed, "todo"), (mark_failed, "review"), (mark_failed, "done"),
        ]
        for function, status in refused:
            with self.subTest(function.__name__, status=status):
                task = self.task(status)
                with self.assertRaises(InvalidTransition) as context:
                    function(task)
                self.assertEqual(context.exception.from_status, status)
                self.assertEqual(task.status, status)
        for status in ("done",):
            with self.subTest("attention", status=status):
                with self.assertRaises(InvalidTransition):
                    set_attention(self.task(status), "still", now=NOW)


class WriteTests(TempStore):
    def test_generation_grows_by_one_per_write_only(self) -> None:
        self.assertEqual(generation(self.store), 0)
        task = self.make()
        self.assertEqual(generation(self.store), 1)
        read(self.store, task.id)
        list_tasks(self.store)
        read_prompt(self.store, task.id)
        self.assertEqual(generation(self.store), 1)
        write_prompt(self.store, task.id, "Prompt")
        self.assertEqual(generation(self.store), 2)
        update(self.store, task.id, lambda item: setattr(item, "title", "Renamed"), now=LATER)
        self.assertEqual(generation(self.store), 3)
        delete(self.store, task.id)
        self.assertEqual(generation(self.store), 4)

    def test_failed_change_writes_nothing(self) -> None:
        task = self.make()
        before = (self.store / task.id / "task.json").read_text(encoding="utf-8")
        with self.assertRaises(InvalidTransition):
            update(self.store, task.id, mark_done)
        with self.assertRaises(RuntimeError):
            update(self.store, task.id, self.raiser)
        self.assertEqual((self.store / task.id / "task.json").read_text(encoding="utf-8"), before)
        self.assertEqual(generation(self.store), 1)

    @staticmethod
    def raiser(task: Task) -> None:
        task.title = "Changed"
        raise RuntimeError("stop")

    def test_update_sets_updated_and_keeps_created(self) -> None:
        task = self.make()
        changed = update(self.store, task.id, lambda item: start(item, run_dir="/runs/x"), now=LATER)
        self.assertEqual(changed.updated, "2026-11-20T15:00:00Z")
        self.assertEqual(changed.created, "2026-11-20T14:30:05Z")
        self.assertEqual(read(self.store, task.id).run_dir, "/runs/x")

    def test_prompt_round_trip_and_missing_task(self) -> None:
        task = self.make()
        self.assertIsNone(read_prompt(self.store, task.id))
        write_prompt(self.store, task.id, "Line one\r\nLine two\n")
        self.assertEqual(read_prompt(self.store, task.id), "Line one\r\nLine two\n")
        with self.assertRaises(UnknownTask):
            write_prompt(self.store, "t20261120-000000-0000", "x")
        with self.assertRaises(UnknownTask):
            read_prompt(self.store, "t20261120-000000-0000")

    def test_delete_removes_the_folder(self) -> None:
        task = self.make()
        delete(self.store, task.id)
        self.assertFalse((self.store / task.id).exists())
        with self.assertRaises(UnknownTask):
            read(self.store, task.id)
        with self.assertRaises(UnknownTask):
            delete(self.store, task.id)

    def test_unknown_task_on_read_and_update(self) -> None:
        self.make()
        with self.assertRaises(UnknownTask):
            read(self.store, "t20261120-000000-0000")
        with self.assertRaises(UnknownTask):
            update(self.store, "t20261120-000000-0000", lambda item: None)

    def test_errors_are_task_errors(self) -> None:
        for error in (InvalidId, InvalidValue, UnknownTask, CorruptTask, InvalidTransition):
            self.assertTrue(issubclass(error, TaskError))

    def test_concurrent_processes_do_not_lose_updates(self) -> None:
        task = self.make()
        update(self.store, task.id, lambda item: setattr(item, "note", "0"))
        before = generation(self.store)
        processes = [
            multiprocessing.Process(target=add_one, args=(str(self.store), task.id, 50)) for _ in range(2)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(120)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(read(self.store, task.id).note, "100")
        self.assertEqual(generation(self.store), before + 100)


class RepoIdentityTests(unittest.TestCase):
    def git(self, *args: str, cwd: Path) -> None:
        env = {
            "PATH": os.environ.get("PATH", ""), "HOME": str(cwd),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
        subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)

    def test_linked_worktree_shares_the_identity_of_its_repository(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root) / "repo"
            repo.mkdir()
            self.git("init", "-q", cwd=repo)
            self.git("commit", "-q", "--allow-empty", "-m", "start", cwd=repo)
            linked = Path(root) / "linked"
            self.git("worktree", "add", "-q", str(linked), cwd=repo)
            self.assertEqual(repo_identity(repo), repo_identity(linked))
            self.assertEqual(repo_identity(repo), str(repo.resolve()))

    def test_plain_folder_gives_its_resolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "plain"
            folder.mkdir()
            self.assertEqual(repo_identity(folder), str(folder.resolve()))


if __name__ == "__main__":
    unittest.main()

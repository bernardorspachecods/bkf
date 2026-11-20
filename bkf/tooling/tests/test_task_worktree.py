from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bkf_cli
import task_store
import task_worktree
from task_worktree import WorktreeError, prepare, slug


GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def git(cwd: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *arguments], capture_output=True, text=True, check=True,
        env={**os.environ, **GIT_IDENTITY},
    )
    return result.stdout.strip()


class WorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.store = self.root / "store"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "file.txt").write_text("one\n", encoding="utf-8")
        git(self.repo, "add", "file.txt")
        git(self.repo, "commit", "-q", "-m", "first")
        environment = patch.dict(os.environ, {"BKF_TASKS_DIR": str(self.store)})
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("BKF_TASK", None)

    def new_task(self, title: str = "First task", repo: Path | None = None) -> task_store.Task:
        return task_store.create(
            self.store, repo=task_store.repo_identity(repo or self.repo), title=title,
        )

    def worktree_path(self, task: task_store.Task) -> Path:
        return self.repo / ".claude" / "worktrees" / slug(task.title, task.id)

    def exclude_lines(self) -> list[str]:
        path = Path(git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "info" / "exclude"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def run_task(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                status = bkf_cli.main(["task", *arguments])
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def test_creates_from_head_and_records_the_card(self) -> None:
        task = self.new_task("Ecrã de início!")
        prepared = prepare(self.store, task.id)
        path = self.worktree_path(task)
        self.assertEqual(prepared.path, str(path))
        self.assertEqual(prepared.branch, f"task/ecra-de-inicio-{task.id[-4:]}")
        self.assertTrue(prepared.created)
        self.assertEqual(git(path, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(git(path, "rev-parse", "--abbrev-ref", "HEAD"), prepared.branch)
        stored = task_store.read(self.store, task.id)
        self.assertEqual(stored.worktree, {"path": prepared.path, "branch": prepared.branch, "head": None})
        self.assertEqual(stored.status, "todo")

    def test_base_option_starts_the_branch_from_the_revision(self) -> None:
        git(self.repo, "branch", "side")
        side = git(self.repo, "rev-parse", "side")
        (self.repo / "file.txt").write_text("two\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "second")
        task = self.new_task()
        prepared = prepare(self.store, task.id, base="side")
        self.assertEqual(git(Path(prepared.path), "rev-parse", "HEAD"), side)

    def test_unknown_base_is_refused_and_nothing_is_created(self) -> None:
        task = self.new_task()
        with self.assertRaisesRegex(WorktreeError, "unknown base revision: nope"):
            prepare(self.store, task.id, base="nope")
        self.assertFalse(self.worktree_path(task).exists())
        self.assertIsNone(task_store.read(self.store, task.id).worktree)

    def test_card_linked_through_a_linked_worktree_lands_in_the_main_checkout(self) -> None:
        linked = self.root / "linked"
        git(self.repo, "worktree", "add", "-q", "-b", "other", str(linked))
        status, output, error = self.run_task("new", "--repo", str(linked), "--title", "Linked")
        self.assertEqual((status, error), (0, ""))
        task_id = output.strip()
        prepared = prepare(self.store, task_id)
        self.assertTrue(prepared.path.startswith(str(self.repo / ".claude" / "worktrees")), prepared.path)

    def test_reuses_its_own_worktree(self) -> None:
        task = self.new_task()
        first = prepare(self.store, task.id)
        second = prepare(self.store, task.id)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual((first.path, first.branch), (second.path, second.branch))

    def test_refuses_a_path_that_holds_another_branch(self) -> None:
        task = self.new_task()
        path = self.worktree_path(task)
        path.parent.mkdir(parents=True)
        git(self.repo, "worktree", "add", "-q", "-b", "other", str(path))
        with self.assertRaisesRegex(WorktreeError, rf"{path}.*a worktree on other"):
            prepare(self.store, task.id)
        self.assertIsNone(task_store.read(self.store, task.id).worktree)

    def test_refuses_a_plain_folder_at_the_path(self) -> None:
        task = self.new_task()
        path = self.worktree_path(task)
        path.mkdir(parents=True)
        with self.assertRaisesRegex(WorktreeError, rf"{path}.*a folder that is not a worktree"):
            prepare(self.store, task.id)

    def test_existing_branch_without_worktree_is_checked_out_and_base_is_ignored(self) -> None:
        task = self.new_task()
        name = slug(task.title, task.id)
        old = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "branch", f"task/{name}")
        (self.repo / "file.txt").write_text("two\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "second")
        prepared = prepare(self.store, task.id, base="HEAD")
        self.assertTrue(prepared.created)
        self.assertEqual(git(Path(prepared.path), "rev-parse", "HEAD"), old)

    def test_exclude_line_is_added_once(self) -> None:
        task = self.new_task()
        prepare(self.store, task.id)
        prepare(self.store, task.id)
        self.assertEqual(self.exclude_lines().count("/.claude/worktrees/"), 1)

    def test_exclude_line_is_not_added_when_already_ignored(self) -> None:
        (self.repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
        task = self.new_task()
        prepare(self.store, task.id)
        self.assertNotIn("/.claude/worktrees/", self.exclude_lines())

    def test_non_git_repository_is_refused(self) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        task = self.new_task(repo=plain)
        with self.assertRaisesRegex(WorktreeError, f"not a git repository: {plain}"):
            prepare(self.store, task.id)

    def test_status_other_than_todo_working_or_failed_is_refused_before_git_runs(self) -> None:
        task = self.new_task()
        task_store.update(self.store, task.id, task_store.start)
        task_store.update(self.store, task.id, task_store.mark_done)
        with patch.object(task_worktree, "_git", side_effect=AssertionError("git ran")):
            with self.assertRaisesRegex(WorktreeError, "todo, working or failed"):
                prepare(self.store, task.id)
        self.assertFalse(self.worktree_path(task).exists())

    def test_failed_task_gets_its_worktree_created_when_missing(self) -> None:
        task = self.new_task()
        task_store.update(self.store, task.id, task_store.start)
        task_store.update(self.store, task.id, task_store.mark_failed)
        prepared = prepare(self.store, task.id)
        self.assertTrue(prepared.created)
        self.assertTrue(os.path.isdir(prepared.path))
        self.assertEqual(task_store.read(self.store, task.id).status, "failed")

    def test_failed_task_reuses_its_existing_worktree(self) -> None:
        task = self.new_task()
        first = prepare(self.store, task.id)
        task_store.update(self.store, task.id, task_store.start)
        task_store.update(self.store, task.id, task_store.mark_failed)
        second = prepare(self.store, task.id)
        self.assertFalse(second.created)
        self.assertEqual((first.path, first.branch), (second.path, second.branch))

    def test_working_task_is_accepted_and_keeps_its_status(self) -> None:
        task = self.new_task()
        task_store.update(self.store, task.id, task_store.start)
        prepared = prepare(self.store, task.id)
        self.assertTrue(prepared.created)
        self.assertEqual(task_store.read(self.store, task.id).status, "working")

    def test_slug_folds_accents_and_symbols(self) -> None:
        self.assertEqual(slug("Ecrã de início!", "t20261120-143005-a3f1"), "ecra-de-inicio-a3f1")

    def test_slug_of_symbols_only_is_task(self) -> None:
        self.assertEqual(slug("!!! ???", "t20261120-143005-a3f1"), "task-a3f1")

    def test_slug_cuts_a_long_title_at_thirty_characters(self) -> None:
        self.assertEqual(slug("a" * 50, "t20261120-143005-a3f1"), "a" * 30 + "-a3f1")

    def test_slug_trims_a_dash_left_by_the_cut(self) -> None:
        title = "abcdefghijklmnopqrstuvwxyzabc de"
        self.assertEqual(slug(title, "t20261120-143005-a3f1"), "abcdefghijklmnopqrstuvwxyzabc-a3f1")

    def test_cli_plain_output_is_path_then_branch(self) -> None:
        task = self.new_task()
        status, output, error = self.run_task("worktree", task.id)
        self.assertEqual((status, error), (0, ""))
        lines = output.splitlines()
        self.assertEqual(lines[0], str(self.worktree_path(task)))
        self.assertEqual(lines[1], f"task/{slug(task.title, task.id)}")

    def test_cli_json_output_reports_created(self) -> None:
        task = self.new_task()
        status, output, _ = self.run_task("worktree", task.id, "--json")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output), {
            "path": str(self.worktree_path(task)),
            "branch": f"task/{slug(task.title, task.id)}",
            "created": True,
        })
        status, output, _ = self.run_task("worktree", task.id, "--json")
        self.assertFalse(json.loads(output)["created"])

    def test_cli_refusal_is_one_line_with_exit_one(self) -> None:
        task = self.new_task()
        task_store.update(self.store, task.id, task_store.start)
        task_store.update(self.store, task.id, task_store.mark_done)
        status, output, error = self.run_task("worktree", task.id)
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertTrue(error.startswith("bkf task: "), error)
        self.assertEqual(error.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()

"""Tests for merge_queue.py against throwaway git repositories."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_queue.py"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
}


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True,
                          capture_output=True, text=True, env=ENV).stdout.strip()


class QueueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "shared.txt").write_text("one\ntwo\nthree\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        self.env = {**ENV, "BKF_TASKS_DIR": str(self.root / "tasks")}  # never the real store

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, name, files):
        """A linked worktree on its own branch with one commit of `files`."""
        wt = self.root / name
        git(self.repo, "worktree", "add", "-q", "-b", name, str(wt))
        for rel, text in files.items():
            (wt / rel).write_text(text)
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", f"work of {name}")
        return wt

    def run_queue(self, cwd, *args, expect=0):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd,
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, expect, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def register(self, name, wt, **over):
        args = ["register", "--session", f"{name} [abc]", "--branch", name,
                "--plans", "plans/p1.md", "--deviations", "notes/d1.md",
                "--base", git(self.repo, "rev-parse", "main"),
                "--fast", "pass", "--full", "pass"]
        for key, value in over.items():
            args[args.index(f"--{key}") + 1] = value
        return self.run_queue(wt, *args)

    def queue_dir(self):
        return Path(git(self.repo, "rev-parse", "--path-format=absolute",
                        "--git-common-dir")) / "bkf-merge-queue"


class RegisterTests(QueueCase):
    def test_entry_is_shared_by_every_worktree_and_lists_changed_files(self):
        wt = self.session("a", {"a.txt": "a\n"})
        self.register("a", wt)
        out = self.run_queue(self.repo, "list")  # read from the main checkout
        self.assertIn("a [abc]", out)
        self.assertIn("a.txt", out)
        entry = json.loads(next((self.queue_dir() / "entries").glob("*.json")).read_text())
        self.assertEqual(entry["head"], git(wt, "rev-parse", "HEAD"))
        self.assertEqual(entry["plans"], ["plans/p1.md"])
        self.assertEqual(entry["deviations"], ["notes/d1.md"])
        self.assertEqual(entry["worktree"], str(wt))

    def test_refuses_when_a_test_level_did_not_pass(self):
        wt = self.session("a", {"a.txt": "a\n"})
        out = self.run_queue(wt, "register", "--session", "a [abc]", "--branch", "a",
                             "--plans", "p.md",
                             "--base", "x", "--fast", "pass", "--full", "fail", expect=1)
        self.assertIn("full", out)
        self.assertFalse((self.queue_dir() / "entries").exists()
                         and any((self.queue_dir() / "entries").iterdir()))

    def test_list_marks_an_entry_stale_when_the_branch_moved(self):
        wt = self.session("a", {"a.txt": "a\n"})
        self.register("a", wt)
        (wt / "more.txt").write_text("x\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", "more")
        self.assertIn("STALE", self.run_queue(self.repo, "list"))


class BusyAndUnregisterTests(QueueCase):
    def test_busy_is_quiet_and_creates_nothing_when_the_repo_has_no_queue(self):
        self.run_queue(self.repo, "busy")
        self.assertFalse(self.queue_dir().exists())

    def test_busy_names_the_queued_session(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        self.assertIn("a [abc]", self.run_queue(self.repo, "busy", expect=1))

    def test_busy_while_an_integration_is_in_progress(self):
        wa = self.session("a", {"shared.txt": "one\nA\nthree\n"})
        wb = self.session("b", {"shared.txt": "one\nB\nthree\n"})
        self.register("a", wa)
        self.register("b", wb)
        self.run_queue(self.repo, "integrate", "--fast-check", "true",
                       "--full-check", "true", expect=2)
        self.assertIn("integration", self.run_queue(self.repo, "busy", expect=1))

    def test_unregister_removes_the_entry_and_frees_the_queue(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        self.run_queue(self.repo, "unregister", "--session", "a [abc]")
        self.run_queue(self.repo, "busy")

    def test_unregister_of_an_unknown_session_fails(self):
        self.run_queue(self.repo, "unregister", "--session", "nobody", expect=1)


class IntegrateTests(QueueCase):
    PASS = ["--fast-check", "true", "--full-check", "true"]

    def test_clean_batch_fast_forwards_main_and_clears_the_queue(self):
        wa = self.session("a", {"a.txt": "a\n"})
        wb = self.session("b", {"b.txt": "b\n"})
        self.register("a", wa)
        self.register("b", wb)
        self.run_queue(self.repo, "integrate", *self.PASS)
        self.assertTrue((self.repo / "a.txt").exists() and (self.repo / "b.txt").exists())
        self.assertEqual(list((self.queue_dir() / "entries").glob("*.json")), [])
        self.assertNotIn("bkf-integration", git(self.repo, "branch", "--list"))

    def test_integrated_sessions_lose_their_worktree_and_branch(self):
        wa = self.session("a", {"a.txt": "a\n"})
        wb = self.session("b", {"b.txt": "b\n"})
        self.register("a", wa)
        self.register("b", wb)
        out = self.run_queue(self.repo, "integrate", *self.PASS)
        self.assertFalse(wa.exists() or wb.exists())
        branches = git(self.repo, "branch", "--list", "a", "b")
        self.assertEqual(branches, "")
        self.assertIn("Removed", out)

    def test_dirty_worktree_is_left_and_reported_but_still_merged(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        (wa / "scratch.txt").write_text("untracked\n")
        out = self.run_queue(self.repo, "integrate", *self.PASS)
        self.assertTrue((self.repo / "a.txt").exists())
        self.assertTrue(wa.exists())
        self.assertIn("Left", out)
        self.assertIn(str(wa), out)

    def test_session_in_the_main_checkout_is_not_removed(self):
        git(self.repo, "switch", "-q", "-c", "m")
        (self.repo / "m.txt").write_text("m\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "m")
        git(self.repo, "worktree", "add", "-q", str(self.root / "other"), "main")
        self.register("m", self.repo, branch="m")
        out = self.run_queue(self.repo, "integrate", *self.PASS)
        self.assertTrue(self.repo.exists())
        self.assertIn("Left", out)
        self.assertEqual(git(self.root / "other", "show", "main:m.txt"), "m")

    def test_stale_entry_is_skipped_and_stays_queued(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        (wa / "more.txt").write_text("x\n")
        git(wa, "add", "-A")
        git(wa, "commit", "-qm", "more")
        out = self.run_queue(self.repo, "integrate", *self.PASS)
        self.assertIn("STALE", out)
        self.assertFalse((self.repo / "a.txt").exists())
        self.assertEqual(len(list((self.queue_dir() / "entries").glob("*.json"))), 1)

    def test_conflict_stops_names_the_session_and_resume_finishes(self):
        wa = self.session("a", {"shared.txt": "one\nA\nthree\n"})
        wb = self.session("b", {"shared.txt": "one\nB\nthree\n"})
        self.register("a", wa)
        self.register("b", wb)
        out = self.run_queue(self.repo, "integrate", *self.PASS, expect=2)
        self.assertIn("b [abc]", out)
        self.assertIn("shared.txt", out)
        wt = Path(json.loads((self.queue_dir() / "integration.json").read_text())["worktree"])
        (wt / "shared.txt").write_text("one\nA\nB\nthree\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", "resolve")
        self.run_queue(self.repo, "integrate", *self.PASS, "--resume")
        self.assertEqual((self.repo / "shared.txt").read_text(), "one\nA\nB\nthree\n")
        self.assertFalse((self.queue_dir() / "integration.json").exists())

    def test_resume_refuses_while_the_conflict_is_unresolved(self):
        wa = self.session("a", {"shared.txt": "one\nA\nthree\n"})
        wb = self.session("b", {"shared.txt": "one\nB\nthree\n"})
        self.register("a", wa)
        self.register("b", wb)
        self.run_queue(self.repo, "integrate", *self.PASS, expect=2)
        self.run_queue(self.repo, "integrate", *self.PASS, "--resume", expect=2)

    def test_fast_check_failure_drops_only_that_entry(self):
        wa = self.session("a", {"a.txt": "a\n"})
        wb = self.session("bad", {"bad.txt": "x\n"})
        self.register("a", wa)
        self.register("bad", wb)
        # the fast check fails whenever bad.txt is present
        out = self.run_queue(self.repo, "integrate", "--fast-check", "test ! -e bad.txt",
                             "--full-check", "true")
        self.assertIn("bad [abc]", out)
        self.assertTrue((self.repo / "a.txt").exists())
        self.assertFalse((self.repo / "bad.txt").exists())
        left = [p.name for p in (self.queue_dir() / "entries").glob("*.json")]
        self.assertEqual(len(left), 1)

    def test_full_check_failure_leaves_main_untouched(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        before = git(self.repo, "rev-parse", "main")
        self.run_queue(self.repo, "integrate", "--fast-check", "true",
                       "--full-check", "false", expect=3)
        self.assertEqual(git(self.repo, "rev-parse", "main"), before)
        self.assertTrue((self.queue_dir() / "integration.json").exists())
        self.run_queue(self.repo, "integrate", "--abort")
        self.assertFalse((self.queue_dir() / "integration.json").exists())
        self.assertEqual(len(list((self.queue_dir() / "entries").glob("*.json"))), 1)

    def test_main_that_moved_during_integration_is_not_overwritten(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        out = self.run_queue(self.repo, "integrate", "--fast-check", "true",
                             "--full-check",
                             f"git -C {self.repo} commit -q --allow-empty -m moved",
                             expect=4)
        self.assertIn("moved", out)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s", "main"), "moved")

    def test_second_integration_is_refused_while_one_is_in_progress(self):
        wa = self.session("a", {"shared.txt": "one\nA\nthree\n"})
        wb = self.session("b", {"shared.txt": "one\nB\nthree\n"})
        self.register("a", wa)
        self.register("b", wb)
        self.run_queue(self.repo, "integrate", *self.PASS, expect=2)
        self.run_queue(self.repo, "integrate", *self.PASS, expect=1)


TOOLING = Path(__file__).resolve().parents[4] / "bkf" / "tooling"


class CardTests(QueueCase):
    """Task cards move with the queue; `bkf` is a shim running this worktree's bkf_cli."""

    def setUp(self):
        super().setUp()
        shim_dir = self.root / "shim"
        shim_dir.mkdir()
        shim = shim_dir / "bkf"
        shim.write_text(f'#!/bin/sh\nPYTHONPATH="{TOOLING}" exec "{sys.executable}" -m bkf_cli "$@"\n')
        shim.chmod(0o755)
        self.env["PATH"] = f"{shim_dir}{os.pathsep}{os.environ['PATH']}"

    def bkf(self, *args):
        r = subprocess.run(["bkf", *args], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def card(self, branch, wt, status="working"):
        """A card on `branch` at `wt`, started (working) or left in todo."""
        cid = self.bkf("task", "new", "--repo", str(self.repo), "--title", branch, "--no-parent")
        if status != "todo":
            self.bkf("task", "start", cid, "--branch", branch, "--worktree", str(wt))
        return cid

    def status(self, cid):
        return json.loads(self.bkf("task", "show", cid, "--json"))

    def test_register_moves_the_card_to_review_with_the_note(self):
        wa = self.session("a", {"a.txt": "a\n"})
        cid = self.card("a", wa)
        out = self.register("a", wa)
        card = self.status(cid)
        self.assertEqual(card["status"], "review")
        self.assertEqual(card["note"], "queued for merge")
        self.assertIn("Registered", out)

    def test_register_leaves_a_todo_card_alone(self):
        wa = self.session("a", {"a.txt": "a\n"})
        cid = self.card("a", wa, status="todo")
        self.register("a", wa)
        self.assertEqual(self.status(cid)["status"], "todo")

    def test_integrate_moves_merged_cards_to_done_and_leaves_unmerged_ones(self):
        wa = self.session("a", {"a.txt": "a\n"})
        wb = self.session("b", {"b.txt": "b\n"})
        wc = self.session("c", {"c.txt": "c\n"})
        ca = self.card("a", wa)
        cc = self.card("c", wc)
        self.register("a", wa)
        self.register("b", wb)  # no card for b
        self.run_queue(self.repo, "integrate", "--fast-check", "true", "--full-check", "true")
        self.assertTrue((self.repo / "a.txt").exists())
        self.assertEqual(self.status(ca)["status"], "done")
        self.assertEqual(self.status(cc)["status"], "working")  # c never registered

    def test_no_card_leaves_the_queue_as_before(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.register("a", wa)
        self.assertEqual(self.bkf("task", "list"), "")
        self.run_queue(self.repo, "integrate", "--fast-check", "true", "--full-check", "true")
        self.assertTrue((self.repo / "a.txt").exists())

    def test_two_cards_on_one_branch_are_reported_and_left_alone(self):
        wa = self.session("a", {"a.txt": "a\n"})
        first = self.card("a", wa)
        second = self.card("a", wa)
        out = self.register("a", wa)
        self.assertIn("2 task cards are on a", out)
        self.assertEqual(self.status(first)["status"], "working")
        self.assertEqual(self.status(second)["status"], "working")

    def test_missing_bkf_warns_once_and_the_queue_result_is_unchanged(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.env["PATH"] = "/usr/bin:/bin"
        r = subprocess.run([sys.executable, str(SCRIPT), "register", "--session", "a [abc]",
                            "--branch", "a", "--plans", "p.md", "--base",
                            git(self.repo, "rev-parse", "main"), "--fast", "pass", "--full", "pass"],
                           cwd=wa, capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Registered a [abc]", r.stdout)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)
        self.assertIn("bkf", r.stderr)
        self.run_queue(self.repo, "integrate", "--fast-check", "true", "--full-check", "true")
        self.assertTrue((self.repo / "a.txt").exists())

    def test_failing_bkf_warns_and_the_queue_result_is_unchanged(self):
        wa = self.session("a", {"a.txt": "a\n"})
        self.card("a", wa)
        failing = self.root / "failing"
        failing.mkdir()
        (failing / "bkf").write_text("#!/bin/sh\necho broken >&2\nexit 1\n")
        (failing / "bkf").chmod(0o755)
        self.env["PATH"] = f"{failing}{os.pathsep}{self.env['PATH']}"
        out = self.register("a", wa)  # the run still succeeds
        self.assertIn("not updated", out)
        self.assertIn("a [abc]", self.run_queue(self.repo, "list"))


if __name__ == "__main__":
    unittest.main()

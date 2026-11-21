"""`bkf merge` against throwaway git repositories and the store's real lock: the turn protocol and its exit statuses."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import bkf_merge
import bkf_task
import merge_store
import task_hook
import task_store


TOOLING = Path(__file__).resolve().parents[1]
GIT_IDENTITY = ["-c", "user.email=e2e@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]


class MergeFixture(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.store = self.root / "tasks"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "-b", "main")
        self.commit(self.repo, "seed.txt", "seed")
        self.env = {"BKF_TASKS_DIR": str(self.store), "HOME": str(self.root)}

    # helpers

    def git(self, cwd: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(cwd), *GIT_IDENTITY, *arguments], capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def commit(self, cwd: Path, name: str, text: str) -> None:
        (cwd / name).write_text(text + "\n", encoding="utf-8")
        self.git(cwd, "add", name)
        self.git(cwd, "commit", "-q", "-m", f"add {name}")

    def session(self, title: str, branch: str) -> tuple[str, Path]:
        """A card for a session on its own branch and worktree, as `bkf task worktree` and `start` leave it."""
        worktree = self.root / "worktrees" / branch.replace("/", "-")
        self.git(self.repo, "worktree", "add", "-q", "-b", branch, str(worktree), "main")
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title=title)
        task_store.update(
            self.store, card.id, lambda task: task_store.start(task, worktree={"path": str(worktree), "branch": branch}),
        )
        return card.id, worktree

    def merge(self, *arguments: str, task: str | None = None, environ: dict[str, str] | None = None) -> tuple[int, str, str]:
        argv = list(arguments)
        if task is not None:
            argv += ["--task", task]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bkf_merge.main(argv, environ=environ or self.env, store=self.store)
        return code, stdout.getvalue(), stderr.getvalue()

    def queue_file(self) -> Path:
        return merge_store.queue_path(self.store, task_store.repo_identity(self.repo))

    def queue(self) -> dict:
        queue = merge_store.load(self.queue_file())
        assert queue is not None
        return queue

    def edit_queue(self, change) -> None:
        queue = self.queue()
        change(queue)
        merge_store.save(self.store, self.queue_file(), queue)

    def card(self, task: str) -> task_store.Task:
        return task_store.read(self.store, task)

    def states(self) -> list[tuple[str, str]]:
        return [(entry["task"], entry["state"]) for entry in self.queue()["entries"]]

    def minutes_ago(self, minutes: int) -> str:
        return merge_store.stamp(datetime.now(timezone.utc) - timedelta(minutes=minutes))


class TwoSessionQueueTests(MergeFixture):
    def test_two_sessions_land_one_after_the_other_and_the_second_merges_the_first(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, wb = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.commit(wb, "beta.txt", "beta")

        self.assertEqual(self.merge("enter", task=a)[0], 0)
        code, out, _ = self.merge("enter", task=b)
        self.assertEqual(code, 0)
        self.assertIn("Position 2, 1 ahead", out)
        self.assertEqual(self.card(a).status, "to-merge")
        self.assertEqual(self.card(b).status, "to-merge")
        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 75)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=a)[0], 0)

        self.assertEqual(self.merge("verify", task=a)[0], 0)
        code, out, _ = self.merge("land", task=a)
        self.assertEqual(code, 0, out)
        self.assertIn("Landed task/alpha on main", out)
        self.assertEqual(self.states(), [(b, "turn")])

        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)
        self.git(wb, "merge", "-q", "main", "-m", "merge main into beta")
        self.assertEqual(self.merge("verify", task=b)[0], 0)
        self.assertEqual(self.merge("land", task=b)[0], 0)

        self.assertEqual(self.git(self.repo, "show", "main:alpha.txt"), "alpha")
        self.assertEqual(self.git(self.repo, "show", "main:beta.txt"), "beta")
        self.assertEqual(self.queue()["entries"], [])
        landed = [event["task"] for event in self.queue()["events"] if event["event"] == "landed"]
        self.assertEqual(landed, [a, b])
        self.assertEqual(self.card(a).status, "to-merge", "the card waits for bkf task close")

    def test_enter_is_idempotent_and_wait_joins_a_task_that_is_not_queued(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        self.assertEqual(self.merge("enter", task=a)[0], 0)
        self.assertEqual(self.merge("enter", task=a)[0], 0)
        self.assertEqual(self.states(), [(a, "turn")])
        b, _ = self.session("beta", "task/beta")
        code, out, _ = self.merge("wait", "--timeout", "0", task=b)
        self.assertEqual(code, 75)
        self.assertIn("Entered the merge queue", out)
        self.assertEqual(self.states(), [(a, "turn"), (b, "waiting")])

    def test_wait_takes_the_worktree_it_is_given_when_it_joins(self) -> None:
        card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="loose")
        self.git(self.repo, "worktree", "add", "-q", "-b", "task/loose", str(self.root / "loose"), "main")
        code, out, err = self.merge("wait", "--timeout", "0", "--worktree", str(self.root / "loose"), task=card.id)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(self.queue()["entries"][0]["branch"], "task/loose")
        self.assertIn("Your turn", out)


class FailureAndLeaveTests(MergeFixture):
    def test_a_failed_turn_passes_to_the_next_and_the_card_says_why(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("enter", task=b)

        code, out, _ = self.merge("fail", "--reason", "tests break on main", task=a)

        self.assertEqual(code, 0, out)
        card = self.card(a)
        self.assertEqual((card.status, card.attention["reason"], card.attention["note"]),
                         ("working", "merge-failed", "tests break on main"))
        self.assertEqual(self.states(), [(b, "turn")])
        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)
        self.assertEqual(self.merge("enter", task=a)[0], 0)
        self.assertEqual(self.card(a).attention, None, "entering again clears the merge-failed mark")
        self.assertEqual(self.states(), [(b, "turn"), (a, "waiting")])

    def test_leave_gives_the_turn_on_and_the_card_goes_back_to_working(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)

        self.assertEqual(self.merge("leave", task=b)[0], 0)
        self.assertEqual(self.states(), [(a, "turn")])
        self.assertEqual((self.card(b).status, self.card(b).attention), ("working", None))

        self.assertEqual(self.merge("leave", task=a)[0], 0)
        self.assertEqual(self.queue()["entries"], [])
        code, out, _ = self.merge("leave", task=a)
        self.assertEqual(code, 0)
        self.assertIn("not in the merge queue", out)


class LandRefusalTests(MergeFixture):
    def test_landing_without_a_verify_is_refused_with_exit_three(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        code, _, err = self.merge("land", task=a)
        self.assertEqual(code, 3)
        self.assertIn("not verified", err)

    def test_the_target_moving_after_verify_is_refused_with_exit_three_and_recorded(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        self.commit(self.repo, "other.txt", "other")

        code, _, err = self.merge("land", task=a)

        self.assertEqual(code, 3)
        self.assertIn("main moved after verify", err)
        self.assertIn("main-moved", [event["event"] for event in self.queue()["events"]])
        self.assertEqual(self.states(), [(a, "turn")], "the entry keeps the turn")
        self.git(wa, "merge", "-q", "main", "-m", "merge main")
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        self.assertEqual(self.merge("land", task=a)[0], 0)
        self.assertEqual(self.git(self.repo, "show", "main:alpha.txt"), "alpha")

    def test_a_branch_without_the_target_is_refused_with_exit_three(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(self.repo, "other.txt", "other")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("verify", task=a)
        code, _, err = self.merge("land", task=a)
        self.assertEqual(code, 3)
        self.assertIn("does not contain main", err)

    def test_a_dirty_main_checkout_is_refused_with_exit_four_and_the_turn_is_kept(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("verify", task=a)
        (self.repo / "seed.txt").write_text("changed by hand\n", encoding="utf-8")

        code, _, err = self.merge("land", task=a)

        self.assertEqual(code, 4)
        self.assertIn("uncommitted changes", err)
        self.assertEqual(self.queue()["entries"][0]["phase"], "testing")
        self.git(self.repo, "checkout", "--", "seed.txt")
        self.assertEqual(self.merge("land", task=a)[0], 0)

    def test_only_the_holder_may_verify_or_land(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        code, _, err = self.merge("verify", task=b)
        self.assertEqual((code, "not your turn" in err), (5, True))
        self.assertEqual(self.merge("land", task=b)[0], 5)
        self.assertEqual(self.merge("land", task="t20990101-000000-dead")[0], 1)

    def test_refusals_that_need_no_queue_change(self) -> None:
        self.assertEqual(self.merge("enter")[0], 1, "no task id")
        main_card = task_store.create(self.store, repo=task_store.repo_identity(self.repo), title="on main")
        task_store.update(
            self.store, main_card.id,
            lambda task: task_store.start(task, worktree={"path": str(self.repo), "branch": "main"}),
        )
        code, _, err = self.merge("enter", task=main_card.id)
        self.assertEqual(code, 1)
        self.assertIn("is the target", err)
        a, _ = self.session("alpha", "task/alpha")
        self.merge("enter", task=a)
        code, _, err = self.merge("enter", "--target", "develop", task=a)
        self.assertEqual(code, 1)
        self.assertIn("lands on main, not develop", err)


class RecoveryTests(MergeFixture):
    def test_a_holder_whose_lease_expired_loses_the_turn_and_the_next_gets_it(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        self.edit_queue(lambda queue: queue["entries"][0].update(lease_until=self.minutes_ago(5)))

        code, out, err = self.merge("wait", "--timeout", "0", task=b)

        self.assertEqual(code, 0, err)
        self.assertIn("Removed", out)
        self.assertEqual(self.states(), [(b, "turn")])
        card = self.card(a)
        self.assertEqual((card.status, card.attention["reason"]), ("working", "merge-failed"))
        self.assertTrue(card.attention["note"].startswith("lost its place in the merge queue: no sign of life"))
        self.assertIn("lock-recovered", [event["event"] for event in self.queue()["events"]])

    def test_a_waiter_that_stops_polling_is_dropped_and_its_own_wait_ends_with_exit_two(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)

        def stop_polling(_seconds: float) -> None:
            self.edit_queue(lambda queue: queue["entries"][1].update(seen=self.minutes_ago(10)))

        with patch.object(bkf_merge.time, "sleep", side_effect=stop_polling):
            code, _, err = self.merge("wait", "--timeout", "30", task=b)

        self.assertEqual(code, 2)
        self.assertIn("did not poll for the turn for 3 minutes", err)
        self.assertEqual(self.states(), [(a, "turn")])
        self.assertIn("did not poll", self.card(b).attention["note"])

    def test_a_dormant_entry_is_dropped_by_any_other_command(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        self.edit_queue(lambda queue: queue["entries"][1].update(seen=self.minutes_ago(10)))
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        self.assertEqual(self.states(), [(a, "turn")])
        self.assertIn("dropped-dormant", [event["event"] for event in self.queue()["events"]])

    def test_a_crashed_land_whose_branch_reached_the_target_counts_as_landed(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("verify", task=a)
        self.git(self.repo, "merge", "-q", "--ff-only", "task/alpha")
        self.edit_queue(lambda queue: queue["entries"][0].update(phase="landing"))

        self.assertEqual(self.merge("enter", task=b)[0], 0)

        self.assertEqual(self.states(), [(b, "turn")])
        self.assertEqual(self.card(a).status, "to-merge")
        landed = [event for event in self.queue()["events"] if event["event"] == "landed" and event["task"] == a]
        self.assertEqual(len(landed), 1)

    def test_a_crashed_land_whose_branch_did_not_reach_the_target_fails_with_the_card_marked(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("verify", task=a)
        self.edit_queue(lambda queue: queue["entries"][0].update(phase="landing"))

        self.assertEqual(self.merge("enter", task=b)[0], 0)

        self.assertEqual(self.states(), [(b, "turn")])
        card = self.card(a)
        self.assertEqual((card.status, card.attention["reason"]), ("working", "merge-failed"))
        self.assertIn("the land did not finish", card.attention["note"])

    def test_a_holder_whose_card_is_gone_loses_the_turn(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        task_store.delete(self.store, a)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)
        self.assertEqual(self.states(), [(b, "turn")])


class StatusTests(MergeFixture):
    def test_status_json_has_the_documented_shape_and_changes_nothing(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        before = task_store.generation(self.store)
        before_file = self.queue_file().read_text(encoding="utf-8")

        code, out, _ = self.merge("status", "--json", "--task", b)

        self.assertEqual(code, 0)
        self.assertEqual(task_store.generation(self.store), before)
        self.assertEqual(self.queue_file().read_text(encoding="utf-8"), before_file)
        payload = json.loads(out)
        self.assertEqual(sorted(payload), ["generation", "queues", "schema", "store", "task"])
        self.assertEqual((payload["schema"], payload["store"]), (1, str(self.store.absolute())))
        queue = payload["queues"][0]
        self.assertEqual(sorted(queue), ["entries", "events", "lock", "repo", "target", "target_head"])
        self.assertEqual(queue["repo"], task_store.repo_identity(self.repo))
        self.assertEqual(queue["target"], "main")
        self.assertEqual(queue["target_head"], self.git(self.repo, "rev-parse", "main"))
        self.assertEqual(sorted(queue["lock"]), ["lease_until", "phase", "since", "stale", "task"])
        self.assertEqual((queue["lock"]["task"], queue["lock"]["phase"], queue["lock"]["stale"]), (a, "testing", False))
        self.assertEqual(
            sorted(queue["entries"][1]),
            ["branch", "entered", "position", "stale", "state", "task", "turn_since", "worktree"],
        )
        self.assertEqual((queue["entries"][1]["position"], queue["entries"][1]["state"]), (2, "waiting"))
        self.assertEqual(payload["task"], {"in_queue": True, "position": 2, "state": "waiting", "queue_ahead": 1})

    def test_a_stale_lock_is_reported_without_anyone_polling(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        self.edit_queue(lambda queue: queue["entries"][0].update(lease_until=self.minutes_ago(5)))
        code, out, _ = self.merge("status", "--json")
        queue = json.loads(out)["queues"][0]
        self.assertTrue(queue["lock"]["stale"])
        self.assertEqual(len(queue["entries"]), 2, "status does not recover the queue")

    def test_status_with_no_queue_is_empty_and_absent_task_is_not_in_queue(self) -> None:
        code, out, _ = self.merge("status", "--json")
        self.assertEqual((code, json.loads(out)["queues"]), (0, []))
        code, out, _ = self.merge("status")
        self.assertEqual((code, out.strip()), (0, "The merge queue is empty."))
        a, _ = self.session("alpha", "task/alpha")
        code, out, _ = self.merge("status", "--json", "--task", a)
        self.assertEqual(json.loads(out)["task"], {"in_queue": False, "position": None, "state": None, "queue_ahead": None})


class HookLeaseTests(MergeFixture):
    def test_the_task_hook_renews_the_holders_lease_on_tool_calls(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        almost_out = merge_store.stamp(datetime.now(timezone.utc) + timedelta(minutes=55))
        self.edit_queue(lambda queue: queue["entries"][0].update(lease_until=almost_out))

        environ = {**self.env, "BKF_TASK": a}
        with contextlib.redirect_stdout(io.StringIO()):
            task_hook.run(environ=environ, stream=io.StringIO(json.dumps(
                {"hook_event_name": "PostToolUse", "tool_name": "Bash"},
            )))
        renewed = self.queue()["entries"][0]["lease_until"]
        self.assertGreater(renewed, almost_out)

        with contextlib.redirect_stdout(io.StringIO()):
            task_hook.run(environ={**self.env, "BKF_TASK": b}, stream=io.StringIO(json.dumps(
                {"hook_event_name": "Stop"},
            )))
        self.assertEqual(self.queue()["entries"][0]["lease_until"], renewed)


class ConcurrencyTests(MergeFixture):
    def test_simultaneous_enters_from_separate_processes_are_all_recorded(self) -> None:
        tasks = [self.session(f"s{index}", f"task/s{index}")[0] for index in range(6)]
        environment = dict(os.environ, PYTHONPATH=str(TOOLING), BKF_TASKS_DIR=str(self.store))
        before = task_store.generation(self.store)
        processes = [
            subprocess.Popen(
                [sys.executable, "-m", "bkf_merge", "enter", "--task", task],
                env=environment, cwd=str(self.repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for task in tasks
        ]
        results = [process.communicate() for process in processes]
        self.assertEqual([process.returncode for process in processes], [0] * 6, results)
        entries = self.queue()["entries"]
        self.assertEqual(sorted(entry["task"] for entry in entries), sorted(tasks))
        self.assertEqual([entry["state"] for entry in entries].count("turn"), 1)
        self.assertGreaterEqual(task_store.generation(self.store) - before, 6)


class CommandShapeTests(MergeFixture):
    def test_each_command_exits_zero_on_the_happy_path_and_the_store_has_one_queue_file(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.assertEqual(self.merge("enter", task=a)[0], 0)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=a)[0], 0)
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        self.assertEqual(self.merge("land", task=a)[0], 0)
        self.assertEqual(merge_store.queue_paths(self.store), [self.queue_file()])
        self.assertRegex(self.queue_file().parent.name, r"^[A-Za-z0-9-]+-[0-9a-f]{8}$")


class InterimLandTests(MergeFixture):
    """`land --continue` lands a batch and keeps the session's branch; the final land is the plain one."""

    def land_first(self, task: str, worktree: Path) -> None:
        self.commit(worktree, "first.txt", "first")
        self.assertEqual(self.merge("enter", task=task)[0], 0)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=task)[0], 0)
        self.assertEqual(self.merge("verify", task=task)[0], 0)

    def test_land_continue_puts_the_card_back_to_working_and_the_next_session_gets_the_turn(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, wb = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.commit(wb, "beta.txt", "beta")
        self.assertEqual(self.merge("enter", task=a)[0], 0)
        self.assertEqual(self.merge("enter", task=b)[0], 0)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=a)[0], 0)
        self.assertEqual(self.merge("verify", task=a)[0], 0)

        code, out, err = self.merge("land", "--continue", task=a)

        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("(interim)", out)
        self.assertEqual((self.card(a).status, self.card(a).attention), ("working", None))
        self.assertEqual(self.states(), [(b, "turn")], "a's entry is gone and b gets the turn")
        landed = [event for event in self.queue()["events"] if event["event"] == "landed"]
        self.assertEqual((landed[-1]["task"], landed[-1]["reason"][:8]), (a, "interim:"))
        self.assertEqual(self.git(self.repo, "show", "main:alpha.txt"), "alpha")

        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)
        self.git(wb, "merge", "-q", "main", "-m", "merge main into beta")
        self.assertEqual(self.merge("verify", task=b)[0], 0)
        self.assertEqual(self.merge("land", task=b)[0], 0)
        self.assertEqual(self.git(self.repo, "show", "main:beta.txt"), "beta")
        self.assertEqual(self.card(b).status, "to-merge", "b's final land keeps the plain card rule")

    def test_the_interim_message_has_no_cleanup_instruction_and_says_how_to_go_on(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.land_first(a, wa)
        code, out, err = self.merge("land", "--continue", task=a)
        self.assertEqual((code, err), (0, ""), out)
        for cleanup in ("git-worktree-cleanup", "bkf task close", "remove your worktree"):
            self.assertNotIn(cleanup, out)
        self.assertIn("may keep working on the same branch", out)
        self.assertIn("run bkf merge enter again", out)
        self.assertIn("without --continue", out)

    def test_plain_land_is_unchanged_and_leaves_the_card_in_to_merge_with_the_cleanup_message(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.land_first(a, wa)
        code, out, err = self.merge("land", task=a)
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("Landed task/alpha on main. Next: remove your worktree and branch "
                      "(git-worktree-cleanup), then bkf task close.", out)
        self.assertEqual((self.card(a).status, self.card(a).attention), ("to-merge", None))
        landed = [event for event in self.queue()["events"] if event["event"] == "landed"]
        self.assertEqual(landed[-1]["reason"], f"task/alpha at {self.git(wa, 'rev-parse', 'HEAD')[:12]}")

    def test_enter_again_after_an_interim_land_and_a_second_land_with_the_target_merged_again(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, wb = self.session("beta", "task/beta")
        self.land_first(a, wa)
        self.assertEqual(self.merge("land", "--continue", task=a)[0], 0)
        self.commit(wb, "beta.txt", "beta")  # another session lands in between, so the target moves
        self.merge("enter", task=b)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)
        self.git(wb, "merge", "-q", "main", "-m", "merge main into beta")
        self.assertEqual(self.merge("verify", task=b)[0], 0)
        self.assertEqual(self.merge("land", task=b)[0], 0)
        self.assertEqual(self.card(a).status, "working")

        self.commit(wa, "second.txt", "second")
        self.assertEqual(self.merge("enter", task=a)[0], 0, "re-entry from a working card")
        self.assertEqual(self.card(a).status, "to-merge")
        self.assertEqual(self.merge("wait", "--timeout", "0", task=a)[0], 0)
        self.git(wa, "merge", "-q", "main", "-m", "merge main into alpha again")
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        code, out, err = self.merge("land", task=a)
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("Next: remove your worktree", out)
        self.assertEqual(self.git(self.repo, "show", "main:second.txt"), "second")
        self.assertEqual(self.git(self.repo, "show", "main:beta.txt"), "beta")

    def test_a_second_land_without_merging_a_moved_target_is_refused_with_exit_three(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, wb = self.session("beta", "task/beta")
        self.land_first(a, wa)
        self.assertEqual(self.merge("land", "--continue", task=a)[0], 0)
        self.commit(wb, "beta.txt", "beta")
        self.merge("enter", task=b)
        self.commit(wa, "second.txt", "second")
        self.merge("enter", task=a)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)
        self.git(wb, "merge", "-q", "main", "-m", "merge main into beta")
        self.assertEqual(self.merge("verify", task=b)[0], 0)
        self.assertEqual(self.merge("land", task=b)[0], 0)

        self.assertEqual(self.merge("wait", "--timeout", "0", task=a)[0], 0)
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        code, _, err = self.merge("land", task=a)
        self.assertEqual(code, 3)
        self.assertIn("does not contain main", err)
        self.assertEqual(self.states(), [(a, "turn")], "the entry keeps the turn")

    def test_when_the_target_has_not_moved_the_branch_already_contains_it_and_lands_as_it_is(self) -> None:
        """Documents the ancestry rule: the target is an ancestor of the branch, so a land after new commits
        is a plain fast-forward of what was verified. The target is not merged again only because it did not move."""
        a, wa = self.session("alpha", "task/alpha")
        self.land_first(a, wa)
        self.assertEqual(self.merge("land", "--continue", task=a)[0], 0)
        self.commit(wa, "second.txt", "second")
        self.merge("enter", task=a)
        self.assertEqual(self.merge("wait", "--timeout", "0", task=a)[0], 0)
        self.assertEqual(self.merge("verify", task=a)[0], 0)
        self.assertEqual(self.merge("land", task=a)[0], 0)
        self.assertEqual(self.git(self.repo, "show", "main:second.txt"), "second")


class TakeOutTests(MergeFixture):
    """A take-out (bkf merge leave by the owner, typed into the session) stops the merge flow for good."""

    def test_a_waiter_whose_entry_is_taken_out_gets_exit_two_and_no_instruction_to_re_enter(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)

        def take_out(_seconds: float) -> None:
            self.assertEqual(self.merge("leave", task=b)[0], 0)

        with patch.object(bkf_merge.time, "sleep", side_effect=take_out):
            code, _, err = self.merge("wait", "--timeout", "30", task=b)

        self.assertEqual(code, 2)
        self.assertIn("the owner took the task out of the merge queue", err)
        self.assertIn("do not re-enter on your own", err)
        self.assertNotIn("run bkf merge enter", err)
        self.assertEqual((self.card(b).status, self.card(b).attention), ("working", None))

    def test_verify_and_land_after_a_take_out_are_refused_with_exit_five_and_no_re_enter_instruction(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.assertEqual(self.merge("leave", task=a)[0], 0)
        for command in ("verify", "land"):
            with self.subTest(command):
                code, _, err = self.merge(command, task=a)
                self.assertEqual(code, 5)
                self.assertIn("not in the merge queue", err)
                self.assertIn("do not re-enter on your own", err)
                self.assertNotIn("run bkf merge enter", err)

    def test_a_to_merge_card_outside_the_queue_may_start_and_one_inside_it_may_not(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        environ = {**self.env, "BKF_TASKS_DIR": str(self.store)}
        with patch.dict(os.environ, environ, clear=False):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                code = bkf_task.main(["start", a])
        self.assertEqual(code, 1)
        self.assertIn("is in the merge queue", stderr.getvalue())
        self.assertEqual(self.card(a).status, "to-merge")

        self.assertEqual(self.merge("leave", task=a)[0], 0)
        self.assertEqual(self.card(a).status, "working")
        self.merge("enter", task=a)
        self.edit_queue(lambda queue: queue["entries"].clear())  # a card left in to-merge with no entry
        self.assertEqual(self.card(a).status, "to-merge")
        with patch.dict(os.environ, environ, clear=False):
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                code = bkf_task.main(["start", a])
        self.assertEqual(code, 0)
        self.assertEqual(self.card(a).status, "working")


class RecoveryDropTests(MergeFixture):
    """A drop by recovery is not the owner's take-out: the session is told so and may enter again."""

    def test_a_holder_that_lost_its_lease_is_told_it_may_enter_again_on_verify(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("enter", task=b)
        self.edit_queue(lambda queue: queue["entries"][0].update(lease_until=self.minutes_ago(5)))
        self.assertEqual(self.merge("wait", "--timeout", "0", task=b)[0], 0)

        code, _, err = self.merge("verify", task=a)

        self.assertEqual(code, 5)
        self.assertIn("not in the merge queue", err)
        self.assertIn("the queue removed it, not the owner", err)
        self.assertIn("no sign of life for 60 minutes", err)
        self.assertIn("You may run bkf merge enter again", err)
        self.assertNotIn("do not re-enter", err)
        self.assertEqual(self.merge("enter", task=a)[0], 0, "the session re-enters at the back")
        self.assertEqual(self.states(), [(b, "turn"), (a, "waiting")])

    def test_a_dormant_waiter_is_told_it_may_enter_again_when_its_wait_ends(self) -> None:
        a, _ = self.session("alpha", "task/alpha")
        b, _ = self.session("beta", "task/beta")
        self.merge("enter", task=a)
        self.merge("enter", task=b)

        def stop_polling(_seconds: float) -> None:
            self.edit_queue(lambda queue: queue["entries"][1].update(seen=self.minutes_ago(10)))

        with patch.object(bkf_merge.time, "sleep", side_effect=stop_polling):
            code, _, err = self.merge("wait", "--timeout", "30", task=b)

        self.assertEqual(code, 2)
        self.assertIn("did not poll for the turn for 3 minutes", err)
        self.assertIn("the queue removed it, not the owner", err)
        self.assertIn("You may run bkf merge enter again", err)
        self.assertNotIn("tell the owner", err)

    def test_a_card_whose_branch_already_landed_is_not_told_to_enter_again(self) -> None:
        a, wa = self.session("alpha", "task/alpha")
        self.commit(wa, "alpha.txt", "alpha")
        self.merge("enter", task=a)
        self.merge("verify", task=a)
        self.git(self.repo, "merge", "-q", "--ff-only", "task/alpha")
        self.edit_queue(lambda queue: queue["entries"][0].update(phase="landing"))
        b, _ = self.session("beta", "task/beta")
        self.assertEqual(self.merge("enter", task=b)[0], 0)  # recovery records a's land as landed

        code, _, err = self.merge("verify", task=a)

        self.assertEqual(code, 5)
        self.assertIn("its branch already landed", err)
        self.assertIn("do not enter again", err)
        self.assertNotIn("You may run bkf merge enter again", err)


if __name__ == "__main__":
    unittest.main()

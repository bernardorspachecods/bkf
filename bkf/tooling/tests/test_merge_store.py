"""The merge queue's file rules, turn rules and recovery, without git: a fake probe answers the outside questions."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import merge_store
import task_store
from merge_store import MergeError


NOW = datetime(2026, 11, 20, 14, 30, 0, tzinfo=timezone.utc)
LEASE = timedelta(minutes=60)
REPO = "/example/repo"
TASK_A = "t20261120-143000-aaaa"
TASK_B = "t20261120-143000-bbbb"
TASK_C = "t20261120-143000-cccc"


class FakeProbe:
    def __init__(self, cards=(TASK_A, TASK_B, TASK_C), windows=None, landed=False) -> None:
        self.cards = set(cards)
        self.windows = windows or {}
        self.is_landed = landed

    def card_exists(self, task: str) -> bool:
        return task in self.cards

    def window_alive(self, task: str) -> bool | None:
        return self.windows.get(task)

    def landed(self, branch: str) -> bool:
        return self.is_landed


def queue_with(*tasks: str, now: datetime = NOW) -> dict:
    queue = merge_store.new_queue(REPO, "main")
    for task in tasks:
        merge_store.add(queue, task, f"task/{task[-4:]}", f"/wt/{task[-4:]}", now)
    merge_store.promote(queue, now, LEASE)
    return queue


class RepoKeyAndLeaseTests(unittest.TestCase):
    def test_repo_key_is_a_slug_that_keeps_same_named_repositories_apart(self) -> None:
        first = merge_store.repo_key("/a/b/app")
        second = merge_store.repo_key("/c/app")
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^[A-Za-z0-9-]+$")
        self.assertEqual(first, merge_store.repo_key("/a/b/app"))

    def test_queue_path_is_under_the_store_merge_folder(self) -> None:
        path = merge_store.queue_path(Path("/state/tasks"), REPO)
        self.assertEqual(path.parent.parent, Path("/state/tasks/.merge"))
        self.assertEqual(path.name, "queue.json")

    def test_lease_defaults_to_sixty_minutes_and_reads_the_environment(self) -> None:
        self.assertEqual(merge_store.lease_length({}), timedelta(minutes=60))
        self.assertEqual(merge_store.lease_length({"BKF_MERGE_LEASE_MINUTES": "5"}), timedelta(minutes=5))
        for bad in ("0", "soon", "-3"):
            with self.subTest(bad):
                with self.assertRaises(MergeError):
                    merge_store.lease_length({"BKF_MERGE_LEASE_MINUTES": bad})


class TurnTests(unittest.TestCase):
    def test_the_head_holds_the_turn_and_others_wait(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        self.assertEqual([entry["state"] for entry in queue["entries"]], ["turn", "waiting"])
        self.assertIs(merge_store.holder(queue), queue["entries"][0])
        self.assertEqual(queue["entries"][0]["lease_until"], merge_store.stamp(NOW + LEASE))

    def test_promote_does_nothing_while_someone_holds_the_turn(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        before = copy.deepcopy(queue)
        self.assertIsNone(merge_store.promote(queue, NOW, LEASE))
        self.assertEqual(queue, before)

    def test_removing_the_head_gives_the_turn_to_the_next_entry(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        merge_store.remove(queue, TASK_A)
        merge_store.promote(queue, NOW, LEASE)
        self.assertEqual(merge_store.holder(queue)["task"], TASK_B)
        self.assertEqual(queue["events"][-1]["event"], "turn-started")

    def test_renew_extends_the_lease_and_respects_the_minimum_age(self) -> None:
        queue = queue_with(TASK_A)
        later = NOW + timedelta(seconds=30)
        self.assertFalse(merge_store.renew(queue, later, LEASE, task=TASK_A, minimum_age=timedelta(seconds=60)))
        self.assertEqual(queue["entries"][0]["lease_until"], merge_store.stamp(NOW + LEASE))
        much_later = NOW + timedelta(minutes=5)
        self.assertTrue(merge_store.renew(queue, much_later, LEASE, task=TASK_A, minimum_age=timedelta(seconds=60)))
        self.assertEqual(queue["entries"][0]["lease_until"], merge_store.stamp(much_later + LEASE))

    def test_renew_ignores_other_tasks(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        self.assertFalse(merge_store.renew(queue, NOW + timedelta(hours=1), LEASE, task=TASK_B))

    def test_the_event_log_keeps_the_last_fifty(self) -> None:
        queue = queue_with(TASK_A)
        for index in range(60):
            merge_store.log(queue, NOW, TASK_A, "verified", str(index))
        self.assertEqual(len(queue["events"]), merge_store.EVENTS_LIMIT)
        self.assertEqual(queue["events"][-1]["reason"], "59")
        self.assertEqual(queue["events"][0]["reason"], "10")


class RecoveryTests(unittest.TestCase):
    def test_a_healthy_queue_changes_nothing(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        before = copy.deepcopy(queue)
        self.assertEqual(merge_store.recover(queue, NOW, LEASE, FakeProbe()), [])
        self.assertEqual(queue, before)

    def test_a_holder_whose_card_is_gone_loses_the_turn_with_a_note(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        found = merge_store.recover(queue, NOW, LEASE, FakeProbe(cards=(TASK_B,)))
        self.assertEqual([(item.task, item.event) for item in found], [(TASK_A, "lock-recovered")])
        self.assertEqual(found[0].note, "lost its place in the merge queue: its card is gone")
        self.assertEqual(merge_store.holder(queue)["task"], TASK_B)
        self.assertEqual(queue["events"][-2]["event"], "lock-recovered")

    def test_a_holder_whose_tmux_window_is_gone_loses_the_turn(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        found = merge_store.recover(queue, NOW, LEASE, FakeProbe(windows={TASK_A: False}))
        self.assertEqual(found[0].reason, "its tmux window is gone")

    def test_a_window_that_cannot_be_checked_does_not_cost_the_turn(self) -> None:
        queue = queue_with(TASK_A)
        self.assertEqual(merge_store.recover(queue, NOW, LEASE, FakeProbe(windows={TASK_A: None})), [])

    def test_an_expired_lease_loses_the_turn(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        later = NOW + LEASE + timedelta(seconds=1)
        queue["entries"][1]["seen"] = merge_store.stamp(later)
        found = merge_store.recover(queue, later, LEASE, FakeProbe())
        self.assertEqual(found[0].reason, "no sign of life for 60 minutes")
        self.assertEqual(merge_store.holder(queue)["task"], TASK_B)

    def test_a_waiter_that_stopped_polling_is_dropped_after_three_minutes(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        later = NOW + timedelta(minutes=3, seconds=1)
        merge_store.renew(queue, later, LEASE, task=TASK_A)
        found = merge_store.recover(queue, later, LEASE, FakeProbe())
        self.assertEqual([(item.task, item.event) for item in found], [(TASK_B, "dropped-dormant")])
        self.assertEqual(found[0].note, "lost its place in the merge queue: it did not poll for the turn for 3 minutes")
        self.assertEqual([entry["task"] for entry in queue["entries"]], [TASK_A])

    def test_a_polling_waiter_stays(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        queue["entries"][1]["seen"] = merge_store.stamp(NOW + timedelta(minutes=2))
        self.assertEqual(merge_store.recover(queue, NOW + timedelta(minutes=3), LEASE, FakeProbe()), [])

    def test_a_waiter_whose_card_is_gone_is_dropped_without_a_note(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        found = merge_store.recover(queue, NOW, LEASE, FakeProbe(cards=(TASK_A,)))
        self.assertEqual(found[0].reason, "its card is gone")
        self.assertEqual(len(queue["entries"]), 1)

    def test_a_crashed_land_whose_branch_is_on_the_target_counts_as_landed(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        queue["entries"][0]["phase"] = "landing"
        found = merge_store.recover(queue, NOW, LEASE, FakeProbe(landed=True))
        self.assertEqual([(item.task, item.event, item.note) for item in found], [(TASK_A, "landed", None)])
        self.assertEqual(merge_store.holder(queue)["task"], TASK_B)
        self.assertEqual(queue["events"][-2]["event"], "landed")

    def test_a_crashed_land_whose_branch_is_not_on_the_target_is_dropped_as_failed(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        queue["entries"][0]["phase"] = "landing"
        found = merge_store.recover(queue, NOW, LEASE, FakeProbe(landed=False))
        self.assertEqual(found[0].event, "failed")
        self.assertEqual(found[0].note, found[0].reason)
        self.assertIn("the land did not finish", found[0].reason)

    def test_stale_map_reports_what_recovery_would_drop_and_changes_nothing(self) -> None:
        queue = queue_with(TASK_A, TASK_B)
        later = NOW + LEASE + timedelta(minutes=1)
        before = copy.deepcopy(queue)
        stale = merge_store.stale_map(queue, later, LEASE, FakeProbe())
        self.assertEqual(stale, {TASK_A: True, TASK_B: True})
        self.assertEqual(queue, before)
        landing = queue_with(TASK_A)
        landing["entries"][0]["phase"] = "landing"
        self.assertEqual(merge_store.stale_map(landing, NOW, LEASE, FakeProbe()), {TASK_A: True})


class FileTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Path(directory.name) / "tasks"
        self.path = merge_store.queue_path(self.store, REPO)

    def test_a_missing_file_loads_as_none_and_save_writes_it_and_bumps_the_generation(self) -> None:
        self.assertIsNone(merge_store.load(self.path))
        queue = queue_with(TASK_A)
        merge_store.save(self.store, self.path, queue)
        self.assertEqual(merge_store.load(self.path), queue)
        self.assertEqual(task_store.generation(self.store), 1)

    def test_a_file_that_is_not_a_schema_one_queue_is_refused(self) -> None:
        self.path.parent.mkdir(parents=True)
        cases = {
            "not json": "{",
            "wrong schema": json.dumps({"schema": 2, "repo": REPO, "target": "main", "entries": [], "events": []}),
            "two turns": json.dumps({
                "schema": 1, "repo": REPO, "target": "main", "lock": None, "events": [],
                "entries": [
                    {**_entry(TASK_A), "state": "turn"}, {**_entry(TASK_B), "state": "turn"},
                ],
            }),
            "turn behind a waiter": json.dumps({
                "schema": 1, "repo": REPO, "target": "main", "lock": None, "events": [],
                "entries": [_entry(TASK_A), {**_entry(TASK_B), "state": "turn"}],
            }),
            "bad state": json.dumps({
                "schema": 1, "repo": REPO, "target": "main", "lock": None, "events": [],
                "entries": [{**_entry(TASK_A), "state": "running"}],
            }),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(MergeError):
                    merge_store.load(self.path)

    def test_touch_from_hook_renews_only_the_holder_and_at_most_once_a_minute(self) -> None:
        task_store.create(self.store, repo=REPO, title="holder", now=NOW)
        tasks = task_store.list_tasks(self.store).tasks
        holder_card = tasks[0].id
        queue = queue_with(holder_card)
        old_lease = merge_store.stamp(NOW + LEASE - timedelta(minutes=5))
        queue["entries"][0]["lease_until"] = old_lease
        merge_store.save(self.store, self.path, queue)
        merge_store.touch_from_hook(self.store, holder_card, {})
        renewed = merge_store.load(self.path)["entries"][0]["lease_until"]
        self.assertNotEqual(renewed, old_lease)
        merge_store.touch_from_hook(self.store, holder_card, {})
        self.assertEqual(merge_store.load(self.path)["entries"][0]["lease_until"], renewed)


def _entry(task: str) -> dict:
    return {
        "task": task, "branch": "task/x", "worktree": "/wt", "entered": merge_store.stamp(NOW),
        "seen": merge_store.stamp(NOW), "state": "waiting", "turn_since": None, "lease_until": None,
        "phase": None, "verified": None,
    }


if __name__ == "__main__":
    unittest.main()

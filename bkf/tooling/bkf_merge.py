"""Queue a session's finished branch to land on the target branch, one session at a time.

The queue is per repository and held in the task store (merge_store.py). A session enters it, waits for its
turn, merges the target into its branch, verifies the result, and lands it; the agent runs the merge, the
checks and any conflict resolution itself. `status` reads the queue for callers that show it, and never changes it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import merge_git
import merge_store
import task_store
import task_tmux
from merge_store import MergeError
from task_store import Task, TaskError


TASK_ENV = "BKF_TASK"
# Events that take an entry out of the queue without the owner: recovery, and a failed land or merge.
RECOVERY_EVENTS = ("lock-recovered", "dropped-dormant", "failed")
JSON_SCHEMA = 1
WAIT_TIMEOUT_SECONDS = 540
WAIT_POLL_SECONDS = 1.0
# A waiting session refreshes its entry at most this often: the store generation rises on each write.
SEEN_EVERY = timedelta(seconds=10)

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_ENTRY_GONE = 2
EXIT_MOVED = 3  # land: the target moved, or the branch is not the verified one
EXIT_MAIN_REFUSED = 4  # land: the target's checkout refuses the fast-forward
EXIT_NOT_TURN = 5
EXIT_TIMEOUT = 75  # wait: the timeout passed; run wait again


class Stop(Exception):
    """Ends a command with an exit status and one line of explanation on standard error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LiveProbe:
    """Reads the cards, tmux windows and git refs that recovery and status ask about."""

    def __init__(self, store: Path, repo: str, target: str, environ: Mapping[str, str]) -> None:
        self.store = store
        self.repo = repo
        self.target = target
        self.environ = environ

    def card_exists(self, task: str) -> bool:
        try:
            task_store.read(self.store, task)
        except TaskError:
            return False
        return True

    def window_alive(self, task: str) -> bool | None:
        try:
            card = task_store.read(self.store, task)
        except TaskError:
            return None
        window = (card.session or {}).get("tmux_window")
        if not window:
            return None
        return task_tmux.window_alive(window, environ=self.environ)

    def landed(self, branch: str) -> bool:
        return merge_git.is_ancestor(self.repo, f"refs/heads/{branch}", f"refs/heads/{self.target}")


class Context:
    """The task, its card, and the queue it belongs to."""

    def __init__(self, store: Path, card: Task, target: str, environ: Mapping[str, str], lease: timedelta) -> None:
        self.store = store
        self.task = card.id
        self.card = card
        self.repo = card.repo
        self.target = target
        self.environ = environ
        self.lease = lease
        self.path = merge_store.queue_path(store, card.repo)

    def probe(self) -> LiveProbe:
        return LiveProbe(self.store, self.repo, self.target, self.environ)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf merge", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def task_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--task", metavar="ID", help="task id (default: $BKF_TASK)")
        sub.add_argument("--target", metavar="BRANCH",
                         help="the branch the work lands on (default: origin's HEAD, else main or master)")

    enter = commands.add_parser("enter", help="join the queue at the back, with the card in to-merge")
    task_options(enter)
    enter.add_argument("--worktree", metavar="PATH", help="the session's worktree (default: the card's, else cwd)")

    wait = commands.add_parser("wait", help="block until the turn is yours (exit 0), joining the queue if needed")
    task_options(wait)
    wait.add_argument("--timeout", type=float, default=WAIT_TIMEOUT_SECONDS, metavar="S",
                      help=f"seconds to wait before exit 75 (default {WAIT_TIMEOUT_SECONDS})")
    wait.add_argument("--worktree", metavar="PATH", help="if joining: the session's worktree")

    verify = commands.add_parser("verify", help="record the branch and target heads the checks ran on")
    task_options(verify)
    land = commands.add_parser("land", help="fast-forward the target to the verified branch")
    task_options(land)
    land.add_argument("--continue", dest="interim", action="store_true",
                      help="an interim land: the card goes back to working and the session keeps its branch")
    fail = commands.add_parser("fail", help="give up the turn: the card gets the reason and leaves the queue")
    task_options(fail)
    fail.add_argument("--reason", required=True, metavar="TEXT")
    leave = commands.add_parser("leave", help="cancel: leave the queue and give the turn to the next")
    task_options(leave)

    status = commands.add_parser("status", help="show the queue (read-only)")
    status.add_argument("--repo", metavar="DIR", help="only the queue of the repository holding DIR")
    status.add_argument("--task", metavar="ID", help="also report this task's place")
    status.add_argument("--json", action="store_true", help="print one JSON object")

    parser.set_defaults()
    return parser


def _task_id(given: str | None, environ: Mapping[str, str]) -> str:
    if given:
        return given
    current = environ.get(TASK_ENV, "")
    if current:
        return current
    raise Stop(EXIT_REFUSED, "no task id: pass --task, or run it from a task's window")


def _context(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> Context:
    card = task_store.read(store, _task_id(args.task, environ))
    path = merge_store.queue_path(store, card.repo)
    existing = merge_store.load(path)
    target = _target(args.target, existing, card.repo)
    return Context(store, card, target, environ, merge_store.lease_length(environ))


def _target(explicit: str | None, existing: dict[str, Any] | None, repo: str) -> str:
    if existing is not None:
        if explicit and explicit != existing["target"]:
            raise Stop(EXIT_REFUSED, f"the queue of {repo} lands on {existing['target']}, not {explicit}")
        return existing["target"]
    return explicit or merge_git.detect_target(repo)


def _work_place(card: Task, explicit: str | None) -> tuple[str, str]:
    """Return (worktree, branch) of the session: the explicit path, else the card's, else the current folder's."""
    path = explicit
    recorded = (card.worktree or {}).get("path")
    if path is None and recorded and Path(recorded).is_dir():
        path = recorded
    if path is None:
        path = merge_git.toplevel(os.getcwd())
    if not path:
        raise Stop(EXIT_REFUSED, "no worktree: run it inside the session's worktree or pass --worktree")
    path = str(Path(path).resolve())
    branch = merge_git.branch_of(path)
    if branch is None:
        raise Stop(EXIT_REFUSED, f"no branch is checked out at {path}")
    return path, branch


def _update_card(store: Path, task: str, change: Callable[[Task], Any]) -> None:
    task_store.update(store, task, change)


def _leave_queue_card(store: Path, task: str) -> None:
    """Move the card out of to-merge after an interim land. A card that is already gone has nothing to move."""
    try:
        _update_card(store, task, task_store.leave_merge)
    except TaskError:
        pass


def _apply_recovery(store: Path, found: merge_store.Recovery) -> None:
    if found.note is None:
        return
    try:
        task_store.update(store, found.task, lambda card: task_store.merge_failed(card, note=found.note, now=None))
    except TaskError:
        return  # the card is gone: there is nothing to tell


def _mutate(ctx: Context, action: Callable[[dict[str, Any], datetime], int | None]) -> int | None:
    """Run one change of the queue under the store lock.

    Stale entries are settled first, so every command sees the same queue as recovery leaves it. The queue is
    saved whenever it changed, even when the action refuses, so a refusal still records what recovery did.
    """
    with task_store.locked(ctx.store):
        queue = merge_store.load(ctx.path) or merge_store.new_queue(ctx.repo, ctx.target)
        before = merge_store.copy_queue(queue)
        now = merge_store.now_utc()
        try:
            for found in merge_store.recover(queue, now, ctx.lease, ctx.probe()):
                _apply_recovery(ctx.store, found)
                print(f"Removed {found.task} from the merge queue: {found.reason}.")
            merge_store.renew(queue, now, ctx.lease, task=ctx.task)
            return action(queue, now)
        finally:
            if queue != before:
                merge_store.save(ctx.store, ctx.path, queue)


def _turn_entry(queue: dict[str, Any], task: str) -> dict[str, Any]:
    head = merge_store.holder(queue)
    if head is not None and head["task"] == task:
        return head
    if merge_store.find(queue, task) is None:
        kind, reason = _gone(queue, task)
        raise Stop(EXIT_NOT_TURN, f"task {task} is not in the merge queue: {_gone_message(kind, reason)}")
    raise Stop(EXIT_NOT_TURN, f"not your turn: {head['task']} holds the turn, your entry waits")


def _join(ctx: Context, queue: dict[str, Any], now: datetime, worktree: str, branch: str) -> None:
    """Put the task at the back of the queue, grant the turn if the queue was idle, and move the card to to-merge."""
    merge_store.add(queue, ctx.task, branch, worktree, now)
    merge_store.promote(queue, now, ctx.lease)
    _update_card(ctx.store, ctx.task, task_store.enter_merge)


def _position(queue: dict[str, Any], task: str) -> str:
    index = merge_store.find(queue, task)
    if index is None:
        return ""
    if merge_store.holder(queue) is queue["entries"][index]:
        return "It is your turn"
    return f"Position {index + 1}, {index} ahead"


def cmd_enter(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    ctx = _context(args, store, environ)
    worktree, branch = _work_place(ctx.card, args.worktree)
    if branch == ctx.target:
        raise Stop(EXIT_REFUSED, f"branch {branch} is the target: only a session's own branch joins the queue")

    def action(queue: dict[str, Any], now: datetime) -> int:
        if merge_store.find(queue, ctx.task) is None:
            _join(ctx, queue, now, worktree, branch)
            verb = "Entered the merge queue"
        else:
            queue["entries"][merge_store.find(queue, ctx.task)]["seen"] = merge_store.stamp(now)
            _update_card(ctx.store, ctx.task, task_store.enter_merge)
            verb = "Already in the merge queue"
        print(f"{verb} for {ctx.target} ({branch}). {_position(queue, ctx.task)}.")
        print("Next: run bkf merge wait; it returns when the turn is yours.")
        return EXIT_OK

    return _mutate(ctx, action) or EXIT_OK


def cmd_wait(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    ctx = _context(args, store, environ)
    deadline = time.monotonic() + args.timeout
    joined = False  # this command has seen the task in the queue
    place: tuple[str, str] | None = None

    def action(queue: dict[str, Any], now: datetime) -> int | None:
        nonlocal joined, place
        index = merge_store.find(queue, ctx.task)
        if index is None:
            if joined:
                kind, reason = _gone(queue, ctx.task)
                raise Stop(EXIT_ENTRY_GONE, f"your entry left the merge queue: {_gone_message(kind, reason)}")
            if place is None:
                place = _work_place(ctx.card, args.worktree)
            _join(ctx, queue, now, *place)
            print(f"Entered the merge queue for {ctx.target} ({place[1]}).")
            index = merge_store.find(queue, ctx.task)
        joined = True
        entry = queue["entries"][index]
        if entry["state"] == "turn":
            print(f"Your turn on {ctx.target}: branch {entry['branch']}. Next: git merge {ctx.target} into the "
                  "branch (a merge commit, no rebase), run the repository's checks, then bkf merge verify "
                  "and bkf merge land. Resolve conflicts yourself; if you cannot, bkf merge fail --reason TEXT.")
            return EXIT_OK
        if now - merge_store.parse(entry["seen"]) >= SEEN_EVERY:
            entry["seen"] = merge_store.stamp(now)
        return None

    while True:
        code = _mutate(ctx, action)
        if code is not None:
            return code
        if time.monotonic() >= deadline:
            print(f"Still waiting for your turn on {ctx.target} after {args.timeout:g} seconds: run bkf merge wait again.")
            return EXIT_TIMEOUT
        time.sleep(WAIT_POLL_SECONDS)


def _gone(queue: dict[str, Any], task: str) -> tuple[str, str]:
    """Why the task's entry left the queue, from its last event: ("takeout", ""), ("landed", why) or ("recovery", why).

    A take-out is a `leave`, by the owner or by the session. A recovery drop is the queue's own doing (a lost
    lease or window, a dormant waiter, a land that died); its reason is the event's reason.
    """
    for event in reversed(queue["events"]):
        if event["task"] != task:
            continue
        if event["event"] == "left":
            return "takeout", ""
        if event["event"] == "landed":
            return "landed", event["reason"] or "it landed"
        if event["event"] in RECOVERY_EVENTS:
            return "recovery", event["reason"] or "the queue removed it"
    return "recovery", "the queue dropped it"


def _gone_message(kind: str, reason: str) -> str:
    """What a session whose entry is gone should do next; the take-out and the recovery read differently."""
    if kind == "takeout":
        return ("the owner took the task out of the merge queue. Stop the merge flow: do not land, and do not "
                "re-enter on your own; tell the owner and wait for instructions")
    if kind == "landed":
        return f"its branch already landed ({reason}), so there is nothing left to land; do not enter again"
    return (f"the queue removed it, not the owner: {reason}. You may run bkf merge enter again if you still want "
            "to land; it joins the back of the queue")


def cmd_verify(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    ctx = _context(args, store, environ)

    def action(queue: dict[str, Any], now: datetime) -> int:
        entry = _turn_entry(queue, ctx.task)
        if not merge_git.is_clean(entry["worktree"]):
            raise Stop(EXIT_REFUSED, f"uncommitted changes in {entry['worktree']}: commit them on the branch first")
        head = merge_git.head_of(entry["worktree"])
        main = merge_git.ref_sha(ctx.repo, f"refs/heads/{ctx.target}")
        if head is None or main is None:
            raise Stop(EXIT_REFUSED, f"cannot read the branch {entry['branch']} or {ctx.target}")
        entry["verified"] = {"head": head, "main": main}
        entry["phase"] = "testing"
        merge_store.log(queue, now, ctx.task, "verified", f"{head[:12]} on {ctx.target} at {main[:12]}")
        print(f"Verified {entry['branch']} at {head[:12]} on {ctx.target} at {main[:12]}. Next: bkf merge land.")
        return EXIT_OK

    return _mutate(ctx, action) or EXIT_OK


def cmd_land(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    ctx = _context(args, store, environ)
    interim = bool(args.interim)

    def action(queue: dict[str, Any], now: datetime) -> int:
        entry = _turn_entry(queue, ctx.task)
        verified = entry["verified"]
        if verified is None:
            raise Stop(EXIT_MOVED, "not verified: run bkf merge verify first")
        head = merge_git.head_of(entry["worktree"])
        if head != verified["head"]:
            raise Stop(EXIT_MOVED, "the branch changed after verify: merge the target, run the checks, "
                                   "then verify again")
        main = merge_git.ref_sha(ctx.repo, f"refs/heads/{ctx.target}")
        if main != verified["main"]:
            merge_store.log(queue, now, ctx.task, "main-moved",
                            f"{ctx.target} moved from {verified['main'][:12]} to {(main or '-')[:12]}")
            raise Stop(EXIT_MOVED, f"{ctx.target} moved after verify: git merge {ctx.target} into the branch, "
                                   "run the checks, then verify again")
        if main is None or not merge_git.is_ancestor(ctx.repo, main, head):
            raise Stop(EXIT_MOVED, f"the branch does not contain {ctx.target}: git merge {ctx.target} into it, "
                                   "then verify again")
        checkout = merge_git.checkout_of(ctx.repo, ctx.target)
        if checkout is not None and not merge_git.is_clean(checkout):
            raise Stop(EXIT_MAIN_REFUSED, f"the checkout of {ctx.target} at {checkout} has uncommitted changes; "
                                          "the owner must clean it before you land")
        entry["phase"] = "landing"
        merge_store.save(ctx.store, ctx.path, queue)  # on disk before the move, so a crash can be settled
        refusal = merge_git.fast_forward(ctx.repo, ctx.target, entry["branch"], main)
        if refusal is not None:
            entry["phase"] = "testing"
            raise Stop(EXIT_MAIN_REFUSED, f"{ctx.target} did not move: {refusal}")
        merge_store.remove(queue, ctx.task)
        landed = f"{entry['branch']} at {head[:12]}"
        merge_store.log(queue, now, ctx.task, "landed", f"interim: {landed}" if interim else landed)
        merge_store.promote(queue, now, ctx.lease)
        if interim:
            _leave_queue_card(ctx.store, ctx.task)
            print(f"Landed {entry['branch']} on {ctx.target} (interim). The card is working again and the entry "
                  "left the queue. The session may keep working on the same branch; before its next land, run "
                  f"bkf merge enter again, then bkf merge wait. On its turn, merge {ctx.target} into the branch, run "
                  "the checks, then bkf merge verify and bkf merge land (without --continue for the last land).")
        else:
            print(f"Landed {entry['branch']} on {ctx.target}. Next: remove your worktree and branch "
                  f"(git-worktree-cleanup), then bkf task close.")
        return EXIT_OK

    return _mutate(ctx, action) or EXIT_OK


def cmd_fail(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    reason = " ".join(args.reason.split())
    if not reason:
        raise Stop(EXIT_REFUSED, "--reason needs text")
    ctx = _context(args, store, environ)

    def action(queue: dict[str, Any], now: datetime) -> int:
        entry = _turn_entry(queue, ctx.task)
        if entry["phase"] == "landing":
            raise Stop(EXIT_REFUSED, "a land is in progress: it finishes or is settled first")
        merge_store.remove(queue, ctx.task)
        merge_store.log(queue, now, ctx.task, "failed", reason)
        merge_store.promote(queue, now, ctx.lease)
        _update_card(ctx.store, ctx.task, lambda card: task_store.merge_failed(card, note=reason, now=None))
        print(f"Failed {entry['branch']}: {reason}. The card is working with the merge-failed mark. "
              "Fix the branch, commit, then bkf merge enter again (the back of the queue).")
        return EXIT_OK

    return _mutate(ctx, action) or EXIT_OK


def cmd_leave(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    ctx = _context(args, store, environ)

    def action(queue: dict[str, Any], now: datetime) -> int:
        index = merge_store.find(queue, ctx.task)
        if index is None:
            print(f"Task {ctx.task} is not in the merge queue; nothing to leave.")
            return EXIT_OK
        if queue["entries"][index]["phase"] == "landing":
            raise Stop(EXIT_REFUSED, "a land is in progress: it finishes or is settled first")
        merge_store.remove(queue, ctx.task)
        merge_store.log(queue, now, ctx.task, "left")
        merge_store.promote(queue, now, ctx.lease)
        _leave_queue_card(ctx.store, ctx.task)
        print(f"Left the merge queue for {ctx.target}.")
        return EXIT_OK

    return _mutate(ctx, action) or EXIT_OK


def _queue_view(queue: dict[str, Any], stale: dict[str, bool], probe: LiveProbe) -> dict[str, Any]:
    head = merge_store.holder(queue)
    lock = None
    if head is not None:
        lock = {
            "task": head["task"], "since": head["turn_since"], "lease_until": head["lease_until"],
            "phase": head["phase"], "stale": stale[head["task"]],
        }
    entries = [
        {
            "position": index, "task": entry["task"], "branch": entry["branch"], "worktree": entry["worktree"],
            "state": entry["state"], "entered": entry["entered"], "turn_since": entry["turn_since"],
            "stale": stale[entry["task"]],
        }
        for index, entry in enumerate(queue["entries"], start=1)
    ]
    return {
        "repo": queue["repo"],
        "target": queue["target"],
        "target_head": merge_git.ref_sha(queue["repo"], f"refs/heads/{queue['target']}"),
        "lock": lock,
        "entries": entries,
        "events": queue["events"],
    }


def _task_view(queues: list[dict[str, Any]], task: str) -> dict[str, Any]:
    for queue in queues:
        for entry in queue["entries"]:
            if entry["task"] == task:
                return {"in_queue": True, "position": entry["position"], "state": entry["state"],
                        "queue_ahead": entry["position"] - 1}
    return {"in_queue": False, "position": None, "state": None, "queue_ahead": None}


def _status_queues(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> list[Path]:
    if args.repo is not None:
        return [merge_store.queue_path(store, task_store.repo_identity(args.repo))]
    if args.task is not None:
        try:
            return [merge_store.queue_path(store, task_store.read(store, args.task).repo)]
        except TaskError:
            pass  # the card is gone: an entry may still wait for it, so look in every queue
    return merge_store.queue_paths(store)


def cmd_status(args: argparse.Namespace, store: Path, environ: Mapping[str, str]) -> int:
    lease = merge_store.lease_length(environ)
    now = merge_store.now_utc()
    queues = []
    for path in _status_queues(args, store, environ):
        queue = merge_store.load(path)
        if queue is None:
            continue
        probe = LiveProbe(store, queue["repo"], queue["target"], environ)
        queues.append(_queue_view(queue, merge_store.stale_map(queue, now, lease, probe), probe))
    payload: dict[str, Any] = {
        "schema": JSON_SCHEMA,
        "store": str(store.absolute()),
        "generation": task_store.generation(store),
        "queues": queues,
    }
    if args.task is not None:
        payload["task"] = _task_view(queues, args.task)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return EXIT_OK
    _print_status(payload)
    return EXIT_OK


def _print_status(payload: dict[str, Any]) -> None:
    if not payload["queues"]:
        print("The merge queue is empty.")
    for queue in payload["queues"]:
        print(f"{queue['repo']} lands on {queue['target']} (head {(queue['target_head'] or '-')[:12]})")
        lock = queue["lock"]
        if lock:
            flag = "  STALE" if lock["stale"] else ""
            print(f"  turn: {lock['task']} phase {lock['phase'] or '-'} since {lock['since']}{flag}")
        for entry in queue["entries"]:
            flag = "  STALE" if entry["stale"] else ""
            print(f"  {entry['position']}. {entry['task']}  {entry['state']}  {entry['branch']}{flag}")
    if "task" in payload:
        task = payload["task"]
        print(f"task: in queue {task['in_queue']}, position {task['position']}, state {task['state']}, "
              f"queue ahead {task['queue_ahead']}")


def main(argv: list[str] | None = None, environ: Mapping[str, str] = os.environ, store: Path | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "enter": cmd_enter, "wait": cmd_wait, "verify": cmd_verify, "land": cmd_land,
        "fail": cmd_fail, "leave": cmd_leave, "status": cmd_status,
    }
    try:
        return handlers[args.command](args, store or task_store.store_dir(environ), environ)
    except Stop as stop:
        print(f"bkf merge: {stop.message}", file=sys.stderr)
        return stop.code
    except (MergeError, TaskError, merge_git.GitError, OSError) as error:
        print(f"bkf merge: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())

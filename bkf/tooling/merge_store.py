"""The merge queue of one repository: its file, the turn rules and the recovery of a stale turn.

One queue file per repository lives under the task store's `.merge` folder. Every change of it happens under
the store's lock and bumps the store generation. The head entry in the turn state is the lock: only the head
may land. A holder that lost its tmux window, its task or its lease, and a waiter that stopped polling, are
recovered by `recover`, which the mutating commands run first. This module changes no git state and no task;
`bkf_merge` applies what `recover` reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import task_store
from task_store import STAMP_FORMAT


SCHEMA = 1
QUEUE_FOLDER = ".merge"
QUEUE_FILE = "queue.json"
EVENTS_LIMIT = 50
LEASE_ENV = "BKF_MERGE_LEASE_MINUTES"
LEASE_DEFAULT_MINUTES = 60
# The task hook renews the holder's lease at most this often, so a busy session does not write on every tool call.
TOUCH_EVERY = timedelta(seconds=60)
DORMANT_AFTER = timedelta(minutes=3)
# The attention note a task gets when its place in the queue is lost.
LOST_PLACE = "lost its place in the merge queue: {}"
ENTRY_KEYS = (
    "task", "branch", "worktree", "entered", "seen", "state", "turn_since", "lease_until", "phase", "verified",
)
EVENT_KEYS = ("at", "task", "event", "reason")
STATES = ("waiting", "turn")
PHASES = ("testing", "landing")


class MergeError(Exception):
    """A queue that cannot be read or a setting that cannot be used."""


@dataclass(frozen=True)
class Recovery:
    """One entry the recovery removed: the event it recorded, the reason, and the task note (None: none)."""

    task: str
    event: str
    reason: str
    note: str | None


class Probe(Protocol):
    """What recovery and status ask about the outside world; the real one reads tasks, tmux and git."""

    def task_exists(self, task: str) -> bool: ...

    def window_alive(self, task: str) -> bool | None: ...

    def landed(self, branch: str) -> bool: ...


def lease_length(environ: Mapping[str, str] = os.environ) -> timedelta:
    text = environ.get(LEASE_ENV, "")
    if not text:
        return timedelta(minutes=LEASE_DEFAULT_MINUTES)
    try:
        minutes = int(text)
    except ValueError:
        raise MergeError(f"{LEASE_ENV} must be a whole number of minutes, not {text!r}") from None
    if minutes < 1:
        raise MergeError(f"{LEASE_ENV} must be at least 1 minute")
    return timedelta(minutes=minutes)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def stamp(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime(STAMP_FORMAT)


def parse(text: str) -> datetime:
    return datetime.strptime(text, STAMP_FORMAT).replace(tzinfo=timezone.utc)


def repo_key(repo: str) -> str:
    """Return the folder name of a repository's queue: its identity as a slug, with a hash so two paths never share one."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", repo).strip("-")[:100] or "repo"
    return f"{slug}-{hashlib.sha256(repo.encode('utf-8')).hexdigest()[:8]}"


def queue_path(store: Path, repo: str) -> Path:
    return Path(store) / QUEUE_FOLDER / repo_key(repo) / QUEUE_FILE


def queue_paths(store: Path) -> list[Path]:
    """Every queue file of the store, sorted by path."""
    folder = Path(store) / QUEUE_FOLDER
    if not folder.is_dir():
        return []
    return sorted(folder.glob(f"*/{QUEUE_FILE}"))


def new_queue(repo: str, target: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "repo": repo, "target": target, "lock": None, "entries": [], "events": []}


def load(path: Path) -> dict[str, Any] | None:
    """Return the queue in path, or None when it has none yet. A file that is not a schema 1 queue is refused."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        raise MergeError(f"cannot read the merge queue {path}: {error}") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise MergeError(f"the merge queue {path} is not valid JSON") from None
    problem = _problem(data)
    if problem:
        raise MergeError(f"the merge queue {path} is unreadable: {problem}")
    return data


def save(store: Path, path: Path, queue: dict[str, Any]) -> None:
    """Write the queue atomically and bump the store generation; the caller holds the store lock."""
    text = json.dumps(queue, indent=2, ensure_ascii=False) + "\n"
    with task_store.locked(store):
        path.parent.mkdir(parents=True, exist_ok=True)
        task_store.write_atomic(path, text)
        task_store.bump(store)


def holder(queue: dict[str, Any]) -> dict[str, Any] | None:
    """The entry holding the turn: the head, when its state is turn. That entry is the lock."""
    entries = queue["entries"]
    return entries[0] if entries and entries[0]["state"] == "turn" else None


def find(queue: dict[str, Any], task: str) -> int | None:
    for index, entry in enumerate(queue["entries"]):
        if entry["task"] == task:
            return index
    return None


def queued(store: Path, repo: str, task: str) -> bool:
    """True when the task holds an entry in its repository's queue; a queue that does not exist holds none."""
    queue = load(queue_path(store, repo))
    return queue is not None and find(queue, task) is not None


def log(queue: dict[str, Any], now: datetime, task: str, event: str, reason: str | None = None) -> None:
    queue["events"].append({"at": stamp(now), "task": task, "event": event, "reason": reason})
    del queue["events"][:-EVENTS_LIMIT]


def add(queue: dict[str, Any], task: str, branch: str, worktree: str | None, now: datetime) -> dict[str, Any]:
    """Append a waiting entry at the back of the queue and log it."""
    entry = {
        "task": task, "branch": branch, "worktree": worktree, "entered": stamp(now), "seen": stamp(now),
        "state": "waiting", "turn_since": None, "lease_until": None, "phase": None, "verified": None,
    }
    queue["entries"].append(entry)
    log(queue, now, task, "entered")
    return entry


def remove(queue: dict[str, Any], task: str) -> dict[str, Any]:
    index = find(queue, task)
    if index is None:
        raise MergeError(f"task {task} is not in the merge queue")
    return queue["entries"].pop(index)


def promote(queue: dict[str, Any], now: datetime, lease: timedelta) -> dict[str, Any] | None:
    """Give the turn to the head when nobody holds it. Return the new holder, or None when nothing changed."""
    if not queue["entries"] or holder(queue) is not None:
        return None
    head = queue["entries"][0]
    head.update(
        state="turn", turn_since=stamp(now), lease_until=stamp(now + lease), phase="testing", verified=None,
    )
    log(queue, now, head["task"], "turn-started")
    return head


def renew(
    queue: dict[str, Any], now: datetime, lease: timedelta,
    *, task: str | None = None, minimum_age: timedelta = timedelta(0),
) -> bool:
    """Extend the holder's lease when its last sign of life is at least minimum_age old. Return True if it did."""
    head = holder(queue)
    if head is None or (task is not None and head["task"] != task):
        return False
    last_sign = parse(head["lease_until"]) - lease
    if now - last_sign < minimum_age:
        return False
    head["lease_until"] = stamp(now + lease)
    return True


def _minutes(lease: timedelta) -> int:
    return int(lease.total_seconds() // 60)


def holder_problem(entry: dict[str, Any], now: datetime, lease: timedelta, probe: Probe) -> str | None:
    """Why the turn holder cannot keep the turn, or None when it may."""
    if not probe.task_exists(entry["task"]):
        return "its task is gone"
    if probe.window_alive(entry["task"]) is False:
        return "its tmux window is gone"
    if parse(entry["lease_until"]) <= now:
        return f"no sign of life for {_minutes(lease)} minutes"
    return None


def waiter_problem(entry: dict[str, Any], now: datetime, probe: Probe) -> str | None:
    """Why a waiting entry is dropped, or None when it may stay."""
    if not probe.task_exists(entry["task"]):
        return "its task is gone"
    if now - parse(entry["seen"]) > DORMANT_AFTER:
        return "it did not poll for the turn for 3 minutes"
    return None


def recover(queue: dict[str, Any], now: datetime, lease: timedelta, probe: Probe) -> list[Recovery]:
    """Remove the entries that cannot stay, log why, and give the turn to the next. Mutates the queue.

    A holder whose recorded land is in phase landing is settled by its branch: an ancestor of the target means
    the land finished before it was written down; otherwise the land failed. Any other stale holder loses its
    place, and so does a waiter that stopped polling or whose task is gone.
    """
    found: list[Recovery] = []
    head = holder(queue)
    if head is not None:
        if head["phase"] == "landing":
            remove(queue, head["task"])
            if probe.landed(head["branch"]):
                log(queue, now, head["task"], "landed", "the land finished before it was written down")
                found.append(Recovery(head["task"], "landed", "the land finished before it was written down", None))
            else:
                reason = "the land did not finish: the branch is not on the target"
                log(queue, now, head["task"], "failed", reason)
                found.append(Recovery(head["task"], "failed", reason, reason))
        else:
            why = holder_problem(head, now, lease, probe)
            if why:
                remove(queue, head["task"])
                log(queue, now, head["task"], "lock-recovered", why)
                found.append(Recovery(head["task"], "lock-recovered", why, LOST_PLACE.format(why)))
    for entry in list(queue["entries"]):
        if entry["state"] != "waiting":
            continue
        why = waiter_problem(entry, now, probe)
        if why:
            remove(queue, entry["task"])
            log(queue, now, entry["task"], "dropped-dormant", why)
            found.append(Recovery(entry["task"], "dropped-dormant", why, LOST_PLACE.format(why)))
    promote(queue, now, lease)
    return found


def stale_map(queue: dict[str, Any], now: datetime, lease: timedelta, probe: Probe) -> dict[str, bool]:
    """Return {task: stale} for each entry without changing the queue: what recover would remove."""
    result: dict[str, bool] = {}
    head = holder(queue)
    for entry in queue["entries"]:
        if entry is head:
            stale = entry["phase"] == "landing" or holder_problem(entry, now, lease, probe) is not None
        else:
            stale = waiter_problem(entry, now, probe) is not None
        result[entry["task"]] = stale
    return result


def touch_from_hook(store: Path, task: str, environ: Mapping[str, str] = os.environ) -> None:
    """Renew the lease of a task that holds the turn, at most once a minute. Other tasks change nothing.

    The unlocked read only skips the lock on the common path; the locked read decides.
    """
    card = task_store.read(store, task)
    path = queue_path(store, card.repo)
    current = load(path)
    if current is None or holder(current) is None or holder(current)["task"] != task:
        return
    lease = lease_length(environ)
    with task_store.locked(store):
        queue = load(path)
        if queue is not None and renew(queue, now_utc(), lease, task=task, minimum_age=TOUCH_EVERY):
            save(store, path, queue)


def _problem(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("schema") != SCHEMA:
        return "unsupported schema"
    for name in ("repo", "target"):
        if not isinstance(data.get(name), str) or not data[name]:
            return f"{name} is missing"
    if not isinstance(data.get("entries"), list) or not isinstance(data.get("events"), list):
        return "entries or events is not a list"
    for entry in data["entries"]:
        if not isinstance(entry, dict) or set(ENTRY_KEYS) - set(entry):
            return "an entry lacks fields"
        if entry["state"] not in STATES or entry["phase"] not in (None, *PHASES):
            return "an entry has an unknown state or phase"
        if not task_store.is_valid_id(entry["task"]):
            return "an entry has a bad task id"
    if any(not isinstance(event, dict) or set(EVENT_KEYS) - set(event) for event in data["events"]):
        return "an event lacks fields"
    turns = [entry for entry in data["entries"] if entry["state"] == "turn"]
    if len(turns) > 1 or (turns and data["entries"][0] is not turns[0]):
        return "more than one turn, or a turn that is not the head"
    return None


def copy_queue(queue: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(queue))

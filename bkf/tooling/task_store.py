"""Keep the machine-wide store of agent tasks, one folder per task, under the BKF state directory."""

from __future__ import annotations

import contextlib
import copy
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path
from typing import Any, Callable, Iterator


SCHEMA = 1
KINDS = ("task", "handoff", "unit")
STATUSES = ("todo", "working", "to-merge", "failed")
REASONS = ("prompt", "quota", "launch-failed", "escalated", "paused", "merge-failed")
SESSION_KEYS = ("agent", "model", "effort", "reviewer", "tmux_session", "tmux_window", "claude_session_id")
WORKTREE_KEYS = ("path", "branch", "head")
ATTENTION_KEYS = ("reason", "since", "note")
FIELDS = (
    "id", "kind", "parent", "repo", "title", "body", "source", "status", "attention", "session",
    "worktree", "run_dir", "exit", "note", "created", "updated",
)
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TITLE_LIMIT = 120
# The title a session card takes from its window name or its first prompt.
SESSION_TITLE_LIMIT = 80
# The folder of the Claude session links, one JSON file per session. Its dot name keeps list_tasks from reading it.
SESSIONS_FOLDER = ".sessions"
# Written once the legacy statuses (done, review) are migrated; its dot name keeps list_tasks from reading it.
MIGRATED_MARKER = ".migrated-statuses"

_ID = re.compile(r"[a-z0-9-]{1,64}")
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_GENERATION = re.compile(r"[0-9]+")
_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_LEADING_MARKS = re.compile(r"^[#\s]+")
_BREAK = re.compile(r"[\r\n\v\f\x1c-\x1e\x85  ]")


class TaskError(Exception):
    """Base class of every error this module raises."""


class InvalidId(TaskError):
    pass


class InvalidValue(TaskError):
    pass


class UnknownTask(TaskError):
    pass


class CorruptTask(TaskError):
    pass


class InvalidTransition(TaskError):
    def __init__(self, from_status: str, to_status: str) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"a task cannot go from {from_status} to {to_status}")


@dataclass
class Task:
    id: str
    kind: str
    parent: str | None
    repo: str
    title: str
    body: str
    source: str | None
    status: str
    attention: dict[str, Any] | None
    session: dict[str, Any] | None
    worktree: dict[str, Any] | None
    run_dir: str | None
    exit: int | None
    note: str | None
    created: str
    updated: str

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {"schema": SCHEMA}
        for name in FIELDS:
            data[name] = copy.deepcopy(getattr(self, name))
        return data

    @classmethod
    def from_json(cls, data: Any, folder_name: str) -> Task:
        if not isinstance(data, dict):
            raise CorruptTask(f"task {folder_name} is not a JSON object")
        problem = _problem(data, folder_name)
        if problem:
            raise CorruptTask(f"task {folder_name} is unreadable: {problem}")
        return cls(**{name: copy.deepcopy(data[name]) for name in FIELDS})


@dataclass
class TaskList:
    tasks: list[Task]
    unreadable: list[str]


def store_dir(environ: Any = os.environ) -> Path:
    """Return the store folder: BKF_TASKS_DIR, else XDG_STATE_HOME, else ~/.local/state."""
    explicit = environ.get("BKF_TASKS_DIR")
    if explicit:
        return Path(explicit)
    state_home = environ.get("XDG_STATE_HOME")
    if state_home:
        return Path(state_home) / "bkf" / "tasks"
    home = Path(environ["HOME"]) if environ.get("HOME") else Path.home()
    return home / ".local" / "state" / "bkf" / "tasks"


def is_valid_id(text: Any) -> bool:
    return isinstance(text, str) and _ID.fullmatch(text) is not None


def repo_identity(path: str | os.PathLike[str]) -> str:
    """Return the folder holding the git common dir, so linked worktrees share one identity."""
    return git_repo(path) or str(Path(path).resolve())


def git_repo(path: str | os.PathLike[str]) -> str | None:
    """Return the repository identity of a directory inside git, or None outside a repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return str(Path(result.stdout.strip()).resolve().parent)


def generation(store: Path) -> int:
    path = Path(store) / "generation"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return 0
    if not _GENERATION.fullmatch(text):
        raise TaskError(f"the store generation is not a number: {path}")
    return int(text)


def create(
    store: Path,
    *,
    repo: str,
    title: str,
    kind: str = "task",
    body: str = "",
    source: str | None = None,
    parent: str | None = None,
    now: datetime | None = None,
) -> Task:
    store = Path(store)
    _ensure_migrated(store)
    when = _utc(now)
    stamp = _stamp(when)
    with locked(store):
        task_id = _fresh_id(store, when)
        task = Task(
            id=task_id, kind=kind, parent=parent, repo=repo,
            title=_normalize_title(title), body=body, source=source, status="todo",
            attention=None, session=None, worktree=None, run_dir=None, exit=None, note=None,
            created=stamp, updated=stamp,
        )
        text = _record_text(task, task_id)
        staging = Path(tempfile.mkdtemp(prefix=".new-", dir=store))
        try:
            write_atomic(staging / "task.json", text)
            os.rename(staging, store / task_id)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        bump(store)
    return task


def read(store: Path, task_id: str) -> Task:
    _ensure_migrated(Path(store))
    return _read_task(_existing(store, task_id))


def list_tasks(store: Path) -> TaskList:
    store = Path(store)
    _ensure_migrated(store)
    if not store.is_dir():
        return TaskList(tasks=[], unreadable=[])
    tasks: list[Task] = []
    unreadable: list[str] = []
    for entry in sorted(store.iterdir(), key=lambda item: item.name):
        if not is_valid_id(entry.name) or not entry.is_dir():
            continue
        try:
            tasks.append(_read_task(entry))
        except CorruptTask:
            unreadable.append(entry.name)
    tasks.sort(key=lambda task: (task.created, task.id))
    _attach_legacy_session_ids(store, tasks)
    return TaskList(tasks=tasks, unreadable=unreadable)


def _attach_legacy_session_ids(store: Path, tasks: list[Task]) -> None:
    """Expose an old link only when it is the sole UUID for a card without a recorded current UUID."""
    folder = Path(store) / SESSIONS_FOLDER
    try:
        files = list(folder.glob("*.json"))
    except OSError:
        return
    links: dict[str, set[str]] = {}
    for path in files:
        session_id = path.stem
        if not is_valid_session_id(session_id):
            continue
        link = session_link(store, session_id)
        if link is None:
            continue
        links.setdefault(link["task"], set()).add(session_id)
    for task in tasks:
        if not task.session or task.session.get("agent") != "claude" or "claude_session_id" in task.session:
            continue
        ids = links.get(task.id, set())
        if len(ids) != 1:
            continue
        task.session = {**(task.session or {}), "claude_session_id": next(iter(ids))}


def update(
    store: Path,
    task_id: str,
    change: Callable[[Task], Any],
    now: datetime | None = None,
) -> Task:
    store = Path(store)
    _ensure_migrated(store)
    folder = _existing(store, task_id)
    with locked(store):
        folder = _existing(store, task_id)
        task = _read_task(folder)
        change(task)
        task.updated = _stamp(now)
        text = _record_text(task, folder.name)
        write_atomic(folder / "task.json", text)
        bump(store)
    return task


def write_prompt(store: Path, task_id: str, text: str) -> None:
    store = Path(store)
    _ensure_migrated(store)
    _existing(store, task_id)
    with locked(store):
        folder = _existing(store, task_id)
        write_atomic(folder / "prompt.md", text)
        bump(store)


def read_prompt(store: Path, task_id: str) -> str | None:
    _ensure_migrated(Path(store))
    path = _existing(store, task_id) / "prompt.md"
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def delete(store: Path, task_id: str) -> None:
    store = Path(store)
    _ensure_migrated(store)
    _existing(store, task_id)
    with locked(store):
        folder = _existing(store, task_id)
        shutil.rmtree(folder)
        bump(store)


# Transitions: pure functions that change a Task in place; store.update writes the result.

def start(
    task: Task,
    *,
    session: dict[str, Any] | None = None,
    worktree: dict[str, Any] | None = None,
    run_dir: str | None = None,
) -> None:
    """Begin a run on the card. A working card may begin again (a rerun): that clears its attention.

    A to-merge card may begin too, as a safety net for a card that a session left in to-merge after landing.
    The command refuses it while the card still holds an entry in the merge queue (bkf_task does that check).
    """
    _require(task, ("todo", "working", "failed", "to-merge"), "working")
    task.status = "working"
    task.attention = None
    task.exit = None
    if session is not None:
        task.session = _object(session, SESSION_KEYS)
        if "claude_session_id" not in session:
            task.session.pop("claude_session_id", None)
    if worktree is not None:
        task.worktree = _object(worktree, WORKTREE_KEYS)
    if run_dir is not None:
        task.run_dir = run_dir


def enter_merge(task: Task) -> None:
    """The card joins the merge queue: to-merge, with no attention (the queue is its wait)."""
    _require(task, ("todo", "working", "failed", "to-merge"), "to-merge")
    task.status = "to-merge"
    task.attention = None


def merge_failed(task: Task, *, note: str, now: datetime | None) -> None:
    """The card left the merge queue with a reason: working again, with the merge-failed attention."""
    _require(task, ("todo", "working", "failed", "to-merge"), "working")
    task.status = "working"
    task.attention = {"reason": "merge-failed", "since": _stamp(now), "note": note}


def leave_merge(task: Task) -> None:
    """The card left the merge queue on purpose: working, with no attention."""
    _require(task, ("todo", "working", "failed", "to-merge"), "working")
    task.status = "working"
    task.attention = None


def mark_failed(task: Task, *, exit: int | None = None, note: str | None = None) -> None:
    _require(task, ("working", "to-merge"), "failed")
    task.status = "failed"
    task.attention = None
    if exit is not None:
        task.exit = exit
    if note is not None:
        task.note = note


def set_attention(task: Task, reason: str, *, note: str | None = None, now: datetime | None) -> None:
    if reason not in REASONS:
        raise InvalidValue(f"unknown attention reason: {reason}")
    _require(task, ("todo", "working", "to-merge", "failed"), task.status)
    task.attention = {"reason": reason, "since": _stamp(now), "note": note}


def clear_attention(task: Task) -> None:
    task.attention = None


# Internal helpers.

def _ensure_migrated(store: Path) -> None:
    """Migrate the legacy statuses once: done cards are deleted, review cards become working.

    The marker file records that it ran, so later reads stop here at one stat call. A store that does not
    exist yet is left alone; the first write creates it and the next read migrates nothing.
    """
    store = Path(store)
    if not store.is_dir() or (store / MIGRATED_MARKER).exists():
        return
    with locked(store):
        if not store.is_dir() or (store / MIGRATED_MARKER).exists():
            return
        changed = False
        for entry in sorted(store.iterdir(), key=lambda item: item.name):
            if not is_valid_id(entry.name) or not entry.is_dir():
                continue
            path = entry / "task.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("status") == "done":
                shutil.rmtree(entry)
                changed = True
            elif data.get("status") == "review":
                data["status"] = "working"
                write_atomic(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
                changed = True
        write_atomic(store / MIGRATED_MARKER, "1\n")
        if changed:
            bump(store)


def _require(task: Task, from_statuses: tuple[str, ...], to_status: str) -> None:
    if task.status not in from_statuses:
        raise InvalidTransition(task.status, to_status)


def _object(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - set(keys):
        raise InvalidValue(f"expected only the fields {', '.join(keys)}")
    return {key: value.get(key) for key in keys}


def _normalize_title(title: str) -> str:
    return " ".join(str(title).splitlines()).strip()


def title_from_text(text: str) -> str | None:
    """Return a card title from free text: the first line that has words, without leading markdown marks.

    Leading `#` marks and spaces are removed, runs of whitespace collapse to one space, and a title longer than
    SESSION_TITLE_LIMIT characters ends with an ellipsis. None when no line has words.
    """
    for line in str(text).splitlines():
        words = _LEADING_MARKS.sub("", line)
        title = " ".join(words.split())
        if not title:
            continue
        if len(title) > SESSION_TITLE_LIMIT:
            title = title[: SESSION_TITLE_LIMIT - 1].rstrip() + "…"
        return title
    return None


def _problem(data: dict[str, Any], folder: str | None) -> str | None:
    for name in ("schema", *FIELDS):
        if name not in data:
            return f"missing {name}"
    if type(data["schema"]) is not int or data["schema"] != SCHEMA:
        return "unsupported schema"
    if not is_valid_id(data["id"]) or (folder is not None and data["id"] != folder):
        return "id does not match the folder name"
    if data["kind"] not in KINDS:
        return f"unknown kind {data['kind']!r}"
    if data["parent"] is not None and not is_valid_id(data["parent"]):
        return "parent is not a valid id"
    if not _one_line(data["repo"]):
        return "repo must be one non-empty line"
    if not _one_line(data["title"]) or data["title"] != data["title"].strip():
        return "title must be one non-empty line without surrounding spaces"
    if not isinstance(data["body"], str):
        return "body is not text"
    if not _opt_str(data["source"]):
        return "source is not text"
    if data["status"] not in STATUSES:
        return f"unknown status {data['status']!r}"
    attention = data["attention"]
    if attention is not None:
        if not _has_keys(attention, ATTENTION_KEYS):
            return "attention has the wrong fields"
        if attention["reason"] not in REASONS:
            return f"unknown attention reason {attention['reason']!r}"
        if not _stamp_ok(attention["since"]) or not _opt_str(attention["note"]):
            return "attention has a bad since or note"
    for name, keys in (("session", SESSION_KEYS), ("worktree", WORKTREE_KEYS)):
        value = data[name]
        if value is None:
            continue
        if not isinstance(value, dict):
            return f"{name} has the wrong fields"
        optional_session_id = name == "session" and set(value) == set(keys[:-1])
        if (not _has_keys(value, keys) and not optional_session_id) or not all(
            _opt_str(value[key]) for key in value
        ):
            return f"{name} has the wrong fields"
    if not _opt_str(data["run_dir"]):
        return "run_dir is not text"
    if data["exit"] is not None and type(data["exit"]) is not int:
        return "exit is not a whole number"
    if not _opt_str(data["note"]):
        return "note is not text"
    if not _stamp_ok(data["created"]) or not _stamp_ok(data["updated"]):
        return "created or updated is not a UTC timestamp"
    return None


def _one_line(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != "" and _BREAK.search(value) is None


def _opt_str(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _has_keys(value: Any, keys: tuple[str, ...]) -> bool:
    return isinstance(value, dict) and all(key in value for key in keys)


def _stamp_ok(value: Any) -> bool:
    if not isinstance(value, str) or _STAMP.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, STAMP_FORMAT)
    except ValueError:
        return False
    return True


def _utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _stamp(now: datetime | None) -> str:
    return _utc(now).strftime(STAMP_FORMAT)


def _fresh_id(store: Path, when: datetime) -> str:
    stamp = when.astimezone().strftime("%Y%m%d-%H%M%S")
    while True:
        candidate = f"t{stamp}-{secrets.token_hex(2)}"
        if not (store / candidate).exists():
            return candidate


def _existing(store: Path, task_id: str) -> Path:
    if not is_valid_id(task_id):
        raise InvalidId(f"not a valid task id: {task_id!r}")
    folder = Path(store) / task_id
    if not folder.is_dir():
        raise UnknownTask(f"no task {task_id}")
    return folder


def _read_task(folder: Path) -> Task:
    path = folder / "task.json"
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        raise CorruptTask(f"task {folder.name} has no task.json") from None
    except (OSError, UnicodeDecodeError) as error:
        raise CorruptTask(f"task {folder.name} cannot be read: {error}") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise CorruptTask(f"task {folder.name} is not valid JSON") from None
    return Task.from_json(data, folder.name)


def _record_text(task: Task, folder_name: str) -> str:
    problem = _problem(task.to_json(), folder_name)
    if problem:
        raise InvalidValue(f"task {folder_name} cannot be saved: {problem}")
    return json.dumps(task.to_json(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_atomic(path: Path, text: str) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def bump(store: Path) -> None:
    """Raise the store generation by one; every write of the store calls it under the lock."""
    write_atomic(store / "generation", f"{generation(store) + 1}\n")


_HELD: set[str] = set()


@contextmanager
def locked(store: Path) -> Iterator[None]:
    """Hold the store's write lock. Re-entrant in one process, so a caller may hold it around several writes."""
    store = Path(store)
    key = str(store.resolve())
    if key in _HELD:
        yield
        return
    store.mkdir(parents=True, exist_ok=True)
    fd = os.open(store / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        flock(fd, LOCK_EX)
        _HELD.add(key)
        try:
            yield
        finally:
            _HELD.discard(key)
            flock(fd, LOCK_UN)
    finally:
        os.close(fd)


# Session links: which card a Claude session writes to. One JSON file per session id, written under the lock.

def is_valid_session_id(text: Any) -> bool:
    return isinstance(text, str) and _SESSION.fullmatch(text) is not None


def session_link(store: Path, session_id: str) -> dict[str, Any] | None:
    """Return {"task": id, "default_title": title or None} for a session, or None when it has no valid link."""
    if not is_valid_session_id(session_id):
        return None
    try:
        with open(Path(store) / SESSIONS_FOLDER / f"{session_id}.json", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not is_valid_id(data.get("task")) or not _opt_str(data.get("default_title")):
        return None
    return {"task": data["task"], "default_title": data.get("default_title")}


def write_session_link(store: Path, session_id: str, link: dict[str, Any]) -> None:
    store = Path(store)
    if not is_valid_session_id(session_id):
        raise InvalidValue(f"not a valid session id: {session_id!r}")
    with locked(store):
        folder = store / SESSIONS_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        write_atomic(folder / f"{session_id}.json", json.dumps(link, sort_keys=True) + "\n")
        bump(store)

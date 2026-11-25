"""Give each interactive Claude session in tmux a task in the task store: created on start, done when it ends."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import task_store
import task_tmux
from task_store import TaskError


ENTRYPOINT_ENV = "CLAUDE_CODE_ENTRYPOINT"
INTERACTIVE_ENTRYPOINT = "cli"  # `claude -p` runs as sdk-cli and gets no task
PANE_ENV = "TMUX_PANE"
SESSION_SOURCE = "session"
AGENT = "claude"


def eligible(environ: Mapping[str, str]) -> bool:
    """Return True for an interactive Claude session inside tmux; the only sessions that may get a task."""
    return environ.get(ENTRYPOINT_ENV) == INTERACTIVE_ENTRYPOINT and bool(environ.get(PANE_ENV))


def task_of(store: Path, session_id: Any) -> str | None:
    """Return the id of the task a session writes to, or None when it has none."""
    if not task_store.is_valid_session_id(session_id):
        return None
    link = task_store.session_link(store, session_id)
    return None if link is None else link["task"]


def session_start(store: Path, session_id: Any, cwd: Any, environ: Mapping[str, str]) -> None:
    """Create the session's task, or reuse it on resume and compact; a session outside git gets nothing."""
    if not task_store.is_valid_session_id(session_id) or not isinstance(cwd, str) or not cwd:
        return
    repo = task_store.git_repo(cwd)
    if repo is None:
        return
    pane = environ.get(PANE_ENV, "")
    window = task_tmux.pane_window(pane, environ) if pane else None
    session = {
        "agent": AGENT,
        "tmux_session": window.session if window else None,
        "tmux_window": window.window_id if window else None,
        "claude_session_id": session_id,
    }
    with task_store.locked(store):
        link = task_store.session_link(store, session_id)
        if link is not None and _task_exists(store, link["task"]):
            _refresh(store, link["task"], session)
            return
        title = (window and task_store.title_from_text(window.window_name)) or Path(repo).name
        task = task_store.create(store, repo=repo, title=title, source=SESSION_SOURCE)
        task_store.update(store, task.id, lambda card: task_store.start(card, session=session))
        task_store.write_session_link(store, session_id, {"task": task.id, "default_title": task.title})


def session_end(store: Path, session_id: Any) -> None:
    """Delete the session's task when the session ends, unless it waits in the merge queue or failed to merge.

    The link stays either way: a resume that finds no task makes a new one.
    """
    if not task_store.is_valid_session_id(session_id):
        return
    with task_store.locked(store):
        link = task_store.session_link(store, session_id)
        if link is None or not _task_exists(store, link["task"]):
            return
        card = task_store.read(store, link["task"])
        if _keeps_task(card):
            return
        task_store.delete(store, card.id)


def bind_explicit_task(store: Path, session_id: Any, task_id: Any, environ: Mapping[str, str]) -> None:
    """Associate an explicit BKF task with its current interactive Claude UUID without owning its lifecycle."""
    if not task_store.is_valid_session_id(session_id) or not task_store.is_valid_id(task_id):
        return
    with task_store.locked(store):
        try:
            card = task_store.read(store, task_id)
        except TaskError:
            return
        current = (card.session or {}).get("claude_session_id")
        if current == session_id or current is not None:
            return
        if card.status != "working" or (card.session or {}).get("agent") != AGENT:
            return
        window = task_tmux.pane_window(environ.get(PANE_ENV, ""), environ)
        if window is None or (card.session or {}).get("tmux_session") != window.session \
                or (card.session or {}).get("tmux_window") != window.window_id:
            return
        task_store.update(store, task_id, lambda active: _set_claude_session(active, session_id))


def _set_claude_session(card: task_store.Task, session_id: str) -> None:
    card.session = {**(card.session or {}), "claude_session_id": session_id}


def _keeps_task(card: task_store.Task) -> bool:
    """A task in the merge queue, or one that failed to merge, outlives its session: the owner still needs it."""
    if card.status == "to-merge":
        return True
    return bool(card.attention) and card.attention.get("reason") == "merge-failed"


def first_prompt(store: Path, session_id: Any, prompt: Any) -> None:
    """Name the task from the session's first prompt, while its title is still the default one."""
    if not task_store.is_valid_session_id(session_id) or not isinstance(prompt, str):
        return
    with task_store.locked(store):
        link = task_store.session_link(store, session_id)
        if link is None or link["default_title"] is None:
            return
        title = task_store.title_from_text(prompt)
        if title is None:
            return
        if _task_exists(store, link["task"]):
            card = task_store.read(store, link["task"])
            if card.title == link["default_title"]:
                task_store.update(store, card.id, lambda current: _rename(current, title))
        task_store.write_session_link(store, session_id, {"task": link["task"], "default_title": None})


def _rename(card: task_store.Task, title: str) -> None:
    card.title = title


def _task_exists(store: Path, task_id: str) -> bool:
    try:
        task_store.read(store, task_id)
    except TaskError:
        return False
    return True


def _refresh(store: Path, task_id: str, session: dict[str, Any]) -> None:
    """Point a task at the session's window again."""
    def change(card: task_store.Task) -> None:
        card.session = {**(card.session or {}), **session}

    task_store.update(store, task_id, change)

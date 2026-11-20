"""Give each interactive Claude session in tmux a card in the task store: created on start, done when it ends."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import task_store
import task_tmux
from task_store import TaskError


ENTRYPOINT_ENV = "CLAUDE_CODE_ENTRYPOINT"
INTERACTIVE_ENTRYPOINT = "cli"  # `claude -p` runs as sdk-cli and gets no card
PANE_ENV = "TMUX_PANE"
SESSION_SOURCE = "session"
AGENT = "claude"
ACTIVE_STATUSES = ("working", "review")


def eligible(environ: Mapping[str, str]) -> bool:
    """Return True for an interactive Claude session inside tmux; the only sessions that may get a card."""
    return environ.get(ENTRYPOINT_ENV) == INTERACTIVE_ENTRYPOINT and bool(environ.get(PANE_ENV))


def card_of(store: Path, session_id: Any) -> str | None:
    """Return the id of the card a session writes to, or None when it has none."""
    if not task_store.is_valid_session_id(session_id):
        return None
    link = task_store.session_link(store, session_id)
    return None if link is None else link["task"]


def session_start(store: Path, session_id: Any, cwd: Any, environ: Mapping[str, str]) -> None:
    """Create the session's card, or reuse it on resume and compact; a session outside git gets nothing."""
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
    }
    with task_store.locked(store):
        link = task_store.session_link(store, session_id)
        if link is not None and _card_exists(store, link["task"]):
            _refresh(store, link["task"], session)
            return
        title = (window and task_store.title_from_text(window.window_name)) or Path(repo).name
        task = task_store.create(store, repo=repo, title=title, source=SESSION_SOURCE)
        task_store.update(store, task.id, lambda card: task_store.start(card, session=session))
        task_store.write_session_link(store, session_id, {"task": task.id, "default_title": task.title})


def session_end(store: Path, session_id: Any) -> None:
    """Mark the session's card done when the session ends; the link stays, so a resume reuses the card."""
    if not task_store.is_valid_session_id(session_id):
        return
    with task_store.locked(store):
        link = task_store.session_link(store, session_id)
        if link is None or not _card_exists(store, link["task"]):
            return
        card = task_store.read(store, link["task"])
        if card.status in ACTIVE_STATUSES:
            task_store.update(store, card.id, task_store.mark_done)


def first_prompt(store: Path, session_id: Any, prompt: Any) -> None:
    """Name the card from the session's first prompt, while its title is still the default one."""
    if not task_store.is_valid_session_id(session_id) or not isinstance(prompt, str):
        return
    with task_store.locked(store):
        link = task_store.session_link(store, session_id)
        if link is None or link["default_title"] is None:
            return
        title = task_store.title_from_text(prompt)
        if title is None:
            return
        if _card_exists(store, link["task"]):
            card = task_store.read(store, link["task"])
            if card.title == link["default_title"]:
                task_store.update(store, card.id, lambda current: _rename(current, title))
        task_store.write_session_link(store, session_id, {"task": link["task"], "default_title": None})


def _rename(card: task_store.Task, title: str) -> None:
    card.title = title


def _card_exists(store: Path, task_id: str) -> bool:
    try:
        task_store.read(store, task_id)
    except TaskError:
        return False
    return True


def _refresh(store: Path, task_id: str, session: dict[str, Any]) -> None:
    """Point a card at the session's window again, and take a done card back to working."""
    def change(card: task_store.Task) -> None:
        card.session = {**(card.session or {}), **session}
        if card.status == "done":
            task_store.resume(card)

    task_store.update(store, task_id, change)

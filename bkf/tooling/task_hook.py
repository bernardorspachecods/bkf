"""Tell a session that works on a task which task it is, and keep its card in step with its turns."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

import task_session
import task_store
from task_store import TaskError


TASK_ENV = "BKF_TASK"
# A script owns the card of these kinds, so the session is not told to move it.
OWNED_KINDS = ("unit",)
# The hook marks a card of these kinds while it is working; other kinds are never marked.
WAITING_KINDS = ("task", "handoff")
MARK_REASON = "prompt"
# The notes of the hook's own mark. Any other attention on a card belongs to someone else.
REPLY_NOTE = "waiting for your reply"
APPROVAL_NOTE = "waiting for your approval"
ANSWER_NOTE = "waiting for your answer"
OWN_NOTES = (REPLY_NOTE, APPROVAL_NOTE, ANSWER_NOTE)
# Claude Code's tool for asking the owner a question.
QUESTION_TOOL = "AskUserQuestion"
# Events that set or clear the hook's own mark; each prints nothing.
MARK_EVENTS = ("Stop", "UserPromptSubmit", "PermissionRequest", "PreToolUse", "PostToolUse")
# Claude Code's end of a session: the card of an interactive session is done then. Prints nothing.
SESSION_END = "SessionEnd"
# Stop with background work or scheduled wake-ups in flight is not a wait for the owner.
IN_FLIGHT_KEYS = ("background_tasks", "session_crons")

Plan = tuple[str, str | None]


class _Unchanged(Exception):
    """Raised inside a store change to leave the card as it is."""


def session_text(environ: Mapping[str, str]) -> str | None:
    """Return the session-start text for the task named by BKF_TASK, or None when the hook stays silent."""
    task_id = environ.get(TASK_ENV, "")
    if not task_id:
        return None
    try:
        task = task_store.read(task_store.store_dir(environ), task_id)
    except TaskError:
        return None
    if task.kind in OWNED_KINDS or task.status == "done":
        return None
    return (
        f"This session works on task {task.id} ({task.kind}): {task.title}. "
        "When the work is done, reviewed and committed on its branch, run "
        "`bkf task ready --note \"<one-line summary>\"` so the card moves to review, then wait for the owner. "
        "After the owner merges it, run `bkf task done`. Both commands read the task id from the environment.\n"
    )


def _plan(task: task_store.Task, event: str, data: Mapping[str, Any]) -> Plan | None:
    """Return what the event asks of the hook's own mark: ("set", note), ("clear", None), or None."""
    if task.status != "working" or task.kind not in WAITING_KINDS:
        return None
    if event == "Stop":
        if any(data.get(key) for key in IN_FLIGHT_KEYS):
            return ("clear", None)
        return ("set", REPLY_NOTE)
    if event == "PermissionRequest":
        return ("set", APPROVAL_NOTE)
    if event == "PreToolUse":
        return ("set", ANSWER_NOTE) if data.get("tool_name") == QUESTION_TOOL else None
    if event in ("PostToolUse", "UserPromptSubmit"):
        return ("clear", None)
    return None


def _is_own(attention: dict[str, Any] | None) -> bool:
    return bool(attention) and attention.get("reason") == MARK_REASON and attention.get("note") in OWN_NOTES


def _would_change(attention: dict[str, Any] | None, plan: Plan | None) -> bool:
    """Return True when the plan changes the card's attention; a foreign attention is never changed."""
    if plan is None:
        return False
    if plan[0] == "clear":
        return _is_own(attention)
    if attention is None:
        return True
    return _is_own(attention) and attention.get("note") != plan[1]


def _apply(task: task_store.Task, plan: Plan) -> None:
    if plan[0] == "clear":
        task_store.clear_attention(task)
    else:
        task_store.set_attention(task, MARK_REASON, note=plan[1], now=None)


def _mark(store: Path, task_id: str, event: str, data: Mapping[str, Any]) -> None:
    """Set or clear the hook's own mark on the card named by task_id. Failures are swallowed."""
    def change(task: task_store.Task) -> None:
        plan = _plan(task, event, data)
        if not _would_change(task.attention, plan):
            raise _Unchanged()
        _apply(task, plan)

    try:
        # Read first so a turn that changes nothing never takes the store lock.
        task = task_store.read(store, task_id)
        if not _would_change(task.attention, _plan(task, event, data)):
            return
        task_store.update(store, task_id, change)
    except (_Unchanged, TaskError, OSError, UnicodeError):
        return


def hook_input(stream: TextIO | None) -> dict[str, Any]:
    """Return the hook's JSON input as a dict, or an empty dict when the input is empty or invalid."""
    try:
        text = (sys.stdin if stream is None else stream).read()
        data: Any = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def run(environ: Mapping[str, str] | None = None, stream: TextIO | None = None) -> int:
    """Handle the hook event on standard input. Always exits 0 and never raises.

    With BKF_TASK, the mark events (Stop, UserPromptSubmit, PermissionRequest, PreToolUse, PostToolUse) set
    or clear the hook's own mark and print nothing; any other event but SessionEnd, or unreadable input,
    prints the session-start text, as SessionStart does. Without BKF_TASK, an interactive Claude session
    in tmux keeps its session card (task_session); every other session returns before reading its input.
    """
    env = os.environ if environ is None else environ
    try:
        if env.get(TASK_ENV, ""):
            _run_bound(env, stream)
        elif task_session.eligible(env):
            _run_session(env, stream)
    except Exception:
        pass
    return 0


def _run_bound(env: Mapping[str, str], stream: TextIO | None) -> None:
    data = hook_input(stream)
    event = data.get("hook_event_name")
    if event in MARK_EVENTS:
        _mark(task_store.store_dir(env), env[TASK_ENV], event, data)
    elif event != SESSION_END:
        text = session_text(env)
        if text:
            sys.stdout.write(text)


def _run_session(env: Mapping[str, str], stream: TextIO | None) -> None:
    data = hook_input(stream)
    event = data.get("hook_event_name")
    store = task_store.store_dir(env)
    session_id = data.get("session_id")
    if event == "SessionStart":
        task_session.session_start(store, session_id, data.get("cwd"), env)
    elif event == SESSION_END:
        task_session.session_end(store, session_id)
    elif event in MARK_EVENTS:
        task_id = task_session.card_of(store, session_id)
        if task_id is None:
            return
        if event == "UserPromptSubmit":
            task_session.first_prompt(store, session_id, data.get("prompt"))
        _mark(store, task_id, event, data)

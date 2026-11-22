"""Tell a session that works on a task which task it is, and keep its card in step with its turns."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

import merge_store
import task_session
import task_store
from task_store import TaskError


TASK_ENV = "BKF_TASK"
# Opt-in: the file that receives every raw hook input as one line, to read a real payload (never set by default).
DEBUG_ENV = "BKF_HOOK_DEBUG_FILE"
# A script owns the card of these kinds, so the session is not told to move it.
# The hook marks a card of these kinds while it is working; other kinds are never marked.
WAITING_KINDS = ("task", "handoff")
MARK_REASON = "prompt"
# The notes of the hook's own mark. Any other attention on a card belongs to someone else.
REPLY_NOTE = "waiting for your reply"
APPROVAL_NOTE = "waiting for your approval"
ANSWER_NOTE = "waiting for your answer"
ERROR_NOTE = "stopped on an error"
OWN_NOTES = (REPLY_NOTE, APPROVAL_NOTE, ANSWER_NOTE, ERROR_NOTE)
# Claude Code's tool for asking the owner a question.
QUESTION_TOOL = "AskUserQuestion"
# Events that set or clear the hook's own mark; each prints nothing.
MARK_EVENTS = ("Stop", "StopFailure", "UserPromptSubmit", "PermissionRequest", "PreToolUse", "PostToolUse")
# Events that show the session is alive: a session that holds the merge turn renews its lease on them.
LEASE_EVENTS = ("PostToolUse", "Stop")
# Claude Code's end of a session: the card of an interactive session is done then. Prints nothing.
SESSION_END = "SessionEnd"
# Stop with background work or scheduled wake-ups in flight is not a wait for the owner.
IN_FLIGHT_KEYS = ("background_tasks", "session_crons")

Plan = tuple[str, str | None]


class _Unchanged(Exception):
    """Raised inside a store change to leave the card as it is."""


def _plan(task: task_store.Task, event: str, data: Mapping[str, Any]) -> Plan | None:
    """Return what the event asks of the hook's own mark: ("set", note), ("clear", None), or None."""
    if task.status != "working" or task.kind not in WAITING_KINDS:
        return None
    if event == "Stop":
        if any(data.get(key) for key in IN_FLIGHT_KEYS):
            return ("clear", None)
        return ("set", REPLY_NOTE)
    if event == "StopFailure":
        return ("set", ERROR_NOTE)
    if event == "PermissionRequest":
        return ("set", APPROVAL_NOTE)
    if event == "PreToolUse":
        # Any tool call means the session works again, as iTerm2's Claude Code status hook treats it.
        if data.get("tool_name") == QUESTION_TOOL:
            return ("set", ANSWER_NOTE)
        return ("clear", None)
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


def _renew_lease(store: Path, task_id: str, environ: Mapping[str, str]) -> None:
    """Renew the merge turn's lease when this task holds it. Failures are swallowed, as for every hook event."""
    try:
        merge_store.touch_from_hook(store, task_id, environ)
    except (TaskError, merge_store.MergeError, OSError, UnicodeError):
        return


def hook_input(stream: TextIO | None, debug_file: str | None = None) -> dict[str, Any]:
    """Return the hook's JSON input as a dict, or an empty dict when the input is empty or invalid.

    With debug_file (BKF_HOOK_DEBUG_FILE), the raw input is also appended to it as one line, so the real payload
    of an event can be read. Write failures are swallowed.
    """
    try:
        text = (sys.stdin if stream is None else stream).read()
    except Exception:
        return {}
    if debug_file:
        _record_raw(debug_file, text)
    try:
        data: Any = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _record_raw(path: str, text: str) -> None:
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text.rstrip("\n") + "\n")
    except OSError:
        return


def run(environ: Mapping[str, str] | None = None, stream: TextIO | None = None) -> int:
    """Handle the hook event on standard input. Always exits 0 and never raises.

    With BKF_TASK, the mark events (Stop, StopFailure, UserPromptSubmit, PermissionRequest, PreToolUse,
    PostToolUse) set or clear the hook's own mark, and PostToolUse and Stop also renew the lease of a merge turn
    the task holds. The hook never prints: nothing it does reaches the agent's context. Without BKF_TASK, an interactive Claude session
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
    data = hook_input(stream, env.get(DEBUG_ENV))
    event = data.get("hook_event_name")
    store = task_store.store_dir(env)
    if event in MARK_EVENTS:
        _mark(store, env[TASK_ENV], event, data)
    if event in LEASE_EVENTS:
        _renew_lease(store, env[TASK_ENV], env)


def _run_session(env: Mapping[str, str], stream: TextIO | None) -> None:
    data = hook_input(stream, env.get(DEBUG_ENV))
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

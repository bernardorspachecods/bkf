"""Tell a session that works on a task which task it is, and keep its card in step with its turns."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from typing import Any, TextIO

import task_store
from task_store import TaskError


TASK_ENV = "BKF_TASK"
# A script or the crew orchestrator owns the card of these kinds, so the session is not told to move it.
OWNED_KINDS = ("unit", "crew")
# A session that stops on a working card of these kinds is waiting for the owner's reply.
WAITING_KINDS = ("task", "handoff")
WAITING_REASON = "prompt"
WAITING_NOTE = "waiting for your reply"


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


def stop(environ: Mapping[str, str]) -> None:
    """Mark a working task card as waiting for the owner, unless it already says why it needs a person."""
    task_id = environ.get(TASK_ENV, "")
    if not task_id:
        return
    store = task_store.store_dir(environ)

    def change(task: task_store.Task) -> None:
        if task.status != "working" or task.kind not in WAITING_KINDS or task.attention is not None:
            raise _Unchanged()
        task_store.set_attention(task, WAITING_REASON, note=WAITING_NOTE, now=None)

    try:
        task_store.update(store, task_id, change)
    except (_Unchanged, TaskError, OSError, UnicodeError):
        return


def prompt_submitted(environ: Mapping[str, str]) -> None:
    """Clear the waiting mark that stop set, once the owner has replied; other attention stays."""
    task_id = environ.get(TASK_ENV, "")
    if not task_id:
        return
    store = task_store.store_dir(environ)

    def change(task: task_store.Task) -> None:
        attention = task.attention
        if not attention or attention.get("reason") != WAITING_REASON or attention.get("note") != WAITING_NOTE:
            raise _Unchanged()
        task_store.clear_attention(task)

    try:
        task_store.update(store, task_id, change)
    except (_Unchanged, TaskError, OSError, UnicodeError):
        return


def event_name(stream: TextIO | None) -> str | None:
    """Return hook_event_name from the hook's JSON input, or None when the input is empty or invalid."""
    try:
        text = (sys.stdin if stream is None else stream).read()
        data: Any = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("hook_event_name")
    return name if isinstance(name, str) else None


def run(environ: Mapping[str, str] | None = None, stream: TextIO | None = None) -> int:
    """Handle the hook event on standard input. Always exits 0 and never raises.

    Stop and UserPromptSubmit print nothing; any other event (SessionStart, or no usable input)
    prints the session-start text.
    """
    env = os.environ if environ is None else environ
    try:
        event = event_name(stream)
        if event == "Stop":
            stop(env)
        elif event == "UserPromptSubmit":
            prompt_submitted(env)
        else:
            text = session_text(env)
            if text:
                sys.stdout.write(text)
    except Exception:
        pass
    return 0

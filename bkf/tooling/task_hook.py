"""Tell a session that works on a task which task it is and the two commands that move its card."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

import task_store
from task_store import TaskError


TASK_ENV = "BKF_TASK"
# A script or the crew orchestrator owns the card of these kinds, so the session is not told to move it.
OWNED_KINDS = ("unit", "crew")


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


def run(environ: Mapping[str, str] | None = None) -> int:
    """Print the session-start text for a task session. Always exits 0."""
    text = session_text(os.environ if environ is None else environ)
    if text:
        sys.stdout.write(text)
    return 0

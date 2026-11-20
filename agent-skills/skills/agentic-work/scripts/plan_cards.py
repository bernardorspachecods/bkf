"""Task cards of plan runs: one card for the run and one per unit, each unit's card the child of the run's card.

The cards serve the Agentic app and `bkf task`; the engine's own state files stay the source of truth. The run's
card id is kept in `<run>/task` and a unit's in `<run>/<unit>/task`. Every `bkf` call is best effort: a failed call
prints one line on standard error and the run goes on.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


RUN_CARD = "task"
_NOTE_LIMIT = 300


def _warn(text):
    print("plan: task card: {0}".format(text), file=sys.stderr)


def _bkf(*args):
    """The standard output of `bkf task <args>`, or None after one warning line when the call fails."""
    try:
        completed = subprocess.run(
            ["bkf", "task"] + [str(arg) for arg in args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
    except OSError as error:
        _warn("bkf is not available ({0}); `bkf task {1}` was not run".format(error, args[0]))
        return None
    if completed.returncode != 0:
        lines = completed.stderr.strip().splitlines()
        _warn("bkf task {0} failed: {1}".format(args[0], lines[0] if lines else "exit {0}".format(completed.returncode)))
        return None
    return completed.stdout


def _note(text):
    return " ".join(str(text).split())[:_NOTE_LIMIT]


def _read_id(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_id(path, task_id):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(task_id + "\n", encoding="utf-8")
    except OSError as error:
        _warn("cannot save the card id to {0}: {1}".format(path, error))


def _status(task_id):
    output = _bkf("show", task_id, "--json")
    if output is None:
        return None
    try:
        return json.loads(output)["status"]
    except (ValueError, KeyError, TypeError):
        return None


def _branch(run, checkout):
    """The run's branch when the checkout is the run's own worktree; a group unit's worktree and in-place runs have none."""
    if os.path.abspath(str(checkout)) == os.path.abspath(str(run.path / "tree")):
        return "plan/" + run.name
    return None


def _start_args(run, task_id, checkout, folder):
    args = ["start", task_id, "--worktree", str(checkout), "--run-dir", str(folder)]
    branch = _branch(run, checkout)
    if branch:
        args += ["--branch", branch]
    return args


def start_run(run):
    """Make the run's card once its start has succeeded: its worktree is the run's checkout."""
    task_id = _bkf("new", "--repo", str(run.repo), "--title", "plan " + run.name, "--kind", "unit")
    if task_id is None:
        return
    task_id = task_id.strip()
    _write_id(run.path / RUN_CARD, task_id)
    _bkf(*_start_args(run, task_id, run.checkout, run.path))


def _unit_card(run, unit, create=True):
    """The unit's card id, made as the child of the run's card the first time the unit has a state when create is set."""
    path = run.path / unit / RUN_CARD
    task_id = _read_id(path)
    if task_id is not None or not create:
        return task_id
    parent = _read_id(run.path / RUN_CARD)
    args = ["new", "--repo", str(run.repo), "--title", unit, "--kind", "unit"]
    args += ["--parent", parent] if parent else ["--no-parent"]
    output = _bkf(*args)
    if output is None:
        return None
    task_id = output.strip()
    _write_id(path, task_id)
    return task_id


def unit_started(run, unit, checkout):
    """A unit's implementer is about to run: its card starts, or a card left by an earlier attempt loses its attention."""
    task_id = _unit_card(run, unit)
    if task_id is None:
        return
    status = _status(task_id)
    if status in ("todo", "failed"):
        _bkf(*_start_args(run, task_id, checkout, run.path / unit))
    elif status == "working":
        _bkf("attention", task_id, "--clear")


def unit_ended(run, unit, state, reason):
    """A unit's loop ended: passed, blocked, escalated, takeover or failed. A unit without a card gets none now."""
    task_id = _unit_card(run, unit, create=False)
    if task_id is None:
        return
    if state == "passed":
        _bkf("done", task_id)
    elif state in ("blocked", "escalated", "takeover"):
        _bkf("attention", task_id, "--set", "escalated", "--note", state)
    else:
        _bkf("fail", task_id, "--note", _note(reason))


def run_state(run, state, reason=""):
    """The run changed state: paused, stopped, crashed, ready, resumed or discarded."""
    if state == "discarded":
        _discard(run)
        return
    task_id = _read_id(run.path / RUN_CARD)
    if task_id is None:
        return
    if state == "paused":
        _bkf("attention", task_id, "--set", "paused", "--note", _note(reason))
    elif state == "stopped":
        _bkf("attention", task_id, "--set", "escalated", "--note", "stopped")
    elif state == "crashed":
        _bkf("fail", task_id, "--note", "crashed")
    elif state == "ready":
        _bkf("ready", task_id, "--no-git", "--note", _note("report at " + reason))
    elif state == "resumed":
        if _status(task_id) == "failed":
            _bkf(*_start_args(run, task_id, run.checkout, run.path))
        else:
            _bkf("attention", task_id, "--clear")


def finish_run(run):
    """The run is kept: its card is done. Called before the run folder is removed."""
    task_id = _read_id(run.path / RUN_CARD)
    if task_id is not None:
        _bkf("done", task_id)


def _discard(run):
    """The run is discarded: its unit cards and its own card are deleted. Called before the run folder is removed."""
    ids = [_read_id(path) for path in sorted(run.path.glob("*/" + RUN_CARD))]
    ids.append(_read_id(run.path / RUN_CARD))
    for task_id in ids:
        if task_id is not None:
            _bkf("delete", task_id)

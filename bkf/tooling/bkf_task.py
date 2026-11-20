"""Record and read the state of agent tasks in the machine-wide task store."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import task_store
import task_tmux
import task_worktree
from task_store import KINDS, REASONS, STATUSES, InvalidTransition, Task, TaskError


JSON_SCHEMA = 1
TASK_ENV = "BKF_TASK"
OUTPUT_LINES_DEFAULT = 200
TMUX_MISSING = 127  # the status task_tmux.default_runner gives when tmux is not on PATH


class Refusal(Exception):
    """A refused command: printed as one line on standard error, exit 1."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf task", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="create a task in the todo state")
    new.add_argument("--repo", required=True, metavar="DIR", help="repository folder the task belongs to")
    new.add_argument("--title", required=True)
    new.add_argument("--body-file", metavar="F", help="read the body from F (or - for standard input)")
    new.add_argument("--source", help="where the task came from")
    new.add_argument("--kind", choices=KINDS, default="task")
    parent = new.add_mutually_exclusive_group()
    parent.add_argument("--parent", metavar="ID", help="parent task (default: $BKF_TASK)")
    parent.add_argument("--no-parent", action="store_true", help="create the task without a parent")
    new.add_argument("--json", action="store_true", help="print the task JSON instead of its id")

    list_ = commands.add_parser("list", help="list tasks, filtered")
    list_.add_argument("--repo", metavar="DIR", help="only tasks of the repository holding DIR")
    list_.add_argument("--status", action="append", choices=STATUSES, help="only this status (repeatable)")
    list_.add_argument("--kind", choices=KINDS)
    list_.add_argument("--parent", metavar="ID")
    list_.add_argument("--json", action="store_true", help="print one JSON object with the store and its tasks")

    show = commands.add_parser("show", help="show one task")
    show.add_argument("id", metavar="ID", nargs="?", help="task id (default: $BKF_TASK)")
    show.add_argument("--json", action="store_true", help="print the task JSON")

    start = commands.add_parser("start", help="record that an agent session started on a task")
    start.add_argument("id", metavar="ID")
    start.add_argument("--agent")
    start.add_argument("--model")
    start.add_argument("--effort")
    start.add_argument("--reviewer")
    start.add_argument("--tmux-session", dest="tmux_session")
    start.add_argument("--tmux-window", dest="tmux_window")
    start.add_argument("--worktree", metavar="PATH")
    start.add_argument("--branch")
    start.add_argument("--run-dir", dest="run_dir", metavar="D")

    ready = commands.add_parser("ready", help="mark a task ready for review, recording its git branch and head")
    ready.add_argument("id", metavar="ID", nargs="?", help="task id (default: $BKF_TASK)")
    ready.add_argument("--note")
    ready.add_argument("--no-git", dest="no_git", action="store_true",
                       help="read no git state: keep the task's branch and head, and accept a dirty tree")

    worktree = commands.add_parser("worktree", help="create or reuse the git worktree of a task")
    worktree.add_argument("id", metavar="ID")
    worktree.add_argument("--base", metavar="REV", help="start a new branch from REV (default: HEAD of the repository)")
    worktree.add_argument("--json", action="store_true", help="print path, branch and created as one JSON object")

    done = commands.add_parser("done", help="mark a task done")
    done.add_argument("id", metavar="ID", nargs="?", help="task id (default: $BKF_TASK)")

    fail = commands.add_parser("fail", help="mark a task failed")
    fail.add_argument("id", metavar="ID", nargs="?", help="task id (default: $BKF_TASK)")
    fail.add_argument("--exit", type=int, metavar="N")
    fail.add_argument("--note")

    attention = commands.add_parser("attention", help="set or clear the reason a task needs a person")
    attention.add_argument("id", metavar="ID", nargs="?", help="task id (default: $BKF_TASK)")
    action = attention.add_mutually_exclusive_group(required=True)
    action.add_argument("--set", dest="reason", metavar="REASON", help="one of: " + ", ".join(REASONS))
    action.add_argument("--clear", action="store_true")
    attention.add_argument("--note")

    output = commands.add_parser("output", help="print the text of a task's tmux window")
    output.add_argument("id", metavar="ID", nargs="?", help="task id (default: $BKF_TASK)")
    output.add_argument("--lines", metavar="N", help="also read N lines of history above the screen "
                        f"(default 200, at most {task_tmux.CAPTURE_LINES_LIMIT})")

    delete = commands.add_parser("delete", help="delete a task folder")
    delete.add_argument("id", metavar="ID")
    return parser


def _task_id(given: str | None) -> str:
    if given:
        return given
    current = os.environ.get(TASK_ENV)
    if current:
        return current
    raise Refusal("no task id: pass an id, or run it from a task's window")


def _body(path: str | None) -> str:
    if path is None:
        return ""
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _git(cwd: str, *arguments: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", cwd, *arguments], capture_output=True, text=True, check=False,
        )
    except OSError:
        return None


def _git_state(cwd: str) -> tuple[str | None, str | None]:
    """Return (branch, head) of the work tree at cwd, or nulls outside a work tree; refuse a dirty tree."""
    inside = _git(cwd, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.returncode != 0 or inside.stdout.strip() != "true":
        return None, None
    status = _git(cwd, "status", "--porcelain")
    if status is None or status.returncode != 0:
        raise Refusal(f"cannot read git status in {cwd}")
    if status.stdout.strip():
        raise Refusal(f"uncommitted changes in {cwd}: commit them on the branch first")
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git(cwd, "rev-parse", "HEAD")
    if branch is None or head is None or branch.returncode != 0 or head.returncode != 0:
        raise Refusal(f"cannot read the branch and head in {cwd}")
    return branch.stdout.strip(), head.stdout.strip()


def _transition_result(store: Path, task_id: str, change: Any) -> Task:
    return task_store.update(store, task_id, change)


def _session(args: argparse.Namespace) -> dict[str, Any] | None:
    values = {
        "agent": args.agent, "model": args.model, "effort": args.effort, "reviewer": args.reviewer,
        "tmux_session": args.tmux_session, "tmux_window": args.tmux_window,
    }
    if all(value is None for value in values.values()):
        return None
    return values


def _worktree(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.worktree is None and args.branch is None:
        return None
    return {"path": args.worktree, "branch": args.branch}


def _emit_task(task: Task, as_json: bool) -> None:
    if as_json:
        print(json.dumps(task.to_json(), ensure_ascii=False, sort_keys=True))
    else:
        print(task.id)


def _show_lines(task: Task) -> list[str]:
    worktree = task.worktree or {}
    session = task.session or {}
    attention = "-"
    if task.attention:
        attention = f"{task.attention['reason']} since {task.attention['since']}"
    values = {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "kind": task.kind,
        "repo": task.repo,
        "parent": task.parent,
        "worktree": worktree.get("path"),
        "branch": worktree.get("branch"),
        "tmux window": session.get("tmux_window"),
        "attention": attention,
        "note": task.note,
    }
    return [f"{key}: {'-' if value in (None, '') else value}" for key, value in values.items()]


def _list(args: argparse.Namespace, store: Path) -> int:
    generation = task_store.generation(store)
    listing = task_store.list_tasks(store)
    repo = task_store.repo_identity(args.repo) if args.repo is not None else None
    tasks = [
        task for task in listing.tasks
        if (repo is None or task.repo == repo)
        and (not args.status or task.status in args.status)
        and (args.kind is None or task.kind == args.kind)
        and (args.parent is None or task.parent == args.parent)
    ]
    if args.json:
        payload = {
            "schema": JSON_SCHEMA,
            "store": str(store.absolute()),
            "generation": generation,
            "tasks": [task.to_json() for task in tasks],
            "unreadable": listing.unreadable,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    for task in tasks:
        print(f"{task.id}  {task.status}  {task.kind}  {task.title}")
    for name in listing.unreadable:
        print(f"bkf task: unreadable task folder {name}", file=sys.stderr)
    return 0


def _ready(args: argparse.Namespace, store: Path) -> None:
    task_id = _task_id(args.id)
    task = task_store.read(store, task_id)
    try:
        task_store.mark_ready(copy.deepcopy(task))
    except InvalidTransition as exc:
        raise Refusal(str(exc)) from None
    if args.no_git:
        branch, head = None, None
    else:
        cwd = task.worktree["path"] if task.worktree and task.worktree.get("path") else os.getcwd()
        branch, head = _git_state(cwd)
    _transition_result(
        store, task_id,
        lambda current: task_store.mark_ready(current, branch=branch, head=head, note=args.note),
    )


def _output_lines(text: str | None) -> int:
    if text is None:
        return OUTPUT_LINES_DEFAULT
    try:
        value = int(text)
    except ValueError:
        raise Refusal("--lines must be a positive integer") from None
    if value < 1:
        raise Refusal("--lines must be a positive integer")
    if value > task_tmux.CAPTURE_LINES_LIMIT:
        raise Refusal(f"--lines must be at most {task_tmux.CAPTURE_LINES_LIMIT}")
    return value


def _output(args: argparse.Namespace, store: Path) -> int:
    history = _output_lines(args.lines)
    task_id = _task_id(args.id)
    task = task_store.read(store, task_id)
    session = task.session or {}
    name, window = session.get("tmux_session"), session.get("tmux_window")
    if not name or not window:
        raise Refusal(f"task {task_id} has no window")
    try:
        result = task_tmux.capture_pane(name, window, history=history)
    except task_tmux.TargetRefused as exc:
        raise Refusal(str(exc)) from None
    if result.returncode == TMUX_MISSING:
        raise Refusal("tmux is not installed or not on PATH")
    if result.returncode != 0:
        raise Refusal(f"the window of task {task_id} is closed")
    sys.stdout.write(result.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "attention" and args.clear and args.note is not None:
        parser.error("--note goes with --set, not --clear")
    store = task_store.store_dir()
    try:
        if args.command == "new":
            parent = None if args.no_parent else (args.parent or os.environ.get(TASK_ENV) or None)
            task = task_store.create(
                store, repo=task_store.repo_identity(args.repo), title=args.title, kind=args.kind,
                body=_body(args.body_file), source=args.source, parent=parent,
            )
            _emit_task(task, args.json)
        elif args.command == "list":
            return _list(args, store)
        elif args.command == "show":
            task = task_store.read(store, _task_id(args.id))
            if args.json:
                print(json.dumps(task.to_json(), ensure_ascii=False, sort_keys=True))
            else:
                print("\n".join(_show_lines(task)))
        elif args.command == "start":
            session, worktree = _session(args), _worktree(args)
            _transition_result(
                store, args.id,
                lambda task: task_store.start(task, session=session, worktree=worktree, run_dir=args.run_dir),
            )
        elif args.command == "ready":
            _ready(args, store)
        elif args.command == "worktree":
            prepared = task_worktree.prepare(store, args.id, base=args.base)
            if args.json:
                print(json.dumps(
                    {"path": prepared.path, "branch": prepared.branch, "created": prepared.created},
                    ensure_ascii=False,
                ))
            else:
                print(f"{prepared.path}\n{prepared.branch}")
        elif args.command == "done":
            _transition_result(store, _task_id(args.id), task_store.mark_done)
        elif args.command == "fail":
            _transition_result(
                store, _task_id(args.id),
                lambda task: task_store.mark_failed(task, exit=args.exit, note=args.note),
            )
        elif args.command == "attention":
            task_id = _task_id(args.id)
            if args.clear:
                _transition_result(store, task_id, task_store.clear_attention)
            else:
                _transition_result(
                    store, task_id,
                    lambda task: task_store.set_attention(task, args.reason, note=args.note, now=None),
                )
        elif args.command == "output":
            return _output(args, store)
        elif args.command == "delete":
            task_store.delete(store, args.id)
    except (Refusal, TaskError, OSError, UnicodeError) as exc:
        print(f"bkf task: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

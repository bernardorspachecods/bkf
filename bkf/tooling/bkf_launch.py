"""Open an interactive Claude or Codex session in tmux, with its task card: the one way skills start one."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import task_store
import task_tmux
import task_worktree
from task_store import KINDS, Task, TaskError


AGENTS = ("claude", "codex")
WORKTREE_MODES = ("auto", "none")
TITLE_LIMIT = 80
FALLBACK_TITLE = "session"
LAUNCH_FAILED = "launch-failed"
PROMPT_NAME = "prompt.md"
TASK_ENV = "BKF_TASK"
TASKS_DIR_ENV = "BKF_TASKS_DIR"
DELEGATED_ENV = "BKF_DELEGATED"
LAUNCHABLE = ("todo", "failed")
SIZE = re.compile(r"([1-9][0-9]*)x([1-9][0-9]*)")
# Options that only a launch takes; --session-name refuses each one it is given.
LAUNCH_ONLY = (
    "agent", "prompt_file", "model", "effort", "reviewer", "name", "permission_mode", "remote_control", "window",
    "delegated", "task", "no_task", "title", "kind", "parent", "no_parent", "body_file", "worktree",
    "no_attach", "size", "json",
)
CARD_ONLY = (
    ("--title", "title"), ("--kind", "kind"), ("--parent", "parent"),
    ("--no-parent", "no_parent"), ("--body-file", "body_file"),
)


class Refusal(Exception):
    """A refusal before the task card exists: one line on standard error, exit 1."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf launch", description=__doc__)
    parser.add_argument("agent", nargs="?", choices=AGENTS, help="the agent to run (not needed with --session-name)")
    parser.add_argument("--dir", required=True, metavar="D", help="the folder the session works in")
    parser.add_argument("--prompt-file", dest="prompt_file", metavar="F",
                        help="the first message, read from F (or - for standard input)")
    parser.add_argument("--model", metavar="M")
    parser.add_argument("--effort", metavar="E")
    parser.add_argument("--reviewer", metavar="R", help="recorded on the card only; changes nothing in the command")
    parser.add_argument("--name", metavar="N", help="claude only: the session name")
    parser.add_argument("--permission-mode", dest="permission_mode", metavar="P", help="claude only")
    parser.add_argument("--remote-control", dest="remote_control", action="store_true", help="claude only")
    parser.add_argument("--window", metavar="W", help="the tmux window name")
    parser.add_argument("--delegated", action="store_true", help="set BKF_DELEGATED=1 in the window")

    card = parser.add_mutually_exclusive_group()
    card.add_argument("--task", metavar="ID", help="launch on this card (status todo or failed)")
    card.add_argument("--no-task", dest="no_task", action="store_true", help="launch with no card")
    parser.add_argument("--title", metavar="T", help="title of the new card")
    parser.add_argument("--kind", choices=KINDS, help="kind of the new card (default: handoff)")
    parent = parser.add_mutually_exclusive_group()
    parent.add_argument("--parent", metavar="ID", help="parent of the new card (default: $BKF_TASK)")
    parent.add_argument("--no-parent", dest="no_parent", action="store_true", help="the new card has no parent")
    parser.add_argument("--body-file", dest="body_file", metavar="F", help="body of the new card, from F (or -)")

    parser.add_argument("--worktree", choices=WORKTREE_MODES,
                        help="auto: a git worktree for the card (default for kind task); none: the --dir folder")
    parser.add_argument("--size", type=_size, metavar="COLSxROWS", help="the size of a new tmux session")
    parser.add_argument("--no-attach", dest="no_attach", action="store_true", help="do not attach a terminal")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of the lines")
    parser.add_argument("--session-name", dest="session_name", action="store_true",
                        help="print the tmux session where --dir's repository has windows open (else its own session) and launch nothing")
    return parser


def _size(text: str) -> tuple[int, int]:
    match = SIZE.fullmatch(text)
    if match is None:
        raise argparse.ArgumentTypeError("expected COLSxROWS, such as 200x50")
    return int(match[1]), int(match[2])


def _given(value: Any) -> bool:
    return value is not None and value is not False


def _check(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Usage errors, which exit 2 before anything is read or written."""
    if args.session_name:
        if any(_given(getattr(args, name)) for name in LAUNCH_ONLY):
            parser.error("--session-name takes only --dir")
        return
    if args.agent is None:
        parser.error("an agent is required: claude or codex")
    if args.agent != "claude":
        for flag, name in (("--name", "name"), ("--permission-mode", "permission_mode"),
                           ("--remote-control", "remote_control")):
            if _given(getattr(args, name)):
                parser.error(f"{flag} works only with claude")
    if args.task is not None or args.no_task:
        given = [flag for flag, name in CARD_ONLY if _given(getattr(args, name))]
        if given:
            parser.error(f"{', '.join(given)} make a new card: not with --task or --no-task")
    if args.prompt_file == "-" and args.body_file == "-":
        parser.error("--prompt-file and --body-file cannot both read standard input")
    if args.worktree == "auto" and args.no_task:
        parser.error("--worktree auto needs a task card")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _check(parser, args)
    store = task_store.store_dir()
    try:
        if args.session_name:
            if not os.path.isdir(args.dir):
                raise Refusal(f"--dir is not a folder: {args.dir}")
            directory = os.path.abspath(args.dir)
            session, _ = task_tmux.resolve_repo_session(
                directory, repo=task_store.repo_identity(directory), environ=os.environ,
                runner=task_tmux.default_runner,
            )
            print(session)
            return 0
        return _launch(args, store)
    except (Refusal, TaskError, OSError) as exc:
        print(f"bkf launch: {exc}", file=sys.stderr)
        return 1


def _launch(args: argparse.Namespace, store: Path) -> int:
    # Step 1: check the request. Nothing is written before this passes.
    if not os.path.isdir(args.dir):
        raise Refusal(f"--dir is not a folder: {args.dir}")
    directory = os.path.abspath(args.dir)
    if shutil.which(args.agent) is None:
        raise Refusal(f"{args.agent} is not installed or not on PATH")
    prompt_text = _read_prompt(args.prompt_file)
    body = _read_body(args.body_file)
    existing: Task | None = None
    if args.task is not None:
        try:
            existing = task_store.read(store, args.task)
        except TaskError as exc:
            raise Refusal(str(exc)) from None
        if existing.status not in LAUNCHABLE:
            raise Refusal(f"task {existing.id} is {existing.status}; a launch needs a todo or failed task")

    # Step 2: the card.
    card: Task | None = existing
    if card is None and not args.no_task:
        card = _create_card(args, store, directory, prompt_text, body)

    worktree: dict[str, Any] | None = None
    try:
        # Step 3: the worktree.
        mode = args.worktree or ("auto" if card is not None and card.kind == "task" else "none")
        if card is not None and mode == "auto":
            worktree = _worktree(store, card)
        session_dir = worktree["path"] if worktree else directory

        # Step 4: the prompt the window reads.
        prompt_path = _prompt_path(store, card, args, prompt_text)

        # Step 5: the command.
        claude_session_id = str(uuid.uuid4()) if card is not None and args.agent == "claude" else None
        command = _command(args, prompt_path, session_id=claude_session_id)

        # Step 6: the window.
        environment: dict[str, str] = {}
        if card is not None:
            environment[TASK_ENV] = card.id
        if os.environ.get(TASKS_DIR_ENV):
            environment[TASKS_DIR_ENV] = os.environ[TASKS_DIR_ENV]
        if args.delegated:
            environment[DELEGATED_ENV] = "1"
        window_name = args.window or (card.title if card is not None else None)
        window = task_tmux.open_window(
            directory=session_dir, command=command, window_name=window_name, environment=environment,
            repo=task_store.repo_identity(directory), size=args.size, attach=not args.no_attach,
        )

        # Step 7: the start transition.
        if card is not None:
            session = {
                "agent": args.agent, "model": args.model, "effort": args.effort,
                "reviewer": args.reviewer, "tmux_session": window.session, "tmux_window": window.window_id,
            }
            if claude_session_id is not None:
                session["claude_session_id"] = claude_session_id
            recorded = None
            if worktree is not None:
                recorded = {"path": worktree["path"], "branch": worktree["branch"]}
            task_store.update(
                store, card.id,
                lambda task: task_store.start(task, session=session, worktree=recorded),
            )
    except (TaskError, OSError, task_tmux.TmuxError) as exc:
        if card is None:
            raise Refusal(str(exc)) from None
        return _failed(store, card.id, exc)

    # Step 8: the output.
    if args.json:
        print(json.dumps({
            "task": card.id if card is not None else None,
            "session": window.session,
            "window": window.window_id,
            "worktree": worktree["path"] if worktree else None,
            "branch": worktree["branch"] if worktree else None,
            "needs_attach": window.needs_attach,
        }, ensure_ascii=False, sort_keys=True))
    else:
        if card is not None:
            print(card.id)
        print(f"{window.session}:{window.window_id}")
        if window.needs_attach:
            print("attach with: " + task_tmux._attach_command(os.environ, window.session, control=False))
    return 0


def _read_prompt(path: str | None) -> str | None:
    if path is None:
        return None
    if path == "-":
        return sys.stdin.read()
    if not os.path.isfile(path):
        raise Refusal(f"no prompt file: {path}")
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise Refusal(f"cannot read the prompt file {path}: {exc}") from None


def _read_body(path: str | None) -> str:
    if path is None:
        return ""
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise Refusal(f"cannot read the body file {path}: {exc}") from None


def _one_line(text: str) -> str:
    return " ".join(text.splitlines()).strip()


def _title(args: argparse.Namespace, prompt_text: str | None) -> str:
    first = ""
    if prompt_text:
        first = next((line.strip()[:TITLE_LIMIT] for line in prompt_text.splitlines() if line.strip()), "")
    for candidate in (args.title, args.window, args.name, first):
        if candidate and _one_line(candidate):
            return _one_line(candidate)
    return FALLBACK_TITLE


def _create_card(args: argparse.Namespace, store: Path, directory: str,
                 prompt_text: str | None, body: str) -> Task:
    parent = None if args.no_parent else (args.parent or os.environ.get(TASK_ENV) or None)
    try:
        return task_store.create(
            store,
            repo=task_store.repo_identity(directory),
            title=_title(args, prompt_text),
            kind=args.kind or "handoff",
            body=body,
            parent=parent,
        )
    except TaskError as exc:
        raise Refusal(str(exc)) from None


def _is_git_repository(path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _worktree(store: Path, card: Task) -> dict[str, Any] | None:
    """The card's worktree: created or reused by task_worktree.prepare; none outside a git repository."""
    if not _is_git_repository(card.repo):
        return None
    prepared = task_worktree.prepare(store, card.id)
    return {"path": prepared.path, "branch": prepared.branch}


def _prompt_path(store: Path, card: Task | None, args: argparse.Namespace, text: str | None) -> str | None:
    if text is None:
        return None
    if card is not None:
        task_store.write_prompt(store, card.id, text)
        return str((store / card.id / PROMPT_NAME).absolute())
    if args.prompt_file != "-":
        return os.path.abspath(args.prompt_file)
    # Standard input with no card: a temporary copy, kept after the launch.
    descriptor, path = tempfile.mkstemp(prefix="bkf-launch-", suffix=".md")
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _command(args: argparse.Namespace, prompt_path: str | None, session_id: str | None = None) -> str:
    quote = shlex.quote
    if args.agent == "claude":
        parts = ["claude"]
        if session_id is not None:
            parts += ["--session-id", quote(session_id)]
        if args.name is not None:
            parts += ["--name", quote(args.name)]
        if args.permission_mode is not None:
            parts += ["--permission-mode", quote(args.permission_mode)]
        if args.remote_control:
            parts += ["--remote-control"]
        if args.model is not None:
            parts += ["--model", quote(args.model)]
        if args.effort is not None:
            parts += ["--effort", quote(args.effort)]
    else:
        parts = ["codex"]
        if args.model is not None:
            parts += ["-m", quote(args.model)]
        if args.effort is not None:
            parts += ["-c", quote(f'model_reasoning_effort="{args.effort}"')]
    if prompt_path is not None:
        # The window's shell expands the file: a typed line of tens of KB overflows the terminal.
        parts.append(f'"$(cat {quote(prompt_path)})"')
    return " ".join(parts)


def _failed(store: Path, task_id: str, error: BaseException) -> int:
    """Record the failure on the card and print it; the card keeps its status."""
    message = " ".join(str(error).split()) or "launch failed"
    try:
        task_store.update(
            store, task_id,
            lambda task: task_store.set_attention(task, LAUNCH_FAILED, note=message, now=None),
        )
    except TaskError:
        pass
    print(f"bkf launch: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Create or reuse the git worktree of a task, under the main checkout's .claude/worktrees folder."""

from __future__ import annotations

import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import task_store
from task_store import Task, TaskError


WORKTREE_DIR = Path(".claude") / "worktrees"
EXCLUDE_LINE = "/.claude/worktrees/"
SLUG_LIMIT = 30
PREPARABLE_STATUSES = ("todo", "working", "failed")


class WorktreeError(TaskError):
    """A refused worktree: printed after 'bkf task: ' by the command."""


@dataclass
class Prepared:
    path: str
    branch: str
    created: bool


def slug(title: str, task_id: str) -> str:
    """Return the folder and branch name of a task: its title folded to a-z0-9, then the id's last 4 characters."""
    folded = unicodedata.normalize("NFKD", title)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    words = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:SLUG_LIMIT].rstrip("-")
    return f"{words or 'task'}-{task_id[-4:]}"


def prepare(store: Path, task_id: str, *, base: str | None = None) -> Prepared:
    """Create the task's worktree, or reuse it, and record it on the task."""
    task = task_store.read(store, task_id)
    if task.status not in PREPARABLE_STATUSES:
        raise WorktreeError(f"a worktree needs a todo, working or failed task, and {task.id} is {task.status}")
    repo = task.repo
    _require_repository(repo)

    name = slug(task.title, task.id)
    path = str(Path(repo) / WORKTREE_DIR / name)
    branch = f"task/{name}"
    worktrees = _worktrees(repo)
    entry = next((item for item in worktrees if _same_path(item["path"], path)), None)

    if os.path.lexists(path):
        if entry is None or entry["branch"] != f"refs/heads/{branch}":
            raise WorktreeError(
                f"the path exists and is not the worktree of {branch}: {path} holds {_describe(path, entry)}"
            )
        created = False
    else:
        created = True

    add_arguments: list[str] | None = None
    if created:
        if _branch_exists(repo, branch):
            add_arguments = ["worktree", "add", path, branch]
        else:
            add_arguments = ["worktree", "add", "-b", branch, path, _resolve(repo, base)]

    _ignore(repo, name)

    if add_arguments is not None:
        result = _git(repo, *add_arguments)
        if result.returncode != 0:
            raise WorktreeError(f"git worktree add failed: {result.stderr.strip()}")

    task_store.update(store, task.id, lambda current: _record(current, path, branch))
    return Prepared(path=path, branch=branch, created=created)


def _record(task: Task, path: str, branch: str) -> None:
    task.worktree = {"path": path, "branch": branch, "head": None}


def _git(repo: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", repo, *arguments],
            capture_output=True, text=True, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError as error:
        raise WorktreeError(f"cannot run git: {error}") from None


def _require_repository(repo: str) -> None:
    result = _git(repo, "rev-parse", "--is-inside-work-tree")
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise WorktreeError(f"not a git repository: {repo}")


def _resolve(repo: str, base: str | None) -> str:
    revision = "HEAD" if base is None else base
    if revision.startswith("-"):
        raise WorktreeError(f"unknown base revision: {revision}")
    result = _git(repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}")
    if result.returncode != 0 or not result.stdout.strip():
        raise WorktreeError(f"unknown base revision: {revision}")
    return result.stdout.strip()


def _branch_exists(repo: str, branch: str) -> bool:
    return _git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def _worktrees(repo: str) -> list[dict[str, Any]]:
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        raise WorktreeError(f"cannot list the worktrees of {repo}: {result.stderr.strip()}")
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current = {"path": line[len("worktree "):], "branch": None}
            entries.append(current)
        elif line.startswith("branch ") and current is not None:
            current["branch"] = line[len("branch "):]
    return entries


def _same_path(left: str, right: str) -> bool:
    return os.path.realpath(left) == os.path.realpath(right)


def _describe(path: str, entry: dict[str, Any] | None) -> str:
    if entry is not None:
        if entry["branch"]:
            return f"a worktree on {entry['branch'].removeprefix('refs/heads/')}"
        return "a worktree with a detached head"
    if os.path.isdir(path) and not os.path.islink(path):
        return "a folder that is not a worktree of this repository"
    return "a file that is not a worktree"


def _ignore(repo: str, name: str) -> None:
    """Keep the worktree folder out of git status, unless a rule already ignores it."""
    relative = (WORKTREE_DIR / name).as_posix()
    if _git(repo, "check-ignore", "-q", relative).returncode == 0:
        return
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0 or not common.stdout.strip():
        raise WorktreeError(f"cannot find the git common directory of {repo}")
    exclude = Path(common.stdout.strip()) / "info" / "exclude"
    text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if EXCLUDE_LINE in text.splitlines():
        return
    exclude.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith("\n"):
        text += "\n"
    exclude.write_text(text + EXCLUDE_LINE + "\n", encoding="utf-8")

"""Read the git state the merge queue checks, and fast-forward the target branch when a session lands."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """A git call the merge queue cannot work around; the message says what to do."""


def _git(cwd: str | Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *arguments], capture_output=True, text=True, check=False,
        )
    except OSError as error:
        raise GitError(f"git is not available: {error}") from None


def _output(cwd: str | Path, *arguments: str) -> str | None:
    result = _git(cwd, *arguments)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def toplevel(path: str | Path) -> str | None:
    """Return the root of the work tree holding path (a linked worktree's own root), or None outside one."""
    return _output(path, "rev-parse", "--show-toplevel")


def branch_of(path: str | Path) -> str | None:
    """Return the branch checked out at path, or None when the head is detached or path is not a work tree."""
    branch = _output(path, "rev-parse", "--abbrev-ref", "HEAD")
    return None if branch in (None, "HEAD") else branch


def head_of(path: str | Path) -> str | None:
    return _output(path, "rev-parse", "HEAD")


def ref_sha(repo: str | Path, ref: str) -> str | None:
    return _output(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")


def is_clean(path: str | Path) -> bool:
    """True when the work tree has no changes, staged, unstaged or untracked."""
    result = _git(path, "status", "--porcelain")
    if result.returncode != 0:
        raise GitError(f"cannot read git status in {path}: {result.stderr.strip()}")
    return result.stdout.strip() == ""


def is_ancestor(repo: str | Path, ancestor: str, descendant: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def checkout_of(repo: str | Path, branch: str) -> str | None:
    """Return the path of the worktree that has branch checked out, or None when no worktree has it."""
    path: str | None = None
    listing = _output(repo, "worktree", "list", "--porcelain") or ""
    for line in listing.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def detect_target(repo: str | Path) -> str:
    """Return the default branch: origin's HEAD when it is set, else a local main, else a local master."""
    remote = _output(repo, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if remote and remote.startswith("origin/"):
        return remote[len("origin/"):]
    for name in ("main", "master"):
        if ref_sha(repo, f"refs/heads/{name}"):
            return name
    raise GitError("cannot tell the target branch: name it with --target")


def fast_forward(repo: str | Path, target: str, branch: str, expected_tip: str) -> str | None:
    """Move target to branch's tip, a fast-forward only. Return None on success, else the reason it refused.

    The target's own checkout does the merge, so its work tree moves with the branch. A target that no
    worktree has checked out is moved by update-ref, which refuses unless the branch still is expected_tip.
    """
    checkout = checkout_of(repo, target)
    if checkout is None:
        result = _git(repo, "update-ref", f"refs/heads/{target}", branch_tip(repo, branch), expected_tip)
        return None if result.returncode == 0 else result.stderr.strip() or "update-ref refused"
    result = _git(checkout, "merge", "--ff-only", branch)
    return None if result.returncode == 0 else (result.stderr or result.stdout).strip() or "merge refused"


def branch_tip(repo: str | Path, branch: str) -> str:
    tip = ref_sha(repo, f"refs/heads/{branch}")
    if tip is None:
        raise GitError(f"the branch {branch} does not exist")
    return tip

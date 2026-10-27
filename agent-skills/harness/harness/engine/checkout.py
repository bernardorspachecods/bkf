"""A run's own working tree: a git worktree on a branch of its own, so the repository's checkout stays untouched.

The tree lives in ``<run>/tree`` and its branch name in ``<run>/branch``. A run without ``tree`` works in the
repository's checkout, as every run did before.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

from ..gate import run_gate
from .run import RunError


def _git(directory, args, **options):
    return subprocess.run(
        ["git", "-C", os.fspath(directory)] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False, **options
    )


def tree_path(run_path):
    return Path(run_path) / "tree"


def uncommitted(repo):
    """The lines ``git status`` shows for the checkout: changed, staged and untracked files that are not ignored."""
    result = _git(repo, ["status", "--porcelain"])
    if result.returncode != 0:
        raise RunError("cannot read the status of {0}".format(repo))
    return [line for line in result.stdout.splitlines() if line.strip()]


def create_tree(run_path, repo, branch=None, commit="HEAD"):
    """Add the run's worktree at ``commit``: on a new ``branch``, or detached when no branch is given."""
    run_path = Path(run_path)
    tree = tree_path(run_path)
    command = ["worktree", "add", "-b", branch] if branch else ["worktree", "add", "--detach"]
    result = _git(repo, command + [os.fspath(tree), commit])
    if result.returncode != 0:
        raise RunError("cannot create the worktree at {0}: {1}".format(commit, result.stderr.strip()))
    if branch:
        (run_path / "branch").write_text(branch + "\n", encoding="utf-8")
    return tree


def remove_tree(run_path, repo, delete_branch=False):
    """Remove the run's worktree, and its branch when asked. Does nothing for a run without one."""
    run_path = Path(run_path)
    tree = tree_path(run_path)
    branch_file = run_path / "branch"
    branch = branch_file.read_text(encoding="utf-8").strip() if branch_file.is_file() else ""
    if tree.exists():
        _git(repo, ["worktree", "remove", "--force", os.fspath(tree)])
        shutil.rmtree(os.fspath(tree), ignore_errors=True)
    _git(repo, ["worktree", "prune"])
    if delete_branch and branch:
        _git(repo, ["branch", "-D", branch])
    return branch


def _declared(repo):
    """What the repository's committed ``.plan-run.json`` says to set up in a new worktree."""
    result = _git(repo, ["show", "HEAD:.plan-run.json"])
    if result.returncode != 0:
        return [], []
    try:
        section = json.loads(result.stdout).get("worktree", {})
        copy, prepare = section.get("copy", []), section.get("prepare", [])
    except (ValueError, AttributeError):
        raise RunError(".plan-run.json is not valid JSON with a `worktree` object")
    if not (isinstance(copy, list) and isinstance(prepare, list)
            and all(isinstance(item, str) for item in copy + prepare)):
        raise RunError(".plan-run.json: worktree.copy and worktree.prepare must be lists of strings")
    return copy, prepare


def prepare_tree(run_path, repo, tree, timeout):
    """Copy the files and run the commands the repository declares, so gates can pass in the new worktree.

    Returns notes for the status log. The commands run outside any agent and a failing one raises RunError.
    """
    copy, prepare = _declared(repo)
    notes = []
    for relative in copy:
        parts = Path(relative).parts
        if os.path.isabs(relative) or ".." in parts or not parts:
            raise RunError(".plan-run.json: worktree.copy needs paths inside the repository: {0}".format(relative))
        source, target = Path(repo) / relative, Path(tree) / relative
        if not source.exists():
            notes.append("worktree.copy: {0} does not exist in the checkout, skipped".format(relative))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(str(source), str(target), symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(str(source), str(target))
        notes.append("worktree.copy: {0}".format(relative))
    if prepare:
        output = Path(run_path) / "prepare"
        result = run_gate(os.fspath(tree), timeout, os.fspath(output), prepare)
        if result["red"]:
            raise RunError("preparing the worktree failed (see {0}/gate.md)".format(output))
        notes.append("worktree.prepare: {0} command(s) passed".format(len(prepare)))
    return notes


def commit_all(tree, message):
    """Commit everything in the worktree as a checkpoint. Returns True when a commit was made."""
    added = _git(tree, ["add", "-A"])
    if added.returncode != 0:
        raise RunError("cannot stage the worktree: {0}".format(added.stderr.strip()))
    if _git(tree, ["diff", "--cached", "--quiet"]).returncode == 0:
        return False
    committed = _git(tree, ["commit", "-q", "--no-verify", "-m", message])
    if committed.returncode != 0:
        raise RunError("cannot commit the worktree: {0}".format(committed.stderr.strip() or committed.stdout.strip()))
    return True

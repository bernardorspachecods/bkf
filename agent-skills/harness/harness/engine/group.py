"""Prepare and run plan groups in detached git worktrees."""

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .diffbase import snapshot_commit


def _git(repo, args, output=None):
    return subprocess.run(
        ["git", "-C", os.fspath(repo)] + list(args),
        stdout=output if output is not None else subprocess.PIPE,
        stderr=output if output is not None else subprocess.PIPE,
        text=output is None,
        check=False,
    )


def _free_kb(run, environ=None):
    try:
        result = subprocess.run(
            ["df", "-k", os.fspath(run)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=environ,
        )
    except OSError:
        return 0
    lines = result.stdout.splitlines()
    try:
        return int(lines[1].split()[3])
    except (IndexError, ValueError):
        return 0


def remove_worktrees(run, repo):
    """Remove all worktrees created for a run and prune their registrations."""
    run_path = Path(run.path if hasattr(run, "path") else run)
    worktrees = run_path / "worktrees"
    if worktrees.is_dir():
        for worktree in worktrees.iterdir():
            if worktree.is_dir():
                _git(repo, ["worktree", "remove", "--force", os.fspath(worktree)])
        shutil.rmtree(worktrees, ignore_errors=True)
    _git(repo, ["worktree", "prune"])


def prepare_worktrees(run, repo, step, units, environ=None):
    """Create missing group worktrees, returning an empty or refusal reason."""
    run_path = Path(run.path if hasattr(run, "path") else run)
    marker = run_path / ".group-ready-S{0}".format(step)
    if marker.exists():
        return ""

    try:
        base = snapshot_commit(repo)
    except Exception:
        result = _git(repo, ["rev-parse", "HEAD"])
        if result.returncode != 0 or not result.stdout.strip():
            return "cannot determine HEAD for the parallel group"
        base = result.stdout.strip()

    worktrees = run_path / "worktrees"
    worktrees.mkdir(parents=True, exist_ok=True)
    missing = [unit for unit in units if not (worktrees / unit).is_dir()]
    todo = len(missing)
    first = True
    for unit in missing:
        before = _free_kb(run_path, environ) if first else 0
        log = run_path / (unit + ".worktree.log")
        with log.open("w", encoding="utf-8", newline="") as output:
            result = _git(
                repo,
                ["worktree", "add", "--detach", os.fspath(worktrees / unit), base],
                output=output,
            )
        if result.returncode != 0:
            return "could not create the worktree for {0} (see {1})".format(unit, log)
        if first:
            first = False
            after = _free_kb(run_path, environ)
            used = before - after
            if used <= 0:
                used = 0
            need = (todo - 1) * used * 5 // 4
            run.note(
                "S{0}: disk: the first worktree took {1} MB; {2} more need about {3} MB, {4} MB free".format(
                    step, used // 1024, todo - 1, need // 1024, after // 1024
                )
            )
            if after < need:
                remove_worktrees(run_path, repo)
                return (
                    "not enough free disk for the parallel group of step {0}: the first worktree took {1} MB, "
                    "the other {2} need about {3} MB with a margin of a quarter, and {4} MB is free where the "
                    "run lives ({5}). Free some space, then resume. The estimate covers the worktrees only, not "
                    "what the units create while they run (temporary database clusters, build output)."
                ).format(step, used // 1024, todo - 1, need // 1024, after // 1024, run_path)

    marker.touch()
    return ""


def run_group(ctx, step, units, unit_runner, environ=None):
    """Run unfinished units concurrently and return (passed, reason)."""
    units = list(units)
    ctx.progress("S{0} início · paralelo · {1}".format(step, ", ".join(units)))
    run = ctx.run
    reason = prepare_worktrees(run, ctx.checkout, step, units, environ=environ)
    if reason:
        run.note("S{0}: {1}".format(step, reason))
        return False, reason

    pending = [unit for unit in units if not (run.path / (".done-" + unit)).exists()]

    def execute(unit):
        unit_dir = run.path / unit
        unit_dir.mkdir(parents=True, exist_ok=True)
        reason_path = unit_dir / "reason"
        try:
            reason_path.unlink()
        except FileNotFoundError:
            pass
        passed, failure = unit_runner(unit, run.path / "worktrees" / unit)
        if passed:
            (run.path / (".done-" + unit)).touch()
            return ""
        failure = failure or ""
        with reason_path.open("w", encoding="utf-8", newline="") as output:
            output.write(failure + "\n")
        return failure

    with ThreadPoolExecutor(max_workers=max(1, len(pending))) as executor:
        futures = [executor.submit(execute, unit) for unit in pending]
        for future in futures:
            future.result()

    failures = []
    for unit in units:
        if (run.path / (".done-" + unit)).exists():
            continue
        try:
            failure = (run.path / unit / "reason").read_text(encoding="utf-8").rstrip("\r\n")
        except OSError:
            failure = ""
        failures.append((failure or "{0} stopped".format(unit)) + "; ")
    return (not failures, "".join(failures))

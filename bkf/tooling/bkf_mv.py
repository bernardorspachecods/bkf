"""Move a tracked file or directory inside a BKF bundle and fix the links that point to it.

Usage: bkf mv [--check] [--root DIR] <source> <target>
"""

from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
from pathlib import Path

from bkf_common import MAP_NAME, BKFInputError, is_bundle_root_map
from relink import apply_moves, find_outermost_bundle_root, planned_updates, refresh_inventories


class MoveRefused(Exception):
    """A move that must not happen; nothing has changed when it is raised."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf mv", description=__doc__)
    parser.add_argument("--check", action="store_true", help="list the moves and link updates without changing anything")
    parser.add_argument("--root", type=Path, help="bundle root (default: outermost ancestor whose MAP.md is a bundle root)")
    parser.add_argument("source", help="tracked file or directory to move")
    parser.add_argument("target", help="new path; it must not exist")
    return parser


def _find_root(cwd: Path) -> Path:
    root = find_outermost_bundle_root(cwd)
    if root is None:
        raise MoveRefused("no bundle root MAP.md above the current directory; pass --root")
    return root


def _relative(root: Path, path: Path, label: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        raise MoveRefused(f"{label} is outside the bundle root: {path}") from None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _missing_parents(root: Path, target: Path) -> list[Path]:
    """Return the directories the move must create for target, deepest first."""
    missing = []
    parent = target.parent
    while not os.path.lexists(parent):
        missing.append(parent)
        parent = parent.parent
    if not parent.is_dir():
        raise MoveRefused(f"target parent is not a directory: {parent.relative_to(root).as_posix()}")
    return missing


def _plan(root: Path, cwd: Path, source_arg: str, target_arg: str) -> tuple[str, str, dict[str, str], list[Path]]:
    """Validate the move and return source, target, its file moves and the directories it must create.

    Raises MoveRefused before anything on disk is changed.
    """
    source = Path(os.path.normpath(cwd / source_arg))
    target = Path(os.path.normpath(cwd / target_arg))
    source_rel = _relative(root, source, "source")
    target_rel = _relative(root, target, "target")
    if source_rel == ".":
        raise MoveRefused("the bundle root cannot be moved")
    if os.path.lexists(target):
        raise MoveRefused(f"target exists: {target_rel}")
    if Path(source_rel).name == MAP_NAME:
        raise MoveRefused(f"a {MAP_NAME} cannot be moved: {source_rel}")
    if target_rel.startswith(source_rel + "/"):
        raise MoveRefused(f"target is inside source: {target_rel}")

    listing = _git(root, "ls-files", "-z", "--", source_rel)
    if listing.returncode != 0:
        raise MoveRefused(f"not inside a git repository: {root}")
    tracked = [name for name in listing.stdout.split("\0") if name]
    if not tracked:
        raise MoveRefused(f"source is not tracked by git: {source_rel}")

    moves = {}
    for old in tracked:
        moves[old] = target_rel + old[len(source_rel):]
    return source_rel, target_rel, moves, _missing_parents(root, target)


def _move(args: argparse.Namespace) -> int:
    cwd = Path.cwd().resolve()
    root = (args.root.resolve() if args.root else _find_root(cwd))
    if not is_bundle_root_map(root / MAP_NAME):
        raise MoveRefused(f"not a bundle root: {root}")

    source_rel, target_rel, moves, missing = _plan(root, cwd, args.source, args.target)
    try:
        updates = planned_updates(root, moves)
    except BKFInputError as exc:
        raise MoveRefused(str(exc)) from None

    if args.check:
        for old, new in moves.items():
            print(f"would move: {old} -> {new}")
        for path in updates:
            print(f"would update: {path}")
        return 0

    try:
        (root / target_rel).parent.mkdir(parents=True, exist_ok=True)
        result = _git(root, "mv", source_rel, target_rel)
    except OSError as exc:
        _remove_dirs(missing)
        raise MoveRefused(f"cannot move: {exc}") from None
    if result.returncode != 0:
        _remove_dirs(missing)
        raise MoveRefused(result.stderr.strip() or "git mv failed")

    changed = apply_moves(root, moves, True)
    status = refresh_inventories(root)
    if status != 0:
        raise MoveRefused(f"the files were moved, but refreshing the inventories failed (exit {status})")

    for old, new in moves.items():
        print(f"moved: {old} -> {new}")
    for path in changed:
        print(f"updated: {path}")
    return 0


def _remove_dirs(directories: list[Path]) -> None:
    """Remove directories this move created, deepest first; they are empty when the move failed."""
    for directory in directories:
        with contextlib.suppress(OSError):
            os.rmdir(directory)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _move(args)
    except MoveRefused as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

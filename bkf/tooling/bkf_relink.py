"""Fix links after files were moved by hand inside a BKF bundle.

Usage: bkf relink [--check] [--root DIR] [--since REF] [--map OLD=NEW ...]

Moves are found with git rename detection on a copy of the index, so the
real index and working tree are not touched by the detection.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bkf_common import MAP_NAME, BKFInputError, is_bundle_root_map, read_text_preserving_newlines
from relink import apply_moves, bundle_files, find_outermost_bundle_root, markdown_link_paths, refresh_inventories


class RelinkError(Exception):
    """A run that cannot continue; nothing has changed when it is raised."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf relink", description=__doc__)
    parser.add_argument("--check", action="store_true", help="list the moves and link updates without changing anything")
    parser.add_argument("--root", type=Path, help="bundle root (default: outermost ancestor whose MAP.md is a bundle root)")
    parser.add_argument("--since", default="HEAD", metavar="REF", help="commit to compare the working tree with (default: HEAD)")
    parser.add_argument(
        "--map", action="extend", nargs="+", metavar="OLD=NEW",
        help="an explicit move, paths relative to the root, for a case detection cannot settle",
    )
    return parser


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", check=False, env=env,
    )


def _repository(root: Path) -> str:
    """Return the prefix of the bundle root inside its git repository ("" or "dir/"), refusing without git."""
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise RelinkError(f"not inside a git repository: {root}")
    try:
        relative = root.relative_to(Path(top.stdout.strip()).resolve()).as_posix()
    except ValueError:
        raise RelinkError(f"bundle root is outside its git repository: {root}") from None
    return "" if relative == "." else relative + "/"


def _staged_entries(root: Path, since: str) -> list[tuple[str, list[str]]]:
    """Return (status, paths) of the working tree compared with since, paths relative to the repository.

    The working tree is staged into a copy of the index, which the real index never sees.
    """
    index = _git(root, "rev-parse", "--git-path", "index").stdout.strip()
    real_index = os.path.join(root, index)
    with tempfile.TemporaryDirectory() as scratch:
        temp_index = os.path.join(scratch, "index")
        if os.path.isfile(real_index):
            shutil.copyfile(real_index, temp_index)
        env = {**os.environ, "GIT_INDEX_FILE": temp_index}
        if _git(root, "add", "-A", env=env).returncode != 0:
            raise RelinkError("cannot stage the working tree to find moves")
        diff = _git(root, "diff", "--cached", "-M", "--name-status", "-z", since, env=env)
    if diff.returncode != 0:
        raise RelinkError(f"cannot compare the working tree with {since}")

    tokens = diff.stdout.split("\0")
    entries = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        count = 2 if status[0] in "RC" else 1
        entries.append((status[0], tokens[i + 1 : i + 1 + count]))
        i += 1 + count
    return entries


def _top_path(path: str, prefix: str) -> str | None:
    """Return path (repository-relative) relative to the run root, or None when it is outside the root."""
    if not prefix:
        return path
    return path[len(prefix):] if path.startswith(prefix) else None


def _detected(prefix: str, entries: list[tuple[str, list[str]]]) -> tuple[dict[str, str], set[str]]:
    """Return the moves found by rename detection and the paths that were added, relative to the run root."""
    moves = {}
    added = set()
    for status, paths in entries:
        if status == "R":
            old, new = (_top_path(path, prefix) for path in paths)
            if old and new:
                moves[old] = new
        elif status == "A":
            new = _top_path(paths[0], prefix)
            if new:
                added.add(new)
    return moves, added


def _top_relative(root: Path, value: str) -> str:
    """Return value (relative to the root) normalized, refusing a path outside the root."""
    target = os.path.normpath(os.path.join(root, value))
    try:
        rel = Path(target).relative_to(root).as_posix()
    except ValueError:
        raise RelinkError(f"--map path is outside the bundle root: {value}") from None
    if rel == ".":
        raise RelinkError(f"--map path is the bundle root: {value}")
    return rel


def _explicit(root: Path, pairs: list[str]) -> dict[str, str]:
    moves = {}
    for pair in pairs:
        old, sep, new = pair.partition("=")
        if not sep or not old or not new:
            raise RelinkError(f"--map needs OLD=NEW: {pair}")
        old_rel = _top_relative(root, old)
        new_rel = _top_relative(root, new)
        if os.path.lexists(root / old_rel):
            raise RelinkError(f"--map OLD still exists: {old_rel}")
        if not (root / new_rel).is_file():
            raise RelinkError(f"--map NEW does not exist: {new_rel}")
        moves[old_rel] = new_rel
    return moves


def _exists_in_bundle(root: Path, path: str) -> bool:
    target = os.path.normpath(os.path.join(root, path))
    if not target.startswith(str(root) + os.sep) and target != str(root):
        return False
    return os.path.exists(target)


def _candidates(top: Path, name: str, pool: set[str]) -> list[str]:
    """Return the files under top that are new in this run and share the basename of name."""
    base = posixpath.basename(name)
    return sorted(rel for rel in bundle_files(top) if rel in pool and posixpath.basename(rel) == base)


def _unresolved(top: Path, moves: dict[str, str], pool: set[str]) -> dict[str, list[str]]:
    """Return each Markdown link target still missing after the moves, in top coordinates, with its candidates.

    Call it before the links are rewritten: a link to a moved file's old path is not missing.
    """
    unresolved = {}
    for rel in bundle_files(top):
        if not rel.endswith(".md"):
            continue
        for path in markdown_link_paths(read_text_preserving_newlines(top / rel)):
            if path in moves or _exists_in_bundle(top, path):
                continue
            unresolved[path] = _candidates(top, path, pool)
    return dict(sorted(unresolved.items()))


def _untracked(root: Path) -> list[str]:
    listing = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if listing.returncode != 0:
        raise RelinkError(f"cannot list untracked files: {root}")
    return [name for name in listing.stdout.split("\0") if name]


def _run(args: argparse.Namespace) -> int:
    cwd = Path.cwd().resolve()
    top = args.root.resolve() if args.root else find_outermost_bundle_root(cwd)
    if top is None:
        raise RelinkError("no bundle root MAP.md above the current directory; pass --root")
    if not is_bundle_root_map(top / MAP_NAME):
        raise RelinkError(f"not a bundle root: {top}")

    prefix = _repository(top)
    if _git(top, "rev-parse", "--verify", "--quiet", f"{args.since}^{{commit}}").returncode != 0:
        raise RelinkError(f"not a commit: {args.since}")

    try:
        detected, added = _detected(prefix, _staged_entries(top, args.since))
        moves = {**detected, **_explicit(top, args.map or [])}
        unresolved = _unresolved(top, moves, {*moves.values(), *added, *_untracked(top)})
        changed = apply_moves(top, moves, write=not args.check)
    except BKFInputError as exc:
        raise RelinkError(str(exc)) from None

    if moves and not args.check:
        status = refresh_inventories(top)
        if status != 0:
            raise RelinkError(f"the links were updated, but refreshing the inventories failed (exit {status})")

    move_label, update_label = ("would relink:", "would update:") if args.check else ("relinked:", "updated:")
    for old, new in sorted(moves.items()):
        print(f"{move_label} {old} -> {new}")
    for path in changed:
        print(f"{update_label} {path}")
    for path, candidates in unresolved.items():
        print(f"unresolved: {path}")
        if candidates:
            print(f"  candidates: {', '.join(candidates)}")
    if not (moves or changed or unresolved):
        print("nothing to relink")
    return 1 if unresolved else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except RelinkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

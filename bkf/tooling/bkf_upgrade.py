"""Migrate bundles written before the current format version to it.

Usage: bkf upgrade [--check] [PATH]...

Before format 0.2 each nested bundle wrote its root-absolute links from its own root. From 0.2 every
link resolves from the outermost bundle root, so a nested bundle's links gain its prefix. Only link
destinations and the bkf_version value change; a file that is already current is left alone.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from bkf_common import (
    MAP_NAME,
    BKFInputError,
    find_bundles,
    in_nested_bundle,
    is_bundle_root_map,
    outermost_bundle_root,
    parse_markdown,
    read_text_preserving_newlines,
)
from relink import bundle_files, prefix_markdown_links_counted, refresh_inventories
from validate_bundle import VERSION_RE

TARGET_VERSION = (0, 2)
_TARGET_TEXT = f"{TARGET_VERSION[0]}.{TARGET_VERSION[1]}"
_VERSION_LINE = re.compile(
    r"^(bkf_version[ \t]*:[ \t]*)(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s#\"'][^\s#]*)([ \t]+#.*|[ \t]*)$"
)


class UpgradeError(Exception):
    """A bundle that cannot be upgraded; nothing has been written when it is raised."""


@dataclass(frozen=True)
class _Plan:
    bundle: Path
    top: Path
    edits: list[tuple[Path, str, int]]  # file, new text, link count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf upgrade", description=__doc__)
    parser.add_argument("--check", action="store_true", help="list what would change without changing anything")
    parser.add_argument("paths", nargs="*", type=Path, metavar="PATH", help="directory to upgrade (default: .)")
    return parser


def _display(path: Path) -> str:
    return os.path.relpath(path, Path.cwd())


def _declared_version(bundle: Path) -> tuple[int, int]:
    map_path = bundle / MAP_NAME
    try:
        value = parse_markdown(map_path).frontmatter.get("bkf_version")
    except (BKFInputError, OSError) as exc:
        raise UpgradeError(f"{_display(map_path)}: {exc}") from None
    match = VERSION_RE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise UpgradeError(f'{_display(map_path)}: bkf_version must be a "<major>.<minor>" string')
    return int(match.group(1)), int(match.group(2))


def _exists_under(root: Path):
    def exists(path: str) -> bool:
        return os.path.exists(root / path)

    return exists


def _with_version(text: str, map_path: Path) -> str:
    """Return text with the bkf_version value of its frontmatter replaced, every other byte kept."""
    lines = text.splitlines(keepends=True)
    closing = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") == "---"), None)
    for index in range(1, closing or 0):
        body = lines[index].rstrip("\r\n")
        match = _VERSION_LINE.match(body)
        if match:
            lines[index] = f'{match.group(1)}"{_TARGET_TEXT}"{match.group(3)}' + lines[index][len(body):]
            return "".join(lines)
    raise UpgradeError(f"{_display(map_path)}: cannot find the bkf_version line to replace")


def _plan_bundle(bundle: Path, top: Path) -> _Plan | None:
    """Return the edits that bring bundle to TARGET_VERSION, or None when it is already current."""
    if _declared_version(bundle) >= TARGET_VERSION:
        return None

    edits: dict[Path, tuple[str, int]] = {}
    if top != bundle:
        prefix = bundle.relative_to(top).as_posix()
        for rel in bundle_files(bundle):
            path = bundle / rel
            if not rel.endswith(".md") or in_nested_bundle(bundle, path):
                continue
            text = read_text_preserving_newlines(path)
            new, count = prefix_markdown_links_counted(text, prefix, _exists_under(bundle))
            if new != text:
                edits[path] = (new, count)

    map_path = bundle / MAP_NAME
    text, count = edits.get(map_path, (read_text_preserving_newlines(map_path), 0))
    edits[map_path] = (_with_version(text, map_path), count)
    return _Plan(
        bundle=bundle,
        top=top,
        edits=[(path, new, count) for path, (new, count) in edits.items()],
    )


def _bundles_under(path: Path) -> list[Path]:
    """Return the bundle roots at or inside path, skipping node_modules and linked worktrees."""
    found = []
    for bundle in find_bundles(path):
        if not is_bundle_root_map(bundle / MAP_NAME):
            continue
        if "node_modules" in bundle.relative_to(path).parts:
            continue
        found.append(bundle)
    return found


def _plan(paths: list[Path]) -> list[_Plan]:
    plans = []
    seen: set[Path] = set()
    for path in paths:
        for bundle in _bundles_under(path):
            if bundle in seen:
                continue
            seen.add(bundle)
            plan = _plan_bundle(bundle, outermost_bundle_root(bundle))
            if plan is not None:
                plans.append(plan)
    return plans


def _write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        target.write(text)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = args.paths or [Path(".")]
    invalid = [path for path in paths if not path.is_dir()]
    if invalid:
        for path in invalid:
            print(f"error: path is not a directory: {path}", file=sys.stderr)
        return 2

    try:
        plans = _plan([path.resolve() for path in paths])
    except (UpgradeError, BKFInputError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not plans:
        print("already current")
        return 0

    if args.check:
        for plan in plans:
            print(f"would upgrade: {_display(plan.bundle)}")
            for path, _text, count in plan.edits:
                if count:
                    print(f"would update: {_display(path)} ({count} links)")
        return 1

    for plan in plans:
        for path, text, _count in plan.edits:
            _write(path, text)
    for plan in plans:
        print(f"upgraded: {_display(plan.bundle)}")
        for path, _text, count in plan.edits:
            if count:
                print(f"updated: {_display(path)} ({count} links)")

    try:
        for top in sorted({plan.top for plan in plans}):
            if refresh_inventories(top) != 0:
                print("error: the bundles were upgraded, but refreshing the inventories failed", file=sys.stderr)
                return 2
    except BKFInputError as exc:
        print(f"error: the bundles were upgraded, but refreshing the inventories failed: {exc}", file=sys.stderr)
        return 2
    return 0

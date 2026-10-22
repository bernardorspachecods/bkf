#!/usr/bin/env python3
"""Generate or check BKF MAP.md member inventories."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import tempfile
from pathlib import Path

from bkf_common import (
    BKFInputError,
    MAP_NAME,
    discover_maps,
    find_bundles,
    inventory_entries,
    render_inventory_entry,
    read_text_preserving_newlines,
    parse_markdown,
)


START_MARKER = "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->"
END_MARKER = "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->"
TAGGED_LIST_END_MARKER = "<!-- BKF:GENERATED-TAGGED-LIST-END -->"
TAGGED_LIST_START_PREFIX = "<!-- BKF:GENERATED-TAGGED-LIST"
TAGGED_LIST_START_RE = re.compile(r"^<!-- BKF:GENERATED-TAGGED-LIST\s+tags:\s*(.*?)\s*-->$")
INJECT_DIRECTIVE_RE = re.compile(r"^<!--\s*inject:\s*(\S+?)\s*-->$")
INJECT_START_MARKER = "<!-- BKF:GENERATED-INJECTED -->"
INJECT_END_MARKER = "<!-- BKF:GENERATED-INJECTED-END -->"
MARKDOWN_LINK_RE = re.compile(r"(\]\()([^)\s]+)(\))")
HEADING_RE = re.compile(r"^(#{1,5})(\s)")
TABLE_HEADER = "| What it is | Document |"
TABLE_SEPARATOR = "| --- | --- |"


def update_map(root: Path, map_path: Path) -> tuple[str, str]:
    try:
        original = read_text_preserving_newlines(map_path)
    except BKFInputError as exc:
        raise BKFInputError(
            f"{map_path.relative_to(root).as_posix()}: {exc}"
        ) from exc

    lines = original.splitlines(keepends=True)
    contents = [line.rstrip("\r\n") for line in lines]
    starts = [i for i, line in enumerate(contents) if line == START_MARKER]
    ends = [i for i, line in enumerate(contents) if line == END_MARKER]
    headings = [i for i, line in enumerate(contents) if line == "## Member inventory"]
    if len(starts) != 1 or len(ends) != 1 or len(headings) != 1:
        raise BKFInputError("map needs one inventory heading and one marker pair")
    start, end = starts[0], ends[0]
    if not (headings[0] < start < end):
        raise BKFInputError("inventory markers are misplaced or reversed")
    if any(line.strip() for line in contents[headings[0] + 1 : start]):
        raise BKFInputError("generated markers must directly follow the inventory heading")

    entries = inventory_entries(root, map_path)
    newline = "\r\n" if "\r\n" in original else "\n"
    generated = [TABLE_HEADER + newline, TABLE_SEPARATOR + newline]
    generated.extend(render_inventory_entry(root, entry) + newline for entry in entries)
    updated = "".join(lines[: start + 1] + generated + lines[end:])
    return original, updated


def update_skill_file(library_root: Path, skill_path: Path) -> tuple[str, str]:
    try:
        original = read_text_preserving_newlines(skill_path)
    except BKFInputError as exc:
        raise BKFInputError(f"{skill_path}: {exc}") from exc
    lines = original.splitlines(keepends=True)
    contents = [line.rstrip("\r\n") for line in lines]
    starts = [i for i, line in enumerate(contents) if TAGGED_LIST_START_PREFIX in line and TAGGED_LIST_END_MARKER not in line]
    ends = [i for i, line in enumerate(contents) if line.strip() == TAGGED_LIST_END_MARKER]
    if not starts and not ends:
        return original, apply_injections(original, skill_path)
    if len(starts) != 1 or len(ends) != 1:
        raise BKFInputError(f"{skill_path}: generated tagged list needs exactly one paired marker set")
    start, end = starts[0], ends[0]
    if start >= end:
        raise BKFInputError(f"{skill_path}: generated tagged list markers are unpaired or reversed")
    match = TAGGED_LIST_START_RE.fullmatch(contents[start].strip())
    if match is None or not match.group(1).strip():
        raise BKFInputError(f"{skill_path}: generated tagged list marker must name at least one tag")
    tags = [tag.strip() for tag in match.group(1).split(",")]
    if not tags or any(not tag for tag in tags):
        raise BKFInputError(f"{skill_path}: generated tagged list marker has an empty tag")

    entries: list[tuple[str, Path, str]] = []
    for group in ("modules", "workflow-types"):
        directory = library_root / group
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md"), key=lambda item: (item.name.casefold(), item.as_posix())):
            if path.name == MAP_NAME:
                continue
            try:
                metadata = parse_markdown(path).frontmatter
            except BKFInputError as exc:
                raise BKFInputError(f"{path.relative_to(library_root).as_posix()}: {exc}") from exc
            file_tags = metadata.get("tags")
            if not isinstance(file_tags, list) or not set(tags).intersection(
                value for value in file_tags if isinstance(value, str)
            ):
                continue
            description = metadata.get("description")
            if not isinstance(description, str) or not description.strip():
                raise BKFInputError(
                    f"{path.relative_to(library_root).as_posix()}: matching file needs a non-empty description"
                )
            entries.append((group, path, " ".join(description.split())))

    newline = "\r\n" if "\r\n" in original else "\n"
    generated = [TABLE_HEADER + newline, TABLE_SEPARATOR + newline]
    for _, path, description in entries:
        relative = os.path.relpath(path, skill_path.parent).replace(os.sep, "/")
        escaped_description = description.replace("|", "\\|")
        generated.append(f"| {escaped_description} | [{path.name}]({relative}) |{newline}")
    updated = "".join(lines[: start + 1] + generated + lines[end:])
    return original, apply_injections(updated, skill_path)


def injected_body(source: Path, skill_path: Path) -> list[str]:
    """The lines of a file to inject into a skill: no frontmatter, headings one level down, links rebased."""
    try:
        text = read_text_preserving_newlines(source)
    except BKFInputError as exc:
        raise BKFInputError(f"{source}: {exc}") from exc
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
        if closing is None:
            raise BKFInputError(f"{source}: frontmatter is not closed")
        lines = lines[closing + 1 :]
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]

    def rebase(match: re.Match[str]) -> str:
        target = match.group(2)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
            return match.group(0)
        if target.startswith("/"):
            raise BKFInputError(
                f"{source}: injected files may not contain bundle-root links (found {target}); use a relative link"
            )
        path, _, fragment = target.partition("#")
        rebased = os.path.relpath((source.parent / path).resolve(), skill_path.parent.resolve()).replace(os.sep, "/")
        return f"{match.group(1)}{rebased}{'#' + fragment if fragment else ''}{match.group(3)}"

    result: list[str] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            result.append(line)
            continue
        if in_fence:
            result.append(line)
            continue
        result.append(MARKDOWN_LINK_RE.sub(rebase, HEADING_RE.sub(r"\1#\2", line, count=1)))
    return result


def apply_injections(text: str, skill_path: Path) -> str:
    """Expand each `<!-- inject: path -->` line into a generated block holding that file's text."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    contents = [line.rstrip("\r\n") for line in lines]
    if any(line.strip() in (INJECT_START_MARKER, INJECT_END_MARKER) for line in contents) and not any(
        INJECT_DIRECTIVE_RE.fullmatch(line.strip()) for line in contents
    ):
        raise BKFInputError(f"{skill_path}: generated injected block has no inject directive")
    out: list[str] = []
    i = 0
    while i < len(lines):
        match = INJECT_DIRECTIVE_RE.fullmatch(contents[i].strip())
        if match is None:
            if contents[i].strip() in (INJECT_START_MARKER, INJECT_END_MARKER):
                raise BKFInputError(f"{skill_path}: generated injected block does not follow an inject directive")
            out.append(lines[i])
            i += 1
            continue
        relative = match.group(1)
        source = (skill_path.parent / relative).resolve()
        if source.suffix != ".md":
            raise BKFInputError(f"{skill_path}: inject target is not a Markdown file: {relative}")
        if not source.is_file():
            raise BKFInputError(f"{skill_path}: inject target does not exist: {relative}")
        out.append(lines[i])
        i += 1
        if i < len(lines) and contents[i].strip() == INJECT_START_MARKER:
            end = next((j for j in range(i + 1, len(lines)) if contents[j].strip() == INJECT_END_MARKER), None)
            if end is None:
                raise BKFInputError(f"{skill_path}: generated injected block is not closed")
            i = end + 1
        body = injected_body(source, skill_path)
        out.append(INJECT_START_MARKER + newline)
        out.extend(line + newline for line in body)
        out.append(INJECT_END_MARKER + newline)
    return "".join(out)


def skill_updates(library_root: Path, skills_dir: Path) -> list[tuple[Path, str, str]]:
    skill_files = sorted(skills_dir.glob("*/SKILL.md"), key=lambda path: path.as_posix())
    updates: list[tuple[Path, str, str]] = []
    for skill_path in skill_files:
        original, updated = update_skill_file(library_root, skill_path)
        updates.append((skill_path, original, updated))
    return updates


def write_atomically(path: Path, content: str) -> None:
    mode = path.stat().st_mode
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf inventory", description=__doc__)
    parser.add_argument("bundle_root", type=Path, help="directory containing the root MAP.md")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write refreshed inventories")
    mode.add_argument("--check", action="store_true", help="fail if any inventory is stale")
    parser.add_argument("--skills", type=Path, help="also generate tagged lists in entry skills (selected bundle only)")
    parser.add_argument(
        "--this-bundle",
        action="store_true",
        help="process only the selected bundle, not the bundles nested inside it",
    )
    return parser


def process_bundle(root: Path, skills: Path | None, check: bool, write: bool) -> int:
    maps = discover_maps(root)
    updates: list[tuple[Path, str, str]] = []
    skill_changes: list[tuple[Path, str, str]] = []
    try:
        for map_path in maps:
            original, updated = update_map(root, map_path)
            updates.append((map_path, original, updated))
        if skills is not None:
            skill_changes = skill_updates(root, skills.resolve())
    except BKFInputError as exc:
        print(f"error: {map_path.relative_to(root).as_posix()}: {exc}", file=sys.stderr)
        return 2

    changed = [(path, old, new) for path, old, new in updates if old != new]
    changed_skills = [(path, old, new) for path, old, new in skill_changes if old != new]
    if check:
        if changed or changed_skills:
            for path, _, _ in changed:
                print(f"stale: {path.relative_to(root).as_posix()}")
            skills_root = skills.resolve() if skills is not None else root
            for path, _, _ in changed_skills:
                print(f"stale: {path.relative_to(skills_root).as_posix()}")
            return 1
        print("all BKF map inventories are up to date")
        return 0

    if write:
        try:
            for path, _, updated in changed + changed_skills:
                write_atomically(path, updated)
        except OSError as exc:
            print(f"error: failed to write map: {exc}", file=sys.stderr)
            return 2
        for path, _, _ in changed:
            print(f"updated: {path.relative_to(root).as_posix()}")
        skills_root = skills.resolve() if skills is not None else root
        for path, _, _ in changed_skills:
            print(f"updated: {path.relative_to(skills_root).as_posix()}")
        if not changed and not changed_skills:
            print("all BKF map inventories are up to date")
        return 0

    if not changed and not changed_skills:
        print("all BKF map inventories are up to date")
        return 0
    for path, old, new in changed:
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.relative_to(root).as_posix()}",
            tofile=f"b/{path.relative_to(root).as_posix()}",
        )
        sys.stdout.writelines(diff)
    skills_root = skills.resolve() if skills is not None else root
    for path, old, new in changed_skills:
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.relative_to(skills_root).as_posix()}",
            tofile=f"b/{path.relative_to(skills_root).as_posix()}",
        )
        sys.stdout.writelines(diff)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.bundle_root.resolve()
    if not root.is_dir() or not (root / MAP_NAME).is_file():
        print(f"error: bundle root must contain {MAP_NAME}: {root}", file=sys.stderr)
        return 2
    if args.skills is not None and not args.skills.resolve().is_dir():
        print(f"error: skills directory does not exist: {args.skills}", file=sys.stderr)
        return 2

    bundles = find_bundles(root, walk_nested=not args.this_bundle)
    status = 0
    for bundle in bundles:
        if len(bundles) > 1:
            print(f"== {bundle.relative_to(root).as_posix()} ==")
        skills = args.skills if bundle == root else None
        status = max(status, process_bundle(bundle, skills, args.check, args.write))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

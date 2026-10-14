#!/usr/bin/env python3
"""Keep conversation turns from a Codex Markdown session export."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path


SECTION_RE = re.compile(r"^## (User|Assistant|Activity)\s*$")
EVENT_CATEGORIES = {
    "command": "Commands and file reads",
    "search": "Web searches",
    "agent": "Agents",
    "opened": "Opened links",
    "other": "Other activity",
}


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    title = "# Codex conversation"
    sections: list[tuple[str, str]] = []
    current_kind: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("# ") and not sections and current_kind is None:
            title = line
            continue
        match = SECTION_RE.fullmatch(line)
        if match:
            if current_kind is not None:
                sections.append((current_kind, "\n".join(current_lines)))
            current_kind = match.group(1)
            current_lines = []
        elif current_kind is not None:
            current_lines.append(line)

    if current_kind is not None:
        sections.append((current_kind, "\n".join(current_lines)))
    return title, sections


def activity_events(body: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    for line in body.splitlines():
        if not line.startswith("    "):
            continue
        item = line[4:].strip()
        if item.startswith("$ "):
            events.append(("command", item[2:]))
        elif item.startswith("Searched the web for "):
            events.append(("search", item.removeprefix("Searched the web for ")))
        elif item == "Searched the web":
            events.append(("search", "Search recorded; query not included in the export."))
        elif item.startswith("Opened "):
            events.append(("opened", item.removeprefix("Opened ")))
        elif item.startswith("• "):
            events.append(("agent" if re.match(r"• (Started|Completed|Interrupted) ", item) else "other", item[2:]))
    return events


def render_activity_run(events: list[tuple[str, str]]) -> str:
    lines = ["## Activity"]
    last_category: str | None = None
    for category, value in events:
        if category != last_category:
            lines.extend(["", f"### {EVENT_CATEGORIES[category]}", ""])
            last_category = category
        if category == "command":
            longest_tick_run = max((len(run) for run in re.findall(r"`+", value)), default=0)
            delimiter = "`" * (longest_tick_run + 1)
            lines.append(f"- {delimiter}{value}{delimiter}")
        else:
            lines.append(f"- {value}")
    return "\n".join(lines)


def clean_transcript(text: str, mode: str) -> str:
    title, sections = split_sections(text)
    output = [title]
    pending_activity: list[tuple[str, str]] = []

    def flush_activity() -> None:
        if pending_activity:
            output.extend(["", render_activity_run(pending_activity)])
            pending_activity.clear()

    for kind, body in sections:
        if kind == "Activity":
            if mode == "messages-and-activity":
                pending_activity.extend(activity_events(body))
            continue

        flush_activity()
        content = body.strip("\n")
        if content:
            output.extend(["", f"## {kind}", "", content])

    flush_activity()
    return "\n".join(output).rstrip() + "\n"


def next_transcript_path(directory: Path) -> Path:
    number = 1
    while (directory / f"codex-trancript-{number}.md").exists():
        number += 1
    return directory / f"codex-trancript-{number}.md"


def write_text(path: Path, text: str) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"output directory does not exist: {path.parent}")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as temporary:
        temporary.write(text)
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Codex Markdown session export")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("messages-only", "messages-and-activity"),
        help="select what to retain",
    )
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="write to this path (default: stdout)")
    destination.add_argument("--in-place", action="store_true", help="replace the source file")
    destination.add_argument("--rename", action="store_true", help="rename to the next codex-trancript-N.md")
    parser.add_argument("--rename-number", type=int, help="number to use with --rename")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.rename_number is not None and not args.rename:
            raise ValueError("--rename-number requires --rename")
        if args.rename_number is not None and args.rename_number < 1:
            raise ValueError("--rename-number must be a positive integer")

        source = args.source
        text = source.read_text(encoding="utf-8")
        cleaned = clean_transcript(text, args.mode)

        if args.in_place:
            write_text(source, cleaned)
        elif args.rename:
            target = (
                source.parent / f"codex-trancript-{args.rename_number}.md"
                if args.rename_number is not None
                else next_transcript_path(source.parent)
            )
            if target.exists():
                raise ValueError(f"rename target already exists: {target}")
            write_text(target, cleaned)
            source.unlink()
            print(target, file=sys.stderr)
        elif args.output:
            target = args.output
            if target.resolve() == source.resolve():
                raise ValueError("use --in-place when the output path is the source")
            write_text(target, cleaned)
        else:
            sys.stdout.write(cleaned)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"clean_transcript.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

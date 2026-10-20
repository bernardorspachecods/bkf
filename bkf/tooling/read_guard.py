"""Guard first whole-file reads of large Markdown documents with navigation maps."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from bkf_common import BKFInputError, needs_navigation_map, parse_markdown
from navigation_map import LINK, MAP_HEADING, fenced_lines, navigation_rows, section_range
from navigation_map import headings as document_headings
from hook_events import REASON_LIMIT, _prune, _state


SHELL_META = ";|&<>()$`\n\r"


def _plain_cat(command: object, cwd: Path) -> Path | None:
    if not isinstance(command, str) or not command.strip():
        return None
    if "\n" in command or "\r" in command:
        return None
    text = command.strip()
    has_cd = "&&" in text
    if has_cd:
        if text.count("&&") != 1 or text.count("&") != 2:
            return None
        left, right = text.split("&&")
        if any(char in SHELL_META for char in left + right):
            return None
        try:
            before = shlex.split(left)
            after = shlex.split(right)
        except ValueError:
            return None
        if len(before) != 2 or before[0] != "cd" or len(after) != 2:
            return None
        base = Path(before[1]).expanduser()
        if not base.is_absolute():
            base = cwd / base
        base = base.resolve()
        tokens = after
    else:
        if any(char in SHELL_META for char in text):
            return None
        try:
            tokens = shlex.split(text)
        except ValueError:
            return None
        base = cwd
    if len(tokens) != 2 or tokens[0] != "cat" or tokens[1].startswith("-"):
        return None
    path = Path(tokens[1]).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def target_path(data: dict) -> Path | None:
    """Return a resolved whole-file Read or single-file cat target, if eligible."""
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    cwd = Path(data.get("cwd") or ".").expanduser().resolve()
    tool = data.get("tool_name")
    if tool == "Read":
        if tool_input.get("offset") is not None or tool_input.get("limit") is not None:
            return None
        file_path = tool_input.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            return None
        target = Path(file_path).expanduser()
        if not target.is_absolute():
            target = cwd / target
        return target.resolve()
    if tool == "Bash":
        return _plain_cat(tool_input.get("command"), cwd)
    return None


def navigation_entries(lines: list[str], file_path: Path) -> list[str]:
    """Render table links with their resolved section ranges or original targets."""
    headings = document_headings(lines)
    by_slug = {heading["slug"]: index for index, heading in enumerate(headings)}
    entries: list[str] = []
    for _, first, second in navigation_rows(lines):
        links = LINK.findall(second)
        for label, target in links:
            if target.startswith("#"):
                anchor = target[1:]
                if anchor not in by_slug:
                    entries.append(f"{first} -> unresolved #{anchor}")
                    continue
                index = by_slug[anchor]
                start, end = section_range(index, headings, len(lines))
                entries.append(f"{first} -> {headings[index]['title']}, lines {start}-{end}")
            else:
                entries.append(f"{first} -> [{label}]({target})")
    return entries


def _reason(entries: list[str]) -> str:
    beginning = "This file was not read because it is large and has a navigation map.\n"
    ending = "\nUse Read with `offset` and `limit` (or `sed -n 'A,Bp'`) to read the section you need. Reading the whole file again will be allowed."
    available = REASON_LIMIT - len(beginning) - len(ending)
    selected: list[str] = []
    for entry in entries:
        addition = ("\n" if selected else "") + entry
        if len("\n".join(selected)) + len(addition) > available:
            marker = "\n… additional navigation entries omitted"
            if len("\n".join(selected)) + len(marker) <= available:
                selected.append(marker.lstrip("\n"))
            break
        selected.append(entry)
    return beginning + "\n".join(selected) + ending


def guard(data: dict, state_dir: Path | None = None) -> dict | None:
    """Return the PreToolUse deny payload for a first whole-file read, if needed."""
    target = target_path(data)
    if target is None:
        return None
    try:
        if not target.is_file() or target.suffix != ".md":
            return None
        content = target.read_text(encoding="utf-8")
        if not needs_navigation_map(parse_markdown(target).body):
            return None
    except (OSError, UnicodeError, BKFInputError):
        return None
    lines = content.splitlines()
    if not any(line == MAP_HEADING for _, line in fenced_lines(lines)):
        return None

    session_id = data.get("session_id", "")
    state_path = _state(session_id if isinstance(session_id, str) else "", "guard", state_dir)
    try:
        refused = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else []
        if not isinstance(refused, list) or any(not isinstance(path, str) for path in refused):
            refused = []
    except (OSError, UnicodeError, ValueError):
        refused = []
    resolved = str(target)
    if resolved in refused:
        return None
    refused.append(resolved)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(refused, ensure_ascii=False) + "\n", encoding="utf-8")
    _prune(state_path.parent)

    reason = _reason(navigation_entries(lines, target))
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}

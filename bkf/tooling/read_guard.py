"""Guard first whole-file reads of large Markdown documents with navigation maps."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from hook_events import REASON_LIMIT, _prune, _state


GUARD_MIN_BYTES = 8000
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
SEPARATOR = re.compile(r"^:?-{3,}:?$")
SHELL_META = ";|&<>()$`\n\r"


def _split_cells(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]


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


def _fenced_lines(lines: list[str]):
    """Yield (line number, line) pairs outside fenced code blocks."""
    fence_char = ""
    fence_size = 0
    for number, line in enumerate(lines, 1):
        match = FENCE.match(line)
        if fence_char:
            if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_size:
                fence_char = ""
            continue
        if match:
            fence_char = match.group(1)[0]
            fence_size = len(match.group(1))
            continue
        yield number, line


def _headings(lines: list[str]) -> list[dict]:
    headings = []
    used: dict[str, int] = {}
    for number, line in _fenced_lines(lines):
        match = HEADING.match(line)
        if not match:
            continue
        title = match.group(2).strip()
        base = "".join(char for char in title.lower() if char.isalnum() or char in " -_")
        base = re.sub(r" +", "-", base.strip())
        ordinal = used.get(base, 0)
        used[base] = ordinal + 1
        slug = base if ordinal == 0 else f"{base}-{ordinal}"
        headings.append({"line": number, "level": len(match.group(1)), "title": title, "slug": slug})
    return headings


def _navigation_rows(lines: list[str]) -> list[tuple[int, str, str]]:
    visible = list(_fenced_lines(lines))
    map_at = next((index for index, (_, line) in enumerate(visible) if line == "## Navigation map"), None)
    if map_at is None:
        return []
    rows: list[tuple[int, str, str]] = []
    table_lines = []
    for number, line in visible[map_at + 1:]:
        stripped = line.strip()
        if not stripped:
            if table_lines:
                break
            continue
        if not stripped.startswith("|"):
            if table_lines:
                break
            continue
        table_lines.append((number, _split_cells(stripped)))
    if len(table_lines) < 3:
        return []
    separator = table_lines[1][1]
    if len(separator) < 2 or not all(SEPARATOR.fullmatch(cell.replace(" ", "")) for cell in separator[:2]):
        return []
    for number, cells in table_lines[2:]:
        if len(cells) >= 2:
            rows.append((number, cells[0], cells[1]))
    return rows


def _section_range(index: int, headings: list[dict], total_lines: int) -> tuple[int, int]:
    heading = headings[index]
    end = total_lines
    for following in headings[index + 1:]:
        if following["level"] <= heading["level"]:
            end = following["line"] - 1
            break
    return heading["line"], max(heading["line"], end)


def navigation_entries(lines: list[str], file_path: Path) -> list[str]:
    """Render table links with their resolved section ranges or original targets."""
    headings = _headings(lines)
    by_slug = {heading["slug"]: index for index, heading in enumerate(headings)}
    entries: list[str] = []
    for _, first, second in _navigation_rows(lines):
        links = LINK.findall(second)
        for label, target in links:
            if target.startswith("#"):
                anchor = target[1:]
                if anchor not in by_slug:
                    entries.append(f"{first} -> unresolved #{anchor}")
                    continue
                index = by_slug[anchor]
                start, end = _section_range(index, headings, len(lines))
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
        if not target.is_file() or target.suffix != ".md" or target.stat().st_size < GUARD_MIN_BYTES:
            return None
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    lines = content.splitlines()
    if not any(line == "## Navigation map" for _, line in _fenced_lines(lines)):
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

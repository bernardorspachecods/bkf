"""Parse a document's `## Navigation map` table and check it against the document's sections."""

from __future__ import annotations

import re


MAP_HEADING = "## Navigation map"
WARNING_CODES = ("NAVIGATION_MAP_REVIEW", "NAVIGATION_MAP_STALE")
GUIDANCE = (
    "Navigation map: the first column of a row should say what the reader is looking for when that differs "
    "from the section title; when it would only repeat the title, write the title. Every level 2 section "
    "needs a row, and every link must point to an existing heading."
)
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
SEPARATOR = re.compile(r"^:?-{3,}:?$")


def split_cells(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]


def fenced_lines(lines: list[str]):
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


def headings(lines: list[str]) -> list[dict]:
    headings = []
    used: dict[str, int] = {}
    for number, line in fenced_lines(lines):
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


def navigation_rows(lines: list[str]) -> list[tuple[int, str, str]]:
    visible = list(fenced_lines(lines))
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
        table_lines.append((number, split_cells(stripped)))
    if len(table_lines) < 3:
        return []
    separator = table_lines[1][1]
    if len(separator) < 2 or not all(SEPARATOR.fullmatch(cell.replace(" ", "")) for cell in separator[:2]):
        return []
    for number, cells in table_lines[2:]:
        if len(cells) >= 2:
            rows.append((number, cells[0], cells[1]))
    return rows


def section_range(index: int, headings: list[dict], total_lines: int) -> tuple[int, int]:
    heading = headings[index]
    end = total_lines
    for following in headings[index + 1:]:
        if following["level"] <= heading["level"]:
            end = following["line"] - 1
            break
    return heading["line"], max(heading["line"], end)



def map_problems(body: str) -> tuple[bool, list[str]]:
    """Return whether the body has a navigation map and what is wrong with it."""
    lines = body.splitlines()
    if not any(line == MAP_HEADING for _, line in fenced_lines(lines)):
        return False, []
    rows = navigation_rows(lines)
    if not rows:
        return True, ["the navigation map has no table rows"]

    found = headings(lines)
    by_slug = {heading["slug"]: heading for heading in found}
    problems: list[str] = []
    mapped: set[int] = set()
    for _, _, second in rows:
        for _, target in LINK.findall(second):
            if not target.startswith("#"):
                continue
            heading = by_slug.get(target[1:])
            if heading is None:
                problems.append(f"the navigation map links {target}, which is not a heading")
            else:
                mapped.add(heading["line"])

    for index, heading in enumerate(found):
        if heading["level"] != 2 or f"## {heading['title']}" == MAP_HEADING:
            continue
        start, end = section_range(index, found, len(lines))
        if not any(start <= line <= end for line in mapped):
            problems.append(f"the navigation map does not cover the section \"{heading['title']}\" (line {start})")
    return True, problems

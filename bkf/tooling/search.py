"""Search tracked BKF document sections using a temporary FTS5 index."""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path


OUTPUT_LIMIT = 4000
PREVIEW_LENGTH = 200
STOPWORDS = frozenset(
    "a about above after again against all am an and any are aren't as at be "
    "because been before being below between both but by can't cannot could "
    "couldn't did didn't do does doesn't doing don't down during each few for "
    "from further had hadn't has hasn't have haven't having he he'd he'll he's "
    "her here here's hers herself him himself his how i i'd i'll i'm i've if "
    "in into is isn't it it's its itself just let's me more most mustn't my "
    "myself no nor not of off on once only or other ought our ours ourselves "
    "out over own same shan't she she'd she'll she's should shouldn't so some "
    "such than that that's the their theirs them themselves then there there's "
    "these they they'd they'll they're they've this those through to too under "
    "until up very was wasn't we we'd we'll we're we've were weren't what "
    "what's when when's where where's which while who who's whom why with "
    "won't would wouldn't you you'd you'll you're you've your yours yourself "
    "yourselves can could should would does did how will or also"
    .split()
)
WORD = re.compile(r"[^\W_]+", re.UNICODE)
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class Section:
    path: str
    heading: str
    description: str
    body: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf search", description=__doc__)
    parser.add_argument("query", nargs="+", help="question or topic to search for")
    parser.add_argument("--cwd", type=Path, help="directory in the bundle (defaults to current directory)")
    parser.add_argument("--limit", type=int, default=5, help="maximum number of hits (default: 5)")
    parser.add_argument("--debug", action="store_true", help="print a traceback when search fails")
    return parser


def _bundle_root(cwd: Path, is_bundle_root_map) -> Path | None:
    candidates = [
        directory
        for directory in cwd.parents
        if (directory / "MAP.md").is_file() and is_bundle_root_map(directory / "MAP.md")
    ]
    if cwd.is_dir() and (cwd / "MAP.md").is_file() and is_bundle_root_map(cwd / "MAP.md"):
        candidates.append(cwd)
    return min(candidates, key=lambda directory: len(directory.parts)) if candidates else None


def _sections(body: str, path: str, description: str) -> list[Section]:
    """Split Markdown into heading sections, ignoring headings inside fences."""
    lines = body.splitlines()
    heading_rows: list[tuple[int, int, str]] = []
    fence_char: str | None = None
    fence_length = 0
    for index, line in enumerate(lines):
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            char = marker[0]
            if fence_char is None:
                fence_char, fence_length = char, len(marker)
            elif char == fence_char and len(marker) >= fence_length:
                fence_char, fence_length = None, 0
            continue
        if fence_char is None:
            match = HEADING.match(line)
            if match:
                title = match.group(2).strip()
                if title:
                    heading_rows.append((index, len(match.group(1)), title))

    sections: list[Section] = []
    first_heading = next((title for _, level, title in heading_rows if level == 1), None)
    if heading_rows and heading_rows[0][0] > 0:
        prefix = "\n".join(lines[: heading_rows[0][0]]).strip()
        if prefix:
            sections.append(Section(path, first_heading or "(top)", description, prefix))
    elif not heading_rows:
        text = "\n".join(lines).strip()
        if text:
            sections.append(Section(path, "(top)", description, text))

    trail: list[tuple[int, str]] = []
    for offset, (line_index, level, title) in enumerate(heading_rows):
        trail = [(prior_level, prior) for prior_level, prior in trail if prior_level < level]
        trail.append((level, title))
        label = " > ".join(item for _, item in trail)
        next_line = heading_rows[offset + 1][0] if offset + 1 < len(heading_rows) else len(lines)
        text = "\n".join(lines[line_index + 1 : next_line]).strip()
        sections.append(Section(path, label, description, text))
    return sections


def _collect_sections(root: Path, find_bundles, is_bundle_root_map, in_nested_bundle) -> list[Section]:
    from bkf_common import BKFInputError, parse_markdown, tracking_state

    result: list[Section] = []
    for bundle in find_bundles(root):
        if any(part.startswith(".") for part in bundle.relative_to(root).parts):
            continue
        for directory, directories, filenames in os.walk(bundle):
            directory_path = Path(directory)
            directories[:] = sorted(
                name
                for name in directories
                if not name.startswith(".")
                and not (
                    (directory_path / name) != bundle
                    and ((directory_path / name) / "MAP.md").is_file()
                    and is_bundle_root_map((directory_path / name) / "MAP.md")
                )
            )
            for filename in sorted(filenames):
                path = directory_path / filename
                if path.suffix.lower() != ".md" or filename == "MAP.md":
                    continue
                if any(part.startswith(".") for part in path.relative_to(bundle).parts[:-1]):
                    continue
                if in_nested_bundle(bundle, path):
                    continue
                relative = "/" + path.relative_to(root).as_posix()
                try:
                    parsed = parse_markdown(path)
                    is_agents = filename == "AGENTS.md"
                    profile = parsed.frontmatter.get("bkf")
                    if not is_agents:
                        if isinstance(profile, str) and profile in {"feedback", "ideas"}:
                            continue
                        if not tracking_state(parsed.frontmatter, path=relative.lstrip("/")):
                            continue
                    description = parsed.frontmatter.get("description", "")
                    if not isinstance(description, str):
                        description = ""
                except BKFInputError as exc:
                    raise BKFInputError(f"{relative.lstrip('/')}: {exc}") from exc
                result.extend(_sections(parsed.body, relative, " ".join(description.split())))
    return result


def _query_terms(question: str) -> list[str]:
    return [word for word in WORD.findall(question.lower()) if word not in STOPWORDS]


def _search(sections: list[Section], terms: list[str], limit: int) -> list[tuple[Section, float]]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE sections USING fts5(path UNINDEXED, heading, description, body, tokenize='porter unicode61')"
        )
        connection.executemany(
            "INSERT INTO sections(path, heading, description, body) VALUES (?, ?, ?, ?)",
            ((section.path, section.heading, section.description, section.body) for section in sections),
        )
        query = " OR ".join(f'"{term}"' for term in terms)
        rows = connection.execute(
            "SELECT rowid, bm25(sections, 0, 20, 1, 1) AS rank "
            "FROM sections WHERE sections MATCH ? ORDER BY rank, path LIMIT ?",
            (query, limit),
        ).fetchall()
        return [(sections[rowid - 1], rank) for rowid, rank in rows]
    finally:
        connection.close()


def _render(hits: list[tuple[Section, float]]) -> str:
    blocks: list[str] = []
    used = 0
    for index, (section, _) in enumerate(hits, 1):
        preview = " ".join(section.body.split())
        if len(preview) > PREVIEW_LENGTH:
            preview = preview[:PREVIEW_LENGTH].rstrip() + "…"
        block = f"{index}  {section.path} § {section.heading}\n   {preview}"
        addition = len(block) + (1 if blocks else 0)
        if used + addition + 1 > OUTPUT_LIMIT:
            break
        blocks.append(block)
        used += addition
    return "\n".join(blocks) + ("\n" if blocks else "")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 1:
        print("bkf search: --limit must be at least 1", file=sys.stderr)
        return 1
    terms = _query_terms(" ".join(args.query))
    if not terms:
        print("query has no searchable words", file=sys.stdout)
        return 2

    try:
        from bkf_common import find_bundles, in_nested_bundle, is_bundle_root_map

        cwd = (args.cwd or Path.cwd()).resolve()
        root = _bundle_root(cwd, is_bundle_root_map)
        if root is None:
            raise ValueError(f"no BKF bundle contains {cwd}")
        sections = _collect_sections(root, find_bundles, is_bundle_root_map, in_nested_bundle)
        hits = _search(sections, terms, args.limit)
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        if not hits:
            print("no sections match")
            return 0
        sys.stdout.write(_render(hits))
        return 0
    except Exception as exc:
        print(f"bkf search: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

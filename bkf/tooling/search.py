"""Search tracked BKF document sections using a temporary FTS5 index."""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import traceback
from dataclasses import dataclass, replace
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
    title: str = ""
    tags: tuple[str, ...] = ()
    preview: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf search", description=__doc__)
    parser.add_argument("query", nargs="+", help="question or topic to search for")
    parser.add_argument("--cwd", type=Path, help="directory in the bundle (defaults to current directory)")
    parser.add_argument("--limit", type=int, default=5, help="maximum number of hits (default: 5)")
    parser.add_argument("--path", type=Path, help="only documents under this directory, or this file")
    parser.add_argument("--heading", help="only sections whose own heading equals this text (case-insensitive)")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="only documents carrying this tag; repeat to require several",
    )
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


def _sections(body: str, path: str, description: str, tags: tuple[str, ...] = ()) -> list[Section]:
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
            sections.append(Section(path, first_heading or "(top)", description, prefix, first_heading or "(top)", tags))
    elif not heading_rows:
        text = "\n".join(lines).strip()
        if text:
            sections.append(Section(path, "(top)", description, text, "(top)", tags))

    trail: list[tuple[int, str]] = []
    for offset, (line_index, level, title) in enumerate(heading_rows):
        trail = [(prior_level, prior) for prior_level, prior in trail if prior_level < level]
        trail.append((level, title))
        label = " > ".join(item for _, item in trail)
        next_line = heading_rows[offset + 1][0] if offset + 1 < len(heading_rows) else len(lines)
        text = "\n".join(lines[line_index + 1 : next_line]).strip()
        sections.append(Section(path, label, description, text, title, tags))
    return sections


def _vocabularies(root: Path, find_bundles) -> dict[Path, dict[str, list[str]]]:
    from bkf_common import load_tag_vocabulary

    result: dict[Path, dict[str, list[str]]] = {}
    for bundle in find_bundles(root):
        if any(part.startswith(".") for part in bundle.relative_to(root).parts):
            continue
        vocabulary = load_tag_vocabulary(bundle)
        if vocabulary is not None:
            result[bundle] = vocabulary
    return result


def _collect_sections(
    root: Path,
    find_bundles,
    is_bundle_root_map,
    in_nested_bundle,
    vocabularies: dict[Path, dict[str, list[str]]] | None = None,
    scope: Path | None = None,
    required_tags: list[str] | None = None,
) -> list[Section]:
    from bkf_common import BKFInputError, canonical_tag, parse_markdown, tracking_state

    vocabularies = vocabularies or {}
    result: list[Section] = []
    for bundle in find_bundles(root):
        if any(part.startswith(".") for part in bundle.relative_to(root).parts):
            continue
        required = _resolve_required_tags(required_tags or [], vocabularies.get(bundle), canonical_tag)
        for directory, directories, filenames in os.walk(bundle):
            directory_path = Path(directory)
            directories[:] = sorted(
                name
                for name in directories
                if not name.startswith(".")
                and not (directory_path / name / ".git").is_file()
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
                if scope is not None and not (path == scope or path.is_relative_to(scope)):
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
                    tags = parsed.frontmatter.get("tags")
                    tags = tuple(tag for tag in tags if isinstance(tag, str)) if isinstance(tags, list) else ()
                except BKFInputError as exc:
                    raise BKFInputError(f"{relative.lstrip('/')}: {exc}") from exc
                if required and not required <= {tag.casefold() for tag in tags}:
                    continue
                result.extend(_sections(parsed.body, relative, " ".join(description.split()), tags))
    return result


def _resolve_required_tags(tags: list[str], vocabulary: dict[str, list[str]] | None, canonical_tag) -> set[str]:
    """Fold the requested tags; with a vocabulary, a synonym resolves to its canonical tag."""
    resolved: set[str] = set()
    for tag in tags:
        canonical = canonical_tag(vocabulary, tag) if vocabulary else None
        resolved.add((canonical or tag).casefold())
    return resolved


def _query_terms(question: str) -> list[str]:
    return [word for word in WORD.findall(question.lower()) if word not in STOPWORDS]


def _expansions(question: str, vocabularies: dict[Path, dict[str, list[str]]]) -> list[str]:
    """Return the canonical tags and synonyms to add as phrases when the question names a tag or a synonym."""
    words = WORD.findall(question.lower())
    phrases: list[str] = []
    for vocabulary in vocabularies.values():
        for key, synonyms in vocabulary.items():
            names = [key, *synonyms]
            if not any(_contains_sequence(words, WORD.findall(name.lower())) for name in names):
                continue
            for name in names:
                phrase = " ".join(WORD.findall(name.lower()))
                if phrase and phrase not in phrases:
                    phrases.append(phrase)
    return phrases


def _contains_sequence(words: list[str], sequence: list[str]) -> bool:
    size = len(sequence)
    return size > 0 and any(words[index : index + size] == sequence for index in range(len(words) - size + 1))


def _search(
    sections: list[Section], terms: list[str], limit: int, phrases: list[str] | None = None
) -> list[tuple[Section, float]]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE sections USING fts5(path UNINDEXED, heading, description, body, tokenize='porter unicode61')"
        )
        # Tags sit in their own index: bm25 length normalization counts every column of a row,
        # so a tags column in `sections` would shift the ranking of queries that match no tag.
        connection.execute("CREATE VIRTUAL TABLE section_tags USING fts5(tags, tokenize='porter unicode61')")
        connection.executemany(
            "INSERT INTO sections(path, heading, description, body) VALUES (?, ?, ?, ?)",
            ((section.path, section.heading, section.description, section.body) for section in sections),
        )
        connection.executemany(
            "INSERT INTO section_tags(tags) VALUES (?)",
            ((" ".join(section.tags),) for section in sections),
        )
        query = " OR ".join([f'"{term}"' for term in terms] + [f'"{phrase}"' for phrase in phrases or []])
        ranks: dict[int, float] = {}
        for rowid, rank in connection.execute(
            "SELECT rowid, bm25(sections, 0, 20, 1, 1) FROM sections WHERE sections MATCH ?", (query,)
        ):
            ranks[rowid] = rank
        for rowid, rank in connection.execute(
            "SELECT rowid, bm25(section_tags) * 20 FROM section_tags WHERE section_tags MATCH ?", (query,)
        ):
            ranks[rowid] = ranks.get(rowid, 0.0) + rank
        ordered = sorted(ranks.items(), key=lambda item: (item[1], sections[item[0] - 1].path))
        return [
            (replace(sections[rowid - 1], preview=_preview(connection, rowid, query, sections[rowid - 1].body)), rank)
            for rowid, rank in ordered[:limit]
        ]
    finally:
        connection.close()


MARK_START = "\x02"
MARK_END = "\x03"
SNIPPET_TOKENS = 64


def _start_of(body: str) -> str:
    preview = " ".join(body.split())
    if len(preview) > PREVIEW_LENGTH:
        preview = preview[:PREVIEW_LENGTH].rstrip() + "…"
    return preview


def _preview(connection: sqlite3.Connection, rowid: int, query: str, body: str) -> str:
    """Return the passage of the body that matches the query, or the start of the body without a match."""
    for tokens in range(SNIPPET_TOKENS, 0, -1):
        row = connection.execute(
            "SELECT snippet(sections, 3, ?, ?, '…', ?) FROM sections WHERE sections MATCH ? AND rowid = ?",
            (MARK_START, MARK_END, tokens, query, rowid),
        ).fetchone()
        if row is None or MARK_START not in row[0]:
            return _start_of(body)
        text = " ".join(row[0].replace(MARK_START, "").replace(MARK_END, "").split())
        if len(text) <= PREVIEW_LENGTH:
            return text
    return text[: PREVIEW_LENGTH - 1].rstrip() + "…"


def _render(hits: list[tuple[Section, float]]) -> str:
    blocks: list[str] = []
    used = 0
    for index, (section, _) in enumerate(hits, 1):
        preview = section.preview or _start_of(section.body)
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
        scope = None
        if args.path is not None:
            scope = (args.path if args.path.is_absolute() else cwd / args.path).resolve()
            if not scope.is_relative_to(root):
                print(f"bkf search: --path is outside the bundle: {args.path}", file=sys.stderr)
                return 2
        vocabularies = _vocabularies(root, find_bundles)
        sections = _collect_sections(
            root, find_bundles, is_bundle_root_map, in_nested_bundle, vocabularies, scope, args.tag
        )
        if args.heading is not None:
            heading = args.heading.strip().casefold()
            sections = [section for section in sections if section.title.casefold() == heading]
        hits = _search(sections, terms, args.limit, _expansions(" ".join(args.query), vocabularies))
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

"""Search tracked BKF document sections with a persistent FTS5 index and memory fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import traceback
from collections.abc import Callable
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
INDEX_SCHEMA = 3
_CACHE_NOTICE: str | None = None


@dataclass(frozen=True)
class Section:
    path: str
    heading: str
    description: str
    body: str
    title: str = ""
    tags: tuple[str, ...] = ()
    preview: str = ""
    kind: str = "section"
    locator: dict | None = None
    start: int | None = None
    end: int | None = None
    document_title: str = ""
    context: str = ""


@dataclass(frozen=True)
class RankedPassage:
    section: Section
    score: float


@dataclass(frozen=True)
class DocumentHit:
    path: str
    title: str
    score: float
    passages: tuple[RankedPassage, ...]


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
    parser.add_argument("--json", action="store_true", help="print document hits as JSON")
    parser.add_argument("--full", action="store_true", help="show each matching passage in full")
    parser.add_argument("--passages", choices=("all", "sections", "text"), default="all",
                        help="passage kinds to search (default: all)")
    return parser


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
            sections.append(Section(
                path, first_heading or "(top)", description, prefix, first_heading or "(top)", tags,
                document_title=first_heading or "",
            ))
    elif not heading_rows:
        text = "\n".join(lines).strip()
        if text:
            sections.append(Section(path, "(top)", description, text, "(top)", tags, document_title=""))

    trail: list[tuple[int, str]] = []
    for offset, (line_index, level, title) in enumerate(heading_rows):
        trail = [(prior_level, prior) for prior_level, prior in trail if prior_level < level]
        trail.append((level, title))
        label = " > ".join(item for _, item in trail)
        next_line = heading_rows[offset + 1][0] if offset + 1 < len(heading_rows) else len(lines)
        text = "\n".join(lines[line_index + 1 : next_line]).strip()
        sections.append(Section(path, label, description, text, title, tags, document_title=first_heading or ""))
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
    on_document_error: Callable[[str], None] | None = None,
) -> list[Section]:
    from bkf_common import canonical_tag, is_root_nonmember
    from search_attached import load_search_config

    vocabularies = vocabularies or {}
    result: list[Section] = []
    for bundle in find_bundles(root):
        if any(part.startswith(".") for part in bundle.relative_to(root).parts):
            continue
        required = _resolve_required_tags(required_tags or [], vocabularies.get(bundle), canonical_tag)
        search_config = load_search_config(bundle)
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
                if in_nested_bundle(bundle, path) or is_root_nonmember(bundle, path):
                    continue
                if scope is not None and not (path == scope or path.is_relative_to(scope)):
                    continue
                _, document_sections = _collect_document_sections(
                    root, bundle, path, vocabularies, required, search_config, on_document_error,
                )
                result.extend(document_sections)
    return result


def _collect_document_sections(
    root: Path, bundle: Path, path: Path,
    vocabularies: dict[Path, dict[str, list[str]]], required_tags: set[str],
    search_config, on_document_error: Callable[[str], None] | None = None,
) -> tuple[bool, list[Section]]:
    """Parse one candidate document, preserving the collector's membership and passage rules."""
    from bkf_common import BKFInputError, parse_markdown, tracking_state
    from search_attached import attached_text_for, read_attached_text, text_passages

    relative = "/" + path.relative_to(root).as_posix()
    try:
        parsed = parse_markdown(path)
        profile = parsed.frontmatter.get("bkf")
        is_agents = path.name == "AGENTS.md"
        if not is_agents:
            if isinstance(profile, str) and profile in {"feedback", "ideas"}:
                return False, []
            if not tracking_state(parsed.frontmatter, path=relative.lstrip("/")):
                return False, []
        description = parsed.frontmatter.get("description", "")
        if not isinstance(description, str):
            description = ""
        tags_field = parsed.frontmatter.get("tags")
        tags = tuple(tag for tag in tags_field if isinstance(tag, str)) if isinstance(tags_field, list) else ()
    except BKFInputError as exc:
        if on_document_error is None:
            raise BKFInputError(f"{relative.lstrip('/')}: {exc}") from exc
        on_document_error(f"{path}: {exc}")
        return False, []

    if required_tags and not required_tags <= {tag.casefold() for tag in tags}:
        return True, []
    normalized_description = " ".join(description.split())
    sections = _sections(parsed.body, relative, normalized_description, tags)
    if search_config is None:
        return True, sections
    attached = attached_text_for(search_config, bundle, path)
    if attached is None:
        return True, sections
    sidecar_path, entry = attached
    document_title = sections[0].document_title if sections else ""
    context = ". ".join(part for part in (document_title, normalized_description) if part)
    for passage in text_passages(read_attached_text(sidecar_path), entry):
        label = passage.locator.get("label") if passage.locator else None
        heading = label if isinstance(label, str) else "(text)"
        sections.append(Section(
            relative, heading, normalized_description, passage.text, heading, tags,
            kind="text", locator=passage.locator, start=passage.start, end=passage.end,
            document_title=document_title, context=context,
        ))
    return True, sections


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
    sections: list[Section], terms: list[str], limit: int | None, phrases: list[str] | None = None,
    *, unique_paths: bool = False, include_previews: bool = True,
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
            ((section.path, section.heading, section.context if section.kind == "text" else section.description, section.body)
             for section in sections),
        )
        connection.executemany(
            "INSERT INTO section_tags(tags) VALUES (?)",
            ((" ".join(section.tags) if section.kind == "section" else "",) for section in sections),
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
        if unique_paths:
            best_by_path = {}
            for rowid, rank in ordered:
                best_by_path.setdefault(sections[rowid - 1].path, (rowid, rank))
            ordered = list(best_by_path.values())
        result = []
        for rowid, rank in (ordered if limit is None else ordered[:limit]):
            section = sections[rowid - 1]
            if include_previews:
                section = replace(section, preview=_preview(connection, rowid, query, section.body))
            result.append((section, rank))
        return result
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


def _cache_directory() -> Path:
    configured = os.environ.get("BKF_SEARCH_CACHE")
    if configured:
        return Path(configured).expanduser()
    return Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser() / "bkf" / "search"


def _candidate_documents(root: Path, find_bundles, is_bundle_root_map, in_nested_bundle):
    """Return possible member documents without parsing their frontmatter."""
    from bkf_common import is_root_nonmember

    for bundle in find_bundles(root):
        if any(part.startswith(".") for part in bundle.relative_to(root).parts):
            continue
        for directory, directories, filenames in os.walk(bundle):
            directory_path = Path(directory)
            directories[:] = sorted(
                name for name in directories
                if not name.startswith(".")
                and not (directory_path / name / ".git").is_file()
                and not ((directory_path / name) != bundle
                         and ((directory_path / name) / "MAP.md").is_file()
                         and is_bundle_root_map((directory_path / name) / "MAP.md"))
            )
            for filename in sorted(filenames):
                path = directory_path / filename
                if path.suffix.lower() != ".md" or filename == "MAP.md":
                    continue
                if any(part.startswith(".") for part in path.relative_to(bundle).parts[:-1]):
                    continue
                if in_nested_bundle(bundle, path) or is_root_nonmember(bundle, path):
                    continue
                yield bundle, path


def _stat(path: Path | None) -> tuple[int | None, int | None]:
    if path is None:
        return None, None
    try:
        info = path.stat()
    except FileNotFoundError:
        return None, None
    return info.st_mtime_ns, info.st_size


def _delete_document(connection: sqlite3.Connection, relative: str) -> None:
    ids = [row[0] for row in connection.execute("SELECT id FROM passages WHERE document_path = ?", (relative,))]
    for passage_id in ids:
        connection.execute("DELETE FROM sections WHERE rowid = ?", (passage_id,))
        connection.execute("DELETE FROM section_tags WHERE rowid = ?", (passage_id,))
    connection.execute("DELETE FROM passages WHERE document_path = ?", (relative,))


def _write_document(connection: sqlite3.Connection, relative: str, sections: list[Section]) -> None:
    _delete_document(connection, relative)
    for section in sections:
        cursor = connection.execute(
            "INSERT INTO passages(document_path, path, kind, heading, title, document_title, description, context, tags, locator, start, end, body) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (relative, section.path, section.kind, section.heading, section.title, section.document_title,
             section.description, section.context, json.dumps(section.tags),
             json.dumps(section.locator, ensure_ascii=False) if section.locator is not None else None,
             section.start, section.end, section.body),
        )
        passage_id = cursor.lastrowid
        indexed_description = section.context if section.kind == "text" else section.description
        connection.execute(
            "INSERT INTO sections(rowid, path, heading, description, body) VALUES (?, ?, ?, ?, ?)",
            (passage_id, section.path, section.heading, indexed_description, section.body),
        )
        connection.execute(
            "INSERT INTO section_tags(rowid, tags) VALUES (?, ?)",
            (passage_id, " ".join(section.tags) if section.kind == "section" else ""),
        )


def _open_index(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != INDEX_SCHEMA:
        connection.executescript("""
            DROP TABLE IF EXISTS sections;
            DROP TABLE IF EXISTS section_tags;
            DROP TABLE IF EXISTS passages;
            DROP TABLE IF EXISTS files;
            CREATE TABLE files (
                path TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL,
                sidecar_path TEXT, sidecar_mtime_ns INTEGER, sidecar_size INTEGER,
                config_sha256 TEXT, bundle_path TEXT NOT NULL, is_member INTEGER NOT NULL
            );
            CREATE TABLE passages (
                id INTEGER PRIMARY KEY, document_path TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL,
                heading TEXT NOT NULL, title TEXT NOT NULL, document_title TEXT NOT NULL,
                description TEXT NOT NULL, context TEXT NOT NULL, tags TEXT NOT NULL, locator TEXT,
                start INTEGER, end INTEGER, body TEXT NOT NULL
            );
            CREATE INDEX passages_document_path ON passages(document_path);
            CREATE VIRTUAL TABLE sections USING fts5(path UNINDEXED, heading, description, body, tokenize='porter unicode61');
            CREATE VIRTUAL TABLE section_tags USING fts5(tags, tokenize='porter unicode61');
        """)
        connection.execute(f"PRAGMA user_version = {INDEX_SCHEMA}")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS passage_vectors ("
        "model TEXT NOT NULL, text_sha256 TEXT NOT NULL, dimension INTEGER NOT NULL, vector BLOB NOT NULL, "
        "PRIMARY KEY(model, text_sha256))"
    )
    return connection


def _persistent_search(
    root: Path, question: str, terms: list[str], phrases: list[str], limit: int | None,
    scope: Path | None, heading: str | None, tags: list[str], vocabularies,
    *, unique_paths: bool = False, passages: str = "all", on_document_error=None,
    include_previews: bool = True,
) -> list[tuple[Section, float]] | None:
    """Refresh changed documents and search the persistent index; None requests memory fallback."""
    global _CACHE_NOTICE
    _CACHE_NOTICE = None
    from bkf_common import find_bundles, in_nested_bundle, is_bundle_root_map
    from search_attached import attached_text_for, load_search_config

    def fallback(reason: Exception):
        global _CACHE_NOTICE
        _CACHE_NOTICE = str(reason)
        return None

    cache_dir = _cache_directory()
    try:
        cache_inside_bundle = cache_dir.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError) as exc:
        return fallback(exc)
    if cache_inside_bundle:
        return fallback(OSError("cache directory is inside the bundle"))
    cache_path = cache_dir / (hashlib.sha256(str(root.resolve()).encode()).hexdigest() + ".sqlite3")

    for attempt in range(2):
        connection = None
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            connection = _open_index(cache_path)
            connection.create_function(
                "casefold", 1, lambda value: value.casefold() if isinstance(value, str) else value,
                deterministic=True,
            )
            connection.execute("BEGIN IMMEDIATE")
            bundles = list(find_bundles(root))
            configs = {bundle: load_search_config(bundle) for bundle in bundles}
            config_hashes = {}
            for bundle in bundles:
                config_path = bundle / "search.yaml"
                config_hashes[bundle] = hashlib.sha256(config_path.read_bytes()).hexdigest() if config_path.is_file() else None
            candidates: dict[str, tuple[Path, Path, int, int, Path | None, int | None, int | None, str | None]] = {}
            for bundle, path in _candidate_documents(root, find_bundles, is_bundle_root_map, in_nested_bundle):
                try:
                    info = path.stat()
                except FileNotFoundError:
                    continue
                attached = attached_text_for(configs.get(bundle), bundle, path) if configs.get(bundle) else None
                sidecar = attached[0] if attached else None
                sidecar_mtime, sidecar_size = _stat(sidecar)
                relative = path.relative_to(root).as_posix()
                candidates[relative] = (bundle, path, info.st_mtime_ns, info.st_size, sidecar,
                                        sidecar_mtime, sidecar_size, config_hashes.get(bundle))
            existing = {row[0]: row[1:] for row in connection.execute(
                "SELECT path, mtime_ns, size, sidecar_path, sidecar_mtime_ns, sidecar_size, config_sha256, bundle_path, is_member FROM files"
            )}
            for vanished in existing.keys() - candidates.keys():
                _delete_document(connection, vanished)
                connection.execute("DELETE FROM files WHERE path = ?", (vanished,))
            for relative, candidate in candidates.items():
                bundle, path, mtime_ns, size, sidecar, sidecar_mtime, sidecar_size, config_hash = candidate
                sidecar_name = sidecar.relative_to(bundle).as_posix() if sidecar else None
                current = (mtime_ns, size, sidecar_name, sidecar_mtime, sidecar_size, config_hash)
                bundle_relative = bundle.relative_to(root).as_posix() or "."
                saved = existing.get(relative, ())
                if saved[:6] == current and len(saved) >= 7 and saved[6] == bundle_relative:
                    continue
                errors = []
                def report_document_error(message):
                    errors.append(message)
                    if on_document_error is not None:
                        on_document_error(message)
                is_member, found = _collect_document_sections(
                    root, bundle, path, vocabularies, set(), configs.get(bundle),
                    report_document_error if on_document_error is not None else None,
                )
                if errors:
                    _delete_document(connection, relative)
                    connection.execute("DELETE FROM files WHERE path = ?", (relative,))
                    continue
                _delete_document(connection, relative)
                connection.execute("DELETE FROM files WHERE path = ?", (relative,))
                if is_member:
                    _write_document(connection, relative, found)
                connection.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (relative, *current, bundle_relative, int(is_member)))
            connection.commit()

            query = " OR ".join([f'"{term}"' for term in terms] + [f'"{phrase}"' for phrase in phrases])
            conditions: list[str] = []
            params: list[object] = [query, query]
            if scope is not None and scope.resolve() != root.resolve():
                scoped = "/" + scope.relative_to(root).as_posix()
                conditions.append("(p.path = ? OR p.path LIKE ? ESCAPE '\\')")
                escaped = scoped.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                params.extend((scoped, escaped.rstrip("/") + "/%"))
            if heading is not None:
                conditions.append("(p.kind = 'section' AND casefold(p.title) = ?)")
                params.append(heading.strip().casefold())
            if passages != "all":
                conditions.append("p.kind = ?")
                params.append("section" if passages == "sections" else "text")
            if tags:
                from bkf_common import canonical_tag
                for tag in tags:
                    alternatives = []
                    for bundle in bundles:
                        vocabulary = vocabularies.get(bundle)
                        canonical = canonical_tag(vocabulary, tag) if vocabulary else None
                        resolved = (canonical or tag).casefold()
                        bundle_relative = bundle.relative_to(root).as_posix() or "."
                        alternatives.append(
                            "(p.document_path IN (SELECT path FROM files WHERE bundle_path = ?) AND "
                            "EXISTS (SELECT 1 FROM json_each(p.tags) WHERE lower(value) = ?))"
                        )
                        params.extend((bundle_relative, resolved))
                    if alternatives:
                        conditions.append("(" + " OR ".join(alternatives) + ")")
                    else:
                        conditions.append("0")
            where = " AND ".join(conditions)
            sql_filter = f" AND {where}" if where else ""
            ranks = {}
            for passage_id, rank in connection.execute(
                "SELECT s.rowid, bm25(sections, 0, 20, 1, 1) FROM sections s JOIN passages p ON p.id=s.rowid "
                "WHERE sections MATCH ?" + sql_filter, params[:1] + params[2:]
            ):
                ranks[passage_id] = rank
            for passage_id, rank in connection.execute(
                "SELECT t.rowid, bm25(section_tags) * 20 FROM section_tags t JOIN passages p ON p.id=t.rowid "
                "WHERE section_tags MATCH ?" + sql_filter, params[:1] + params[2:]
            ):
                ranks[passage_id] = ranks.get(passage_id, 0.0) + rank
            passage_ids = list(ranks)
            if passage_ids:
                connection.execute("CREATE TEMP TABLE matched_passages (id INTEGER PRIMARY KEY)")
                connection.executemany(
                    "INSERT INTO matched_passages(id) VALUES (?)", ((passage_id,) for passage_id in passage_ids),
                )
                rows = {
                    row[0]: row[1:]
                    for row in connection.execute(
                        "SELECT p.id, p.path, p.kind, p.heading, p.title, p.document_title, p.description, "
                        "p.context, p.tags, p.locator, p.start, p.end, p.body "
                        "FROM passages p JOIN matched_passages m ON m.id = p.id"
                    )
                }
            else:
                rows = {}
            ordered = sorted(ranks.items(), key=lambda item: (item[1], rows[item[0]][0]))
            if unique_paths:
                selected = {}
                for passage_id, rank in ordered:
                    selected.setdefault(rows[passage_id][0], (passage_id, rank))
                ordered = list(selected.values())
            result = []
            for passage_id, rank in (ordered if limit is None else ordered[:limit]):
                (_, path, kind, heading_value, title, document_title, description, context, tags_json,
                 locator_json, start, end, body) = (passage_id, *rows[passage_id])
                section = Section(path, heading_value, description, body, title, tuple(json.loads(tags_json)),
                                  kind=kind, locator=json.loads(locator_json) if locator_json else None,
                                  start=start, end=end, document_title=document_title, context=context)
                if include_previews:
                    section = replace(section, preview=_preview(connection, passage_id, query, body))
                result.append((section, rank))
            return result
        except (sqlite3.DatabaseError, OSError) as exc:
            if connection is not None:
                try:
                    connection.rollback()
                    connection.close()
                except sqlite3.Error:
                    pass
            corrupt = isinstance(exc, sqlite3.DatabaseError) and any(
                marker in str(exc).casefold()
                for marker in ("not a database", "malformed", "encrypted", "file is not a database")
            )
            if corrupt and attempt == 0 and cache_path.exists():
                try:
                    cache_path.unlink()
                    Path(str(cache_path) + "-wal").unlink(missing_ok=True)
                    Path(str(cache_path) + "-shm").unlink(missing_ok=True)
                    continue
                except OSError:
                    pass
            return fallback(exc)
        except Exception:
            if connection is not None:
                try:
                    connection.rollback()
                    connection.close()
                except sqlite3.Error:
                    pass
            raise
        finally:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
    return fallback(OSError("cache unavailable"))


def rank_passages(
    root: Path, question: str, *, scope: Path | None = None, heading: str | None = None,
    tags: list[str] | None = None, passages: str = "all", depth: int | None = None,
    on_document_error=None,
) -> list[RankedPassage]:
    """Every matching passage (or the best depth), best first, filters applied, synonym expansion included."""
    if passages not in {"all", "sections", "text"}:
        raise ValueError("passages must be all, sections, or text")
    terms = _query_terms(question)
    if not terms:
        return []
    from bkf_common import find_bundles, in_nested_bundle, is_bundle_root_map
    vocabularies = _vocabularies(root, find_bundles)
    phrases = _expansions(question, vocabularies)
    indexed = _persistent_search(root, question, terms, phrases, None, scope, heading, tags or [],
                                 vocabularies, passages=passages, on_document_error=on_document_error,
                                 include_previews=False)
    if indexed is None:
        sections = _collect_sections(root, find_bundles, is_bundle_root_map, in_nested_bundle,
                                     vocabularies, scope, tags, on_document_error)
        if passages != "all":
            kind = "section" if passages == "sections" else "text"
            sections = [section for section in sections if section.kind == kind]
        if heading is not None:
            wanted = heading.strip().casefold()
            sections = [s for s in sections if s.kind == "section" and s.title.casefold() == wanted]
        indexed = _search(sections, terms, None, phrases, include_previews=False)
    ranked = [RankedPassage(section, -score) for section, score in indexed]
    return ranked if depth is None else ranked[:depth]


def _embedder(model: str):
    """Create fastembed lazily, keeping model files beside the search cache."""
    from bkf_common import BKFInputError

    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise BKFInputError(
            "vector search requires fastembed; install it with: "
            "uv tool install --editable ./bkf/tooling --with fastembed --reinstall"
        ) from exc
    return TextEmbedding(model_name=model, cache_dir=str(_cache_directory() / "models"))


def _embedded_text(section: Section) -> str:
    if section.kind == "text":
        return section.context[:300] + "\n" + section.body
    return section.heading + "\n" + section.body


def _normalise(vector) -> list[float]:
    values = [float(value) for value in vector]
    norm = sum(value * value for value in values) ** 0.5
    if not values or not norm:
        raise ValueError("embedder returned an empty or zero vector")
    return [value / norm for value in values]


def _vector_similarity(query: list[float], vectors: list[list[float]]) -> list[float]:
    try:
        import numpy as np
    except ImportError:
        return [sum(left * right for left, right in zip(query, vector)) for vector in vectors]
    query_array = np.asarray(query, dtype=np.float64)
    matrix = np.asarray(vectors, dtype=np.float64)
    return [float(score) for score in matrix @ query_array]


def _vector_cache(root: Path) -> sqlite3.Connection | None:
    cache_dir = _cache_directory()
    try:
        if cache_dir.resolve().is_relative_to(root.resolve()):
            return None
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / (hashlib.sha256(str(root.resolve()).encode()).hexdigest() + ".sqlite3")
        connection = _open_index(path)
        return connection
    except (OSError, sqlite3.Error):
        return None


def vector_rank(
    root: Path, question: str, *, scope: Path | None = None, heading: str | None = None,
    tags: list[str] | None = None, passages: str = "all", depth: int | None = None,
    on_document_error=None,
) -> list[RankedPassage]:
    """Rank filtered passages by cosine similarity, computing and caching missing vectors."""
    if passages not in {"all", "sections", "text"}:
        raise ValueError("passages must be all, sections, or text")
    from bkf_common import BKFInputError, find_bundles, in_nested_bundle, is_bundle_root_map
    from search_attached import embeddings_config

    bundles = list(find_bundles(root))
    if not bundles:
        raise BKFInputError(f"no BKF bundle contains {root}")
    # The caller supplies the outermost bundle root; its config owns the model.
    config = embeddings_config(root)
    embedder = _embedder(config.model)
    vocabularies = _vocabularies(root, find_bundles)
    sections = _collect_sections(root, find_bundles, is_bundle_root_map, in_nested_bundle,
                                 vocabularies, scope, tags, on_document_error)
    if passages != "all":
        kind = "section" if passages == "sections" else "text"
        sections = [section for section in sections if section.kind == kind]
    if heading is not None:
        wanted = heading.strip().casefold()
        sections = [section for section in sections if section.kind == "section" and section.title.casefold() == wanted]
    if not sections:
        return []

    embedded = [_embedded_text(section) for section in sections]
    keys = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in embedded]
    connection = _vector_cache(root)
    import array
    cached: dict[str, list[float]] = {}
    if connection is not None:
        try:
            cached = {
                key: list(array.array("f", blob))
                for key, blob in connection.execute(
                    "SELECT text_sha256, vector FROM passage_vectors WHERE model = ?", (config.model,)
                )
            }
        except sqlite3.Error:
            connection.close()
            connection = None
            cached = {}
    missing_by_key = {key: value for key, value in zip(keys, embedded) if key not in cached}
    missing = list(missing_by_key.items())
    try:
        if len(missing) > 200:
            print(f"embedding {len(missing)} passages…", file=sys.stderr)
        for start in range(0, len(missing), 128):
            batch = missing[start:start + 128]
            vectors = [_normalise(vector) for vector in embedder.embed([text for _, text in batch])]
            if len(vectors) != len(batch):
                raise ValueError("embedder returned the wrong number of passage vectors")
            cached.update((key, vector) for (key, _), vector in zip(batch, vectors))
            if connection is not None:
                connection.executemany(
                    "INSERT OR REPLACE INTO passage_vectors(model, text_sha256, dimension, vector) VALUES (?, ?, ?, ?)",
                    ((config.model, key, len(vector), array.array("f", vector).tobytes())
                     for (key, _), vector in zip(batch, vectors)),
                )
                connection.commit()
        query_rows = list(embedder.query_embed([question]))
        if len(query_rows) != 1:
            raise ValueError("embedder returned the wrong number of query vectors")
        query_vector = list(array.array("f", _normalise(query_rows[0])))
        vectors = [cached[key] for key in keys]
        if any(len(vector) != len(query_vector) for vector in vectors):
            raise ValueError("embedder returned vectors with inconsistent dimensions")
        scores = _vector_similarity(query_vector, vectors)
        ranked = [RankedPassage(section, score) for section, score in zip(sections, scores)]
        ranked.sort(key=lambda hit: (-hit.score, hit.section.path, hit.section.heading, hit.section.body[:80]))
        return ranked if depth is None else ranked[:depth]
    finally:
        if connection is not None:
            connection.close()


def group_documents(ranked: list[RankedPassage], *, limit: int, per_document: int = 2) -> list[DocumentHit]:
    """Documents in order of their first passage in ranked, each with its first per_document passages."""
    grouped: dict[str, list[RankedPassage]] = {}
    for hit in ranked:
        grouped.setdefault(hit.section.path, []).append(hit)
    return [DocumentHit(path, rows[0].section.document_title, rows[0].score, tuple(rows[:per_document]))
            for path, rows in list(grouped.items())[:limit]]


def _preview_sections(
    sections: list[Section], question: str, phrases: list[str] | None = None,
) -> list[Section]:
    """Compute previews for an already selected set of passages."""
    if not sections:
        return []
    terms = _query_terms(question)
    if not terms:
        return [replace(section, preview=_start_of(section.body)) for section in sections]
    query = " OR ".join([f'"{term}"' for term in terms] + [f'"{phrase}"' for phrase in phrases or []])
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE sections USING fts5(path UNINDEXED, heading, description, body, "
            "tokenize='porter unicode61')"
        )
        connection.executemany(
            "INSERT INTO sections(path, heading, description, body) VALUES (?, ?, ?, ?)",
            ((section.path, section.heading,
              section.context if section.kind == "text" else section.description, section.body)
             for section in sections),
        )
        return [replace(section, preview=_preview(connection, index, query, section.body))
                for index, section in enumerate(sections, 1)]
    finally:
        connection.close()


def prepare_previews(
    hits: list[DocumentHit], question: str, *, phrases: list[str] | None = None,
) -> list[DocumentHit]:
    """Fill previews after document grouping, so only output passages incur snippet work."""
    flattened = [passage.section for hit in hits for passage in hit.passages]
    previewed = iter(_preview_sections(flattened, question, phrases))
    return [replace(hit, passages=tuple(
        replace(passage, section=next(previewed)) for passage in hit.passages
    )) for hit in hits]


def _full_text(section: Section) -> str:
    return " ".join(section.body.split())


def _render(hits: list[DocumentHit], *, full: bool = False) -> str:
    blocks: list[str] = []
    used = 0
    for index, hit in enumerate(hits, 1):
        title = f"  {hit.title}" if hit.title else ""
        lines = [f"{index}  {hit.path}{title}"]
        for ranked in hit.passages:
            section = ranked.section
            label = (f"§ {section.heading}" if section.kind == "section"
                     else ((section.locator or {}).get("label") or "(text)"))
            preview = _full_text(section) if full else (section.preview or _start_of(section.body))
            lines.append(f"   {label}  {preview}")
        block = "\n".join(lines)
        addition = len(block) + (1 if blocks else 0)
        if used + addition + 1 > OUTPUT_LIMIT:
            break
        blocks.append(block)
        used += addition
    return "\n".join(blocks) + ("\n" if blocks else "")


def search_bundle(
    root: Path, question: str, *, limit: int, scope: Path | None = None, heading: str | None = None,
    tags: list[str] | None = None, unique_paths: bool = False,
    on_document_error: Callable[[str], None] | None = None,
) -> list[tuple[Section, float]]:
    if limit < 1:
        return []
    ranked = rank_passages(root, question, scope=scope, heading=heading, tags=tags,
                           on_document_error=on_document_error)
    selected: list[RankedPassage] = []
    seen: set[str] = set()
    for hit in ranked:
        if unique_paths and hit.section.path in seen:
            continue
        seen.add(hit.section.path)
        selected.append(hit)
        if len(selected) >= limit:
            break
    from bkf_common import find_bundles
    phrases = _expansions(question, _vocabularies(root, find_bundles))
    sections = _preview_sections([hit.section for hit in selected], question, phrases)
    return [(section, -hit.score) for section, hit in zip(sections, selected)]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 1:
        print("bkf search: --limit must be at least 1", file=sys.stderr)
        return 1
    question = " ".join(args.query)
    if not _query_terms(question):
        print("query has no searchable words", file=sys.stdout)
        return 2

    try:
        from bkf_common import find_outermost_bundle_root

        cwd = (args.cwd or Path.cwd()).resolve()
        root = find_outermost_bundle_root(cwd)
        if root is None:
            raise ValueError(f"no BKF bundle contains {cwd}")
        scope = None
        if args.path is not None:
            scope = (args.path if args.path.is_absolute() else cwd / args.path).resolve()
            if not scope.is_relative_to(root):
                print(f"bkf search: --path is outside the bundle: {args.path}", file=sys.stderr)
                return 2
        ranked = rank_passages(root, question, scope=scope, heading=args.heading, tags=args.tag,
                               passages=args.passages)
        hits = group_documents(ranked, limit=args.limit)
        if not args.full:
            from bkf_common import find_bundles
            phrases = _expansions(question, _vocabularies(root, find_bundles))
            hits = prepare_previews(hits, question, phrases=phrases)
        if args.debug and _CACHE_NOTICE:
            print(f"bkf search: cache unavailable; using memory ({_CACHE_NOTICE})", file=sys.stderr)
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        if not hits:
            print("[]" if args.json else "no sections match")
            return 0
        if args.json:
            payload = []
            for hit in hits:
                payload.append({
                    "path": hit.path, "title": hit.title, "score": hit.score,
                    "passages": [{
                        "kind": row.section.kind,
                        "heading": row.section.heading if row.section.kind == "section" else None,
                        "locator": row.section.locator,
                        "start": row.section.start, "end": row.section.end,
                        "preview": _full_text(row.section) if args.full else (row.section.preview or _start_of(row.section.body)),
                        "score": row.score,
                    } for row in hit.passages],
                })
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(_render(hits, full=args.full))
        return 0
    except Exception as exc:
        print(f"bkf search: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

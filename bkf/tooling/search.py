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
INDEX_SCHEMA = 2
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
    sections: list[Section], terms: list[str], limit: int, phrases: list[str] | None = None,
    *, unique_paths: bool = False,
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
    return connection


def _persistent_search(
    root: Path, question: str, terms: list[str], phrases: list[str], limit: int,
    scope: Path | None, heading: str | None, tags: list[str], vocabularies,
    *, unique_paths: bool = False, on_document_error=None,
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
            base = "SELECT path, kind, heading, title, document_title, description, context, tags, locator, start, end, body FROM passages WHERE id = ?"
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
            rows = {passage_id: connection.execute(base, (passage_id,)).fetchone() for passage_id in ranks}
            ordered = sorted(ranks.items(), key=lambda item: (item[1], rows[item[0]][0]))
            if unique_paths:
                selected = {}
                for passage_id, rank in ordered:
                    selected.setdefault(rows[passage_id][0], (passage_id, rank))
                ordered = list(selected.values())
            result = []
            for passage_id, rank in ordered[:limit]:
                (_, path, kind, heading_value, title, document_title, description, context, tags_json,
                 locator_json, start, end, body) = (passage_id, *rows[passage_id])
                section = Section(path, heading_value, description, body, title, tuple(json.loads(tags_json)),
                                  kind=kind, locator=json.loads(locator_json) if locator_json else None,
                                  start=start, end=end, document_title=document_title, context=context)
                result.append((replace(section, preview=_preview(connection, passage_id, query, body)), rank))
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


def search_bundle(
    root: Path, question: str, *, limit: int, scope: Path | None = None, heading: str | None = None,
    tags: list[str] | None = None, unique_paths: bool = False,
    on_document_error: Callable[[str], None] | None = None,
) -> list[tuple[Section, float]]:
    from bkf_common import find_bundles, in_nested_bundle, is_bundle_root_map

    terms = _query_terms(question)
    if not terms:
        return []
    vocabularies = _vocabularies(root, find_bundles)
    indexed = _persistent_search(
        root, question, terms, _expansions(question, vocabularies), limit, scope, heading, tags or [],
        vocabularies, unique_paths=unique_paths, on_document_error=on_document_error,
    )
    if indexed is not None:
        return indexed
    sections = _collect_sections(
        root, find_bundles, is_bundle_root_map, in_nested_bundle, vocabularies, scope, tags, on_document_error,
    )
    if heading is not None:
        heading = heading.strip().casefold()
        sections = [section for section in sections if section.kind == "section" and section.title.casefold() == heading]
    return _search(sections, terms, limit, _expansions(question, vocabularies), unique_paths=unique_paths)


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
        hits = search_bundle(
            root, question, limit=args.limit, scope=scope, heading=args.heading, tags=args.tag,
        )
        if args.debug and _CACHE_NOTICE:
            print(f"bkf search: cache unavailable; using memory ({_CACHE_NOTICE})", file=sys.stderr)
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

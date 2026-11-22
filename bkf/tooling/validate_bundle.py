#!/usr/bin/env python3
"""Check BKF bundle structure, metadata, maps, and links."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from markdown_it import MarkdownIt
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bkf_common import (
    BKFInputError,
    MAP_NAME,
    ParsedMarkdown,
    README_NAME,
    TAG_VOCABULARY_NAME,
    body_size,
    canonical_tag,
    discover_maps,
    find_bundles,
    in_linked_worktree,
    inventory_entries,
    is_bundle_root_map,
    is_notes_file,
    load_tag_vocabulary,
    needs_navigation_map,
    nested_bundle_roots,
    outermost_bundle_root,
    parse_markdown,
    render_inventory_entry,
    tracking_state,
)
from navigation_map import GUIDANCE, WARNING_CODES, map_problems


SUPPORTED_VERSION = (0, 2)
VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")
DOCUMENT_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
REPO_LIBRARY_PATH_RE = re.compile(
    r"/"
    + "".join(f"(?:{re.escape(char)}|%{ord(char):02x})" for char in "repo-library")
    + r"(?:/|%2f)",
    re.IGNORECASE,
)
MARKDOWN = MarkdownIt("commonmark")
START_MARKER = "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->"
END_MARKER = "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->"
PROFILE_FIELDS = {
    "feedback": {"bkf", "description"},
    "ideas": {"bkf", "description"},
}
GENERIC_FIELDS = {"bkf", "description", "tags"}
EXT_SCHEMA_NAME = "ext-schema.yaml"
OPTIONAL_FIELDS = {
    "generic": {"ext"},
}
DESCRIPTION_REVIEW_RE = re.compile(r"\b(?:open\s+when|use\s+when)\b", re.IGNORECASE)
LOG_PROFILES = frozenset({"feedback", "ideas"})
AGENT_INSTRUCTION_NAMES = frozenset({"AGENTS.md", "CLAUDE.md"})
AGENT_INSTRUCTION_WORD_LIMIT = 250
MAP_SIZE_LIMIT = 4


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


class Validator:
    def __init__(self, root: Path, link_root: Path | None = None) -> None:
        self.root = root
        # Every link resolves from the outermost bundle root, so a nested bundle's links match its enclosing bundle's.
        self.link_root = link_root if link_root is not None else outermost_bundle_root(root)
        self.findings: list[Finding] = []
        self.member_documents: dict[Path, ParsedMarkdown] = {}
        self.parsed_markdown_files: dict[Path, ParsedMarkdown] = {}
        self.markdown_files: list[Path] = []
        self._ext_validator: Draft202012Validator | None = None
        self._ext_schema_reported = False
        self._tag_vocabulary: dict[str, list[str]] | None = None
        self._bundle_root_folders: dict[Path, bool] = {}

    def add(self, severity: str, code: str, path: Path, message: str) -> None:
        try:
            label = path.relative_to(self.root).as_posix()
        except ValueError:
            label = str(path)
        self.findings.append(Finding(severity, code, label, message))

    def error(self, code: str, path: Path, message: str) -> None:
        self.add("ERROR", code, path, message)

    def warning(self, code: str, path: Path, message: str) -> None:
        self.add("WARNING", code, path, message)

    def validate(self) -> None:
        root_map = self.root / MAP_NAME
        if not root_map.is_file():
            self.error("ROOT_MAP_MISSING", root_map, "bundle root must contain MAP.md")
            return

        self.markdown_files = self._discover_markdown_files()
        maps = discover_maps(self.root)
        version = self._validate_root_map(root_map)
        self._check_version(version, root_map)

        self._load_tag_vocabulary()
        self._validate_documents()
        self._validate_agent_instructions_size()
        self._validate_notes_files()
        for map_path in maps:
            self._validate_map(map_path, root_map)
            self._validate_map_size(map_path, root_map)

        for path, parsed in list(self.member_documents.items()):
            self._validate_links(path, parsed.body)

        for map_path in maps:
            try:
                body = self._map_body(map_path, root_map)
            except BKFInputError:
                continue
            self._validate_links(map_path, body)

        self._validate_repo_library_links()

    def _load_tag_vocabulary(self) -> None:
        try:
            self._tag_vocabulary = load_tag_vocabulary(self.root)
        except BKFInputError as exc:
            self.error("TAG_VOCABULARY_INVALID", self.root / TAG_VOCABULARY_NAME, str(exc))

    def _validate_tag_vocabulary(self, path: Path, tags: list[str]) -> None:
        vocabulary = self._tag_vocabulary
        if vocabulary is None:
            return
        for tag in tags:
            if tag in vocabulary:
                continue
            canonical = canonical_tag(vocabulary, tag)
            if canonical is not None:
                self.error("TAG_UNKNOWN", path, f"tag `{tag}` is a synonym; use `{canonical}`")
                continue
            close = difflib.get_close_matches(tag, list(vocabulary), n=3)
            hint = f"; closest tags: {', '.join(f'`{key}`' for key in close)}" if close else ""
            self.error("TAG_UNKNOWN", path, f"tag `{tag}` is not in {TAG_VOCABULARY_NAME}{hint}")

    def _validate_repo_library_links(self) -> None:
        repo_library = self.root / "repo-library"
        if not repo_library.is_dir():
            return

        entries = [
            path
            for path in repo_library.rglob("*")
            if path.is_file() and path.suffix.lower() == ".md" and path.name != MAP_NAME
        ]
        if not entries:
            return
        entry_targets = {entry.resolve() for entry in entries}

        linked_entries: set[Path] = set()
        for source in self.markdown_files:
            if source.is_relative_to(repo_library):
                continue
            parsed = self.parsed_markdown_files.get(source)
            if parsed is None:
                try:
                    parsed = parse_markdown(source)
                except BKFInputError:
                    continue
            markdown = parsed.body
            if REPO_LIBRARY_PATH_RE.search(markdown) is None:
                continue
            for destination in self._link_destinations(markdown):
                try:
                    parsed = urlsplit(destination)
                    if (
                        parsed.scheme
                        or parsed.netloc
                        or not parsed.path.startswith("/")
                        or destination.startswith("//")
                        or any(character.isspace() for character in destination)
                        or PERCENT_ESCAPE_RE.search(parsed.path)
                        or any(character.isspace() or ord(character) > 127 for character in parsed.path)
                    ):
                        continue
                    decoded = unquote(parsed.path, encoding="utf-8", errors="strict")
                except (ValueError, UnicodeDecodeError):
                    continue
                target = (self.link_root / decoded.lstrip("/")).resolve()
                if target.is_relative_to(self.link_root) and target in entry_targets:
                    linked_entries.add(target)

        for entry in sorted(entries, key=lambda path: path.relative_to(self.root).as_posix()):
            if entry.resolve() in linked_entries:
                continue
            self.warning(
                "REPO_LIBRARY_ENTRY_UNLINKED",
                entry,
                "No document outside repo-library/ links to this entry, so nothing sends an agent to it. "
                "Link it from the document where this activity starts, or from a task route in the nearest map.",
            )

    def _parse(self, path: Path):
        try:
            return parse_markdown(path)
        except BKFInputError as exc:
            self.error("FRONTMATTER_INVALID", path, str(exc))
            return None

    def _validate_root_map(self, path: Path) -> str | None:
        parsed = self._parse(path)
        if parsed is None:
            return None
        self.parsed_markdown_files[path] = parsed
        fields = set(parsed.frontmatter)
        if not {"bkf_version"} <= fields or not fields <= {"bkf_version", "description"}:
            self.error(
                "ROOT_MAP_FRONTMATTER",
                path,
                "root MAP.md frontmatter must contain bkf_version and may contain description only",
            )
        description = parsed.frontmatter.get("description")
        if "description" in parsed.frontmatter and (
            not isinstance(description, str) or not description.strip()
        ):
            self.error(
                "MAP_DESCRIPTION_MISSING",
                path,
                "map needs a non-empty string `description`",
            )
        version = parsed.frontmatter.get("bkf_version")
        if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
            self.error(
                "VERSION_INVALID",
                path,
                "bkf_version must be a quoted <major>.<minor> string",
            )
            return None
        return version

    def _check_version(self, version: str | None, path: Path) -> None:
        if version is None:
            return
        match = VERSION_RE.fullmatch(version)
        assert match is not None
        declared = (int(match.group(1)), int(match.group(2)))
        if declared == SUPPORTED_VERSION:
            return

        self.warning(
            "VERSION_UNSUPPORTED",
            path,
            f"validator supports {SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]}, while this bundle declares {version}; checks are best-effort",
        )
        if declared[0] < SUPPORTED_VERSION[0]:
            self.warning(
                "MIGRATION_RECOMMENDED",
                path,
                "run `bkf updates <bundle-root>` on this bundle, then migrate it to the supported major version 0",
            )
        elif declared[0] == SUPPORTED_VERSION[0] and declared[1] < SUPPORTED_VERSION[1]:
            self.warning(
                "MINOR_MIGRATION_RECOMMENDED",
                path,
                f"run `bkf updates <bundle-root>` on this bundle, then migrate it to the supported version {SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]} with `bkf upgrade <bundle-root>`",
            )
        elif declared[0] > SUPPORTED_VERSION[0]:
            self.warning(
                "VALIDATOR_UPDATE_MAY_BE_NEEDED",
                path,
                "the validator may need an update for this newer major version",
            )
        elif declared[1] > SUPPORTED_VERSION[1]:
            self.warning(
                "VALIDATOR_UPDATE_RECOMMENDED",
                path,
                "update the validator to check all rules in this newer minor version",
            )

    def _map_body(self, path: Path, root_map: Path) -> str:
        return parse_markdown(path).body

    def _section_headings(self, body: str) -> list[tuple[str, int, int]]:
        tokens = MARKDOWN.parse(body)
        headings: list[tuple[str, int, int]] = []
        for index, token in enumerate(tokens):
            if token.type != "heading_open" or token.tag != "h2" or not token.map:
                continue
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            title = inline.content.strip() if inline and inline.type == "inline" else ""
            headings.append((title, token.map[0], token.map[1]))
        return headings

    def _validate_map(self, path: Path, root_map: Path) -> None:
        try:
            parsed = parse_markdown(path)
            body = self._map_body(path, root_map)
        except (BKFInputError, OSError, UnicodeError) as exc:
            self.error("MAP_INVALID", path, str(exc))
            return
        self.parsed_markdown_files[path] = parsed

        if path != root_map:
            if set(parsed.frontmatter) != {"description"}:
                self.error(
                    "MAP_FRONTMATTER",
                    path,
                    "nested MAP.md frontmatter must contain only description",
                )
            description = parsed.frontmatter.get("description")
            if not isinstance(description, str) or not description.strip():
                self.error(
                    "MAP_DESCRIPTION_MISSING",
                    path,
                    "map needs a non-empty string `description`",
                )
        description = parsed.frontmatter.get("description")
        if isinstance(description, str) and DESCRIPTION_REVIEW_RE.search(description):
            self.warning(
                "DESCRIPTION_REVIEW",
                path,
                "description includes an `open when` or `use when` instruction",
            )

        headings = self._section_headings(body)
        named = [title for title, _, _ in headings]
        known = [title for title in named if title in {"Task routes", "Member inventory", "Artifact references"}]
        if named.count("Member inventory") != 1:
            self.error("MAP_INVENTORY_HEADING", path, "map must have exactly one '## Member inventory' section")
        if any(known.count(title) > 1 for title in {"Task routes", "Artifact references"}):
            self.error("MAP_SECTION_DUPLICATE", path, "map sections must not be duplicated")
        order = ["Task routes", "Member inventory", "Artifact references"]
        order_positions = [order.index(title) for title in known]
        if order_positions != sorted(order_positions):
            self.error("MAP_SECTION_ORDER", path, "map sections are out of the required order")

        lines = body.splitlines()
        inventory_heading = next(
            (heading for heading in headings if heading[0] == "Member inventory"),
            None,
        )
        if inventory_heading is None:
            return

        starts = [i for i, line in enumerate(lines) if line == START_MARKER]
        ends = [i for i, line in enumerate(lines) if line == END_MARKER]
        heading_line = inventory_heading[1]
        if len(starts) != 1 or len(ends) != 1:
            self.error("MAP_MARKERS", path, "inventory must contain exactly one start and end marker")
            return
        start, end = starts[0], ends[0]
        if not (heading_line < start < end):
            self.error("MAP_MARKERS", path, "inventory markers are misplaced or reversed")
            return
        if any(line.strip() for line in lines[heading_line + 1 : start]):
            self.error("MAP_MARKERS", path, "inventory markers must directly follow the inventory heading")
            return

        actual = lines[start + 1 : end]
        try:
            expected = [
                "| What it is | Document |",
                "| --- | --- |",
                *(
                render_inventory_entry(self.link_root, entry)
                for entry in inventory_entries(self.root, path)
                ),
            ]
        except BKFInputError as exc:
            message = str(exc)
            missing_path = message.partition(": ")[0]
            reported = {f.path for f in self.findings if f.severity == "ERROR"}
            if missing_path in reported:
                return  # the document's own error already explains this
            if "map needs a non-empty string `description`" in message:
                self.error(
                    "MAP_DESCRIPTION_MISSING",
                    self.root / missing_path,
                    "map needs a non-empty string `description`",
                )
            else:
                self.error("MAP_MEMBERSHIP", path, message)
            return
        if actual != expected:
            self.error(
                "MAP_INVENTORY_STALE",
                path,
                "member inventory must list the exact in-scope members once, with current descriptions and ordering",
            )

        for title, section_start, section_end in headings:
            if title == "Task routes":
                self._validate_task_routes(path, lines[section_end : self._next_heading_start(headings, section_start, len(lines))])
            elif title == "Artifact references":
                self._validate_artifact_references(path, body, section_start, self._next_heading_start(headings, section_start, len(lines)))

    def _validate_map_size(self, path: Path, root_map: Path) -> None:
        """Warn when a non-root map covers too few items to earn its own navigation purpose."""
        if path == root_map or is_bundle_root_map(path):
            return
        try:
            entries = inventory_entries(self.root, path)
            body = self._map_body(path, root_map)
        except (BKFInputError, OSError, UnicodeError):
            return  # the map's own errors already explain this
        size = len(entries)  # tracked documents and child maps in scope

        lines = body.splitlines()
        headings = self._section_headings(body)
        for title, start, end in headings:
            section_end = self._next_heading_start(headings, start, len(lines))
            if title == "Artifact references":
                tokens = MARKDOWN.parse("\n".join(lines[start:section_end]))
                size += sum(1 for token in tokens if token.type == "list_item_open")
            elif title == "Task routes":
                rows = [line for line in lines[end:section_end] if line.strip().startswith("|")]
                size += max(len(rows) - 2, 0)  # the header and separator rows are not routes

        if size <= MAP_SIZE_LIMIT:
            self.warning(
                "MAP_TOO_SMALL",
                path,
                f"map covers {size} items (limit {MAP_SIZE_LIMIT}). Folders without a distinct navigation "
                "purpose use their nearest ancestor map. If that is obvious here, delete this MAP.md and let "
                "the parent map list its contents; if it is not obvious, ignore it.",
            )

    @staticmethod
    def _next_heading_start(
        headings: list[tuple[str, int, int]], current_start: int, default: int
    ) -> int:
        later = [start for _, start, _ in headings if start > current_start]
        return min(later) if later else default

    def _validate_task_routes(self, path: Path, section_lines: list[str]) -> None:
        content = [line.strip() for line in section_lines if line.strip()]
        rows = [line for line in content if line.startswith("|")]
        if len(rows) < 2:
            self.error("MAP_ROUTES_TABLE", path, "Task routes must use a non-empty Markdown table")
            return

        header = self._table_cells(rows[0])
        separator = self._table_cells(rows[1])
        if header != ["Task", "Start here"] or len(separator) != 2 or any(
            re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) is None for cell in separator
        ):
            self.error("MAP_ROUTES_TABLE", path, "Task routes table must have Task and Start here columns")
            return
        if any(not line.startswith("|") for line in content):
            self.error("MAP_ROUTES_TABLE", path, "Task routes section may contain only its table")
        for row in rows[2:]:
            cells = self._table_cells(row)
            if len(cells) != 2 or not cells[0]:
                self.error("MAP_ROUTES_ROW", path, "each Task routes row needs a task and a start link")
                continue
            destinations = self._link_destinations(cells[1])
            if len(destinations) != 1 or len(self._link_destinations(row)) != 1:
                self.error("MAP_ROUTES_ROW", path, "each route must contain exactly one start link")
            else:
                self._require_member_target(path, destinations[0], "route start")

    @staticmethod
    def _table_cells(row: str) -> list[str]:
        return [cell.strip() for cell in row.strip().strip("|").split("|")]

    @staticmethod
    def _flatten(tokens):
        for token in tokens:
            yield token
            if token.children:
                yield from Validator._flatten(token.children)

    def _validate_artifact_references(
        self, path: Path, body: str, start: int, end: int
    ) -> None:
        section = "\n".join(body.splitlines()[start:end])
        tokens = MARKDOWN.parse(section)
        list_items = [i for i, token in enumerate(tokens) if token.type == "list_item_open"]
        if not list_items:
            self.error("MAP_ARTIFACT_REFERENCES", path, "Artifact references must contain linked list items")
            return
        for index in list_items:
            depth = 0
            destinations: list[str] = []
            for token in self._flatten(tokens[index:]):
                if token.type == "list_item_open":
                    depth += 1
                elif token.type == "list_item_close":
                    depth -= 1
                    if depth == 0:
                        break
                elif token.type == "link_open":
                    destination = token.attrGet("href")
                    if destination is not None:
                        destinations.append(destination)
            if len(destinations) != 1:
                self.error("MAP_ARTIFACT_REFERENCES", path, "each artifact reference must contain exactly one link")
                continue
            self._require_scoped_nonmember_target(path, destinations[0])

    @staticmethod
    def _link_destinations(markdown: str) -> list[str]:
        destinations = []
        for token in Validator._flatten(MARKDOWN.parse(markdown)):
            if token.type == "link_open":
                destination = token.attrGet("href")
                if destination is not None:
                    destinations.append(destination)
        return destinations

    def _require_member_target(self, source: Path, destination: str, relation: str) -> None:
        try:
            parsed = urlsplit(destination)
        except ValueError as exc:
            self.error("MAP_ROUTE_TARGET", source, f"invalid {relation} URL: {exc}")
            return
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            self.error("MAP_ROUTE_TARGET", source, f"{relation} must link to a BKF document in the bundle")
            return
        target = self._resolve_internal_target(source, parsed.path)
        if target is not None and target not in self.member_documents:
            self.error("MAP_ROUTE_TARGET", source, f"{relation} must target a BKF document")

    def _require_scoped_nonmember_target(self, source: Path, destination: str) -> None:
        try:
            parsed = urlsplit(destination)
        except ValueError as exc:
            self.error("MAP_ARTIFACT_TARGET", source, f"invalid artifact URL: {exc}")
            return
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            self.error("MAP_ARTIFACT_TARGET", source, "artifact references must target a file in the bundle")
            return
        target = self._resolve_internal_target(source, parsed.path)
        if target is None:
            return
        if target in self.member_documents:
            self.error("MAP_ARTIFACT_TARGET", source, "artifact references must target non-member files")
        scope = source.parent.resolve()
        if not target.is_relative_to(scope):
            self.error("MAP_ARTIFACT_TARGET", source, "artifact references must stay within the map's scope")
            return
        for parent in target.parents:
            if parent == scope:
                break
            if parent != scope and (parent / MAP_NAME).is_file():
                self.error("MAP_ARTIFACT_TARGET", source, "artifact reference crosses a child map boundary")
                return

    def _discover_markdown_files(self) -> list[Path]:
        nested_roots = nested_bundle_roots(self.root)
        cache: dict[Path, bool] = {}
        return sorted(
            (
                path for path in self.root.rglob("*")
                if path.is_file() and path.suffix.lower() == ".md"
                and not is_notes_file(self.root, path)
                and not in_linked_worktree(self.root, path, cache)
                and not any(path.is_relative_to(nested_root) for nested_root in nested_roots)
            ),
            key=lambda path: path.relative_to(self.root).as_posix(),
        )

    def _validate_notes_files(self) -> None:
        for path in sorted(self.root.iterdir()):
            if not path.is_file() or not is_notes_file(self.root, path):
                continue
            try:
                frontmatter = parse_markdown(path).frontmatter
            except BKFInputError:
                continue
            if "bkf" in frontmatter:
                self.error(
                    "NOTES_TRACKED",
                    path,
                    "a notes file holds the user's private notes and must not carry a `bkf` field; "
                    "ask the user before editing it",
                )

    def _is_notes_target(self, target: Path) -> bool:
        folder = target.parent
        if folder not in self._bundle_root_folders:
            map_path = folder / MAP_NAME
            self._bundle_root_folders[folder] = map_path.is_file() and is_bundle_root_map(map_path)
        if not self._bundle_root_folders[folder]:
            return False
        return any(
            is_notes_file(folder, folder / name) and os.path.samefile(folder / name, target)
            for name in os.listdir(folder)
        )

    def _validate_documents(self) -> None:
        markdown_files = self.markdown_files
        for path in markdown_files:
            if path.name == MAP_NAME:
                continue
            if not path.resolve().is_relative_to(self.root):
                self.error("DOCUMENT_OUTSIDE_ROOT", path, "Markdown file resolves outside the bundle root")
                continue
            if path == self.root / README_NAME:
                continue
            parsed = self._parse(path)
            if parsed is None:
                continue
            self.parsed_markdown_files[path] = parsed
            metadata = parsed.frontmatter
            try:
                tracked = tracking_state(metadata, path=path.relative_to(self.root).as_posix())
            except BKFInputError as exc:
                self.error("METADATA_TYPE", path, str(exc).split(": ", 1)[-1])
                continue
            if not tracked:
                for reserved in ("AGENTS.md", "feedback.md", "ideas.md"):
                    if path == self.root / reserved:
                        self.error(
                            f"ROOT_{reserved.removesuffix('.md').upper()}_UNTRACKED",
                            path,
                            f"bundle-root {reserved} must be a tracked BKF document",
                        )
                continue

            profile = metadata.get("bkf")
            if path.name == "feedback.md" and path.parent != self.root:
                self.error("FEEDBACK_LOCATION", path, "feedback.md is reserved for the bundle root")
            if path == self.root / "feedback.md" and profile != "feedback":
                self.error("FEEDBACK_PROFILE", path, "root feedback.md must use `bkf: feedback`")
            if profile == "feedback" and path != self.root / "feedback.md":
                self.error("FEEDBACK_PROFILE", path, "the `feedback` profile is reserved for the bundle-root feedback.md")
            if path.name == "ideas.md" and path.parent != self.root:
                self.error("IDEAS_LOCATION", path, "ideas.md is reserved for the bundle root")
            if path == self.root / "ideas.md" and profile != "ideas":
                self.error("IDEAS_PROFILE", path, "root ideas.md must use `bkf: ideas`")
            if profile == "ideas" and path != self.root / "ideas.md":
                self.error("IDEAS_PROFILE", path, "the `ideas` profile is reserved for the bundle-root ideas.md")

            if path.name != "AGENTS.md":
                if not DOCUMENT_NAME_RE.fullmatch(path.name):
                    self.error("DOCUMENT_FILENAME", path, "generic document filenames must use lowercase kebab-case")
            self.member_documents[path.resolve()] = parsed
            self._validate_metadata(path, metadata, profile if profile in PROFILE_FIELDS else "generic")
            description = metadata.get("description")
            if isinstance(description, str) and DESCRIPTION_REVIEW_RE.search(description):
                self.warning(
                    "DESCRIPTION_REVIEW",
                    path,
                    "description includes an `open when` or `use when` instruction",
                )
            if profile not in LOG_PROFILES:
                self._validate_navigation_map(path, parsed.body)

    def _validate_agent_instructions_size(self) -> None:
        """Warn when an AGENTS.md or CLAUDE.md body is long enough to crowd every session's context."""
        for path in self.markdown_files:
            if path.name not in AGENT_INSTRUCTION_NAMES:
                continue
            try:
                body = parse_markdown(path).body
            except (BKFInputError, OSError, UnicodeError):
                continue  # the file's own errors are reported by document validation
            _, words = body_size(body)
            if words > AGENT_INSTRUCTION_WORD_LIMIT:
                self.warning(
                    "AGENT_INSTRUCTIONS_LONG",
                    path,
                    f"{path.name} is loaded into every session; its body has {words} words "
                    f"(limit {AGENT_INSTRUCTION_WORD_LIMIT}). Move rules that a hook or a script can check into "
                    "that hook or script, move detail into the document that owns it, and leave a pointer to it.",
                )

    def _validate_navigation_map(self, path: Path, body: str) -> None:
        has_map, problems = map_problems(body)
        if not has_map:
            if needs_navigation_map(body):
                line_count, word_count = body_size(body)
                self.warning(
                    "NAVIGATION_MAP_REVIEW",
                    path,
                    f"body has {line_count} lines and {word_count} words but lacks a `## Navigation map` table",
                )
            return
        for problem in problems:
            self.warning("NAVIGATION_MAP_STALE", path, problem)

    def _validate_metadata(self, path: Path, metadata: dict[str, object], profile: str) -> None:
        fields = PROFILE_FIELDS[profile] if profile in PROFILE_FIELDS else GENERIC_FIELDS
        if profile == "generic" and metadata.get("bkf") != "document":
            self.error("METADATA_PROFILE", path, "`bkf` must be a defined profile or `document`")
        for field in sorted(fields - set(metadata)):
            self.error("METADATA_MISSING", path, f"missing required field `{field}`")
        for field in sorted(set(metadata) - fields - OPTIONAL_FIELDS.get(profile, set())):
            self.error("METADATA_UNKNOWN_FIELD", path, f"unknown field `{field}` for this profile")
        description = metadata.get("description")
        if "description" in fields and not isinstance(description, str):
            self.error("METADATA_DESCRIPTION", path, "`description` must be a string")
        if profile == "generic":
            tags = metadata.get("tags")
            if not isinstance(tags, list) or not tags or not all(
                isinstance(tag, str) and bool(tag.strip()) for tag in tags
            ):
                self.error("METADATA_TAGS", path, "`tags` must be a non-empty list of non-empty strings")
            else:
                self._validate_tag_vocabulary(path, tags)
            if "ext" in metadata:
                self._validate_ext(path, metadata["ext"])

    def _validate_ext(self, path: Path, value: object) -> None:
        if not isinstance(value, dict):
            self.error("EXT_INVALID", path, "`ext` must be a mapping")
            return
        validator = self._load_ext_validator(path)
        if validator is None:
            return
        for error in sorted(validator.iter_errors({"ext": value}), key=lambda item: list(map(str, item.absolute_path))):
            location = "/".join(str(part) for part in error.absolute_path) or "ext"
            self.error("EXT_INVALID", path, f"`{location}`: {error.message}")

    def _load_ext_validator(self, path: Path) -> Draft202012Validator | None:
        """Load the bundle's ext schema once; report why it is unusable once."""
        if self._ext_validator is not None:
            return self._ext_validator
        if self._ext_schema_reported:
            return None
        self._ext_schema_reported = True
        schema_path = self.root / EXT_SCHEMA_NAME
        if not schema_path.is_file():
            self.error("EXT_SCHEMA_MISSING", path, f"`ext` is only allowed when the bundle root has {EXT_SCHEMA_NAME}")
            return None
        yaml = YAML(typ="safe")
        yaml.version = (1, 2)
        yaml.allow_duplicate_keys = False
        try:
            schema = yaml.load(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, UnicodeError, YAMLError, SchemaError) as exc:
            self.error("EXT_SCHEMA_INVALID", schema_path, f"cannot use {EXT_SCHEMA_NAME}: {exc}")
            return None
        self._ext_validator = Draft202012Validator(schema)
        return self._ext_validator

    def _validate_links(self, source: Path, markdown: str) -> None:
        for token in self._flatten(MARKDOWN.parse(markdown)):
            if token.type == "link_open":
                destination = token.attrGet("href")
            elif token.type == "image":
                destination = token.attrGet("src")
            else:
                continue
            if destination is None:
                continue
            self._validate_destination(source, destination)

    def _validate_destination(self, source: Path, destination: str) -> None:
        if (
            not destination
            or any(character.isspace() for character in destination)
            or PERCENT_ESCAPE_RE.search(destination)
        ):
            self.error(
                "LINK_INVALID",
                source,
                "link destination is empty, contains unescaped whitespace, or has malformed percent-encoding",
            )
            return
        try:
            parsed = urlsplit(destination)
        except ValueError as exc:
            self.error("LINK_INVALID", source, f"invalid link destination: {exc}")
            return

        if parsed.scheme:
            if parsed.scheme in {"http", "https"}:
                try:
                    if not parsed.hostname:
                        raise ValueError("missing host")
                    _ = parsed.port
                except ValueError as exc:
                    self.error("LINK_INVALID", source, f"invalid absolute web URL: {exc}")
            return
        if parsed.netloc:
            self.error("LINK_INVALID", source, "protocol-relative URLs are not absolute URLs")
            return
        if not parsed.path:
            if destination.startswith("#"):
                return
            self.error("LINK_INVALID", source, "internal file links must have a bundle-root absolute path")
            return
        if not parsed.path.startswith("/"):
            self.error("LINK_PATH", source, "internal links must use bundle-root absolute paths")
            return
        target = self._resolve_internal_target(source, parsed.path)
        if target is not None and self._is_notes_target(target):
            self.error("NOTES_LINKED", source, f"links must not target the user's private notes file {parsed.path}")

    def _resolve_internal_target(self, source: Path, target: str) -> Path | None:
        if not target.startswith("/") or PERCENT_ESCAPE_RE.search(target):
            self.error("LINK_PATH", source, "internal target must use a valid bundle-root absolute path")
            return None
        if target.startswith("//") or any(
            character.isspace() or ord(character) > 127 for character in target
        ):
            self.error("LINK_PATH", source, "internal path must use URL-safe UTF-8 percent-encoding")
            return None
        try:
            decoded = unquote(target, encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            self.error("LINK_PATH", source, "internal path must use valid UTF-8 percent-encoding")
            return None
        resolved = (self.link_root / decoded.lstrip("/")).resolve()
        if not resolved.is_relative_to(self.link_root):
            self.error("LINK_PATH", source, "internal target resolves outside the outermost bundle root")
            return None
        if not resolved.is_file():
            self.error("LINK_TARGET_MISSING", source, f"internal file target does not exist: {target}")
            return None
        return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf validate", description=__doc__)
    parser.add_argument("bundle_root", type=Path, help="directory containing the root MAP.md")
    parser.add_argument(
        "--this-bundle",
        action="store_true",
        help="check only the selected bundle, not the bundles nested inside it",
    )
    return parser


def validate_one(root: Path, validator: Validator | None = None) -> int:
    """Print the findings for one bundle; pass a validator that already ran to reuse its findings."""
    if validator is None:
        validator = Validator(root)
        validator.validate()
    for finding in validator.findings:
        print(f"{finding.severity} {finding.code} {finding.path}: {finding.message}")
    if any(finding.code in WARNING_CODES for finding in validator.findings):
        print(GUIDANCE)

    errors = any(finding.severity == "ERROR" for finding in validator.findings)
    incomplete = any(
        finding.code == "VERSION_UNSUPPORTED" for finding in validator.findings
    )
    if errors:
        print("Result: NONCONFORMANT")
        return 1
    if incomplete:
        print("Result: INCOMPLETE — validator cannot assess the declared version fully")
        return 2
    print(f"Result: CONFORMANT with BKF {SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.bundle_root.resolve()
    if not root.is_dir():
        print(f"error: bundle root is not a directory: {root}", file=sys.stderr)
        return 2

    bundles = find_bundles(root, walk_nested=not args.this_bundle)
    status = 0
    for bundle in bundles:
        if len(bundles) > 1:
            print(f"== {bundle.relative_to(root).as_posix()} ==")
        status = max(status, validate_one(bundle))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

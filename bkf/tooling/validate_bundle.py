#!/usr/bin/env python3
"""Check BKF bundle structure, metadata, maps, and links."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from bkf_common import (
    BKFInputError,
    MAP_NAME,
    ParsedMarkdown,
    README_NAME,
    discover_maps,
    find_bundles,
    in_nested_bundle,
    inventory_entries,
    parse_markdown,
    render_inventory_entry,
    tracking_state,
)
from workflow_validation import WorkflowChecks


SUPPORTED_VERSION = (0, 1)
VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")
DOCUMENT_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
MARKDOWN = MarkdownIt("commonmark")
START_MARKER = "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->"
END_MARKER = "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->"
PROFILE_FIELDS = {
    "feedback": {"bkf", "description"},
    "ideas": {"bkf", "description"},
    "workflow": {"bkf", "description", "workflow_id"},
    "workflow.work_unit": {"bkf", "work_unit_id"},
    "workflow.stage": {"bkf", "stage_id"},
    "workflow.file": {"bkf", "stage_ids"},
}
GENERIC_FIELDS = {"bkf", "description", "tags"}
OPTIONAL_FIELDS = {
    "workflow": {"execution_status", "unit_status"},
    "workflow.work_unit": {"description"},
    "workflow.stage": {"description", "reviews", "human_checkpoint"},
    "workflow.file": {"description"},
}
WORKFLOW_PROFILES = {"workflow", "workflow.work_unit", "workflow.stage", "workflow.file"}
DESCRIPTION_REVIEW_RE = re.compile(r"\b(?:open\s+when|use\s+when)\b", re.IGNORECASE)
NAVIGATION_MAP_REVIEW_LINES = 350
NAVIGATION_MAP_REVIEW_WORDS = 2_000
NAVIGATION_MAP_EARLY_LINES = 40
LOG_PROFILES = frozenset({"feedback", "ideas"})


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


class Validator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: list[Finding] = []
        self.member_documents: dict[Path, ParsedMarkdown] = {}

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

        maps = discover_maps(self.root)
        version = self._validate_root_map(root_map)
        self._check_version(version, root_map)

        self._validate_documents()
        self._validate_workflows()
        for map_path in maps:
            self._validate_map(map_path, root_map)

        for path, parsed in list(self.member_documents.items()):
            self._validate_links(path, parsed.body)

        for map_path in maps:
            try:
                body = self._map_body(map_path, root_map)
            except BKFInputError:
                continue
            self._validate_links(map_path, body)

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
                f"run `bkf updates <bundle-root>` on this bundle, then migrate it to the supported version {SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]}",
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
                render_inventory_entry(self.root, entry)
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

    def _validate_documents(self) -> None:
        markdown_files = sorted(
            (
                path for path in self.root.rglob("*")
                if path.is_file() and path.suffix.lower() == ".md"
                and not in_nested_bundle(self.root, path)
            ),
            key=lambda path: path.relative_to(self.root).as_posix(),
        )
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

            if profile not in WORKFLOW_PROFILES:
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

    def _validate_navigation_map(self, path: Path, body: str) -> None:
        lines = body.splitlines(keepends=True)
        line_count = len(body.splitlines())
        word_count = len(re.findall(r"\b\w+\b", body))
        if line_count <= NAVIGATION_MAP_REVIEW_LINES and word_count <= NAVIGATION_MAP_REVIEW_WORDS:
            return

        tokens = MARKDOWN.parse(body)
        headings: list[tuple[str, int, int, int]] = []
        for index, token in enumerate(tokens):
            if token.type != "heading_open" or not token.map:
                continue
            try:
                level = int(token.tag.removeprefix("h"))
            except ValueError:
                continue
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            if inline is None or inline.type != "inline":
                title = ""
            elif inline.children is None:
                title = inline.content
            else:
                title_parts: list[str] = []
                for child in inline.children:
                    if child.type in {"text", "code_inline"}:
                        title_parts.append(child.content)
                    elif child.type in {"softbreak", "hardbreak"}:
                        title_parts.append(" ")
                title = "".join(title_parts)
            headings.append((" ".join(title.split()).casefold(), level, token.map[0], token.map[1]))

        for heading_index, (title, level, start, end) in enumerate(headings):
            if start >= NAVIGATION_MAP_EARLY_LINES:
                continue
            section_end = next(
                (
                    next_start
                    for _, _, next_start, _ in headings[heading_index + 1 :]
                ),
                len(lines),
            )
            section = "".join(lines[end:section_end])
            if sum(
                self._has_heading_fragment(destination)
                for destination in self._link_destinations(section)
            ) >= 2:
                return

        self.warning(
            "NAVIGATION_MAP_REVIEW",
            path,
            f"body has {line_count} lines and {word_count} words but lacks an early section with a heading-fragment link",
        )

    @staticmethod
    def _has_heading_fragment(destination: str) -> bool:
        try:
            return bool(urlsplit(destination).fragment)
        except ValueError:
            return False

    def _validate_workflows(self) -> None:
        checks = WorkflowChecks(self.root, self.error, self.warning)
        parents = [
            (path, parsed) for path, parsed in self.member_documents.items()
            if parsed.frontmatter.get("bkf") == "workflow"
        ]
        workflow_ids: dict[str, Path] = {}
        for path, parsed in parents:
            workflow_id = parsed.frontmatter.get("workflow_id")
            if isinstance(workflow_id, str):
                if workflow_id in workflow_ids:
                    self.error("WORKFLOW_ID_DUPLICATE", path, f"workflow_id {workflow_id} is also used by {workflow_ids[workflow_id].relative_to(self.root).as_posix()}")
                workflow_ids[workflow_id] = path
            checks.validate_parent(path)
        parent_paths = {path for path, _ in parents}
        for path in self.member_documents:
            if path not in parent_paths:
                checks.validate_embedded_declarations(path)

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
        self._resolve_internal_target(source, parsed.path)

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
        resolved = (self.root / decoded.lstrip("/")).resolve()
        if not resolved.is_relative_to(self.root):
            self.error("LINK_PATH", source, "internal target resolves outside the bundle root")
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


def validate_one(root: Path) -> int:
    validator = Validator(root)
    validator.validate()
    for finding in validator.findings:
        print(f"{finding.severity} {finding.code} {finding.path}: {finding.message}")

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

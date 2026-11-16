"""Shared YAML, path, and inventory rules for BKF command-line tools."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


MAP_NAME = "MAP.md"
README_NAME = "readme.md"
TAG_VOCABULARY_NAME = "tag-vocabulary.yaml"


NAVIGATION_MAP_REVIEW_LINES = 350
NAVIGATION_MAP_REVIEW_WORDS = 2_000


def body_size(body: str) -> tuple[int, int]:
    """Return the line and word counts that decide whether a document needs a navigation map."""
    return len(body.splitlines()), len(re.findall(r"\b\w+\b", body))


def needs_navigation_map(body: str) -> bool:
    """Return whether a document body is large enough to need a navigation map."""
    lines, words = body_size(body)
    return lines > NAVIGATION_MAP_REVIEW_LINES or words > NAVIGATION_MAP_REVIEW_WORDS


class BKFInputError(ValueError):
    """Raised when a BKF input cannot be parsed or interpreted safely."""


@dataclass(frozen=True)
class ParsedMarkdown:
    frontmatter: dict[str, object]
    body: str


@dataclass(frozen=True)
class InventoryEntry:
    path: Path
    label: str
    description: str


def read_text_preserving_newlines(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            return source.read()
    except (OSError, UnicodeError) as exc:
        raise BKFInputError(f"cannot read UTF-8 file: {exc}") from exc


def parse_markdown(path: Path) -> ParsedMarkdown:
    text = read_text_preserving_newlines(path)
    lines = text.splitlines(keepends=True)
    first = lines[0].rstrip("\r\n").removeprefix("\ufeff") if lines else ""
    if first != "---":
        return ParsedMarkdown(frontmatter={}, body="".join(lines))

    closing = next(
        (
            i
            for i, line in enumerate(lines[1:], 1)
            if line.rstrip("\r\n") == "---"
        ),
        None,
    )
    if closing is None:
        raise BKFInputError("unterminated YAML frontmatter")

    yaml = YAML(typ="safe")
    yaml.version = (1, 2)
    yaml.allow_duplicate_keys = False
    frontmatter_text = "".join(lines[1:closing])
    try:
        values = yaml.load(frontmatter_text)
    except YAMLError as exc:
        raise BKFInputError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(values, dict):
        raise BKFInputError("frontmatter must be a YAML mapping")

    return ParsedMarkdown(
        frontmatter=values,
        body="".join(lines[closing + 1 :]),
    )


def load_tag_vocabulary(root: Path) -> dict[str, list[str]] | None:
    """Return the bundle's canonical tags with their synonyms, or None when it has no vocabulary file.

    Raises BKFInputError naming the first problem when the file is unusable.
    """
    path = root / TAG_VOCABULARY_NAME
    if not path.is_file():
        return None
    yaml = YAML(typ="safe")
    yaml.version = (1, 2)
    yaml.allow_duplicate_keys = False
    try:
        data = yaml.load(read_text_preserving_newlines(path))
    except (YAMLError, BKFInputError) as exc:
        raise BKFInputError(f"cannot use {TAG_VOCABULARY_NAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise BKFInputError(f"{TAG_VOCABULARY_NAME} must be a mapping from each tag to a list of synonyms")
    keys = {key.casefold() for key in data if isinstance(key, str)}
    seen: dict[str, str] = {}
    for key, synonyms in data.items():
        if not isinstance(key, str) or not key.strip():
            raise BKFInputError(f"{TAG_VOCABULARY_NAME}: tag {key!r} must be a non-empty string")
        if not isinstance(synonyms, list):
            raise BKFInputError(f"{TAG_VOCABULARY_NAME}: synonyms of `{key}` must be a list")
        for synonym in synonyms:
            if not isinstance(synonym, str) or not synonym.strip():
                raise BKFInputError(f"{TAG_VOCABULARY_NAME}: synonyms of `{key}` must be non-empty strings")
            folded = synonym.casefold()
            if folded in keys:
                raise BKFInputError(f"{TAG_VOCABULARY_NAME}: synonym `{synonym}` of `{key}` equals a tag")
            if folded in seen:
                raise BKFInputError(
                    f"{TAG_VOCABULARY_NAME}: synonym `{synonym}` of `{key}` is already a synonym of `{seen[folded]}`"
                )
            seen[folded] = key
    return {key: list(synonyms) for key, synonyms in data.items()}


def canonical_tag(vocabulary: dict[str, list[str]], tag: str) -> str | None:
    """Return the canonical tag that `tag` names as a synonym (case-insensitive), or None."""
    folded = tag.casefold()
    for key, synonyms in vocabulary.items():
        if any(synonym.casefold() == folded for synonym in synonyms):
            return key
    return None


def tracking_state(frontmatter: dict[str, object], *, path: str) -> bool:
    """Return whether a member is tracked, enforcing description presence by profile."""
    if "bkf" not in frontmatter:
        return False

    profile = frontmatter["bkf"]
    if not isinstance(profile, str) or not profile.strip():
        raise BKFInputError(f"{path}: `bkf` must be a non-empty profile name string")

    description = frontmatter.get("description")
    if isinstance(description, str) and description.strip():
        return True
    if "description" in frontmatter:
        raise BKFInputError(f"{path}: `description` must be a non-empty string")
    raise BKFInputError(f"{path}: tracked BKF document needs a non-empty string `description`")


def is_bundle_root_map(map_path: Path) -> bool:
    """Return whether this MAP.md declares `bkf_version` in its frontmatter."""
    try:
        return "bkf_version" in parse_markdown(map_path).frontmatter
    except BKFInputError:
        return False


def is_linked_worktree(directory: Path) -> bool:
    """Return whether `directory` is the root of a linked git worktree (its `.git` is a file)."""
    return (directory / ".git").is_file()


def in_linked_worktree(root: Path, path: Path, cache: dict[Path, bool] | None = None) -> bool:
    """Return whether `path` lies inside a linked git worktree below `root`; `root` itself never counts."""
    cache = {} if cache is None else cache
    try:
        parents = path.relative_to(root).parents
    except ValueError:
        return False
    for parent in parents:
        if parent == Path("."):
            continue
        directory = root / parent
        if directory not in cache:
            cache[directory] = is_linked_worktree(directory)
        if cache[directory]:
            return True
    return False


def nested_bundle_roots(root: Path) -> list[Path]:
    """Return the outermost nested bundle roots below `root`, never `root` itself."""
    found: list[Path] = []
    for directory, directories, filenames in os.walk(root):
        directories[:] = sorted(name for name in directories if not is_linked_worktree(Path(directory) / name))
        directory_path = Path(directory)
        if directory_path != root and MAP_NAME in filenames and is_bundle_root_map(directory_path / MAP_NAME):
            found.append(directory_path)
            directories.clear()
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


def find_bundles(root: Path, walk_nested: bool = True) -> list[Path]:
    """Return `root` plus, when requested, every nested bundle at any depth."""
    bundles = [root]
    if walk_nested:
        for nested in nested_bundle_roots(root):
            bundles.extend(find_bundles(nested))
    return sorted(bundles, key=lambda path: path.relative_to(root).as_posix())


def in_nested_bundle(root: Path, path: Path) -> bool:
    """Return whether `path` lies inside a bundle nested below `root`."""
    try:
        parents = path.relative_to(root).parents
    except ValueError:
        return False
    for parent in parents:
        if parent == Path("."):
            continue
        map_path = root / parent / MAP_NAME
        if map_path.is_file() and is_bundle_root_map(map_path):
            return True
    return False


def rglob_in_bundle(root: Path, base: Path, pattern: str) -> list[Path]:
    """`base.rglob(pattern)` without anything inside nested bundles or linked git worktrees of `root`."""
    cache: dict[Path, bool] = {}
    return [
        path for path in base.rglob(pattern)
        if not in_nested_bundle(root, path) and not in_linked_worktree(root, path, cache)
    ]


def discover_maps(root: Path) -> list[Path]:
    return sorted(
        rglob_in_bundle(root, root, MAP_NAME),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _child_map_description(root: Path, map_path: Path) -> str:
    relative = map_path.relative_to(root).as_posix()
    try:
        description = parse_markdown(map_path).frontmatter.get("description")
    except BKFInputError as exc:
        raise BKFInputError(f"{relative}: {exc}") from exc
    if not isinstance(description, str) or not description.strip():
        raise BKFInputError(
            f"{relative}: map needs a non-empty string `description`"
        )
    return " ".join(description.split())


def inventory_entries(root: Path, map_path: Path) -> list[InventoryEntry]:
    scope = map_path.parent
    entries: list[InventoryEntry] = []

    for directory, directories, filenames in os.walk(scope):
        directory_path = Path(directory)
        directories[:] = sorted(name for name in directories if not is_linked_worktree(directory_path / name))
        filenames.sort()

        if directory_path != scope and MAP_NAME in filenames:
            child_map = directory_path / MAP_NAME
            entries.append(
                InventoryEntry(
                    path=child_map,
                    label=MAP_NAME,
                    description=_child_map_description(root, child_map),
                )
            )
            directories.clear()
            continue

        for filename in filenames:
            if Path(filename).suffix.lower() != ".md" or filename == MAP_NAME:
                continue
            if directory_path == root and filename == README_NAME:
                continue
            document = directory_path / filename
            try:
                if not document.resolve().is_relative_to(root):
                    raise BKFInputError("Markdown file resolves outside the bundle root")
                parsed = parse_markdown(document)
            except BKFInputError as exc:
                relative = document.relative_to(root).as_posix()
                raise BKFInputError(f"{relative}: {exc}") from exc

            relative = document.relative_to(root).as_posix()
            if not tracking_state(parsed.frontmatter, path=relative):
                continue

            description = parsed.frontmatter.get("description")
            if not isinstance(description, str) or not description.strip():
                raise BKFInputError(
                    f"{document.relative_to(root).as_posix()}: BKF document needs a non-empty string `description`"
                )
            entries.append(
                InventoryEntry(
                    path=document,
                    label=filename,
                    description=" ".join(description.split()),
                )
            )

    entries.sort(key=lambda entry: entry.path.relative_to(root).as_posix())
    return entries


def markdown_path(root: Path, target: Path) -> str:
    return "/" + quote(target.relative_to(root).as_posix(), safe="/-._~")


def render_inventory_entry(root: Path, entry: InventoryEntry) -> str:
    description = entry.description.replace("|", "\\|")
    return f"| {description} | [{entry.label}]({markdown_path(root, entry.path)}) |"

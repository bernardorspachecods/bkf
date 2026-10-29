#!/usr/bin/env python3
"""Shared discovery, validation, and generation logic for the skill catalog.

This module deliberately uses only the Python standard library.  Its public
functions are read-only except for ``write_catalog``, which has a narrow,
explicit output boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = "SC1"
SKILL_ROOT_RELATIVE = Path("agent-skills/skills")
CATALOG_RELATIVE = Path("agent-skills/SKILL-ARCHITECTURE.md")
# Folders under the skill root that an app manages and the catalog does not cover.
EXCLUDED_PACKAGE_DIRS = frozenset({"synced"})
FRONTMATTER_START = re.compile(r"^---\s*$")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(
    r"!?(?:\[[^\]]*\])\((?:<([^>]+)>|([^\s)]+))(?:\s+(?:\"[^\"]*\"|'[^']*'))?\)"
)
MACHINE_PATH_RE = re.compile(
    r"(?:^|[\s(\[=])(?:/Users/|/home/|/private/var/|~/|[A-Za-z]:[\\/])"
)
EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel"}
SUPPORTED_INTERFACE_FIELDS = {"display_name", "short_description"}
SUPPORTED_POLICY_FIELDS = {"allow_implicit_invocation"}


@dataclass(frozen=True)
class ParsedDocument:
    data: dict[str, Any]
    body: str
    frontmatter_end_line: int


class ParseError(ValueError):
    """Raised when a supported, intentionally small YAML subset is invalid."""


def display_path(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path)
    return relative.as_posix() or "."


def issue(
    code: str,
    severity: str,
    path: str,
    explanation: str,
    suggestion: str,
    *,
    line: int | None = None,
    status: str = "invalid",
    location: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "status": status,
        "path": path,
        "line": line,
        "location": location,
        "explanation": explanation,
        "suggestion": suggestion,
    }


def _strip_comment(value: str) -> str:
    quoted = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quoted == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quoted is None:
                quoted = char
            elif quoted == char:
                quoted = None
            continue
        if char == "#" and quoted is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.strip()


def _scalar(value: str) -> Any:
    value = _strip_comment(value.strip())
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_scalar(item) for item in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ParseError(f"invalid quoted scalar: {value}") from exc
        return value[1:-1].replace("''", "'")
    if ": " in value or value.endswith(":"):
        raise ParseError(f"unquoted value contains ': ', which YAML reads as a mapping: quote it ({value[:60]})")
    if value[0] in "@`%&*!":
        raise ParseError(f"unquoted value starts with {value[0]!r}, which YAML reserves: quote it ({value[:60]})")
    return value


def parse_mapping(text: str) -> dict[str, Any]:
    """Parse the mapping subset used by frontmatter and openai.yaml.

    Supported values are scalars, inline lists, and nested mappings.  This is
    intentionally stricter than silently accepting YAML that the catalog does
    not know how to interpret.
    """

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    lines = text.splitlines()
    number = 0
    while number < len(lines):
        raw = lines[number]
        number += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ParseError(f"tabs are not supported at line {number}")
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw[indent:]
        if content.startswith("-"):
            raise ParseError(f"lists are not supported at line {number}")
        if ":" not in content:
            raise ParseError(f"expected key/value mapping at line {number}")
        key, raw_value = content.split(":", 1)
        key = key.strip()
        if not KEY_RE.fullmatch(key):
            raise ParseError(f"invalid key {key!r} at line {number}")
        while stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            raise ParseError(f"invalid indentation at line {number}")
        current = stack[-1][1]
        if key in current:
            raise ParseError(f"duplicate key {key!r} at line {number}")
        raw_value = raw_value.strip()
        if raw_value in {">", ">-", ">+", "|", "|-", "|+"}:
            block: list[str] = []
            block_indent: int | None = None
            while number < len(lines):
                candidate = lines[number]
                candidate_indent = len(candidate) - len(candidate.lstrip(" "))
                if candidate.strip() and candidate_indent <= indent:
                    break
                number += 1
                if not candidate.strip():
                    block.append("")
                    continue
                if block_indent is None:
                    block_indent = candidate_indent
                if candidate_indent < block_indent:
                    raise ParseError(f"invalid block indentation at line {number}")
                block.append(candidate[block_indent:])
            value = (" " if raw_value.startswith(">") else "\n").join(block).strip()
        else:
            value = _scalar(raw_value)
        if value is None and not raw_value:
            value = {}
            current[key] = value
            stack.append((indent, value))
        else:
            current[key] = value
    return root


def parse_frontmatter(text: str) -> ParsedDocument:
    lines = text.splitlines(keepends=True)
    if not lines or not FRONTMATTER_START.match(lines[0].rstrip("\r\n")):
        raise ParseError("SKILL.md must start with YAML frontmatter")
    closing = None
    for index in range(1, len(lines)):
        if FRONTMATTER_START.match(lines[index].rstrip("\r\n")):
            closing = index
            break
    if closing is None:
        raise ParseError("frontmatter closing delimiter is missing")
    frontmatter = "".join(lines[1:closing])
    data = parse_mapping(frontmatter)
    return ParsedDocument(data, "".join(lines[closing + 1 :]), closing + 1)


def discover_packages(root: Path, skill_root: Path | None = None) -> list[Path]:
    root = root.resolve()
    skill_root = (skill_root or root / SKILL_ROOT_RELATIVE).resolve()
    if not skill_root.is_dir():
        return []
    candidates = [path for path in skill_root.iterdir() if path.is_dir() and path.name not in EXCLUDED_PACKAGE_DIRS]
    ignored = _git_ignored(root, candidates)
    return sorted((path for path in candidates if path not in ignored), key=lambda p: p.name)


def _git_ignored(root: Path, paths: list[Path]) -> set[Path]:
    """Return the paths that git ignores, so local-only skills stay out of the catalog.

    Outside a git repository, or without git, nothing is ignored. Tracked paths are never reported.
    """
    if not paths or shutil.which("git") is None:
        return set()
    names = "".join(f"{path.relative_to(root).as_posix()}\0" for path in paths)
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"],
            cwd=root,
            input=names,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    return {(root / name).resolve() for name in result.stdout.split("\0") if name}


def has_files(path: Path) -> bool:
    return any(candidate.is_file() for candidate in path.rglob("*"))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_external(target: str) -> bool:
    parsed = urlsplit(target)
    return parsed.scheme.lower() in EXTERNAL_SCHEMES or target.startswith("//")


def _validate_links(
    root: Path,
    package: Path,
    source_file: Path,
    text: str,
    issues: list[dict[str, Any]],
) -> set[Path]:
    referenced_files: set[Path] = set()
    for match in LINK_RE.finditer(text):
        target = unquote(match.group(1) or match.group(2) or "").strip()
        line = _line_number(text, match.start())
        if not target or target.startswith("#") or _is_external(target):
            continue
        if (
            target.startswith("/")
            or target.startswith("~/")
            or re.match(r"^[A-Za-z]:[\\/]", target)
            or target.startswith("file:")
        ):
            issues.append(
                issue(
                    "ABSOLUTE_REFERENCE",
                    "error",
                    display_path(root, source_file),
                    "a skill link uses an absolute or machine-specific path",
                    "Use a repository-relative link inside the skill package.",
                    line=line,
                    location=f"link target {target!r}",
                )
            )
            continue
        path_target = target.split("#", 1)[0].split("?", 1)[0]
        if not path_target:
            continue
        resolved = (source_file.parent / path_target).resolve()
        try:
            resolved.relative_to(package.resolve())
        except ValueError:
            if not resolved.exists():
                issues.append(
                    issue(
                        "REFERENCE_MISSING",
                        "error",
                        display_path(root, source_file),
                        f"referenced path does not exist: {target}",
                        "Create the referenced file or correct the relative link.",
                        line=line,
                        location=f"link target {target!r}",
                    )
                )
            continue
        if not resolved.exists():
            issues.append(
                issue(
                    "REFERENCE_MISSING",
                    "error",
                    display_path(root, source_file),
                    f"referenced path does not exist: {target}",
                    "Create the referenced file or correct the relative link.",
                    line=line,
                    location=f"link target {target!r}",
                )
            )
        elif resolved.is_file():
            referenced_files.add(resolved)
    return referenced_files


def _is_generated_skill_file(package: Path, path: Path) -> bool:
    relative = path.relative_to(package)
    return (
        ".DS_Store" in relative.parts
        or "__pycache__" in relative.parts
        or path.suffix in {".pyc", ".pyo"}
    )


def _mask_fenced_code(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    fence_char: str | None = None
    fence_size = 0
    for line in lines:
        stripped = line.lstrip(" ")
        if fence_char is None:
            match = re.match(r"^(`{3,}|~{3,})", stripped)
            if match:
                fence_char = match.group(1)[0]
                fence_size = len(match.group(1))
        else:
            closing = re.match(r"^([`~]+)\s*$", stripped.rstrip("\r\n"))
            if closing and closing.group(1)[0] == fence_char and len(closing.group(1)) >= fence_size:
                fence_char = None
                fence_size = 0
        if fence_char is not None or re.match(r"^([`~]+)\s*$", stripped.rstrip("\r\n")):
            output.append("".join("\n" if char == "\n" else "\r" if char == "\r" else " " for char in line))
        else:
            output.append(line)
    return "".join(output)


def _validate_package_file_links(
    root: Path, package: Path, issues: list[dict[str, Any]]
) -> None:
    package_root = package.resolve()
    package_files = sorted(
        (
            path.resolve()
            for path in package.rglob("*")
            if path.is_file() and not _is_generated_skill_file(package, path)
        ),
        key=lambda path: path.as_posix(),
    )
    documents: dict[Path, str] = {}
    links: dict[Path, set[Path]] = {}

    for path in package_files:
        if path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            issues.append(
                issue(
                    "RESOURCE_UNAVAILABLE",
                    "error",
                    display_path(root, path),
                    f"Markdown resource could not be read: {exc}",
                    "Make the resource readable as UTF-8 and rerun the validator.",
                    status="unavailable",
                )
            )
            continue
        documents[path] = text
        links[path] = _validate_links(
            root, package, path, _mask_fenced_code(text), issues
        )

    skill_file = (package / "SKILL.md").resolve()
    reachable: set[Path] = {skill_file}
    pending = [skill_file]
    while pending:
        source = pending.pop()
        for target in links.get(source, set()):
            if target not in reachable:
                reachable.add(target)
                if target in documents:
                    pending.append(target)

    for path in package_files:
        if path == skill_file or path in reachable:
            continue
        try:
            path.relative_to(package_root)
        except ValueError:
            continue
        issues.append(
            issue(
                "SKILL_FILE_UNLINKED",
                "error",
                display_path(root, path),
                "skill package file is not reachable through links from SKILL.md",
                "Add a Markdown link from SKILL.md or another reachable package document.",
            )
        )


def _validate_machine_paths(root: Path, package: Path, text: str, relative_file: Path, issues: list[dict[str, Any]]) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if MACHINE_PATH_RE.search(line):
            issues.append(
                issue(
                    "MACHINE_SPECIFIC_PATH",
                    "error",
                    display_path(root, package / relative_file),
                    "a machine-specific absolute path appears where repository-relative paths are expected",
                    "Use a repository-relative path or a documented symbolic placeholder.",
                    line=line_number,
                )
            )


def _validate_runtime_metadata(root: Path, package: Path, issues: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_path = package / "agents" / "openai.yaml"
    if not metadata_path.exists():
        return {"status": "missing", "supported": {}}
    try:
        metadata_text = metadata_path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(
            issue(
                "RUNTIME_METADATA_UNAVAILABLE",
                "error",
                display_path(root, metadata_path),
                f"agents/openai.yaml could not be read: {exc}",
                "Make the optional runtime metadata readable or remove it.",
                status="unavailable",
            )
        )
        return {"status": "unavailable", "supported": {}}
    except UnicodeDecodeError as exc:
        issues.append(
            issue(
                "RUNTIME_METADATA_INDETERMINATE",
                "error",
                display_path(root, metadata_path),
                f"agents/openai.yaml is not valid UTF-8: {exc}",
                "Rewrite the optional runtime metadata as UTF-8 YAML.",
                status="indeterminate",
            )
        )
        return {"status": "indeterminate", "supported": {}}
    try:
        metadata = parse_mapping(metadata_text)
    except ParseError as exc:
        issues.append(
            issue(
                "RUNTIME_METADATA_INVALID",
                "error",
                display_path(root, metadata_path),
                f"agents/openai.yaml cannot be parsed: {exc}",
                "Fix the YAML structure or remove the optional runtime metadata file.",
            )
        )
        return {"status": "invalid", "supported": {}}
    for key in sorted(set(metadata) - {"interface", "policy"}):
        issues.append(
            issue(
                "RUNTIME_METADATA_UNKNOWN",
                "warning",
                display_path(root, metadata_path),
                f"runtime metadata field is not supported by the catalog: {key}",
                "Document a supported field before relying on it in generated output.",
                status="unknown",
            )
        )
    interface = metadata.get("interface")
    if interface is None:
        issues.append(
            issue(
                "RUNTIME_INTERFACE_MISSING",
                "warning",
                display_path(root, metadata_path),
                "optional runtime metadata has no supported interface mapping",
                "Add interface metadata only when the runtime supports it; otherwise leave the file absent.",
                status="missing",
            )
        )
        return {"status": "present", "supported": {}}
    if not isinstance(interface, dict):
        issues.append(
            issue(
                "RUNTIME_INTERFACE_INVALID",
                "error",
                display_path(root, metadata_path),
                "the interface runtime metadata must be a mapping",
                "Use an interface mapping with supported scalar fields.",
            )
        )
        return {"status": "invalid", "supported": {}}
    supported: dict[str, str] = {}
    for key in sorted(set(interface) - SUPPORTED_INTERFACE_FIELDS):
        issues.append(
            issue(
                "RUNTIME_FIELD_UNKNOWN",
                "warning",
                display_path(root, metadata_path),
                f"runtime interface field is not supported by the catalog: interface.{key}",
                "Document a supported field before relying on it in generated output.",
                status="unknown",
            )
        )
    for key in sorted(SUPPORTED_INTERFACE_FIELDS):
        value = interface.get(key)
        if value is None:
            issues.append(
                issue(
                    "RUNTIME_FIELD_MISSING",
                    "warning",
                    display_path(root, metadata_path),
                    f"optional runtime field is missing: interface.{key}",
                    "Add the field if the runtime integration needs it; otherwise keep the supported metadata minimal.",
                    status="missing",
                )
            )
        elif not isinstance(value, str) or not value.strip():
            issues.append(
                issue(
                    "RUNTIME_FIELD_INVALID",
                    "error",
                    display_path(root, metadata_path),
                    f"interface.{key} must be a non-empty string",
                    "Set the runtime field to a non-empty string.",
                )
            )
        else:
            supported[key] = value.strip()
    policy = metadata.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            issues.append(
                issue(
                    "RUNTIME_POLICY_INVALID",
                    "error",
                    display_path(root, metadata_path),
                    "the policy runtime metadata must be a mapping",
                    "Use a policy mapping with supported boolean fields.",
                )
            )
        else:
            for key in sorted(set(policy) - SUPPORTED_POLICY_FIELDS):
                issues.append(
                    issue(
                        "RUNTIME_POLICY_UNKNOWN",
                        "warning",
                        display_path(root, metadata_path),
                        f"runtime policy field is not supported by the catalog: policy.{key}",
                        "Document a supported policy field before relying on it in generated output.",
                        status="unknown",
                    )
                )
            value = policy.get("allow_implicit_invocation")
            if value is not None and not isinstance(value, bool):
                issues.append(
                    issue(
                        "RUNTIME_POLICY_INVALID",
                        "error",
                        display_path(root, metadata_path),
                        "policy.allow_implicit_invocation must be a boolean",
                        "Set policy.allow_implicit_invocation to true or false.",
                    )
                )
            elif isinstance(value, bool):
                supported["allow_implicit_invocation"] = value
    return {"status": "present", "supported": supported}


def validate_repository(root: Path, *, check_catalog: bool = False, catalog_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    skill_root = root / SKILL_ROOT_RELATIVE
    packages: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen_names: dict[str, Path] = {}
    resolved_packages: dict[Path, Path] = {}

    if not skill_root.is_dir():
        issues.append(
            issue(
                "SKILL_ROOT_UNAVAILABLE",
                "error",
                display_path(root, skill_root),
                "the configured skill root does not exist or is not a directory",
                "Provide the repository with agent-skills/skills/ or select the correct repository root.",
                status="unavailable",
            )
        )

    for package in discover_packages(root, skill_root):
        package_label = display_path(root, package)
        if not has_files(package):
            packages.append({"name": package.name, "path": package_label, "status": "empty"})
            issues.append(
                issue(
                    "SKILL_EMPTY",
                    "error",
                    package_label,
                    "candidate skill directory contains no files",
                    "Add SKILL.md and the package resources, or remove the empty directory.",
                    status="empty",
                )
            )
            continue

        try:
            canonical = package.resolve()
            previous = resolved_packages.get(canonical)
            if previous is not None and previous != package:
                issues.append(
                    issue(
                        "PACKAGE_PATH_AMBIGUOUS",
                        "error",
                        package_label,
                        f"package path resolves to the same directory as {display_path(root, previous)}",
                        "Keep one canonical package path under agent-skills/skills/.",
                    )
                )
            resolved_packages[canonical] = package
        except OSError:
            issues.append(
                issue(
                    "PACKAGE_UNAVAILABLE",
                    "error",
                    package_label,
                    "package path could not be resolved",
                    "Make the package path readable and resolve filesystem indirection.",
                    status="unavailable",
                )
            )

        skill_file = package / "SKILL.md"
        if not skill_file.is_file():
            packages.append({"name": package.name, "path": package_label, "status": "missing"})
            issues.append(
                issue(
                    "SKILL_MISSING",
                    "error",
                    package_label,
                    "candidate skill directory has no SKILL.md",
                    "Add SKILL.md with name and description frontmatter.",
                    status="missing",
                )
            )
            continue

        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            packages.append({"name": package.name, "path": package_label, "status": "unavailable"})
            issues.append(
                issue(
                    "SKILL_UNAVAILABLE",
                    "error",
                    display_path(root, skill_file),
                    f"SKILL.md could not be read: {exc}",
                    "Make SKILL.md readable and rerun the validator.",
                    status="unavailable",
                )
            )
            continue
        except UnicodeDecodeError as exc:
            packages.append({"name": package.name, "path": package_label, "status": "indeterminate"})
            issues.append(
                issue(
                    "FRONTMATTER_INDETERMINATE",
                    "error",
                    display_path(root, skill_file),
                    f"SKILL.md is not valid UTF-8: {exc}",
                    "Rewrite SKILL.md as UTF-8 and rerun the validator.",
                    status="indeterminate",
                )
            )
            continue
        try:
            parsed = parse_frontmatter(text)
        except ParseError as exc:
            packages.append({"name": package.name, "path": package_label, "status": "invalid"})
            issues.append(
                issue(
                    "FRONTMATTER_INVALID",
                    "error",
                    display_path(root, skill_file),
                    f"SKILL.md frontmatter cannot be parsed: {exc}",
                    "Add valid YAML frontmatter delimited by --- lines.",
                )
            )
            continue

        package_issues_before = len(issues)
        name = parsed.data.get("name")
        description = parsed.data.get("description")
        for key in sorted(set(parsed.data) - {"name", "description"}):
            issues.append(
                issue(
                    "FRONTMATTER_FIELD_UNKNOWN",
                    "warning",
                    display_path(root, skill_file),
                    f"frontmatter field is not supported by the catalog: {key}",
                    "Keep optional metadata in a supported runtime configuration or document its contract.",
                    status="unknown",
                )
            )
        if name is None:
            issues.append(
                issue(
                    "FRONTMATTER_NAME_MISSING",
                    "error",
                    display_path(root, skill_file),
                    "frontmatter is missing name",
                    "Add a lowercase hyphen-case name matching the package directory.",
                    line=1,
                    status="missing",
                )
            )
        elif not isinstance(name, str) or not name.strip():
            issues.append(
                issue(
                    "FRONTMATTER_NAME_INVALID",
                    "error",
                    display_path(root, skill_file),
                    "frontmatter name must be a non-empty string",
                    "Set name to the package directory name.",
                )
            )
        else:
            name = name.strip()
            if not NAME_RE.fullmatch(name):
                issues.append(
                    issue(
                        "SKILL_NAME_INVALID",
                        "error",
                        display_path(root, skill_file),
                        "skill name must use lowercase hyphen-case",
                        "Use only lowercase letters, digits, and single hyphens.",
                    )
                )
            if name != package.name:
                issues.append(
                    issue(
                        "SKILL_NAME_MISMATCH",
                        "error",
                        display_path(root, skill_file),
                        f"frontmatter name {name!r} does not match directory {package.name!r}",
                        "Rename the directory or set frontmatter name to the directory name.",
                    )
                )
            previous = seen_names.get(name)
            if previous is not None and previous != package:
                issues.append(
                    issue(
                        "DUPLICATE_SKILL_NAME",
                        "error",
                        package_label,
                        f"skill name {name!r} is also declared by {display_path(root, previous)}",
                        "Give each package a unique canonical skill name.",
                    )
                )
            seen_names[name] = package
        if description is None:
            issues.append(
                issue(
                    "FRONTMATTER_DESCRIPTION_MISSING",
                    "error",
                    display_path(root, skill_file),
                    "frontmatter is missing description",
                    "Add a concise description that states capability, trigger, and boundary.",
                    line=1,
                    status="missing",
                )
            )
        elif not isinstance(description, str) or not description.strip():
            issues.append(
                issue(
                    "FRONTMATTER_DESCRIPTION_INVALID",
                    "error",
                    display_path(root, skill_file),
                    "frontmatter description must be a non-empty string",
                    "Set description to a concise non-empty string.",
                )
            )

        _validate_package_file_links(root, package, issues)
        _validate_machine_paths(root, package, text, Path("SKILL.md"), issues)
        runtime = _validate_runtime_metadata(root, package, issues)
        metadata_path = package / "agents" / "openai.yaml"
        if metadata_path.is_file():
            try:
                metadata_text = metadata_path.read_text(encoding="utf-8")
            except OSError:
                metadata_text = None
            except UnicodeDecodeError:
                metadata_text = None
            if metadata_text is not None:
                _validate_machine_paths(root, package, metadata_text, Path("agents/openai.yaml"), issues)
        package_issues = issues[package_issues_before:]
        package_status = "valid" if not any(item["severity"] == "error" for item in package_issues) else "invalid"
        if runtime["status"] in {"unavailable", "indeterminate"}:
            package_status = runtime["status"]
        packages.append(
            {
                "name": package.name,
                "path": package_label,
                "status": package_status,
                "description": description.strip() if isinstance(description, str) else None,
                "runtime_metadata": runtime,
            }
        )

    catalog: dict[str, Any] = {"status": "not_checked", "path": display_path(root, catalog_path or root / CATALOG_RELATIVE)}
    if check_catalog:
        markdown_target = (catalog_path or root / CATALOG_RELATIVE).resolve()
        expected_markdown = generate_catalog(root)

        def check_generated_file(
            target: Path,
            expected: str,
            missing_code: str,
            drift_code: str,
            label: str,
        ) -> dict[str, Any]:
            if not target.exists():
                issues.append(
                    issue(
                        missing_code,
                        "error",
                        display_path(root, target),
                        f"generated {label} does not exist",
                        "Run bkf skills --write to create generated catalog outputs.",
                        status="missing",
                    )
                )
                return {"status": "missing", "expected_sha256": _sha256(expected)}
            try:
                actual = target.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(
                    issue(
                        "CATALOG_OUTPUT_UNAVAILABLE",
                        "error",
                        display_path(root, target),
                        f"generated {label} could not be read: {exc}",
                        "Make the generated output readable and rerun the check.",
                        status="unavailable",
                    )
                )
                return {"status": "unavailable"}
            except UnicodeDecodeError as exc:
                issues.append(
                    issue(
                        "CATALOG_OUTPUT_INDETERMINATE",
                        "error",
                        display_path(root, target),
                        f"generated {label} is not valid UTF-8: {exc}",
                        "Rewrite the generated output as UTF-8.",
                        status="indeterminate",
                    )
                )
                return {"status": "indeterminate"}
            if actual != expected:
                issues.append(
                    issue(
                        drift_code,
                        "error",
                        display_path(root, target),
                        f"committed generated {label} differs from deterministic output",
                        "Regenerate the catalog and commit only the generated result.",
                        status="drifted",
                    )
                )
                return {
                    "status": "drifted",
                    "expected_sha256": _sha256(expected),
                    "actual_sha256": _sha256(actual),
                }
            return {"status": "valid", "sha256": _sha256(actual)}

        markdown_result = check_generated_file(
            markdown_target,
            expected_markdown,
            "CATALOG_MISSING",
            "CATALOG_DRIFT",
            "Markdown catalog",
        )
        catalog["markdown"] = markdown_result
        states = {markdown_result["status"]}
        catalog["status"] = (
            "unavailable" if "unavailable" in states else
            "indeterminate" if "indeterminate" in states else
            "drifted" if "drifted" in states else
            "missing" if "missing" in states else
            "valid"
        )

    errors = [item for item in issues if item["severity"] == "error"]
    issue_statuses = {item["status"] for item in issues}
    if "unavailable" in issue_statuses:
        status = "unavailable"
    elif "indeterminate" in issue_statuses:
        status = "indeterminate"
    else:
        status = "invalid" if errors else "valid"
    if not errors and catalog["status"] in {"drifted", "missing"}:
        status = catalog["status"]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "skill_root": display_path(root, skill_root),
        "catalog": catalog,
        "packages": packages,
        "summary": {
            "packages": len(packages),
            "valid": sum(item["status"] == "valid" for item in packages),
            "invalid": sum(item["status"] == "invalid" for item in packages),
            "missing": sum(item["status"] == "missing" for item in packages),
            "empty": sum(item["status"] == "empty" for item in packages),
            "unavailable": sum(item["status"] == "unavailable" for item in packages),
            "indeterminate": sum(item["status"] == "indeterminate" for item in packages),
            "issues": len(issues),
        },
        "issues": issues,
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _markdown_value(value: str | None) -> str:
    if value is None:
        return "unknown"
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _discover_references(package_name: str, text: str, known_names: set[str]) -> list[str]:
    references: set[str] = set()
    for match in re.finditer(r"\$([a-z0-9]+(?:-[a-z0-9]+)*)", text):
        candidate = match.group(1)
        if candidate in known_names and candidate != package_name:
            references.add(candidate)
    for match in LINK_RE.finditer(text):
        target = unquote(match.group(1) or match.group(2) or "").split("#", 1)[0]
        target_match = re.search(r"(?:^|/)skills/([^/]+)/SKILL\.md$", target)
        if target_match and target_match.group(1) in known_names and target_match.group(1) != package_name:
            references.add(target_match.group(1))
    return sorted(references)


def _catalog_entries(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    entries: list[dict[str, Any]] = []
    packages = [
        package
        for package in discover_packages(root, root / SKILL_ROOT_RELATIVE)
        if has_files(package)
    ]
    known_names = {package.name for package in packages}
    for package in packages:
        skill_file = package / "SKILL.md"
        data: dict[str, Any] = {}
        skill_text = ""
        if skill_file.is_file():
            try:
                skill_text = skill_file.read_text(encoding="utf-8")
                data = parse_frontmatter(skill_text).data
            except (OSError, UnicodeDecodeError, ParseError):
                data = {}
        description = data.get("description") if isinstance(data.get("description"), str) else None
        metadata_file = package / "agents" / "openai.yaml"
        runtime_status = "missing"
        supported: dict[str, Any] = {}
        metadata_text = ""
        if metadata_file.is_file():
            try:
                metadata_text = metadata_file.read_text(encoding="utf-8")
                metadata = parse_mapping(metadata_text)
                runtime_status = "present"
                interface = metadata.get("interface")
                if isinstance(interface, dict):
                    for key in sorted(SUPPORTED_INTERFACE_FIELDS):
                        if isinstance(interface.get(key), str) and interface[key].strip():
                            supported[key] = interface[key].strip()
                policy = metadata.get("policy")
                if isinstance(policy, dict) and isinstance(policy.get("allow_implicit_invocation"), bool):
                    supported["allow_implicit_invocation"] = policy["allow_implicit_invocation"]
            except (OSError, UnicodeDecodeError, ParseError):
                runtime_status = "invalid"
        entries.append(
            {
                "name": package.name,
                "description": description,
                "package_path": display_path(root, package),
                "skill_link": f"skills/{package.name}/SKILL.md",
                "runtime_status": runtime_status,
                "supported": supported,
                "references": _discover_references(package.name, f"{skill_text}\n{metadata_text}", known_names),
            }
        )
    return entries


def generate_catalog(root: Path) -> str:
    entries = _catalog_entries(root)
    lines = [
        "<!-- Generated by bkf skills --write; do not edit manually. -->",
        "# Skill catalog",
        "",
        "This document is generated from the non-empty packages under `agent-skills/skills/`.",
        "It contains only package metadata and supported runtime metadata derived from the repository.",
        "",
        "| Skill | When to use it | Explicit only |",
        "| --- | --- | --- |",
    ]
    for entry in entries:
        explicit = "yes" if entry["supported"].get("allow_implicit_invocation") is False else ""
        lines.append(
            f"| [{entry['name']}]({entry['skill_link']}) | {_markdown_value(entry['description'])} | {explicit} |"
        )
    lines.append("")
    for entry in entries:
        description = entry["description"]
        supported = entry["supported"]
        lines.extend(
            [
                f"## {entry['name']}",
                "",
                f"- Description: {_markdown_value(description)}",
                f"- Package: [`{entry['package_path']}`]({entry['skill_link']})",
                f"- Runtime metadata: `{entry['runtime_status']}`",
            ]
        )
        if supported:
            lines.append("- Supported UI metadata:")
            for key in ("display_name", "short_description"):
                if key in supported:
                    lines.append(f"  - `{key}`: {_markdown_value(supported[key])}")
        if "allow_implicit_invocation" in supported:
            policy_label = "implicit invocation allowed" if supported["allow_implicit_invocation"] else "explicit invocation required"
            lines.append(f"- Runtime policy: `{policy_label}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_catalog(root: Path, output_path: Path | None = None) -> Path:
    root = root.resolve()
    target = (output_path or root / CATALOG_RELATIVE).resolve()
    canonical = (root / CATALOG_RELATIVE).resolve()
    if target != canonical:
        raise ValueError("write mode is limited to agent-skills/SKILL-ARCHITECTURE.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_catalog(root), encoding="utf-8")
    return target

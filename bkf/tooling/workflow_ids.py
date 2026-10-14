"""Allocate hierarchical workflow, work-unit, and stage identifiers."""

from __future__ import annotations

import re
from pathlib import Path

from bkf_common import BKFInputError, rglob_in_bundle


ID_PATTERNS = {
    "W": re.compile(r"\bW-(\d{2})\b"),
    "WU": re.compile(r"\bWU-((?:\d{2})(?:\.\d{2})*)\b"),
    "ST": re.compile(r"\bST-((?:\d{2})(?:\.\d{2})*)\b"),
}


def _mentions(root: Path, kind: str) -> list[tuple[int, ...]]:
    found: list[tuple[int, ...]] = []
    pattern = ID_PATTERNS[kind]
    for path in rglob_in_bundle(root, root, "*.md"):
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise BKFInputError(f"cannot scan {path}: {exc}") from exc
        for match in pattern.finditer(contents):
            found.append(tuple(int(part) for part in match.group(1).split(".")))
    return found


def _next_segment(used: list[tuple[int, ...]], parent: tuple[int, ...]) -> int:
    sequence = [value[-1] for value in used if value[:-1] == parent]
    next_value = max(sequence, default=0) + 1
    if next_value > 99:
        raise BKFInputError(f"ID sequence under {parent or 'bundle'} exceeds 99")
    return next_value


def allocate_workflow_id(root: Path, reserved: list[str] | None = None) -> str:
    mentions = _mentions(root, "W")
    for value in reserved or []:
        if value.startswith("W-"):
            mentions.append((int(value.partition("-")[2]),))
    number = _next_segment(mentions, ())
    identifier = f"W-{number:02d}"
    if reserved is not None:
        reserved.append(identifier)
    return identifier


def allocate_child_id(
    root: Path, kind: str, parent_id: str, reserved: list[str] | None = None
) -> str:
    if kind not in {"WU", "ST"}:
        raise ValueError(f"unsupported child ID kind: {kind}")
    parent_kind, _, parent_value = parent_id.partition("-")
    if (kind == "WU" and parent_kind not in {"W", "WU"}) or (
        kind == "ST" and parent_kind not in {"W", "WU"}
    ):
        raise BKFInputError(f"invalid parent ID for {kind}: {parent_id}")
    try:
        parent = tuple(int(part) for part in parent_value.split("."))
    except ValueError as exc:
        raise BKFInputError(f"invalid parent ID: {parent_id}") from exc
    if not parent or any(part < 1 or part > 99 for part in parent):
        raise BKFInputError(f"invalid parent ID: {parent_id}")
    mentions = _mentions(root, kind)
    for value in reserved or []:
        if value.startswith(kind + "-"):
            mentions.append(tuple(int(part) for part in value.partition("-")[2].split(".")))
    number = _next_segment(mentions, parent)
    identifier = f"{kind}-" + ".".join(f"{part:02d}" for part in (*parent, number))
    if reserved is not None:
        reserved.append(identifier)
    return identifier

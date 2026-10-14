"""Declaration-only workflow checks shared by the validator, scaffold, and sync.

These checks need nothing but the parsed declaration, so they work before IDs
exist: references may be author keys or allocated IDs. Each problem is a
``(code, message)`` pair using the validator's finding codes.
"""

from __future__ import annotations

import re

from bkf_common import BKFInputError

Problem = tuple[str, str]
TAGS = {"stage", "work_unit", "parallel"}
FILE_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def structure_problems(steps: object) -> tuple[list[Problem], bool]:
    """Check tags, required fields, and value types.

    Returns the problems and whether the declaration is walkable, so callers
    can skip checks that need a well-formed structure.
    """
    entries: list[tuple[str, dict]] = []

    def walk(items: object) -> None:
        if not isinstance(items, list):
            raise BKFInputError("steps must be a list")
        for step in items:
            if not isinstance(step, dict) or len(step) != 1:
                raise BKFInputError("each workflow entry must contain exactly one tag")
            tag, entry = next(iter(step.items()))
            if tag not in TAGS:
                raise BKFInputError(f"unknown workflow entry tag: {tag}")
            if tag == "parallel":
                if not isinstance(entry, list) or not entry:
                    raise BKFInputError("parallel list must not be empty")
                walk(entry)
            elif not isinstance(entry, dict):
                raise BKFInputError(f"{tag} value must be a mapping")
            else:
                entries.append((tag, entry))
                if tag == "work_unit":
                    if not isinstance(entry.get("steps"), list) or not entry["steps"]:
                        raise BKFInputError("work unit must have a non-empty steps list")
                    walk(entry["steps"])

    try:
        walk(steps)
    except (BKFInputError, TypeError, KeyError) as exc:
        return [("WORKFLOW_STRUCTURE", str(exc))], False

    problems: list[Problem] = []
    for tag, entry in entries:
        if tag == "stage":
            if not isinstance(entry.get("title"), str) or not entry["title"].strip():
                problems.append(("WORKFLOW_TITLE", "stage title must be a non-empty string"))
            if "human_checkpoint" in entry and not isinstance(entry["human_checkpoint"], bool):
                problems.append(("WORKFLOW_BOOLEAN", "human_checkpoint must be a boolean"))
            if "file" in entry and (
                not isinstance(entry["file"], str) or FILE_NAME_RE.fullmatch(entry["file"]) is None
            ):
                problems.append(("WORKFLOW_FILE_NAME", "file must be a lowercase hyphenated name"))
        else:
            if not isinstance(entry.get("title"), str) or not entry["title"].strip():
                problems.append(("WORKFLOW_TITLE", "work unit title must be a non-empty string"))
            if "work_unit_file" in entry and not isinstance(entry["work_unit_file"], bool):
                problems.append(("WORKFLOW_BOOLEAN", "work_unit_file must be a boolean"))
    return problems, True


def reference_problems(steps: list) -> list[Problem]:
    """Check keys, `reviews` targets, and `after` placement and targets.

    Requires a walkable declaration (see ``structure_problems``).
    """
    problems: list[Problem] = []
    nodes: list[dict] = []
    # entry index -> (directly inside a parallel group, indices of earlier siblings)
    context: dict[int, tuple[bool, list[int]]] = {}

    def visit(items: list, in_parallel: bool = False, previous: list[int] | None = None) -> None:
        for step in items:
            tag, value = next(iter(step.items()))
            if tag == "parallel":
                earlier: list[int] = []
                for child in value:
                    child_tag = next(iter(child))
                    index = len(nodes)
                    visit([child], True, earlier)
                    if child_tag in {"stage", "work_unit"}:
                        earlier.append(index)
                continue
            index = len(nodes)
            nodes.append(value)
            context[index] = (in_parallel, list(previous or []))
            if tag == "work_unit":
                visit(value["steps"])

    visit(steps)

    by_key: dict[str, int] = {}
    by_id: dict[str, int] = {}
    for index, entry in enumerate(nodes):
        if isinstance(entry.get("id"), str):
            by_id[entry["id"]] = index
        key = entry.get("key")
        if key is not None:
            if not isinstance(key, str) or not key.strip() or key in by_key:
                problems.append(("WORKFLOW_KEY", f"workflow key must be unique and non-empty: {key!r}"))
            else:
                by_key[key] = index

    def resolve(target: object) -> int | None:
        if not isinstance(target, str):
            return None
        return by_key[target] if target in by_key else by_id.get(target)

    for index, entry in enumerate(nodes):
        in_parallel, earlier = context[index]
        if entry.get("reviews") is not None:
            targets = entry["reviews"]
            if not isinstance(targets, list):
                problems.append(("WORKFLOW_REVIEW", "reviews must be a list"))
                targets = []
            for target in targets:
                found = resolve(target)
                if found is None or found >= index:
                    problems.append(("WORKFLOW_REVIEW", f"reviews target must exist earlier: {target}"))
        if "after" in entry:
            targets = entry["after"]
            if not in_parallel:
                problems.append(("WORKFLOW_AFTER", "after is valid only directly inside a parallel group"))
            if not isinstance(targets, list):
                problems.append(("WORKFLOW_AFTER", "after must be a list"))
                targets = []
            for target in targets:
                if resolve(target) not in earlier:
                    problems.append((
                        "WORKFLOW_AFTER",
                        f"after target must be an earlier sibling in the same parallel group: {target}",
                    ))
    return problems


def declaration_problems(steps: object) -> list[Problem]:
    """All declaration-only problems, for callers that act before writing files."""
    problems, walkable = structure_problems(steps)
    if walkable:
        problems.extend(reference_problems(steps))  # type: ignore[arg-type]
    return problems


def require_valid_declaration(steps: object) -> None:
    """Raise one error listing every problem, so callers write nothing."""
    problems = declaration_problems(steps)
    if problems:
        details = "\n".join(f"  - {message}" for _, message in problems)
        raise BKFInputError(f"the declaration is invalid; nothing was written:\n{details}")

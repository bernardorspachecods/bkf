"""Parse and update the YAML declaration embedded in a workflow parent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bkf_common import BKFInputError, read_text_preserving_newlines
from workflow_ids import allocate_child_id


BLOCK_RE = re.compile(r"(?ms)^```bkf-workflow\r?\n(.*?)^```[ \t]*$", re.MULTILINE)
ID_RE = re.compile(r"^(?:W-\d{2}|WU-\d{2}(?:\.\d{2})+|ST-\d{2}(?:\.\d{2})+)$")


@dataclass
class Declaration:
    path: Path
    text: str
    block: str
    data: object
    match: re.Match[str]

    @property
    def steps(self) -> list[dict[str, object]]:
        if not isinstance(self.data, dict) or not isinstance(self.data.get("steps"), list):
            raise BKFInputError("bkf-workflow block must contain a steps list")
        return self.data["steps"]


def roundtrip_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.allow_duplicate_keys = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_declaration(path: Path) -> Declaration:
    text = read_text_preserving_newlines(path)
    matches = list(BLOCK_RE.finditer(text))
    if len(matches) != 1:
        raise BKFInputError(f"{path}: expected exactly one bkf-workflow block, found {len(matches)}")
    match = matches[0]
    block = match.group(1)
    data = parse_declaration_block(path, block)
    declaration = Declaration(path, text, block, data, match)
    declaration.steps
    return declaration


def parse_declaration_block(path: Path, block: str) -> object:
    try:
        return roundtrip_yaml().load(block)
    except YAMLError as exc:
        raise BKFInputError(f"{path}: invalid bkf-workflow YAML: {exc}") from exc


def _tagged(step: object) -> tuple[str, object]:
    if not isinstance(step, dict) or len(step) != 1:
        raise BKFInputError("each workflow step must be a single-key tagged mapping")
    tag, value = next(iter(step.items()))
    if tag not in {"stage", "work_unit", "parallel"}:
        raise BKFInputError(f"unknown workflow step tag: {tag}")
    return str(tag), value


def _walk(step_list: list[object]):
    for step in step_list:
        tag, value = _tagged(step)
        if tag == "parallel":
            if not isinstance(value, list):
                raise BKFInputError("parallel value must be a list")
            yield from _walk(value)
        elif tag == "work_unit":
            if not isinstance(value, dict):
                raise BKFInputError("work_unit value must be a mapping")
            yield tag, value
            children = value.get("steps")
            if not isinstance(children, list):
                raise BKFInputError("work unit steps must be a list")
            yield from _walk(children)
        else:
            if not isinstance(value, dict):
                raise BKFInputError("stage value must be a mapping")
            yield tag, value


def _resolve_references(steps: list[object]) -> None:
    keys: dict[str, str] = {}
    entries: list[dict[str, object]] = []
    for _, entry in _walk(steps):
        entries.append(entry)
        key = entry.get("key")
        if key is not None:
            if not isinstance(key, str) or not key.strip() or key in keys:
                raise BKFInputError(f"workflow keys must be unique non-empty strings: {key!r}")
            keys[key] = str(entry.get("id", ""))
    for entry in entries:
        for field in ("reviews", "after"):
            value = entry.get(field)
            if value is None:
                continue
            if not isinstance(value, list):
                raise BKFInputError(f"{field} must be a list")
            resolved: list[str] = []
            for target in value:
                if not isinstance(target, str):
                    raise BKFInputError(f"{field} targets must be strings")
                identifier = keys.get(target, target)
                if not ID_RE.fullmatch(identifier):
                    raise BKFInputError(f"unresolved {field} target {target!r}")
                resolved.append(identifier)
            entry[field] = resolved


def assign_ids(declaration: Declaration, root: Path, workflow_id: str) -> None:
    """Fill missing step IDs and resolve key references in declaration order."""
    reserved: list[str] = []

    def assign(steps: list[object], parent_id: str) -> None:
        for step in steps:
            tag, value = _tagged(step)
            if tag == "parallel":
                if not isinstance(value, list) or not value:
                    raise BKFInputError("parallel must contain at least one step")
                assign(value, parent_id)
                continue
            assert isinstance(value, dict)
            kind = "WU" if tag == "work_unit" else "ST"
            identifier = value.get("id")
            if identifier is None:
                identifier = allocate_child_id(root, kind, parent_id, reserved)
                value["id"] = identifier
            if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
                raise BKFInputError(f"invalid {kind} identifier: {identifier!r}")
            if kind == "WU":
                children = value.get("steps")
                if not isinstance(children, list) or not children:
                    raise BKFInputError("work unit must contain a non-empty steps list")
                assign(children, identifier)
            else:
                if not isinstance(value.get("title"), str) or not value["title"].strip():
                    raise BKFInputError("stage title must be a non-empty string")

    assign(declaration.steps, workflow_id)
    _resolve_references(declaration.steps)


def render_declaration(declaration: Declaration) -> str:
    yaml = roundtrip_yaml()
    import io

    output = io.StringIO()
    yaml.dump(declaration.data, output)
    replacement = output.getvalue().rstrip("\r\n")
    if declaration.block.endswith("\r\n"):
        replacement += "\r\n"
    elif declaration.block.endswith("\n"):
        replacement += "\n"
    original = declaration.text
    return original[: declaration.match.start(1)] + replacement + original[declaration.match.end(1) :]


def write_declaration(declaration: Declaration) -> None:
    declaration.path.write_text(render_declaration(declaration), encoding="utf-8", newline="")


def walk_entries(steps: list[object]):
    """Yield (tag, entry, ancestor-unit-ids) in declared order."""
    def walk(items: list[object], ancestors: tuple[str, ...]):
        for step in items:
            tag, value = _tagged(step)
            if tag == "parallel":
                yield from walk(value, ancestors)
            elif tag == "work_unit":
                yield tag, value, ancestors
                yield from walk(value["steps"], ancestors + (value["id"],))
            else:
                yield tag, value, ancestors
    yield from walk(steps, ())

"""Shared path, frontmatter, and scaffold helpers for workflow tooling."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.error import YAMLError

from bkf_common import BKFInputError, ParsedMarkdown, parse_markdown, read_text_preserving_newlines
from workflow_declaration import BLOCK_RE, Declaration, render_declaration


def slug(value: str, *, words: int | None = None, limit: int = 48) -> str:
    value = value.lower()
    if words is not None:
        # Title words are whitespace-separated; punctuation inside a word is removed.
        pieces = [w for w in (re.sub(r"[^a-z0-9]", "", raw) for raw in value.split()) if w][:words]
    else:
        value = re.sub(r"[^a-z0-9\s-]", "", value)
        pieces = re.findall(r"[a-z0-9]+", value)
    result = "-".join(pieces)[:limit].strip("-")
    return result or "stage"


def frontmatter_text(metadata: dict[str, object], body: str = "") -> str:
    import io

    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    out = io.StringIO()
    yaml.dump(metadata, out)
    return "---\n" + out.getvalue() + "---\n\n" + body


def update_frontmatter(path: Path, updates: dict[str, object]) -> str:
    original = read_text_preserving_newlines(path)
    lines = original.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise BKFInputError(f"{path}: expected YAML frontmatter")
    closing = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") == "---"), None)
    if closing is None:
        raise BKFInputError(f"{path}: unterminated YAML frontmatter")
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.allow_duplicate_keys = False
    try:
        metadata = yaml.load("".join(lines[1:closing]))
    except YAMLError as exc:
        raise BKFInputError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise BKFInputError(f"{path}: frontmatter must be a mapping")
    for key, value in updates.items():
        metadata[key] = value
    import io
    output = io.StringIO()
    yaml.dump(metadata, output)
    ending = "\r\n" if "\r\n" in original else "\n"
    return "---" + ending + output.getvalue() + "---" + ending + "".join(lines[closing + 1 :])


def replace_body_declaration(parent_text: str, source_path: Path, declaration: Declaration) -> str:
    rendered = render_declaration(declaration)
    original_match = BLOCK_RE.search(declaration.text)
    rendered_match = BLOCK_RE.search(rendered)
    if original_match is None or rendered_match is None:
        raise BKFInputError(f"{source_path}: cannot replace bkf-workflow declaration")
    body_match = BLOCK_RE.search(parent_text)
    if body_match is None:
        raise BKFInputError(f"{source_path}: parent body lost its bkf-workflow block")
    return parent_text[: body_match.start(1)] + rendered_match.group(1) + parent_text[body_match.end(1) :]


@dataclass
class PlannedFile:
    identifier: str
    kind: str
    path: Path
    metadata: dict[str, object]
    body: str
    folder: Path | None = None


def parent_title(body: str) -> str:
    for line in body.splitlines():
        found = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if found:
            return found.group(1).strip()
    raise BKFInputError("workflow parent must have a top-level heading")


def build_layout(workflow_folder: Path, workflow_id: str, steps: list[object]) -> list[PlannedFile]:
    planned: list[PlannedFile] = []
    shared: dict[str, PlannedFile] = {}

    def direct_steps(items: list[object]):
        for step in items:
            tag, entry = next(iter(step.items()))
            if tag == "parallel":
                yield from direct_steps(entry)
            else:
                yield tag, entry

    def scan(items: list[object], folder: Path) -> None:
        ordinal = 0
        for tag, entry in direct_steps(items):
            ordinal += 1
            if tag == "work_unit":
                unit_id = entry["id"]
                unit_folder = folder / f"{ordinal:02d}-{unit_id}-{slug(entry['title'])}"
                unit_meta = {
                    "bkf": "workflow.work_unit", "work_unit_id": unit_id,
                }
                planned.append(PlannedFile(unit_id, "work_unit", unit_folder / "WORK-UNIT.md", unit_meta,
                                           f"# {entry['title']}\n" if entry.get("work_unit_file") is True else "",
                                           unit_folder))
                scan(entry["steps"], unit_folder)
            elif tag == "stage":
                stage_id = entry["id"]
                if entry.get("file"):
                    key = entry["file"]
                    if key not in shared:
                        shared_meta = {"bkf": "workflow.file", "stage_ids": [stage_id]}
                        shared_body = f"# {entry['file']}\n\n## {stage_id} — {entry['title']}\n"
                        if entry.get("human_checkpoint") is True:
                            shared_body += "\nHuman checkpoint: approval is required after this stage.\n"
                        item = PlannedFile(stage_id, "shared", folder / f"{ordinal:02d}-{entry['file']}.md",
                                           shared_meta, shared_body)
                        shared[key] = item
                        planned.append(item)
                    else:
                        item = shared[key]
                        item.metadata["stage_ids"].append(stage_id)
                        item.body += f"\n## {stage_id} — {entry['title']}\n"
                        if entry.get("human_checkpoint") is True:
                            item.body += "\nHuman checkpoint: approval is required after this stage.\n"
                else:
                    meta = {"bkf": "workflow.stage", "stage_id": stage_id}
                    if entry.get("reviews"):
                        meta["reviews"] = list(entry["reviews"])
                    if entry.get("human_checkpoint") is True:
                        meta["human_checkpoint"] = True
                    name = f"{ordinal:02d}-{slug(entry['title'], words=2)}.md"
                    planned.append(PlannedFile(stage_id, "stage", folder / name, meta,
                                               f"# {entry['title']}\n"))

    scan(steps, workflow_folder)
    return planned


def write_new_file(path: Path, metadata: dict[str, object], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter_text(metadata, body), encoding="utf-8", newline="")


def get_title_and_body(path: Path) -> tuple[str, ParsedMarkdown]:
    parsed = parse_markdown(path)
    return parent_title(parsed.body), parsed

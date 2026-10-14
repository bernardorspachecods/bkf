"""Scaffold a workflow folder and its declared work-unit and stage files."""

from __future__ import annotations

import argparse
import difflib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from bkf_common import BKFInputError, parse_markdown
from workflow_declaration import assign_ids, load_declaration
from workflow_declaration_checks import require_valid_declaration
from workflow_files import build_layout, frontmatter_text, get_title_and_body, replace_body_declaration, slug
from workflow_ids import allocate_workflow_id


def bundle_root(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if (candidate / "MAP.md").is_file():
            return candidate
    raise BKFInputError(f"no bundle root MAP.md found above {path}")


@dataclass
class ScaffoldPlan:
    root: Path
    parent: Path
    parent_target: Path
    folder: Path
    parent_text: str
    layout: list


def plan_scaffold(parent: Path) -> ScaffoldPlan:
    parent = parent.resolve()
    root = bundle_root(parent)
    title, parsed = get_title_and_body(parent)
    if parsed.frontmatter.get("bkf") == "workflow" or "workflow_id" in parsed.frontmatter:
        raise BKFInputError(f"{parent.name} is already a scaffolded workflow; sync it from its workflow folder")
    declaration = load_declaration(parent)
    require_valid_declaration(declaration.steps)
    attempted: list[str] = []
    workflow_id = allocate_workflow_id(root, attempted)
    while (parent.parent / f"{workflow_id}-{slug(title)}").exists():
        workflow_id = allocate_workflow_id(root, attempted)

    assign_ids(declaration, root, workflow_id)
    metadata = dict(parsed.frontmatter)
    metadata.update({
        "bkf": "workflow",
        "description": metadata.get("description") or "Defines the composed workflow and its execution order.",
        "workflow_id": workflow_id,
    })
    parent_text = frontmatter_text(metadata, parsed.body.lstrip("\r\n"))
    parent_text = replace_body_declaration(parent_text, parent, declaration)
    folder = parent.parent / f"{workflow_id}-{slug(title)}"
    layout = build_layout(folder, workflow_id, declaration.steps)
    return ScaffoldPlan(root, parent, folder / f"{workflow_id}.md", folder, parent_text, layout)


def print_scaffold_plan(plan: ScaffoldPlan) -> None:
    print(f"create directory: {plan.folder}")
    print(f"move: {plan.parent} -> {plan.parent_target}")
    original = plan.parent.read_text(encoding="utf-8")
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        plan.parent_text.splitlines(keepends=True),
        fromfile=str(plan.parent),
        tofile=str(plan.parent_target),
    )
    sys.stdout.writelines(diff)
    for item in plan.layout:
        if item.kind == "work_unit" and item.body == "":
            print(f"create directory: {item.folder}")
        else:
            print(f"create: {item.path} ({item.kind})")


def apply_scaffold_plan(plan: ScaffoldPlan) -> Path:
    if plan.folder.exists():
        raise BKFInputError(f"workflow folder destination already exists: {plan.folder}")
    try:
        plan.folder.mkdir()
        plan.parent_target.write_text(plan.parent_text, encoding="utf-8", newline="")
        for item in plan.layout:
            if item.kind == "work_unit" and item.body == "":
                item.path.parent.mkdir(parents=True, exist_ok=True)
                continue
            item.path.parent.mkdir(parents=True, exist_ok=True)
            item.path.write_text(frontmatter_text(item.metadata, item.body), encoding="utf-8", newline="")
        plan.parent.unlink()
        return plan.parent_target
    except Exception:
        shutil.rmtree(plan.folder, ignore_errors=True)
        raise


def scaffold(parent: Path) -> Path:
    """Apply a first-time sync plan; retained for the CLI alias and test setup."""
    return apply_scaffold_plan(plan_scaffold(parent))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path, help="workflow parent Markdown file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = scaffold(args.parent)
    except (BKFInputError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"scaffolded: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

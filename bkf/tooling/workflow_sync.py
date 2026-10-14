"""Preview or apply declaration-driven workflow file synchronization."""

from __future__ import annotations

import re
import argparse
import os
import sys
import uuid
from pathlib import Path

from bkf_common import BKFInputError, parse_markdown, rglob_in_bundle
from workflow_declaration import assign_ids, load_declaration, render_declaration
from workflow_declaration_checks import require_valid_declaration
from workflow_files import build_layout, get_title_and_body, slug, update_frontmatter
from workflow_scaffold import (
    apply_scaffold_plan,
    bundle_root,
    plan_scaffold,
    print_scaffold_plan,
)


def _frontmatter(path: Path) -> dict[str, object] | None:
    try:
        return parse_markdown(path).frontmatter
    except BKFInputError:
        return None


def sync(parent: Path, *, write: bool = False, confirm_in_progress: bool = False) -> int:
    parent = parent.resolve()
    root = bundle_root(parent)
    metadata = parse_markdown(parent).frontmatter
    workflow_id = metadata.get("workflow_id")
    if not isinstance(workflow_id, str):
        if metadata.get("bkf") == "workflow":
            raise BKFInputError("workflow parent must have workflow_id before sync")
        plan = plan_scaffold(parent)
        if not write:
            print_scaffold_plan(plan)
            return 0
        target = apply_scaffold_plan(plan)
        print(f"workflow scaffolded: {target}")
        return 0
    title, _ = get_title_and_body(parent)
    folder = parent.parent
    declaration = load_declaration(parent)
    require_valid_declaration(declaration.steps)
    assign_ids(declaration, root, workflow_id)
    expected = build_layout(folder, workflow_id, declaration.steps)
    expected_ids = {item.identifier for item in expected}
    expected_ids.update(stage_id for item in expected if item.kind == "shared" for stage_id in item.metadata["stage_ids"])

    actual: dict[str, tuple[Path, dict[str, object], str]] = {}
    orphan_paths: list[Path] = []
    shared: list[tuple[Path, dict[str, object]]] = []
    unit_dirs: dict[str, Path] = {}
    for path in sorted(rglob_in_bundle(root, folder, "*.md")):
        if path == parent:
            continue
        front = _frontmatter(path)
        if not front:
            continue
        if front.get("bkf") == "workflow.stage" and isinstance(front.get("stage_id"), str):
            actual[front["stage_id"]] = (path, front, "stage")
        elif front.get("bkf") == "workflow.work_unit" and isinstance(front.get("work_unit_id"), str):
            actual[front["work_unit_id"]] = (path, front, "work_unit")
        elif front.get("bkf") == "workflow.file":
            shared.append((path, front))
    for directory in (p for p in rglob_in_bundle(root, folder, "*") if p.is_dir()):
        # Use only the folder's own name; ancestor names belong to other units.
        match = re.search(r"WU-\d{2}(?:\.\d{2})+", directory.name)
        if match:
            unit_dirs[match.group(0)] = directory

    mapping: list[tuple[Path, Path, dict[str, object], str]] = []
    consumed_shared: set[Path] = set()
    for item in expected:
        if item.kind == "shared":
            ids = set(item.metadata["stage_ids"])
            matches = [(p, f) for p, f in shared if ids.intersection(set(f.get("stage_ids", [])))]
            if matches:
                source, front = matches[0]
                consumed_shared.add(source)
                mapping.append((source, item.path, item.metadata, "shared"))
            else:
                mapping.append((Path(), item.path, item.metadata, "shared"))
            continue
        if item.kind == "work_unit":
            unit_dir = unit_dirs.get(item.identifier)
            if unit_dir is not None and unit_dir != item.folder:
                mapping.append((unit_dir, item.folder, {}, "directory"))
        match = actual.get(item.identifier)
        if match:
            mapping.append((match[0], item.path, item.metadata, item.kind))
        elif item.kind == "work_unit" and item.body and item.path.name == "WORK-UNIT.md":
            mapping.append((Path(), item.path, item.metadata, item.kind))
        elif item.kind == "work_unit":
            unit_dir = unit_dirs.get(item.identifier)
            if unit_dir is None:
                mapping.append((Path(), item.folder, {}, "directory"))
        else:
            mapping.append((Path(), item.path, item.metadata, item.kind))

    declared_ids = {item.identifier for item in expected}
    for identifier, (path, _, _) in actual.items():
        if identifier not in declared_ids:
            orphan_paths.append(path)
    for path, front in shared:
        declared = any(set(item.metadata["stage_ids"]).intersection(set(front.get("stage_ids", []))) for item in expected if item.kind == "shared")
        if not declared:
            orphan_paths.append(path)
    for identifier, path in unit_dirs.items():
        if identifier not in expected_ids:
            orphan_paths.append(path)

    # The workflow folder itself follows the parent heading slug.
    folder_target = folder.parent / f"{workflow_id}-{slug(title)}"
    if folder_target != folder:
        mapping.append((folder, folder_target, {}, "directory"))
    parent_target = folder_target / f"{workflow_id}.md"
    if parent_target != parent:
        mapping.append((parent, parent_target, {}, "parent"))

    rename_pairs = [(src, dst) for src, dst, _, _ in mapping if src != Path() and src != dst]
    additions = [(dst, meta, kind) for src, dst, meta, kind in mapping if src == Path() and kind != "directory"]
    new_directories = [(dst, kind) for src, dst, _, kind in mapping if src == Path() and kind == "directory"]
    updates = [(src, dst, meta) for src, dst, meta, kind in mapping if src != Path() and kind == "shared"]
    in_progress = isinstance(metadata.get("unit_status"), dict) and "in_progress" in metadata["unit_status"].values()
    if rename_pairs and in_progress:
        print("WARNING: a work unit is in_progress; renames may disrupt an agent writing to these files.")
        if write and not confirm_in_progress:
            raise BKFInputError("refusing writes with renames while in_progress; pass --confirm-in-progress after judging it safe")

    for source, destination in rename_pairs:
        print(f"rename: {source} -> {destination}")
    for destination, _, kind in additions:
        print(f"create: {destination} ({kind})")
    for destination, _ in new_directories:
        print(f"create directory: {destination}")
    for source in orphan_paths:
        print(f"orphan: {source}")
    if any(source != destination for source, destination in rename_pairs):
        print("References to renamed paths are the agent's responsibility to update.")
    for source, destination, meta in updates:
        if _frontmatter(source).get("stage_ids") != meta.get("stage_ids"):
            print(f"update frontmatter: {source} stage_ids -> {meta['stage_ids']}")
            print("Add a section for the joining stage to the shared file body; sync leaves the body untouched.")
    shared_changes = any(
        _frontmatter(source).get("stage_ids") != meta.get("stage_ids")
        for source, _, meta in updates if _frontmatter(source) is not None
    )
    declaration_changes = render_declaration(declaration) != declaration.text
    if not rename_pairs and not additions and not new_directories and not orphan_paths and not shared_changes and not declaration_changes:
        print("workflow is synchronized")
    if not write:
        return 0

    # Move matched files to a temporary holding directory, then rename folders
    # in two phases so sequence changes and swaps cannot collide.
    holding = root / f".bkf-sync-{uuid.uuid4().hex}"
    file_holding: list[tuple[Path, Path]] = []
    directory_moves = [(src, dst) for src, dst, _, kind in mapping
                       if src != Path() and kind == "directory" and src != folder]
    root_move = folder_target != folder
    committed_dirs: list[tuple[Path, Path]] = []

    def transform(path: Path, moves: list[tuple[Path, Path]]) -> Path:
        applicable = [(old, new) for old, new in moves if path == old or old in path.parents]
        if not applicable:
            return path
        old, new = max(applicable, key=lambda pair: len(pair[0].parts))
        return new / path.relative_to(old)

    try:
        holding.mkdir()
        for index, (source, destination, _, kind) in enumerate(mapping):
            if source == Path() or source == destination or kind in {"directory", "parent"}:
                continue
            if source.is_file():
                temp = holding / f"{index:04d}-{source.name}"
                source.rename(temp)
                file_holding.append((temp, destination))

        staged: list[tuple[Path, Path, str]] = []
        for source, destination in sorted(directory_moves, key=lambda pair: len(pair[0].parts), reverse=True):
            if not source.exists():
                continue
            temp_name = f".bkf-sync-{uuid.uuid4().hex}"
            temp = source.with_name(temp_name)
            source.rename(temp)
            staged.append((source, destination, temp_name))
        for source, destination, temp_name in sorted(staged, key=lambda item: len(item[0].parts)):
            current_parent = transform(source.parent, committed_dirs)
            temp = current_parent / temp_name
            if destination.exists():
                raise BKFInputError(f"rename destination already exists: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp.rename(destination)
            committed_dirs.append((source, destination))

        if root_move:
            if folder_target.exists():
                raise BKFInputError(f"workflow folder destination already exists: {folder_target}")
            folder.rename(folder_target)

        for temp, destination in file_holding:
            destination = transform(destination, [(folder, folder_target)] if root_move else [])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise BKFInputError(f"rename destination already exists: {destination}")
            temp.rename(destination)

        for source, destination, meta in updates:
            destination = transform(destination, [(folder, folder_target)] if root_move else [])
            if destination.exists():
                content = update_frontmatter(destination, {"stage_ids": meta["stage_ids"]})
                destination.write_text(content, encoding="utf-8", newline="")
        for destination, meta, kind in additions:
            destination = transform(destination, [(folder, folder_target)] if root_move else [])
            if kind == "work_unit" and not meta:
                destination.mkdir(parents=True, exist_ok=True)
            else:
                from workflow_files import write_new_file
                item = next(i for i in expected if i.path == destination)
                write_new_file(destination, meta, item.body)
        for destination, _ in new_directories:
            destination = transform(destination, [(folder, folder_target)] if root_move else [])
            destination.mkdir(parents=True, exist_ok=True)
        from workflow_files import replace_body_declaration
        target_parent = transform(parent, [(folder, folder_target)] if root_move else [])
        parent_content = target_parent.read_text(encoding="utf-8")
        parent_content = replace_body_declaration(parent_content, target_parent, declaration)
        target_parent.write_text(parent_content, encoding="utf-8", newline="")
        holding.rmdir()
    except Exception:
        raise
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or synchronize workflow files, including first-time scaffolding.")
    parser.add_argument("parent", type=Path)
    parser.add_argument("--write", action="store_true", help="apply the synchronization plan")
    parser.add_argument("--confirm-in-progress", action="store_true", help="confirm renames are safe while work is in progress")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return sync(args.parent, write=args.write, confirm_in_progress=args.confirm_in_progress)
    except (BKFInputError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""The twelve BKF workflow declaration and file checks."""

from __future__ import annotations

import re
from pathlib import Path

from bkf_common import BKFInputError, parse_markdown, rglob_in_bundle
from workflow_declaration import BLOCK_RE, ID_RE, load_declaration, parse_declaration_block, walk_entries
from workflow_declaration_checks import declaration_problems, reference_problems, structure_problems
from workflow_files import build_layout, parent_title, slug


class WorkflowChecks:
    def __init__(self, root: Path, error, warning):
        self.root = root
        self.error = error
        self.warning = warning

    def validate_parent(self, parent: Path) -> None:
        try:
            declaration = load_declaration(parent)
        except BKFInputError as exc:
            self.error("WORKFLOW_DECLARATION", parent, str(exc))
            return
        metadata = parse_markdown(parent).frontmatter
        workflow_id = metadata.get("workflow_id")
        if not isinstance(workflow_id, str):
            self.error("WORKFLOW_ID", parent, "workflow_id must be a W identifier")
            return
        steps = declaration.steps
        if not self._structure(parent, steps):
            return
        self._ids(parent, workflow_id, steps)
        for code, message in reference_problems(steps):
            self.error(code, parent, message)
        try:
            self._files(parent, workflow_id, steps, metadata)
        except (BKFInputError, KeyError, TypeError) as exc:
            self.error("WORKFLOW_FILES", parent, str(exc))
        self._status(parent, metadata, steps)

    def validate_embedded_declarations(self, document: Path) -> None:
        text = document.read_text(encoding="utf-8")
        for match in BLOCK_RE.finditer(text):
            try:
                data = parse_declaration_block(document, match.group(1))
                steps = data.get("steps") if isinstance(data, dict) else None
                problems = declaration_problems(steps)
            except (BKFInputError, TypeError, AttributeError) as exc:
                self.error("WORKFLOW_DECLARATION", document, str(exc))
                continue
            for code, message in problems:
                self.error(code, document, message)

    def _structure(self, parent: Path, steps: list[object]) -> bool:
        problems, walkable = structure_problems(steps)
        for code, message in problems:
            self.error(code, parent, message)
        return walkable

    def _ids(self, parent: Path, workflow_id: str, steps: list[object]) -> None:
        seen: set[str] = set()

        def visit(items: list[object], parent_id: str) -> None:
            for step in items:
                tag, entry = next(iter(step.items()))
                if tag == "parallel":
                    visit(entry, parent_id)
                    continue
                identifier = entry.get("id")
                expected_kind = "WU" if tag == "work_unit" else "ST"
                if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier) or not identifier.startswith(expected_kind + "-"):
                    self.error("WORKFLOW_ID", parent, f"invalid {expected_kind} identifier {identifier!r}")
                else:
                    numeric = identifier.partition("-")[2].split(".")
                    if any(int(part) < 1 or int(part) > 99 for part in numeric):
                        self.error("WORKFLOW_ID", parent, f"ID segments must be between 01 and 99: {identifier}")
                    if identifier in seen:
                        self.error("WORKFLOW_ID_DUPLICATE", parent, f"duplicate workflow identifier {identifier}")
                    seen.add(identifier)
                    parts = identifier.partition("-")[2].split(".")
                    parent_parts = parent_id.partition("-")[2].split(".")
                    if parts[:-1] != parent_parts:
                        self.error("WORKFLOW_ID_PARENT", parent, f"{identifier} does not belong under {parent_id}")
                if tag == "work_unit":
                    visit(entry.get("steps", []), identifier if isinstance(identifier, str) else parent_id)

        if not re.fullmatch(r"W-(?:0[1-9]|[1-9]\d)", workflow_id):
            self.error("WORKFLOW_ID", parent, f"invalid workflow_id {workflow_id!r}")
        visit(steps, workflow_id)

    def _files(self, parent: Path, workflow_id: str, steps: list[object], metadata: dict[str, object]) -> None:
        folder = parent.parent
        expected_folder = folder.parent / f"{workflow_id}-{slug(parent_title(parse_markdown(parent).body))}"
        if expected_folder != folder:
            self.warning("WORKFLOW_NAME_DRIFT", parent, f"expected workflow folder name {expected_folder.name}")
        if parent.name != f"{workflow_id}.md":
            self.warning("WORKFLOW_NAME_DRIFT", parent, f"expected parent filename {workflow_id}.md")
        expected = build_layout(folder, workflow_id, steps)
        stage_files: dict[str, tuple[Path, dict[str, object]]] = {}
        work_files: dict[str, tuple[Path, dict[str, object]]] = {}
        shared_files: list[tuple[Path, dict[str, object]]] = []
        for path in rglob_in_bundle(self.root, folder, "*.md"):
            if path == parent:
                continue
            try:
                front = parse_markdown(path).frontmatter
            except BKFInputError:
                continue
            profile = front.get("bkf")
            if profile == "workflow.stage" and isinstance(front.get("stage_id"), str):
                stage_files[front["stage_id"]] = (path, front)
            elif profile == "workflow.work_unit" and isinstance(front.get("work_unit_id"), str):
                work_files[front["work_unit_id"]] = (path, front)
            elif profile == "workflow.file":
                shared_files.append((path, front))

        expected_ids = {item.identifier for item in expected}
        declared_stage = {item.identifier: item for item in expected if item.kind == "stage"}
        declared_units = {item.identifier: item for item in expected if item.kind == "work_unit"}
        declared_shared = {tuple(item.metadata["stage_ids"]): item for item in expected if item.kind == "shared"}
        for identifier, item in declared_stage.items():
            match = stage_files.get(identifier)
            if match is None:
                self.error("WORKFLOW_FILE_MISSING", parent, f"stage {identifier} has no file")
                continue
            path, front = match
            if front.get("stage_id") != identifier:
                self.error("WORKFLOW_FILE_ID", path, "stage_id does not match the declaration")
            entry = next(e for t, e, _ in walk_entries(steps) if t == "stage" and e.get("id") == identifier)
            expected_checkpoint = True if entry.get("human_checkpoint") is True else None
            if front.get("human_checkpoint") is not expected_checkpoint:
                self.error("WORKFLOW_CHECKPOINT", path, "human_checkpoint does not match the declaration")
            if path != item.path:
                self.warning("WORKFLOW_NAME_DRIFT", path, f"expected generated path {item.path.relative_to(folder)}")
        for identifier, item in declared_units.items():
            # Every unit owns a folder; WORK-UNIT.md is optional.
            folder_pattern = re.compile(rf"^\d{{2}}-(WU-{re.escape(identifier.partition('-')[2])})-")
            actual_unit_folder = next((p for p in rglob_in_bundle(self.root, folder, "*") if p.is_dir() and folder_pattern.match(p.name)), None)
            if actual_unit_folder is None:
                self.error("WORKFLOW_UNIT_FOLDER", parent, f"work unit {identifier} has no generated folder")
                continue
            if actual_unit_folder != item.folder:
                self.warning("WORKFLOW_NAME_DRIFT", actual_unit_folder, f"expected generated path {item.folder.relative_to(folder)}")
            match = work_files.get(identifier)
            unit_entry = next(e for t, e, _ in walk_entries(steps) if t == "work_unit" and e.get("id") == identifier)
            if unit_entry.get("work_unit_file") is True and match is None:
                self.error("WORKFLOW_FILE_MISSING", parent, f"work unit {identifier} requests WORK-UNIT.md but has none")
            if match and match[0].parent.name != actual_unit_folder.name:
                self.error("WORKFLOW_UNIT_FOLDER_ID", match[0], "work_unit_id does not match its folder name")
            if match:
                folder_id = re.match(r"^\d{2}-(WU-\d{2}(?:\.\d{2})+)-", match[0].parent.name)
                if folder_id is None or folder_id.group(1) != identifier:
                    self.error("WORKFLOW_UNIT_FOLDER_ID", match[0], "work_unit_id does not match the ID in its folder name")
            if match and match[0] != item.path:
                self.warning("WORKFLOW_NAME_DRIFT", match[0], f"expected generated path {item.path.relative_to(folder)}")
            elif not match and item.path.exists():
                self.error("WORKFLOW_UNIT_FILE_ID", item.path, "work-unit file lacks its work_unit_id frontmatter")
        for path, front in shared_files:
            if {"stage_id", "reviews", "human_checkpoint"}.intersection(front):
                self.error("WORKFLOW_SHARED_STAGE_FIELDS", path, "shared files must not carry per-stage frontmatter")
            stage_ids = front.get("stage_ids")
            if not isinstance(stage_ids, list):
                self.error("WORKFLOW_SHARED_IDS", path, "shared file stage_ids must be a list")
                continue
            matches = [item for key, item in declared_shared.items() if set(key) == set(stage_ids)]
            if len(matches) != 1:
                self.error("WORKFLOW_SHARED_IDS", path, "shared file stage_ids do not match the declaration")
            elif path != matches[0].path:
                self.warning("WORKFLOW_NAME_DRIFT", path, f"expected generated path {matches[0].path.relative_to(folder)}")
        for item in expected:
            if item.kind == "shared" and not any(set(f.get("stage_ids", [])) == set(item.metadata["stage_ids"]) for _, f in shared_files):
                self.error("WORKFLOW_FILE_MISSING", parent, f"shared file for {', '.join(item.metadata['stage_ids'])} is missing")

    def _status(self, parent: Path, metadata: dict[str, object], steps: list[object]) -> None:
        execution = metadata.get("execution_status")
        valid = {"not_started", "in_progress", "blocked", "complete"}
        if execution is not None and execution not in valid:
            self.error("WORKFLOW_STATUS", parent, "execution_status has an unsupported value")
        units = {entry.get("id") for tag, entry, _ in walk_entries(steps) if tag == "work_unit"}
        unit_status = metadata.get("unit_status", {})
        if not isinstance(unit_status, dict):
            self.error("WORKFLOW_UNIT_STATUS", parent, "unit_status must be a mapping")
            return
        for identifier, status in unit_status.items():
            if identifier not in units:
                self.error("WORKFLOW_UNIT_STATUS", parent, f"unit_status key is not a declared work unit: {identifier}")
            if status not in {"in_progress", "blocked", "complete"}:
                self.error("WORKFLOW_UNIT_STATUS", parent, f"invalid unit_status value for {identifier}")

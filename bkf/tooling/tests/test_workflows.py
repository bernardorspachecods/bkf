from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))

from bkf_common import BKFInputError, parse_markdown
from workflow_declaration import load_declaration
from workflow_ids import allocate_child_id, allocate_workflow_id
from workflow_files import slug
from workflow_scaffold import scaffold
from workflow_sync import sync
from workflow_validation import WorkflowChecks


DECLARATION = '''```bkf-workflow
# Council example: an ordered work unit with parallel advice stages.
steps:
  - work_unit:
      title: "Advisor round"
      work_unit_file: true
      steps:
        - parallel:
            - stage:
                key: brief
                title: "Council brief preparation"
                human_checkpoint: true
            - stage:
                key: advice
                title: "Advisor advice writing"
                file: advice-record
                after: [brief]
            - stage:
                key: first_principles
                title: "First principles advice"
                file: advice-record
                after: [brief]
        - stage:
            key: packet
            title: "Anonymized packet preparation"
            reviews: [advice]
  - work_unit:
      title: "Peer review"
      steps:
        - stage:
            title: "Completeness review"
            reviews: [packet]
```
'''


def make_parent(root: Path) -> Path:
    (root / "MAP.md").write_text("# Map\n", encoding="utf-8")
    parent = root / "council.md"
    parent.write_text(
        "---\nbkf: document\ndescription: Council workflow.\ntags: [test]\n---\n\n# Council\n\n"
        "Prior example reference: W-01.\n\n" + DECLARATION,
        encoding="utf-8",
    )
    return parent


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        # sync prints its plan; tests that assert on it capture stdout themselves
        stdout = redirect_stdout(StringIO())
        stdout.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)

    def test_sync_previews_and_applies_first_time_scaffolding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            original = parent.read_bytes()
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(sync(parent), 0)
            preview = output.getvalue()
            self.assertIn("create directory:", preview)
            self.assertIn("move:", preview)
            self.assertIn("workflow_id: W-02", preview)
            self.assertIn("create:", preview)
            self.assertEqual(parent.read_bytes(), original)
            self.assertEqual(list(root.glob("W-*")), [])

            with redirect_stdout(StringIO()):
                self.assertEqual(sync(parent, write=True), 0)
            target = root / "W-02-council" / "W-02.md"
            self.assertTrue(target.is_file())
            self.assertFalse(parent.exists())
            self.assertTrue((target.parent / "01-WU-02.01-advisor-round" / "01-council-brief.md").is_file())

    def test_scaffold_assigns_ids_and_creates_workflow_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            front = parse_markdown(target).frontmatter
            text = target.read_text(encoding="utf-8")
            work = target.parent / "01-WU-02.01-advisor-round"
            shared = work / "02-advice-record.md"
            stages = list(work.glob("*-council-brief.md"))
            validator = subprocess.run(
                [sys.executable, str(TOOLING / "validate_bundle.py"), str(root)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(front["workflow_id"], "W-02")
            self.assertIn("ST-02.01.01", text)
            self.assertIn("# Council example: an ordered work unit", text)
            self.assertTrue((work / "WORK-UNIT.md").is_file())
            self.assertTrue(shared.is_file())
            self.assertEqual(parse_markdown(shared).frontmatter["stage_ids"], ["ST-02.01.02", "ST-02.01.03"])
            self.assertEqual(parse_markdown(stages[0]).frontmatter["human_checkpoint"], True)
            self.assertNotIn("consumer", parse_markdown(shared).frontmatter)
            self.assertNotIn("consumer", parse_markdown(stages[0]).frontmatter)
            self.assertNotIn("consumer", parse_markdown(work / "WORK-UNIT.md").frontmatter)
            self.assertEqual(validator.returncode, 1)  # The synthetic bundle intentionally has no valid map/log.
            self.assertNotIn("WORKFLOW_", validator.stdout)

    def test_id_reuse_depends_on_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").touch()
            mention = root / "citation.md"
            mention.write_text("WU-01.04 is still referenced\n", encoding="utf-8")
            self.assertEqual(allocate_child_id(root, "WU", "W-01"), "WU-01.05")
            mention.unlink()
            self.assertEqual(allocate_child_id(root, "WU", "W-01"), "WU-01.01")
            self.assertEqual(allocate_workflow_id(root), "W-01")

    def test_direct_parent_stage_id_and_segment_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").touch()
            self.assertEqual(allocate_child_id(root, "ST", "W-01"), "ST-01.01")
            (root / "cite.md").write_text("WU-01.99\n", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "exceeds 99"):
                allocate_child_id(root, "WU", "W-01")

    def test_scaffold_retries_when_workflow_folder_name_is_taken(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            (root / "W-02-council").mkdir()
            target = scaffold(parent)
            self.assertEqual(parse_markdown(target).frontmatter["workflow_id"], "W-03")
            self.assertTrue(target.parent.is_dir())

    def test_sync_previews_and_applies_stage_rename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            content = target.read_text(encoding="utf-8").replace("Council brief preparation", "Council charter preparation")
            target.write_text(content, encoding="utf-8")
            output_parent = target.parent
            preview = sync(target)
            self.assertEqual(preview, 0)
            old_file = output_parent / "01-WU-02.01-advisor-round" / "01-council-brief.md"
            self.assertTrue(old_file.is_file())
            sync(target, write=True)
            self.assertTrue((output_parent / "01-WU-02.01-advisor-round" / "01-council-charter.md").is_file())
            self.assertFalse(old_file.exists())

    def test_sync_renames_a_legacy_role_based_stage_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = scaffold(make_parent(root))
            stage = target.parent / "01-WU-02.01-advisor-round" / "01-council-brief.md"
            legacy = stage.with_name("01-define-council-brief.md")
            stage.rename(legacy)
            self.assertEqual(sync(target, write=True), 0)
            self.assertTrue(stage.is_file())
            self.assertFalse(legacy.exists())

    def test_leftover_stage_role_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            parent.write_text(
                parent.read_text(encoding="utf-8").replace(
                    '                title: "Council brief preparation"',
                    '                role: old_role\n                title: "Council brief preparation"',
                    1,
                ),
                encoding="utf-8",
            )
            target = scaffold(parent)
            self.assertIn("role: old_role", target.read_text(encoding="utf-8"))
            self.assertTrue((target.parent / "01-WU-02.01-advisor-round" / "01-council-brief.md").is_file())

    def test_sync_rename_in_progress_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            target.write_text(
                target.read_text(encoding="utf-8").replace(
                    "workflow_id: W-02",
                    "workflow_id: W-02\nexecution_status: in_progress\nunit_status:\n  WU-02.01: in_progress",
                ),
                encoding="utf-8",
            )
            target.write_text(target.read_text(encoding="utf-8").replace("Council brief preparation", "Council charter preparation"), encoding="utf-8")
            with self.assertRaises(Exception):
                sync(target, write=True)
            self.assertEqual(sync(target, write=True, confirm_in_progress=True), 0)

    def test_sync_adds_stage_and_updates_shared_ids_without_touching_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            shared = target.parent / "01-WU-02.01-advisor-round" / "02-advice-record.md"
            body_before = parse_markdown(shared).body
            content = target.read_text(encoding="utf-8").replace(
                '      id: WU-02.02\n```',
                '        - stage:\n'
                '            title: "Revision writing"\n'
                '            file: advice-record\n'
                '      id: WU-02.02\n```',
            )
            target.write_text(content, encoding="utf-8")
            self.assertEqual(sync(target, write=True), 0)
            metadata = parse_markdown(shared).frontmatter
            self.assertEqual(metadata["stage_ids"], ["ST-02.01.02", "ST-02.01.03", "ST-02.02.02"])
            self.assertEqual(parse_markdown(shared).body, body_before)
            self.assertIn("ST-02.02.02", target.read_text(encoding="utf-8"))

    def test_sync_renames_work_unit_folder_when_its_title_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            old_folder = target.parent / "01-WU-02.01-advisor-round"
            content = target.read_text(encoding="utf-8").replace("title: \"Advisor round\"", "title: \"Advisor panel\"")
            target.write_text(content, encoding="utf-8")
            self.assertEqual(sync(target, write=True), 0)
            new_folder = target.parent / "01-WU-02.01-advisor-panel"
            self.assertTrue((new_folder / "WORK-UNIT.md").is_file())
            self.assertFalse(old_folder.exists())

    def test_sync_renames_workflow_folder_from_parent_heading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            old_folder = target.parent
            target.write_text(target.read_text(encoding="utf-8").replace("# Council\n", "# Council report\n"), encoding="utf-8")
            self.assertEqual(sync(target, write=True), 0)
            new_folder = root / "W-02-council-report"
            self.assertTrue((new_folder / "W-02.md").is_file())
            self.assertFalse(old_folder.exists())

    def test_workflow_with_description_is_validated_even_if_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "MAP.md").write_text("---\nbkf_version: \"0.1\"\n---\n", encoding="utf-8")
            parent = root / "closed.md"
            parent.write_text(
                "---\nbkf: workflow\ndescription: Closed workflow.\nworkflow_id: W-01\n---\n\n"
                "# Closed\n\n```bkf-workflow\nsteps: nope\n```\n",
                encoding="utf-8",
            )
            from validate_bundle import Validator
            validator = Validator(root)
            validator._validate_documents()
            validator._validate_workflows()
            self.assertTrue(any(f.code.startswith("WORKFLOW_") for f in validator.findings), validator.findings)

    def test_validator_rejects_invalid_status_map_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            content = target.read_text(encoding="utf-8").replace("workflow_id: W-02", "workflow_id: W-02\nexecution_status: lost\nunit_status:\n  WU-02.01: waiting")
            target.write_text(content, encoding="utf-8")
            found = []
            checks = WorkflowChecks(root, lambda code, path, message: found.append(code), lambda *args: None)
            checks.validate_parent(target)
            self.assertIn("WORKFLOW_STATUS", found)
            self.assertIn("WORKFLOW_UNIT_STATUS", found)

    def test_sync_with_nested_units_renames_each_folder_to_its_own_path(self) -> None:
        nested = (
            "```bkf-workflow\nsteps:\n"
            "  - stage: {title: \"Kickoff notes\"}\n"
            "  - work_unit:\n      title: \"Build phase\"\n      steps:\n"
            "        - work_unit:\n            title: \"Code check\"\n            steps:\n"
            "              - stage: {title: \"Style check\"}\n"
            "        - stage: {title: \"Module writing\"}\n```\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text("# Map\n", encoding="utf-8")
            parent = root / "flow.md"
            parent.write_text(
                "---\nbkf: document\ndescription: Flow.\ntags: [test]\n---\n\n"
                "# Flow\n\n" + nested,
                encoding="utf-8",
            )
            target = scaffold(parent)
            text = target.read_text(encoding="utf-8").replace(
                '  - stage: {title: "Kickoff notes"',
                '  - stage: {title: "Intake notes"}\n  - stage: {title: "Kickoff notes"',
                1,
            )
            target.write_text(text, encoding="utf-8")
            self.assertEqual(sync(target, write=True), 0)
            unit = target.parent / "03-WU-01.01-build-phase"
            self.assertTrue((unit / "01-WU-01.01.01-code-check").is_dir())
            directories = sorted(p.relative_to(target.parent).as_posix() for p in target.parent.rglob("*") if p.is_dir())
            self.assertEqual(directories, ["03-WU-01.01-build-phase", "03-WU-01.01-build-phase/01-WU-01.01.01-code-check"])

    def test_scaffold_refuses_an_already_scaffolded_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = make_parent(root)
            target = scaffold(parent)
            with self.assertRaises(BKFInputError):
                scaffold(target)
            self.assertEqual(len(list(root.glob("W-*"))), 1)

    def test_sync_reorder_swaps_two_stages_and_keeps_their_ids(self) -> None:
        declaration = (
            "```bkf-workflow\nsteps:\n"
            "  - stage: {title: \"Alpha notes\"}\n"
            "  - stage: {title: \"Beta work\"}\n"
            "  - stage: {title: \"Gamma check\"}\n```\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text("# Map\n", encoding="utf-8")
            parent = root / "flow.md"
            parent.write_text(
                "---\nbkf: document\ndescription: Flow.\ntags: [test]\n---\n\n"
                "# Flow\n\n" + declaration,
                encoding="utf-8",
            )
            target = scaffold(parent)
            text = target.read_text(encoding="utf-8")
            beta = next(l for l in text.splitlines(keepends=True) if "Beta work" in l)
            gamma = next(l for l in text.splitlines(keepends=True) if "Gamma check" in l)
            target.write_text(text.replace(beta, "@@B@@").replace(gamma, "@@C@@").replace("@@B@@", gamma).replace("@@C@@", beta), encoding="utf-8")
            self.assertEqual(sync(target, write=True), 0)
            ids = {p.name: parse_markdown(p).frontmatter["stage_id"] for p in target.parent.glob("0*.md")}
            self.assertEqual(ids["02-gamma-check.md"], "ST-01.03")
            self.assertEqual(ids["03-beta-work.md"], "ST-01.02")
            self.assertEqual(sync(target), 0)

    def test_scaffold_refuses_an_invalid_declaration_and_writes_nothing(self) -> None:
        bad = (
            "```bkf-workflow\nsteps:\n"
            "  - parallel:\n"
            "      - stage: {key: a, title: \"Alpha work\", after: [b]}\n"
            "      - stage: {key: b, title: \"Beta work\"}\n"
            "  - stage: {title: \"Final check\", reviews: [z], after: [a]}\n"
            "  - stage: {title: \"Odd role\"}\n"
            "  - stage: {title: \"\"}\n```\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text("# Map\n", encoding="utf-8")
            parent = root / "flow.md"
            parent.write_text(
                "---\nbkf: document\ndescription: Flow.\ntags: [test]\n---\n\n"
                "# Flow\n\n" + bad,
                encoding="utf-8",
            )
            before = parent.read_bytes()
            with self.assertRaises(BKFInputError) as raised:
                scaffold(parent)
            message = str(raised.exception)
            self.assertEqual(parent.read_bytes(), before)
            self.assertEqual([p.name for p in root.iterdir()], ["MAP.md", "flow.md"])
        for expected in (
            "after target must be an earlier sibling in the same parallel group: b",
            "reviews target must exist earlier: z",
            "after is valid only directly inside a parallel group",
            "stage title must be a non-empty string",
        ):
            self.assertIn(expected, message)

    def test_sync_refuses_an_invalid_declaration_and_renames_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = scaffold(make_parent(root))
            before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            text = target.read_text(encoding="utf-8").replace("# Council\n", "# Council renamed\n", 1)
            text = text.replace('title: "Peer review"', 'title: "Peer review"\n      reviews: [nowhere]', 1)
            target.write_text(text, encoding="utf-8")
            with self.assertRaises(BKFInputError) as raised:
                sync(target, write=True)
            after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
        self.assertEqual(before, after)
        self.assertIn("nothing was written", str(raised.exception))

    def test_validator_and_scaffold_share_the_same_declaration_messages(self) -> None:
        from workflow_declaration_checks import declaration_problems

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = scaffold(make_parent(root))
            text = target.read_text(encoding="utf-8").replace("after:\n                  - ST-02.01.01", "after:\n                  - ST-02.01.03", 1)
            target.write_text(text, encoding="utf-8")
            problems = declaration_problems(load_declaration(target).steps)
            found: list[tuple[str, str]] = []
            WorkflowChecks(root, lambda code, path, message: found.append((code, message)), lambda *args: None).validate_parent(target)
        self.assertTrue(problems)
        for problem in problems:
            self.assertIn(problem, found)

    def test_slug_removes_punctuation_inside_a_word_and_declaration_keeps_plain_yaml(self) -> None:
        self.assertEqual(slug("Final sign-off", words=2), "final-signoff")
        with tempfile.TemporaryDirectory() as directory:
            target = scaffold(make_parent(Path(directory)))
            block = target.read_text(encoding="utf-8").split("```bkf-workflow", 1)[1]
            self.assertNotIn("%YAML", block)
            self.assertNotIn("\n---\n", block.split("```", 1)[0])

    def test_slug_transliterates_accented_letters(self) -> None:
        self.assertEqual(slug("Fundação"), "fundacao")
        self.assertEqual(slug("Inventário e âmbito"), "inventario-e-ambito")
        self.assertEqual(slug("Guarda revisão", words=2), "guarda-revisao")


if __name__ == "__main__":
    unittest.main()

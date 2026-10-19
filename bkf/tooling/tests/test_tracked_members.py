from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"
HOME_DESCRIPTION = "Starts navigation from the bundle root."


def make_bundle(root: Path) -> None:
    (root / "MAP.md").write_text(
        "---\nbkf_version: \"0.1\"\n---\n\n# Bundle\n\n"
        "## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
        encoding="utf-8",
    )
    (root / "home.md").write_text(
        f"---\nbkf: document\ndescription: {HOME_DESCRIPTION}\ntags: [history]\n---\n\n# Home\n",
        encoding="utf-8",
    )
    refresh(root)


def refresh(root: Path) -> None:
    subprocess.run([sys.executable, str(INVENTORY), "--write", str(root)], check=True, capture_output=True, text=True)


def run(script: Path, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


class TrackedMemberTests(unittest.TestCase):
    def test_untracked_member_without_frontmatter_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "W-01.md").write_text("[Broken relative link](missing.md)\n", encoding="utf-8")

            result = run(VALIDATOR, root)
            inventory = run(INVENTORY, root, "--check")
            map_text = (root / "MAP.md").read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(inventory.returncode, 0, inventory.stdout + inventory.stderr)
        self.assertNotIn("W-01.md", map_text)

    def test_a_bkf_value_other_than_a_profile_or_document_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "custom.md").write_text(
                "---\nbkf: custom.profile\ndescription: Custom document.\ntags: [test]\n---\n\n# Custom\n",
                encoding="utf-8",
            )
            refresh(root)
            result = run(VALIDATOR, root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("METADATA_PROFILE", result.stdout + result.stderr)

    def test_generic_profile_requires_non_empty_description_and_tags(self) -> None:
        for frontmatter in (
            "bkf: document\ntags: [test]\n",
            "bkf: document\ndescription: Guide.\ntags: none\n",
            "bkf: document\ndescription: Guide.\ntags: [test, ' ']\n",
        ):
            with self.subTest(frontmatter=frontmatter), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bundle(root)
                (root / "bad.md").write_text(f"---\n{frontmatter}---\n\n# Bad\n", encoding="utf-8")
                result = run(VALIDATOR, root)
                inventory = run(INVENTORY, root, "--check")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotEqual(inventory.returncode, 0)


    def test_root_agents_is_an_ordinary_generic_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "AGENTS.md").write_text(
                "---\nbkf: document\ndescription: Gives repository agent instructions.\ntags: [agents]\n---\n\n# Agents\n",
                encoding="utf-8",
            )
            refresh(root)
            result = run(VALIDATOR, root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_untracked_root_agents_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(
                "---\nbkf_version: \"0.1\"\n---\n\n# Bundle\n\n"
                "## Member inventory\n\n"
                "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
                "| What it is | Document |\n| --- | --- |\n"
                "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text("x", encoding="utf-8")

            result = run(VALIDATOR, root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ROOT_AGENTS_UNTRACKED", result.stdout + result.stderr)

    def test_nested_agents_file_is_allowed_tracked_or_untracked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "app").mkdir()
            (root / "app" / "AGENTS.md").write_text("Framework-generated rules.\n", encoding="utf-8")
            (root / "tool").mkdir()
            (root / "tool" / "AGENTS.md").write_text(
                "---\nbkf: document\ndescription: Gives the tool folder agent instructions.\ntags: [agents]\n---\n\n# Tool\n",
                encoding="utf-8",
            )
            refresh(root)
            result = run(VALIDATOR, root)
            inventory = run(INVENTORY, root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(inventory.returncode, 0, inventory.stdout + inventory.stderr)

    def test_unknown_frontmatter_fields_are_errors(self) -> None:
        cases = {
            "document": "bkf: document\ndescription: Guide.\ntags: [test]\nkind: guide\n",
            "typo": "bkf: document\ndescription: Guide.\ntags: [test]\ntgas: [x]\n",
            "feedback": "bkf: feedback\ndescription: Feedback.\nstatus: draft\n",
            "ideas": "bkf: ideas\ndescription: Ideas.\ntracked: true\n",
        }
        for label, frontmatter in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bundle(root)
                name = {"feedback": "feedback.md", "ideas": "ideas.md"}.get(label, "extra.md")
                (root / name).write_text(f"---\n{frontmatter}---\n\n# Extra\n", encoding="utf-8")
                refresh(root)
                result = run(VALIDATOR, root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(f"METADATA_UNKNOWN_FIELD {name}", result.stdout)


    def test_a_non_empty_description_tracks_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "custom.md").write_text(
                "---\nbkf: document\ndescription: Custom document.\ntags: [test]\n---\n\n# Custom\n",
                encoding="utf-8",
            )
            refresh(root)
            result = run(VALIDATOR, root)
            map_text = (root / "MAP.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("custom.md", map_text)

    def test_invalid_bkf_value_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "legacy.md").write_text(
                "---\nbkf: true\ndescription: Legacy.\ntags: [test]\n---\n\n# Legacy\n",
                encoding="utf-8",
            )
            result = run(VALIDATOR, root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("`bkf` must be a non-empty profile name string", result.stdout)

    def test_open_when_and_use_when_are_advisory_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "advice.md").write_text(
                "---\nbkf: document\ndescription: Use when you need advice.\ntags: [test]\n---\n\n# Advice\n",
                encoding="utf-8",
            )
            refresh(root)
            result = run(VALIDATOR, root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING DESCRIPTION_REVIEW advice.md", result.stdout)


    def test_the_retired_workflow_profiles_are_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "stage.md").write_text(
                "---\nbkf: workflow.stage\nstage_id: ST-01.01\ndescription: Stage.\n---\n\n# Stage\n",
                encoding="utf-8",
            )
            refresh(root)
            result = run(VALIDATOR, root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("METADATA_PROFILE stage.md", result.stdout)


if __name__ == "__main__":
    unittest.main()

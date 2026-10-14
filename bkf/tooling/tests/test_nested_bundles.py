from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"

MAP_TEXT = (
    "{front}# Bundle\n\n"
    "## Member inventory\n\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
ROOT_FRONT = '---\nbkf_version: "0.1"\n---\n\n'
CHILD_FRONT = '---\ndescription: Inner bundle holds its own guides and agent instructions.\nbkf_version: "0.1"\n---\n\n'


def document(description: str, body: str = "# Doc\n") -> str:
    return f"---\nbkf: document\ndescription: {description}\ntags: [test]\n---\n{body}"


def run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
    )


def build(root: Path, *, inner_body: str = "# Inner\n", outer_body: str = "# Outer\n") -> Path:
    """Create an outer bundle with a nested bundle in `inner/`; return the nested root."""
    inner = root / "inner"
    inner.mkdir()
    (root / "MAP.md").write_text(MAP_TEXT.format(front=ROOT_FRONT), encoding="utf-8")
    (root / "outer.md").write_text(document("Outer document.", outer_body), encoding="utf-8")
    (inner / "MAP.md").write_text(MAP_TEXT.format(front=CHILD_FRONT), encoding="utf-8")
    (inner / "AGENTS.md").write_text(document("Nested agent entry."), encoding="utf-8")
    (inner / "guide.md").write_text(document("Nested guide.", inner_body), encoding="utf-8")
    result = run(INVENTORY, "--write", root)
    assert result.returncode == 0, result.stderr
    return inner


class NestedBundleTests(unittest.TestCase):
    def test_default_validation_reports_broken_link_in_nested_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, inner_body="# Inner\n\n[gone](/missing.md)\n")

            result = run(VALIDATOR, root)

            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("== . ==", result.stdout)
            self.assertIn("== inner ==", result.stdout)
            self.assertIn("LINK_TARGET_MISSING guide.md", result.stdout)

    def test_this_bundle_ignores_nested_broken_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, inner_body="# Inner\n\n[gone](/missing.md)\n")

            result = run(VALIDATOR, "--this-bundle", root)

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("==", result.stdout)
            self.assertIn("Result: CONFORMANT", result.stdout)

    def test_outer_inventory_lists_nested_map_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)

            text = (root / "MAP.md").read_text(encoding="utf-8")

            self.assertIn("[MAP.md](/inner/MAP.md)", text)
            self.assertIn("Inner bundle holds its own guides and agent instructions.", text)
            self.assertNotIn("/inner/guide.md", text)
            self.assertNotIn("/inner/AGENTS.md", text)
            self.assertIn("[outer.md](/outer.md)", text)

    def test_outer_bundle_is_clean_despite_nested_root_map_and_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)

            result = run(VALIDATOR, "--this-bundle", root)

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(result.stdout, "Result: CONFORMANT with BKF 0.1\n")
            default = run(VALIDATOR, root)
            self.assertEqual(default.returncode, 0, default.stdout)

    def test_inventory_check_detects_stale_nested_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inner = build(root)
            (inner / "guide.md").write_text(document("Changed description."), encoding="utf-8")

            default = run(INVENTORY, "--check", root)
            outer_only = run(INVENTORY, "--check", "--this-bundle", root)

            self.assertEqual(default.returncode, 1, default.stdout)
            self.assertIn("== inner ==", default.stdout)
            self.assertIn("stale: MAP.md", default.stdout)
            self.assertEqual(outer_only.returncode, 0, outer_only.stdout)
            self.assertEqual(outer_only.stdout, "all BKF map inventories are up to date\n")

    def test_inventory_write_refreshes_nested_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inner = build(root)
            (inner / "guide.md").write_text(document("Changed description."), encoding="utf-8")

            self.assertEqual(run(INVENTORY, "--write", "--this-bundle", root).returncode, 0)
            self.assertEqual(run(INVENTORY, "--check", root).returncode, 1)
            self.assertEqual(run(INVENTORY, "--write", root).returncode, 0)
            self.assertEqual(run(INVENTORY, "--check", root).returncode, 0)
            self.assertIn("Changed description.", (inner / "MAP.md").read_text(encoding="utf-8"))

    def test_missing_child_map_description_fails_generator_and_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            child = root / "area"
            child.mkdir()
            (child / "MAP.md").write_text(MAP_TEXT.format(front=""), encoding="utf-8")

            generated = run(INVENTORY, "--write", root)
            validated = run(VALIDATOR, "--this-bundle", root)

        self.assertEqual(generated.returncode, 2)
        self.assertIn("area/MAP.md", generated.stderr)
        self.assertIn("map needs a non-empty string `description`", generated.stderr)
        self.assertEqual(validated.returncode, 1)
        self.assertIn("ERROR MAP_DESCRIPTION_MISSING area/MAP.md", validated.stdout)

    def test_nested_map_allows_only_description_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            child = root / "area"
            child.mkdir()
            (child / "MAP.md").write_text(
                MAP_TEXT.format(front="---\ndescription: An area map.\nextra: forbidden\n---\n\n"),
                encoding="utf-8",
            )
            run(INVENTORY, "--write", root)

            validated = run(VALIDATOR, "--this-bundle", root)

        self.assertEqual(validated.returncode, 1, validated.stdout)
        self.assertIn("MAP_FRONTMATTER area/MAP.md", validated.stdout)

    def test_nested_map_description_is_accepted_and_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            child = root / "area"
            child.mkdir()
            (child / "MAP.md").write_text(
                MAP_TEXT.format(front="---\ndescription: Open when working in this area.\n---\n\n"),
                encoding="utf-8",
            )
            run(INVENTORY, "--write", root)

            validated = run(VALIDATOR, "--this-bundle", root)

        self.assertEqual(validated.returncode, 0, validated.stdout)
        self.assertIn("WARNING DESCRIPTION_REVIEW area/MAP.md", validated.stdout)

    def test_child_description_change_makes_parent_inventory_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inner = build(root)
            (inner / "MAP.md").write_text(
                (inner / "MAP.md").read_text(encoding="utf-8").replace(
                    "Inner bundle holds its own guides and agent instructions.",
                    "Inner bundle owns separate workflows and guides.",
                ),
                encoding="utf-8",
            )

            checked = run(INVENTORY, "--check", "--this-bundle", root)

        self.assertEqual(checked.returncode, 1)
        self.assertIn("stale: MAP.md", checked.stdout)

    def test_child_map_description_escapes_table_pipe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            child = root / "area"
            child.mkdir()
            (child / "MAP.md").write_text(
                MAP_TEXT.format(front="---\ndescription: Owns tools | reports for this area.\n---\n\n"),
                encoding="utf-8",
            )

            generated = run(INVENTORY, "--write", root)

            text = (root / "MAP.md").read_text(encoding="utf-8")

        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("Owns tools \\| reports for this area.", text)

    def test_root_absolute_link_into_nested_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, outer_body="# Outer\n\n[guide](/inner/guide.md)\n")

            result = run(VALIDATOR, "--this-bundle", root)
            self.assertEqual(result.returncode, 0, result.stdout)

            (root / "outer.md").write_text(
                document("Outer document.", "# Outer\n\n[guide](/inner/nope.md)\n"),
                encoding="utf-8",
            )
            broken = run(VALIDATOR, "--this-bundle", root)
            self.assertEqual(broken.returncode, 1, broken.stdout)
            self.assertIn("LINK_TARGET_MISSING outer.md", broken.stdout)

    def test_bundle_without_nesting_has_old_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(MAP_TEXT.format(front=ROOT_FRONT), encoding="utf-8")
            (root / "doc.md").write_text(document("A document."), encoding="utf-8")
            self.assertEqual(run(INVENTORY, "--write", root).returncode, 0)

            validated = run(VALIDATOR, root)
            checked = run(INVENTORY, "--check", root)

            self.assertEqual(validated.returncode, 0)
            self.assertEqual(validated.stdout, "Result: CONFORMANT with BKF 0.1\n")
            self.assertEqual(checked.stdout, "all BKF map inventories are up to date\n")
            self.assertEqual(
                validated.stdout, run(VALIDATOR, "--this-bundle", root).stdout
            )


if __name__ == "__main__":
    unittest.main()

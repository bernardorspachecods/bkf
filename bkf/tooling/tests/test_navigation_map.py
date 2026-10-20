from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"


def make_bundle(root: Path) -> None:
    (root / "MAP.md").write_text(
        "---\nbkf_version: \"0.1\"\n---\n\n# Bundle\n\n"
        "## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
        encoding="utf-8",
    )
    refresh(root)


def refresh(root: Path) -> None:
    subprocess.run(
        [sys.executable, str(INVENTORY), "--write", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )


def write_document(root: Path, body: str) -> None:
    (root / "document.md").write_text(
        "---\nbkf: document\ndescription: A test document.\ntags: [test]\n---\n"
        + body,
        encoding="utf-8",
    )
    refresh(root)


def validate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        check=False,
        capture_output=True,
        text=True,
    )


class NavigationMapTests(unittest.TestCase):
    def test_short_document_without_map_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, "# Document\n\nA short body.")

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("NAVIGATION_MAP_REVIEW", result.stdout)

    def test_long_document_without_map_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            body = "\n".join(["# Document", *(f"Body line {i}" for i in range(350))])
            write_document(root, body)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING NAVIGATION_MAP_REVIEW document.md", result.stdout)
        self.assertIn("351 lines", result.stdout)

    def test_long_document_by_words_without_map_warns_and_keeps_exit_code_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, "# Document\n\n" + "word " * 2_001)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING NAVIGATION_MAP_REVIEW document.md", result.stdout)
        self.assertIn("2002 words", result.stdout)
        self.assertIn("Result: CONFORMANT", result.stdout)

    def check(self, body: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, body)
            result = validate(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    MAP = (
        "# Document\n\n## Navigation map\n\n| If you need to... | See |\n| --- | --- |\n"
        "| Find alpha | [Alpha](#alpha) |\n| Find beta | [Beta](#beta) |\n\n"
    )

    def test_large_document_with_a_complete_map_does_not_warn(self) -> None:
        body = self.MAP + "## Alpha\n" + "line\n" * 200 + "## Beta\n" + "line\n" * 200
        self.assertNotIn("NAVIGATION_MAP", self.check(body))

    def test_map_guidance_is_printed_once_and_only_with_a_map_warning(self) -> None:
        stale = self.MAP + "## Alpha\nx\n## Beta\nx\n## Gamma\nx\n## Delta\nx\n"
        output = self.check(stale)
        self.assertEqual(output.count("Navigation map: the first column"), 1)
        self.assertNotIn("Navigation map: the first column", self.check(self.MAP + "## Alpha\nx\n## Beta\nx\n"))

    def test_a_list_of_links_under_another_heading_is_not_a_map(self) -> None:
        body = (
            "# Document\n\n## In this file\n\n- [Alpha](#alpha)\n- [Beta](#beta)\n\n"
            "## Alpha\n" + "line\n" * 200 + "## Beta\n" + "line\n" * 200
        )
        self.assertIn("WARNING NAVIGATION_MAP_REVIEW document.md", self.check(body))

    def test_a_link_to_a_missing_heading_is_stale(self) -> None:
        body = self.MAP.replace("#beta", "#gone") + "## Alpha\nx\n## Beta\nx\n"
        output = self.check(body)
        self.assertIn("WARNING NAVIGATION_MAP_STALE document.md", output)
        self.assertIn("#gone, which is not a heading", output)

    def test_an_unmapped_level_two_section_is_stale_even_in_a_short_document(self) -> None:
        output = self.check(self.MAP + "## Alpha\nx\n## Beta\nx\n## Gamma\nx\n")
        self.assertIn('does not cover the section "Gamma"', output)
        self.assertNotIn('"Alpha"', output)

    def test_a_subsection_link_covers_its_level_two_section(self) -> None:
        body = self.MAP.replace("#beta", "#detail") + "## Alpha\nx\n## Beta\nx\n### Detail\nx\n"
        self.assertNotIn("NAVIGATION_MAP_STALE", self.check(body))

    def test_a_map_without_rows_is_stale(self) -> None:
        output = self.check("# Document\n\n## Navigation map\n\nNothing here.\n\n## Alpha\nx\n")
        self.assertIn("has no table rows", output)

    def test_long_map_and_untracked_file_do_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            map_path = root / "MAP.md"
            map_path.write_text(
                map_path.read_text(encoding="utf-8")
                + "\n"
                + "\n".join(f"Map line {i}" for i in range(360)),
                encoding="utf-8",
            )
            (root / "untracked.md").write_text(
                "\n".join(["# Untracked", *(f"Body line {i}" for i in range(350))]),
                encoding="utf-8",
            )

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("NAVIGATION_MAP_REVIEW", result.stdout)

    def test_long_feedback_and_ideas_logs_do_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            for name in ("feedback", "ideas"):
                (root / f"{name}.md").write_text(
                    f"---\nbkf: {name}\ndescription: A test log.\n---\n\n# Log\n\n"
                    + "\n".join(f"Entry line {i}" for i in range(360)),
                    encoding="utf-8",
                )
            refresh(root)

            result = validate(root)

        self.assertNotIn("NAVIGATION_MAP_REVIEW", result.stdout, result.stdout)

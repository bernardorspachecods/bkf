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

    def test_early_map_with_heading_fragment_link_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            body = "\n".join(
                [
                    "# Document",
                    "### nAvIgAtIoN mAp",
                    "#### Nested heading",
                    "[Details](#details)",
                    "[This document](/document.md#details)",
                    "### Details",
                    "Details are below.",
                    *(f"Body line {i}" for i in range(350)),
                ]
            )
            write_document(root, body)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("NAVIGATION_MAP_REVIEW", result.stdout)

    def test_early_map_under_a_translated_heading_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            body = "\n".join(
                [
                    "# Documento",
                    "## Mapa de navegação",
                    "[Detalhes](#detalhes)",
                    "[Outros](#outros)",
                    "## Detalhes",
                    "## Outros",
                    *(f"Body line {i}" for i in range(350)),
                ]
            )
            write_document(root, body)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("NAVIGATION_MAP_REVIEW", result.stdout)

    def test_map_after_body_line_40_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            body = "\n".join(
                [
                    "# Document",
                    *(f"Early body {i}" for i in range(40)),
                    "## Navigation map",
                    "[Details](#details)",
                    "## Details",
                    *(f"Body line {i}" for i in range(310)),
                ]
            )
            write_document(root, body)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING NAVIGATION_MAP_REVIEW document.md", result.stdout)

    def test_map_without_a_fragment_link_in_its_section_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            body = "\n".join(
                [
                    "# Document",
                    "## Navigation map",
                    "[Guide](https://example.com/guide)",
                    "## Details",
                    "[Details](#details)",
                    *(f"Body line {i}" for i in range(350)),
                ]
            )
            write_document(root, body)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING NAVIGATION_MAP_REVIEW document.md", result.stdout)

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

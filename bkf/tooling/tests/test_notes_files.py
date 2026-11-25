from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
CLI = TOOLING / "bkf_cli.py"
sys.path.insert(0, str(TOOLING))
_SEARCH_CACHE = tempfile.TemporaryDirectory()
from bkf_common import is_notes_file
from validate_bundle import SUPPORTED_VERSION


VERSION = f"{SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]}"
ROOT_MAP = (
    f'---\nbkf_version: "{VERSION}"\ndescription: Test bundle.\n---\n\n# Bundle\n\n'
    "## Member inventory\n\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
TRACKED = "---\nbkf: document\ndescription: Private plans needle.\ntags: [test]\n---\n\n# Notes\n\nneedle\n"
HEADER = "<!-- Personal notes of the user. Agents: do not read, list, track or edit this file unless the user asks. -->\n"


def bkf(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *map(str, arguments)],
        cwd=TOOLING,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "BKF_SEARCH_CACHE": _SEARCH_CACHE.name},
    )


def make_bundle(root: Path, files: dict[str, str]) -> None:
    (root / "MAP.md").write_text(ROOT_MAP, encoding="utf-8")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    result = bkf("inventory", "--write", root)
    assert result.returncode == 0, result.stdout + result.stderr


class NotesNameTests(unittest.TestCase):
    def test_reserved_names_at_the_bundle_root(self) -> None:
        root = Path("/bundle")
        for name in ("notes.md", "notes2.md", "notes9.md", "notes10.md", "notes123.md"):
            with self.subTest(name=name):
                self.assertTrue(is_notes_file(root, root / name))
        for name in ("notes1.md", "notes02.md", "notes0.md", "Notes.md", "NOTES.md", "notes.MD",
                     "notes-2.md", "notes2a.md", "my-notes.md", "notes", "notes2"):
            with self.subTest(name=name):
                self.assertFalse(is_notes_file(root, root / name))

    def test_a_notes_name_below_the_root_is_not_reserved(self) -> None:
        root = Path("/bundle")
        self.assertFalse(is_notes_file(root, root / "area" / "notes.md"))


class NotesValidationTests(unittest.TestCase):
    def test_untracked_notes_files_are_conformant_and_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {
                "notes.md": HEADER + "# Mine\n",
                "notes2.md": "plain text, no header\n",
                "notes10.md": "---\n: [ not yaml\n---\nbroken frontmatter\n",
            })
            result = bkf("validate", root)
            check = bkf("inventory", "--check", root)
            map_text = (root / "MAP.md").read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertNotIn("notes", map_text)

    def test_a_bkf_field_in_a_notes_file_is_an_error_and_it_stays_unlisted(self) -> None:
        for name in ("notes.md", "notes3.md"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bundle(root, {name: TRACKED})
                result = bkf("validate", root)
                map_text = (root / "MAP.md").read_text(encoding="utf-8")

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f"NOTES_TRACKED {name}", result.stdout)
            self.assertIn("ask the user", result.stdout)
            self.assertNotIn(name, map_text)

    def test_names_outside_the_pattern_are_ordinary_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {"notes1.md": TRACKED, "notes02.md": TRACKED, "area/notes.md": TRACKED})
            result = bkf("validate", root)
            map_text = (root / "MAP.md").read_text(encoding="utf-8")

        self.assertNotIn("NOTES_TRACKED", result.stdout)
        for path in ("/notes1.md", "/notes02.md", "/area/notes.md"):
            self.assertIn(f"]({path})", map_text)

    def test_links_to_a_notes_file_are_errors_in_documents_and_maps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {
                "notes2.md": "mine\n",
                "guide.md": "---\nbkf: document\ndescription: A guide.\ntags: [test]\n---\n\n"
                            "See [my notes](/notes2.md#todo).\n",
            })
            with (root / "MAP.md").open("a", encoding="utf-8") as handle:
                handle.write("\n## Artifact references\n\n- [notes2.md](/notes2.md) — The user's notes.\n")
            result = bkf("validate", root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("NOTES_LINKED guide.md", result.stdout)
        self.assertIn("NOTES_LINKED MAP.md", result.stdout)

    def test_a_link_that_differs_only_in_case_is_caught_on_a_case_insensitive_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe").write_text("", encoding="utf-8")
            if not (root / "PROBE").exists():
                self.skipTest("case-sensitive file system")
            make_bundle(root, {
                "notes.md": "mine\n",
                "guide.md": "---\nbkf: document\ndescription: A guide.\ntags: [test]\n---\n\n[x](/NOTES.md)\n",
            })
            result = bkf("validate", root)

        self.assertIn("NOTES_LINKED guide.md", result.stdout)

    def test_a_nested_bundle_root_reserves_its_own_notes_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested_map = ROOT_MAP.replace("Test bundle.", "Inner bundle.")
            make_bundle(root, {"inner/MAP.md": nested_map, "inner/notes.md": TRACKED})
            result = bkf("validate", root)

        self.assertIn("NOTES_TRACKED notes.md", result.stdout)


class NotesReaderTests(unittest.TestCase):
    def test_orient_and_search_skip_notes_files_even_when_tracked_or_broken(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {
                "notes.md": TRACKED,
                "notes2.md": "---\n: [ not yaml\n---\nneedle\n",
                "guide.md": "---\nbkf: document\ndescription: A guide.\ntags: [test]\n---\n\n# Guide\n",
            })
            oriented = bkf("orient", "--cwd", root, "--debug")
            searched = bkf("search", "needle", "--cwd", root)

        self.assertEqual(oriented.returncode, 0, oriented.stderr)
        self.assertIn("/guide.md", oriented.stdout)
        self.assertNotIn("notes", oriented.stdout)
        self.assertEqual(searched.returncode, 0, searched.stderr)
        self.assertNotIn("notes", searched.stdout)

    def test_search_skips_the_root_readme_like_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {"readme.md": TRACKED})
            searched = bkf("search", "needle", "--cwd", root)

        self.assertEqual(searched.returncode, 0, searched.stderr)
        self.assertNotIn("readme", searched.stdout)


if __name__ == "__main__":
    unittest.main()

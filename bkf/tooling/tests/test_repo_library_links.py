from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"

ROOT_MAP = (
    '---\nbkf_version: "0.1"\n---\n\n# Bundle\n\n'
    "## Member inventory\n\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
DOCUMENT = "---\nbkf: document\ndescription: Test document.\ntags: [test]\n---\n"


def run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
    )


def make_bundle(root: Path, *, nested_library: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "MAP.md").write_text(ROOT_MAP, encoding="utf-8")
    library = root / "repo-library"
    library.mkdir()
    if nested_library:
        (library / "MAP.md").write_text(
            '---\ndescription: Nested library bundle.\nbkf_version: "0.1"\n---\n\n'
            "# Library\n\n## Member inventory\n\n"
            "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
            "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
            encoding="utf-8",
        )
    (library / "modules").mkdir()
    (library / "modules" / "x.md").write_text("# X\n", encoding="utf-8")
    refresh(root)
    return library


def refresh(root: Path) -> None:
    result = run(INVENTORY, "--write", root)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def add_document(root: Path, name: str, body: str) -> None:
    (root / name).write_text(DOCUMENT + body, encoding="utf-8")
    refresh(root)


def validate(root: Path) -> subprocess.CompletedProcess[str]:
    return run(VALIDATOR, root)


class RepoLibraryLinkTests(unittest.TestCase):
    def check_no_warning(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("REPO_LIBRARY_ENTRY_UNLINKED", result.stdout)

    def test_root_map_link_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "MAP.md").write_text(ROOT_MAP + "\n[Module](/repo-library/modules/x.md)\n", encoding="utf-8")
            refresh(root)

            self.check_no_warning(validate(root))

    def test_other_enclosing_document_link_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            add_document(root, "start.md", "[Module](/repo-library/modules/x.md)\n")

            self.check_no_warning(validate(root))

    def test_links_only_inside_repo_library_do_not_count(self) -> None:
        for source in ("MAP.md", "another-entry"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                library = make_bundle(root)
                if source == "MAP.md":
                    map_path = library / "MAP.md"
                    map_path.write_text(
                        "---\ndescription: Plain library map.\n---\n\n"
                        "# Library\n\n## Member inventory\n\n"
                        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
                        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n\n"
                        "[Module](/repo-library/modules/x.md)\n",
                        encoding="utf-8",
                    )
                    refresh(root)
                else:
                    (library / "modules" / "y.md").write_text(
                        "[Module](/repo-library/modules/x.md)\n", encoding="utf-8"
                    )

                result = validate(root)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("WARNING REPO_LIBRARY_ENTRY_UNLINKED repo-library/modules/x.md", result.stdout)

    def test_unlinked_entry_warns_and_keeps_exit_status_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)

            result = validate(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING REPO_LIBRARY_ENTRY_UNLINKED repo-library/modules/x.md", result.stdout)
        self.assertIn(
            "No document outside repo-library/ links to this entry, so nothing sends an agent to it.",
            result.stdout,
        )

    def test_fragment_and_percent_encoded_links_count(self) -> None:
        for destination in (
            "/repo-library/modules/x.md#section",
            "/repo-library/modules/%78.md",
            "/%72epo-library/modules/x.md",
        ):
            with self.subTest(destination=destination), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bundle(root)
                add_document(root, "start.md", f"[Module]({destination})\n")

                self.check_no_warning(validate(root))

    def test_nested_bundle_and_plain_folder_are_checked(self) -> None:
        for nested in (False, True):
            with self.subTest(nested=nested), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bundle(root, nested_library=nested)

                result = validate(root)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("WARNING REPO_LIBRARY_ENTRY_UNLINKED repo-library/modules/x.md", result.stdout)

    def test_no_repo_library_folder_has_no_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            (root / "MAP.md").write_text(ROOT_MAP, encoding="utf-8")
            refresh(root)

            self.check_no_warning(validate(root))

    def test_link_from_another_nested_bundle_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            inner = root / "inner"
            inner.mkdir()
            (inner / "MAP.md").write_text(
                '---\ndescription: Separate nested bundle.\nbkf_version: "0.1"\n---\n\n'
                "# Inner\n\n## Member inventory\n\n"
                "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
                "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
                encoding="utf-8",
            )
            (inner / "guide.md").write_text(DOCUMENT + "[Module](/repo-library/modules/x.md)\n", encoding="utf-8")
            refresh(root)

            result = validate(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("WARNING REPO_LIBRARY_ENTRY_UNLINKED repo-library/modules/x.md", result.stdout)
        self.assertIn("LINK_TARGET_MISSING guide.md", result.stdout)


if __name__ == "__main__":
    unittest.main()

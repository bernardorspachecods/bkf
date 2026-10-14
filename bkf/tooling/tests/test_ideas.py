from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"
IDEAS_DESCRIPTION = "Collects ideas from the user and agents for later review as future possibilities, not instructions."


def ideas_text(*, profile: str = "ideas", description: bool = True, body: str = "") -> str:
    return (
        f"---\nbkf: {profile}\n"
        + (f"description: {IDEAS_DESCRIPTION}\n" if description else "")
        + f"---\n{body}"
    )


def make_bundle(root: Path, files: dict[str, str]) -> None:
    (root / "MAP.md").write_text(
        "---\nbkf_version: \"0.1\"\n---\n\n# Bundle\n\n## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
        encoding="utf-8",
    )
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, str(INVENTORY), "--write", str(root)], check=False, capture_output=True, text=True)


def validate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(VALIDATOR), str(root)], check=False, capture_output=True, text=True)


class IdeasTests(unittest.TestCase):
    def run_bundle(self, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, files)
            return validate(root)

    def test_a_bundle_needs_no_log_or_ideas_file(self) -> None:
        result = self.run_bundle({})
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_ideas_file_with_free_form_or_empty_body_is_conformant(self) -> None:
        for body in ("", "just a line, no headings or dates\n- an entry\n"):
            result = self.run_bundle({"ideas.md": ideas_text(body=body)})
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_ideas_file_is_listed_in_the_map_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {"ideas.md": ideas_text()})
            map_text = (root / "MAP.md").read_text(encoding="utf-8")
        self.assertIn(f"| {IDEAS_DESCRIPTION} | [ideas.md](/ideas.md) |", map_text)

    def test_root_ideas_without_bkf_is_an_error(self) -> None:
        result = self.run_bundle({"ideas.md": "# Ideas\n"})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("ERROR ROOT_IDEAS_UNTRACKED ideas.md", result.stdout)

    def test_root_ideas_file_must_use_the_ideas_profile(self) -> None:
        document = (
            f"---\nbkf: document\ndescription: {IDEAS_DESCRIPTION}\ntags: [test]\n---\n\nBody.\n"
        )
        result = self.run_bundle({"ideas.md": document})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("ERROR IDEAS_PROFILE ideas.md", result.stdout)

    def test_ideas_profile_is_reserved_for_the_root_ideas_file(self) -> None:
        result = self.run_bundle({"notes.md": ideas_text(body="x\n")})
        self.assertIn("ERROR IDEAS_PROFILE notes.md", result.stdout)
        nested = self.run_bundle({"area/ideas.md": ideas_text(body="x\n")})
        self.assertIn("ERROR IDEAS_LOCATION area/ideas.md", nested.stdout)

    def test_ideas_profile_needs_a_description(self) -> None:
        result = self.run_bundle({"ideas.md": ideas_text(description=False)})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("description`", result.stdout)



if __name__ == "__main__":
    unittest.main()

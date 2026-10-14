from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"
FEEDBACK_DESCRIPTION = "Collects what went wrong in agent work; open only in a filtering session."


def feedback_text(*, profile: str = "feedback", description: bool = True, body: str = "") -> str:
    return (
        f"---\nbkf: {profile}\n"
        + (f"description: {FEEDBACK_DESCRIPTION}\n" if description else "")
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


class FeedbackTests(unittest.TestCase):
    def run_bundle(self, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, files)
            return validate(root)

    def test_a_bundle_needs_no_log_or_feedback_file(self) -> None:
        result = self.run_bundle({})
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_feedback_file_with_free_form_or_empty_body_is_conformant(self) -> None:
        for body in ("", "just a line, no headings or dates\n- an entry\n"):
            result = self.run_bundle({"feedback.md": feedback_text(body=body)})
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_feedback_file_is_listed_in_the_map_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, {"feedback.md": feedback_text()})
            map_text = (root / "MAP.md").read_text(encoding="utf-8")
        self.assertIn(f"| {FEEDBACK_DESCRIPTION} | [feedback.md](/feedback.md) |", map_text)

    def test_root_feedback_without_bkf_is_an_error(self) -> None:
        result = self.run_bundle({"feedback.md": "# Feedback\n"})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("ERROR ROOT_FEEDBACK_UNTRACKED feedback.md", result.stdout)

    def test_root_feedback_file_must_use_the_feedback_profile(self) -> None:
        document = (
            f"---\nbkf: document\ndescription: {FEEDBACK_DESCRIPTION}\ntags: [test]\n---\n\nBody.\n"
        )
        result = self.run_bundle({"feedback.md": document})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("ERROR FEEDBACK_PROFILE feedback.md", result.stdout)

    def test_feedback_profile_is_reserved_for_the_root_feedback_file(self) -> None:
        result = self.run_bundle({"notes.md": feedback_text(body="x\n")})
        self.assertIn("ERROR FEEDBACK_PROFILE notes.md", result.stdout)
        nested = self.run_bundle({"area/feedback.md": feedback_text(body="x\n")})
        self.assertIn("ERROR FEEDBACK_LOCATION area/feedback.md", nested.stdout)

    def test_feedback_profile_needs_a_description(self) -> None:
        result = self.run_bundle({"feedback.md": feedback_text(description=False)})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("description`", result.stdout)



if __name__ == "__main__":
    unittest.main()

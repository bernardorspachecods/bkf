from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_bundle import Validator


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"


def make_bundle(root: Path, search_config: str) -> None:
    (root / "MAP.md").write_text(
        "---\nbkf_version: \"0.2\"\n---\n\n# Bundle\n\n## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
        encoding="utf-8",
    )
    (root / "topic.md").write_text(
        "---\nbkf: document\ndescription: A topic.\ntags: [search]\n---\n\n# Topic\n",
        encoding="utf-8",
    )
    (root / "search.yaml").write_text(search_config, encoding="utf-8")
    subprocess.run(
        [sys.executable, str(INVENTORY), "--write", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )


def validate(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        check=False,
        capture_output=True,
        text=True,
    )
    return f"{result.returncode}\n{result.stdout}{result.stderr}"


class SearchConfigValidationTests(unittest.TestCase):
    def test_valid_search_config_passes_and_is_not_a_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, 'attached_text: [{documents: "**/*.md", text: "{stem}.txt"}]\n')

            validator = Validator(root)
            validator.validate()
            output = validate(root)

        self.assertNotIn((root / "search.yaml").resolve(), validator.member_documents)
        self.assertTrue(output.startswith("0\n"), output)
        self.assertNotIn("SEARCH_CONFIG_INVALID", output)

    def test_invalid_search_config_reports_loader_message_on_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, "attached_text: true\n")

            output = validate(root)

        self.assertTrue(output.startswith("1\n"), output)
        self.assertIn(
            "ERROR SEARCH_CONFIG_INVALID search.yaml: search.yaml: `attached_text` must be a list\n",
            output,
        )


if __name__ == "__main__":
    unittest.main()

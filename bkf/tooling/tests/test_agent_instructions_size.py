from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"

ROOT_FRONT = '---\nbkf_version: "0.2"\n---\n\n'
WARNING = "WARNING AGENT_INSTRUCTIONS_LONG {path}: {name} is loaded into every session; its body has {words} words (limit 250)."


def instructions(words: int, description: str = "Agent instructions for the test.") -> str:
    return f"---\nbkf: document\ndescription: {description}\ntags: [test]\n---\n" + "word " * words + "\n"


def build(root: Path, files: dict[str, str]) -> None:
    (root / "MAP.md").write_text(ROOT_FRONT + "# Map\n", encoding="utf-8")
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    subprocess.run(
        [sys.executable, str(INVENTORY), "--write", str(root)],
        check=False, capture_output=True, text=True,
    )


def validate(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        check=False, capture_output=True, text=True,
    )
    return result.stdout


class AgentInstructionsSizeTests(unittest.TestCase):
    def test_body_over_the_limit_warns_with_its_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, {"AGENTS.md": instructions(251)})

            self.assertIn(WARNING.format(path="AGENTS.md", name="AGENTS.md", words=251), validate(root))

    def test_body_at_the_limit_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, {"AGENTS.md": instructions(250)})

            self.assertNotIn("AGENT_INSTRUCTIONS_LONG", validate(root))

    def test_frontmatter_is_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            long_description = " ".join(["detail"] * 400)
            build(root, {"AGENTS.md": instructions(10, description=long_description)})

            self.assertNotIn("AGENT_INSTRUCTIONS_LONG", validate(root))

    def test_claude_md_in_a_subfolder_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, {"area/CLAUDE.md": instructions(300)})

            self.assertIn(
                WARNING.format(path="area/CLAUDE.md", name="CLAUDE.md", words=300),
                validate(root),
            )


if __name__ == "__main__":
    unittest.main()

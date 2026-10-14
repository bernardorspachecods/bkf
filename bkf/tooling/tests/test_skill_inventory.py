from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
INVENTORY = TOOLING / "generate_inventory.py"


def run_inventory(library: Path, skills: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INVENTORY), str(library), "--skills", str(skills), *flags],
        check=False,
        capture_output=True,
        text=True,
    )


def add_document(path: Path, description: str, tags: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nbkf: document\ndescription: {description}\ntags: {tags}\n---\n\n# {path.stem}\n",
        encoding="utf-8",
    )


class SkillInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.skills = self.root / "skills"
        self.library.mkdir()
        self.skills.mkdir()
        (self.library / "MAP.md").write_text(
            "---\nbkf_version: \"0.1\"\n---\n\n# Library\n\n## Member inventory\n\n"
            "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
            "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
            encoding="utf-8",
        )
        add_document(self.library / "modules" / "zeta.md", "Zeta module description.", "[code]")
        add_document(self.library / "modules" / "alpha.md", "Alpha module description.", "[always, code]")
        add_document(self.library / "workflow-types" / "beta.md", "Beta workflow description.", "[code]")
        add_document(self.library / "modules" / "other.md", "Other module.", "[writing]")
        (self.skills / "sample").mkdir()
        self.skill = self.skills / "sample" / "SKILL.md"
        self.skill.write_text(
            "# Sample skill\n\nAuthored before.\n"
            "<!-- BKF:GENERATED-TAGGED-LIST tags: code, always -->\n"
            "old list\n"
            "<!-- BKF:GENERATED-TAGGED-LIST-END -->\n"
            "Authored after.\n",
            encoding="utf-8",
        )
        subprocess.run([sys.executable, str(INVENTORY), str(self.library), "--write"], check=True, capture_output=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_preview_check_write_and_check_round_trip(self) -> None:
        original = self.skill.read_text(encoding="utf-8")
        preview = run_inventory(self.library, self.skills)
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertIn("Alpha module description", preview.stdout)
        self.assertIn("Beta workflow description", preview.stdout)
        self.assertIn("../../library/modules/alpha.md", preview.stdout)
        self.assertIn("../../library/workflow-types/beta.md", preview.stdout)
        self.assertLess(preview.stdout.index("alpha.md"), preview.stdout.index("zeta.md"))
        self.assertLess(preview.stdout.index("zeta.md"), preview.stdout.index("beta.md"))
        self.assertEqual(self.skill.read_text(encoding="utf-8"), original)

        stale = run_inventory(self.library, self.skills, "--check")
        self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
        self.assertIn("stale: sample/SKILL.md", stale.stdout)

        written = run_inventory(self.library, self.skills, "--write")
        self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
        actual = self.skill.read_text(encoding="utf-8")
        self.assertIn("Authored before.", actual)
        self.assertIn("Authored after.", actual)
        self.assertIn("| What it is | Document |", actual)
        self.assertIn("| Alpha module description. | [alpha.md](../../library/modules/alpha.md) |", actual)
        self.assertIn("| Beta workflow description. | [beta.md](../../library/workflow-types/beta.md) |", actual)
        self.assertEqual(run_inventory(self.library, self.skills, "--check").returncode, 0)

    def test_skill_without_markers_is_unchanged(self) -> None:
        plain = self.skills / "plain" / "SKILL.md"
        plain.parent.mkdir()
        plain.write_text("# Plain\n\nAuthored list.\n", encoding="utf-8")
        result = run_inventory(self.library, self.skills, "--write")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(plain.read_text(encoding="utf-8"), "# Plain\n\nAuthored list.\n")

    def test_invalid_marker_errors_write_nothing(self) -> None:
        for markers in (
            "<!-- BKF:GENERATED-TAGGED-LIST tags: -->\nold\n<!-- BKF:GENERATED-TAGGED-LIST-END -->\n",
            "<!-- BKF:GENERATED-TAGGED-LIST tags: code -->\nold\n",
            "<!-- BKF:GENERATED-TAGGED-LIST tags: code -->\nold\n"
            "<!-- BKF:GENERATED-TAGGED-LIST-END -->\n"
            "<!-- BKF:GENERATED-TAGGED-LIST tags: code -->\nold\n"
            "<!-- BKF:GENERATED-TAGGED-LIST-END -->\n",
        ):
            with self.subTest(markers=markers):
                original = "# Sample\n" + markers
                self.skill.write_text(original, encoding="utf-8")
                map_before = (self.library / "MAP.md").read_bytes()
                result = run_inventory(self.library, self.skills, "--write")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(self.skill.read_text(encoding="utf-8"), original)
                self.assertEqual((self.library / "MAP.md").read_bytes(), map_before)

    def test_matching_file_without_description_is_an_error(self) -> None:
        path = self.library / "modules" / "missing-description.md"
        path.write_text("---\ntags: [code]\n---\n\n# No description\n", encoding="utf-8")
        original = self.skill.read_bytes()
        map_before = (self.library / "MAP.md").read_bytes()
        result = run_inventory(self.library, self.skills, "--write")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("matching file needs a non-empty description", result.stderr)
        self.assertEqual(self.skill.read_bytes(), original)
        self.assertEqual((self.library / "MAP.md").read_bytes(), map_before)


if __name__ == "__main__":
    unittest.main()

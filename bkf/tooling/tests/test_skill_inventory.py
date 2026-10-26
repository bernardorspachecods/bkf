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


class SkillWithoutDirectivesTests(unittest.TestCase):
    def test_skill_without_inject_directives_is_unchanged_and_old_tagged_markers_are_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / "modules"
            skills = root / "skills"
            modules.mkdir()
            (skills / "plain").mkdir(parents=True)
            (modules / "MAP.md").write_text(
                "---\nbkf_version: \"0.1\"\n---\n\n# Modules\n\n## Member inventory\n\n"
                "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
                "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
                encoding="utf-8",
            )
            plain = skills / "plain" / "SKILL.md"
            text = "# Plain\n\nAuthored list.\n<!-- BKF:GENERATED-TAGGED-LIST tags: code -->\nold\n"
            plain.write_text(text, encoding="utf-8")
            result = run_inventory(modules, skills, "--write")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(plain.read_text(encoding="utf-8"), text)


class SkillInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.skills = self.root / "skills"
        (self.library / "modules").mkdir(parents=True)
        (self.skills / "sample").mkdir(parents=True)
        (self.library / "MAP.md").write_text(
            "---\nbkf_version: \"0.1\"\n---\n\n# Library\n\n## Member inventory\n\n"
            "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
            "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
            encoding="utf-8",
        )
        self.module = self.library / "modules" / "rule.md"
        self.module.write_text(
            "---\nbkf: document\ndescription: A rule.\ntags: [code]\n---\n\n# Rule\n\n"
            "- Always do the thing, see [other](other.md) and [site](https://example.com/a).\n\n"
            "## Detail\n\n```\n# not a heading\n```\n",
            encoding="utf-8",
        )
        (self.library / "modules" / "other.md").write_text("# Other\n", encoding="utf-8")
        subprocess.run([sys.executable, str(INVENTORY), str(self.library), "--write"], check=True, capture_output=True)
        self.skill = self.skills / "sample" / "SKILL.md"
        self.directive = "<!-- inject: ../../library/modules/rule.md -->\n"
        self.skill.write_text(f"# Sample\n\nBefore.\n\n{self.directive}\nAfter.\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_directive_expands_into_a_generated_block(self) -> None:
        self.assertEqual(run_inventory(self.library, self.skills, "--check").returncode, 1)
        result = run_inventory(self.library, self.skills, "--write")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.skill.read_text(encoding="utf-8")
        self.assertIn(self.directive + "<!-- BKF:GENERATED-INJECTED -->\n## Rule\n", text)
        self.assertIn("- Always do the thing", text)
        self.assertNotIn("description: A rule.", text)
        self.assertIn("### Detail", text)
        self.assertIn("# not a heading", text)
        self.assertNotIn("## not a heading", text)
        self.assertIn("[other](../../library/modules/other.md)", text)
        self.assertIn("[site](https://example.com/a)", text)
        self.assertTrue(text.index("Before.") < text.index("## Rule") < text.index("After."))
        self.assertEqual(run_inventory(self.library, self.skills, "--check").returncode, 0)

    def test_a_changed_source_makes_the_block_stale_and_write_replaces_it(self) -> None:
        run_inventory(self.library, self.skills, "--write")
        self.module.write_text(self.module.read_text(encoding="utf-8").replace("Always do", "Never skip"), encoding="utf-8")
        stale = run_inventory(self.library, self.skills, "--check")
        self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
        self.assertIn("stale: sample/SKILL.md", stale.stdout)
        run_inventory(self.library, self.skills, "--write")
        text = self.skill.read_text(encoding="utf-8")
        self.assertIn("Never skip the thing", text)
        self.assertNotIn("Always do the thing", text)
        self.assertEqual(text.count("<!-- BKF:GENERATED-INJECTED -->"), 1)

    def test_write_twice_changes_nothing(self) -> None:
        run_inventory(self.library, self.skills, "--write")
        once = self.skill.read_bytes()
        run_inventory(self.library, self.skills, "--write")
        self.assertEqual(self.skill.read_bytes(), once)

    def test_errors_write_nothing(self) -> None:
        cases = {
            "missing target": "<!-- inject: ../../library/modules/nope.md -->\n",
            "not markdown": "<!-- inject: ../../library/MAP.txt -->\n",
            "unclosed block": self.directive + "<!-- BKF:GENERATED-INJECTED -->\nold\n",
            "block without directive": "<!-- BKF:GENERATED-INJECTED -->\nold\n<!-- BKF:GENERATED-INJECTED-END -->\n",
        }
        (self.library / "MAP.txt").write_text("x\n", encoding="utf-8")
        for name, body in cases.items():
            with self.subTest(name):
                original = f"# Sample\n\n{body}"
                self.skill.write_text(original, encoding="utf-8")
                result = run_inventory(self.library, self.skills, "--write")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(self.skill.read_text(encoding="utf-8"), original)

    def test_a_bundle_root_link_in_the_source_is_an_error(self) -> None:
        self.module.write_text("# Rule\n\nSee [x](/modules/other.md).\n", encoding="utf-8")
        result = run_inventory(self.library, self.skills, "--write")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("bundle-root links", result.stderr)

    def test_two_directives_expand_in_order(self) -> None:
        self.skill.write_text(
            "# Sample\n\n<!-- inject: ../../library/modules/other.md -->\n\nMid.\n\n" + self.directive,
            encoding="utf-8",
        )
        run_inventory(self.library, self.skills, "--write")
        text = self.skill.read_text(encoding="utf-8")
        self.assertTrue(text.index("## Other") < text.index("Mid.") < text.index("## Rule"))


if __name__ == "__main__":
    unittest.main()

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from harness.inject import inject_rules


HARNESS_DIR = pathlib.Path(__file__).resolve().parents[1]


class InjectRulesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.guides = self.root / "roles"
        self.modules = self.root / "modules"
        self.guides.mkdir()
        self.modules.mkdir()
        self.rule = self.modules / "rule.md"
        self.rule.write_bytes(
            b"---\nbkf: document\ndescription: Rule\n---\n\n# Rule\n\n- Keep it.\n"
        )
        (self.modules / "other.md").write_bytes(b"---\nfront: matter\n---\n\n- Other.\n")

    def tearDown(self):
        self.temp.cleanup()

    def guide(self, name, text):
        path = self.guides / name
        path.write_text(text, encoding="utf-8")
        return path

    def prompt(self, guides=()):
        path = self.root / "brief.md"
        body = "# Brief\n\nDo it.\n"
        for guide in guides:
            body += "\n## Role\nOpen and follow the role guide: {0} (read-only).\n".format(guide)
        path.write_bytes(body.encode("utf-8"))
        return path

    def test_no_guide_is_unchanged(self):
        prompt = self.prompt()
        original = prompt.read_bytes()
        inject_rules(prompt)
        self.assertEqual(prompt.read_bytes(), original)

    def test_guide_without_directive_is_unchanged(self):
        guide = self.guide("plain.md", "# Plain guide\n\nNo directive here.\n")
        prompt = self.prompt([guide])
        original = prompt.read_bytes()
        inject_rules(prompt)
        self.assertEqual(prompt.read_bytes(), original)

    def test_one_directive_adds_body_without_frontmatter(self):
        guide = self.guide("one.md", "# One\n\n<!-- inject: ../modules/rule.md -->\n")
        prompt = self.prompt([guide])
        original = prompt.read_bytes()
        inject_rules(prompt)
        result = prompt.read_bytes()
        self.assertTrue(result.startswith(original))
        self.assertIn(b"\n\n---\n## Rules from rule\n", result)
        self.assertIn(b"The script added this text from ../modules/rule.md, as the role guide asked.\n", result)
        self.assertIn(b"\n# Rule\n\n- Keep it.\n\n<!-- rules injected by the script -->\n", result)
        self.assertNotIn(b"description: Rule", result)
        self.assertNotIn(b"bkf: document", result)

    def test_running_twice_adds_once(self):
        guide = self.guide("one.md", "<!-- inject: ../modules/rule.md -->\n")
        prompt = self.prompt([guide])
        inject_rules(prompt)
        once = prompt.read_bytes()
        inject_rules(prompt)
        self.assertEqual(prompt.read_bytes(), once)

    def test_two_directives_keep_order(self):
        guide = self.guide(
            "two.md", "<!-- inject: ../modules/rule.md -->\n<!-- inject: ../modules/other.md -->\n"
        )
        prompt = self.prompt([guide])
        inject_rules(prompt)
        result = prompt.read_bytes()
        self.assertLess(result.index(b"- Keep it."), result.index(b"- Other."))

    def test_missing_file_fails_without_changing_prompt(self):
        guide = self.guide("bad.md", "<!-- inject: ../modules/missing.md -->\n")
        prompt = self.prompt([guide])
        original = prompt.read_bytes()
        with self.assertRaises(Exception) as raised:
            inject_rules(prompt)
        self.assertIn("missing.md", str(raised.exception))
        self.assertEqual(prompt.read_bytes(), original)

    def test_absolute_directive_path_stays_under_guide_directory(self):
        # A leading slash remains relative to the guide directory, as in lib-inject.sh.
        target = self.root / "absolute-rule.md"
        target.write_bytes(b"# Absolute rule\n")
        guide = self.guide("absolute.md", "<!-- inject: {0} -->\n".format(target))
        prompt_py = self.prompt([guide])
        original = prompt_py.read_bytes()

        with self.assertRaises(Exception) as raised:
            inject_rules(prompt_py)
        self.assertIn("does not exist", str(raised.exception))
        self.assertEqual(prompt_py.read_bytes(), original)

    def test_non_markdown_file_fails_without_changing_prompt(self):
        (self.modules / "rule.md.sh").touch()
        guide = self.guide("odd.md", "<!-- inject: ../modules/rule.md.sh -->\n")
        prompt = self.prompt([guide])
        original = prompt.read_bytes()
        with self.assertRaises(Exception):
            inject_rules(prompt)
        self.assertEqual(prompt.read_bytes(), original)

    def test_duplicate_directive_is_added_once(self):
        guide = self.guide(
            "duplicate.md",
            "<!-- inject: ../modules/rule.md -->\n<!-- inject: ../modules/rule.md -->\n",
        )
        prompt = self.prompt([guide])
        inject_rules(prompt)
        self.assertEqual(prompt.read_bytes().count(b"## Rules from rule"), 1)

    def test_same_guide_named_twice_is_processed_once(self):
        guide = self.guide("one.md", "<!-- inject: ../modules/rule.md -->\n")
        prompt = self.prompt([guide, guide])
        inject_rules(prompt)
        self.assertEqual(prompt.read_bytes().count(b"## Rules from rule"), 1)

    def test_invalid_guide_does_not_partially_append_earlier_rules(self):
        good = self.guide("good.md", "<!-- inject: ../modules/rule.md -->\n")
        bad = self.guide("bad.md", "<!-- inject: ../modules/missing.md -->\n")
        prompt = self.prompt([good, bad])
        original = prompt.read_bytes()
        with self.assertRaises(Exception):
            inject_rules(prompt)
        self.assertEqual(prompt.read_bytes(), original)

class InjectCliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(HARNESS_DIR)
        return subprocess.run(
            [sys.executable, "-m", "harness", "inject", *map(str, arguments)],
            cwd=HARNESS_DIR,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_cli_usage_error_exits_two(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)

    def test_cli_missing_guide_exits_one_and_preserves_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            guide = root / "guide.md"
            guide.write_text("<!-- inject: missing.md -->\n", encoding="utf-8")
            prompt = root / "brief.md"
            prompt.write_text("role guide: {0}\n".format(guide), encoding="utf-8")
            original = prompt.read_bytes()
            result = self.run_cli(prompt)
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"does not exist", result.stderr)
            self.assertEqual(prompt.read_bytes(), original)

    def test_cli_unreadable_prompt_exits_two(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(pathlib.Path(directory))
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

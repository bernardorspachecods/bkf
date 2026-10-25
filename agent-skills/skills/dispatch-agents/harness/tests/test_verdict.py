import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from harness import cli
from harness.verdict import checked_ok, read_verdict


HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VerdictTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "problems.md")

    def write(self, content):
        with open(self.path, "w", encoding="utf-8", newline="") as output:
            output.write(content)
        return self.path

    def run_cli(self, *arguments):
        env = os.environ.copy()
        env["PYTHONPATH"] = HARNESS_DIR
        return subprocess.run(
            [sys.executable, "-m", "harness", "verdict"] + list(arguments),
            cwd=HARNESS_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_each_valid_verdict(self):
        for word in ("pass", "back", "escalate"):
            with self.subTest(word=word):
                self.assertEqual(read_verdict(self.write("VERDICT:" + word + "\n")), word)
                result = self.run_cli("read", self.path)
                self.assertEqual((result.returncode, result.stdout), (0, word + "\n"))

    def test_verdict_must_be_last_nonempty_line(self):
        self.assertIsNone(read_verdict(self.write("VERDICT:pass\nmore text\n")))
        self.assertEqual(read_verdict(self.write("VERDICT:pass\n\n  \t\n")), "pass")

    def test_verdict_whitespace_and_wrong_word(self):
        self.assertEqual(read_verdict(self.write(" VER\tDICT: pass \n")), "pass")
        self.assertIsNone(read_verdict(self.write("VERDICT:unknown\n")))

    def test_carriage_return_only_line_is_nonempty(self):
        path = self.write("VERDICT:pass\n\r\n")
        self.assertIsNone(read_verdict(path))
        self.assertFalse(checked_ok(self.write("## What I checked\n\r\n"), 2))
        self.assertTrue(checked_ok(self.write("## What I checked\n\r\n"), 1))

    def test_missing_and_empty_verdict_file(self):
        self.assertIsNone(read_verdict(os.path.join(self.temp_dir.name, "missing")))
        self.assertIsNone(read_verdict(self.write("\n  \t\n")))
        result = self.run_cli("read", self.path)
        self.assertEqual((result.returncode, result.stdout), (1, ""))

    def test_checked_section_at_start_middle_and_end(self):
        cases = (
            "## What I checked\none\ntwo\n# Later\n",
            "before\n## What I checked\none\ntwo\n# Later\nafter\n",
            "before\n## What I checked\none\ntwo\n",
        )
        for content in cases:
            with self.subTest(content=content):
                self.assertTrue(checked_ok(self.write(content), 2))

    def test_checked_count_short_and_exact(self):
        self.assertFalse(checked_ok(self.write("## What I checked\none\n"), 2))
        self.assertTrue(checked_ok(self.write("## What I checked\none\ntwo\n"), 2))

    def test_nested_heading_ends_checked_section(self):
        self.assertFalse(
            checked_ok(self.write("## What I checked\none\n### Nested\ntwo\n"), 2)
        )

    def test_zero_minimum_and_missing_checked_file(self):
        self.assertTrue(checked_ok(os.path.join(self.temp_dir.name, "missing"), 0))
        self.assertFalse(checked_ok(os.path.join(self.temp_dir.name, "missing"), 1))
        result = self.run_cli("checked", self.path, "--min", "0")
        self.assertEqual(result.returncode, 0)
        missing_result = self.run_cli(
            "checked", os.path.join(self.temp_dir.name, "missing"), "--min", "1"
        )
        self.assertEqual(missing_result.returncode, 1)

    def test_checked_cli_usage_error(self):
        result = self.run_cli("checked", self.path, "--min", "many")
        self.assertEqual(result.returncode, 2)

    def test_checked_cli_calls_public_library_function(self):
        self.write("## What I checked\nline\n")
        with patch("harness.cli.checked_ok", return_value=True) as checked:
            result = cli.main(["verdict", "checked", self.path, "--min", "1"])

        self.assertEqual(result, 0)
        checked.assert_called_once_with(self.path, 1)

if __name__ == "__main__":
    unittest.main()

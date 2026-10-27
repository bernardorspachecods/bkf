"""Brief templates: placeholders are replaced once, and a mismatch with the values fails."""
import tempfile
import unittest
from pathlib import Path

from harness.template import TemplateError, render, render_file


class RenderTests(unittest.TestCase):
    def test_replaces_every_occurrence(self):
        self.assertEqual(render("{{a}} and {{a}} and {{b}}", {"a": "1", "b": "2"}), "1 and 1 and 2")

    def test_a_value_is_never_read_as_a_placeholder(self):
        self.assertEqual(render("{{a}} {{b}}", {"a": "{{b}}", "b": "x"}), "{{b}} x")

    def test_braces_that_are_not_placeholders_stay(self):
        self.assertEqual(render("{a} {{ b }} {{a}}", {"a": "1"}), "{a} {{ b }} 1")

    def test_a_missing_value_fails_and_names_it(self):
        with self.assertRaises(TemplateError) as error:
            render("{{a}} {{b}}", {"a": "1"}, source="t.md")
        self.assertEqual(str(error.exception), "t.md: no value for b")

    def test_an_unused_value_fails_and_names_it(self):
        with self.assertRaises(TemplateError) as error:
            render("{{a}}", {"a": "1", "c": "2"})
        self.assertIn("no placeholder for c", str(error.exception))

    def test_text_without_placeholders_is_returned_as_it_is(self):
        self.assertEqual(render("plain\r\ntext\n", {}), "plain\r\ntext\n")

    def test_render_file_keeps_the_bytes_of_the_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "brief.md"
            path.write_bytes(b"# Brief\r\n{{x}}\n")
            self.assertEqual(render_file(path, {"x": "ok"}), "# Brief\r\nok\n")
            with self.assertRaises(TemplateError) as error:
                render_file(path, {})
            self.assertEqual(str(error.exception), "brief.md: no value for x")


if __name__ == "__main__":
    unittest.main()

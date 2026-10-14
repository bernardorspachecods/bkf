from __future__ import annotations

import contextlib
import io
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import log_entry


MAP = '---\nbkf_version: "0.1"\ndescription: A test bundle.\n---\n\n# Map\n'


def today_heading(text: str) -> str:
    return f"## {log_entry.dt.date.today().isoformat()}: {text}"


class LogEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / "bundle"
        self.root.mkdir()
        (self.root / "MAP.md").write_text(MAP)
        (self.root / "ideas.md").write_text("# Ideas\n")
        (self.root / "feedback.md").write_text("# Feedback")

    def test_short_single_line_has_no_quote_block(self) -> None:
        path = log_entry.write_entry("idea", "A small idea", self.root)
        content = path.read_text()
        self.assertIn("## ", content)
        self.assertIn(": A small idea\n\nRaised by the user", content)
        self.assertNotIn("> A small idea", content)

    def test_seventy_character_heading_is_not_repeated(self) -> None:
        text = "x" * 70
        log_entry.write_entry("idea", text, self.root)
        content = (self.root / "ideas.md").read_text()
        self.assertIn(f": {text}\n\nRaised", content)
        self.assertNotIn(f"> {text}", content)

    def test_long_text_heading_is_cut_at_a_word_boundary_and_quoted_once(self) -> None:
        text = "one two three four five six seven eight nine ten eleven twelve thirteen"
        log_entry.write_entry("idea", text, self.root)
        content = (self.root / "ideas.md").read_text()
        heading = content.splitlines()[2]
        self.assertTrue(heading.endswith("…"))
        self.assertLessEqual(len(heading.removeprefix(today_heading(""))), 61)
        self.assertTrue(heading.removesuffix("…").endswith(("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen")))
        self.assertIn(f"> {text}\n\nRaised", content)
        self.assertEqual(content.count(text), 1)

    def test_heading_collapses_whitespace_before_measuring(self) -> None:
        text = "short  " * 11
        log_entry.write_entry("idea", text, self.root)
        content = (self.root / "ideas.md").read_text()
        self.assertIn(": short short short", content)
        self.assertNotIn("…", content)

    def test_multiline_text_is_quoted_and_heading_uses_first_line(self) -> None:
        log_entry.write_entry("idea", "First line\nsecond line", self.root)
        content = (self.root / "ideas.md").read_text()
        self.assertIn(": First line\n\n> First line\n> second line", content)

    def test_feedback_entry_has_feedback_label_and_context_excerpt(self) -> None:
        path = self.root / "feedback.md"
        path.write_text("# Feedback\n\n## Older feedback\n\nOld\n")
        log_entry.write_entry("feedback", "Please correct this", self.root, "Earlier answer")
        content = path.read_text()
        self.assertLess(content.index(today_heading("Please correct this")), content.index("## Older feedback"))
        self.assertIn("Noticed by the user, working in", content)
        self.assertIn("Just before, the agent had said:\n> Earlier answer", content)

    def test_idea_and_feedback_entries_render_repo_name_and_working_folder(self) -> None:
        subprocess.run(["git", "init"], cwd=self.base, check=True, capture_output=True)
        nested = self.root / "nested"
        nested.mkdir()
        log_entry.write_entry("idea", "At bundle root", self.root)
        log_entry.write_entry("feedback", "In nested folder", nested)
        idea = (self.root / "ideas.md").read_text()
        feedback = (self.root / "feedback.md").read_text()
        self.assertIn(f"working in {self.base.name}/bundle.", idea)
        self.assertIn(f"working in {self.base.name}/bundle/nested.", feedback)
        self.assertNotIn("..\n", idea + feedback)

    def test_context_excerpt_is_untouched_through_the_safety_limit(self) -> None:
        for length in (500, 1500, log_entry.EXCERPT_LIMIT):
            with self.subTest(length=length):
                context = "x" * length
                self.assertEqual(log_entry._excerpt(context), "> " + context)

    def test_long_context_marks_exact_omitted_characters_and_keeps_word_boundary(self) -> None:
        context = "prefix " + ("alpha " * 834)
        excerpt = log_entry._excerpt(context)
        lines = excerpt.splitlines()
        self.assertEqual(lines[0], "> [message truncated: 13 earlier characters omitted]")
        self.assertTrue(lines[1].startswith("> alpha "))
        self.assertTrue(all(line.startswith("> ") for line in lines))
        self.assertEqual(len(lines[1][2:]), len(context.strip()) - 13)

    def test_empty_context_is_omitted(self) -> None:
        log_entry.write_entry("idea", "Small", self.root, "  \n ")
        content = (self.root / "ideas.md").read_text()
        self.assertNotIn("Just before", content)

    def test_introduction_only_files_get_an_entry_after_the_introduction(self) -> None:
        cases = (
            ("empty", "", ""),
            ("no newline", "# Ideas", "# Ideas\n\n"),
            ("one newline", "# Ideas\n", "# Ideas\n\n"),
            ("one blank line", "# Ideas\n\n", "# Ideas\n\n"),
            ("several blank lines", "# Ideas\n\n\n\n", "# Ideas\n\n\n\n"),
        )
        path = self.root / "ideas.md"
        for label, initial, expected_prefix in cases:
            with self.subTest(label=label):
                path.write_text(initial)
                log_entry.write_entry("idea", "Entry", self.root)
                self.assertTrue(path.read_text().startswith(expected_prefix + "## "))
                self.assertTrue(path.read_text().endswith("\n"))

    def test_new_entries_are_inserted_before_existing_entries_and_newest_first(self) -> None:
        path = self.root / "ideas.md"
        intro = "# Ideas\n\n"
        path.write_text(intro + "## Old entry\n\nOld text\n")
        log_entry.write_entry("idea", "First", self.root)
        log_entry.write_entry("idea", "Second", self.root)
        content = path.read_text()
        headings = [line for line in content.splitlines() if line.startswith("## ")]
        self.assertEqual(headings[0].endswith(": Second"), True)
        self.assertEqual(headings[1].endswith(": First"), True)
        self.assertEqual(headings[2], "## Old entry")
        self.assertTrue(content.startswith(intro))
        self.assertIn("Second\n\nRaised by the user", content)
        self.assertIn("Raised by the user, working in", content)
        self.assertIn("working in", content)
        self.assertIn("\n\n## ", content)
        self.assertNotIn("\n\n\n## ", content)
        self.assertTrue(content.endswith("\n"))
        self.assertEqual(list(self.root.glob(".ideas.md.*.tmp")), [])

    def test_first_heading_after_extra_blank_lines_keeps_introduction_and_spacing(self) -> None:
        path = self.root / "ideas.md"
        introduction = "# Ideas\n\n\n\n"
        path.write_text(introduction + "## Existing\n\nOld\n")
        log_entry.write_entry("idea", "Newest", self.root)
        content = path.read_text()
        self.assertTrue(content.startswith(introduction + "## "))
        self.assertIn("Raised by the user, working in", content)
        self.assertIn("\n\n## Existing\n", content)

    def test_frontmatter_is_skipped_and_preserved_when_it_contains_heading_text(self) -> None:
        path = self.root / "ideas.md"
        frontmatter = '---\ntitle: "## value"\n## a frontmatter comment\n---\n\n'
        introduction = "# Ideas\n\n"
        path.write_text(frontmatter + introduction + "## Existing\n\nOld\n")
        log_entry.write_entry("idea", "Newest", self.root)
        content = path.read_text()
        self.assertTrue(content.startswith(frontmatter + introduction + "## "))
        self.assertLess(content.index(today_heading("Newest")), content.index("## Existing"))

    def test_file_without_trailing_newline_gets_one_terminal_newline(self) -> None:
        path = self.root / "ideas.md"
        path.write_text("# Ideas\n\n## Existing")
        log_entry.write_entry("idea", "Newest", self.root)
        content = path.read_text()
        self.assertTrue(content.endswith("## Existing\n"))
        self.assertFalse(content.endswith("\n\n"))

    def test_permissions_are_preserved(self) -> None:
        path = self.root / "ideas.md"
        path.chmod(0o640)
        log_entry.write_entry("idea", "Newest", self.root)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_concurrent_change_retries_and_keeps_both_updates(self) -> None:
        path = self.root / "ideas.md"
        path.write_text("# Ideas\n\n## Existing\n")
        insert = log_entry._insert_entry
        calls = 0

        def concurrent_insert(content: str, body: str) -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                path.write_text("# Ideas\n\n## Concurrent\n\nExternal edit\n## Existing\n")
            return insert(content, body)

        with mock.patch.object(log_entry, "_insert_entry", side_effect=concurrent_insert):
            log_entry.write_entry("idea", "New entry", self.root)
        content = path.read_text()
        self.assertIn(today_heading("New entry"), content)
        self.assertIn("## Concurrent\n\nExternal edit", content)
        self.assertIn("## Existing", content)
        self.assertEqual(calls, 2)
        self.assertEqual(list(self.root.glob(".ideas.md.*.tmp")), [])

    def test_three_concurrent_changes_fail_without_overwriting_or_leaking_temp_files(self) -> None:
        path = self.root / "ideas.md"
        path.write_text("# Ideas\n\n## Existing\n")
        insert = log_entry._insert_entry
        calls = 0

        def always_change(content: str, body: str) -> str:
            nonlocal calls
            calls += 1
            path.write_text(f"# Ideas\n\n## Concurrent {calls}\n")
            return insert(content, body)

        with mock.patch.object(log_entry, "_insert_entry", side_effect=always_change):
            with self.assertRaisesRegex(ValueError, "changed during all 3 write attempts"):
                log_entry.write_entry("idea", "Not written", self.root)
        self.assertEqual(calls, 3)
        self.assertEqual(path.read_text(), "# Ideas\n\n## Concurrent 3\n")
        self.assertNotIn("Not written", path.read_text())
        self.assertEqual(list(self.root.glob(".ideas.md.*.tmp")), [])

    def test_nearest_bundle_above_wins(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "MAP.md").write_text(MAP)
        (nested / "ideas.md").write_text("nested\n")
        result = log_entry.write_entry("idea", "Here", nested)
        self.assertEqual(result, nested / "ideas.md")

    def test_unique_bundle_below_is_selected(self) -> None:
        cwd = self.base / "workspace"
        bundle = cwd / "one"
        bundle.mkdir(parents=True)
        (bundle / "MAP.md").write_text(MAP)
        (bundle / "ideas.md").write_text("# Ideas\n")
        self.assertEqual(log_entry.write_entry("idea", "Here", cwd), bundle / "ideas.md")

    def test_no_target_fails_without_writing(self) -> None:
        empty = self.base / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "no bundle containing ideas.md"):
            log_entry.write_entry("idea", "Here", empty)

    def test_multiple_targets_fail_with_relative_paths(self) -> None:
        cwd = self.base / "workspace"
        cwd.mkdir()
        for name in ("one", "two"):
            bundle = cwd / name
            bundle.mkdir()
            (bundle / "MAP.md").write_text(MAP)
            (bundle / "feedback.md").write_text("# Feedback\n")
        with self.assertRaisesRegex(ValueError, r"one/feedback.md, two/feedback.md"):
            log_entry.write_entry("feedback", "Here", cwd)

    def test_git_folder_rendering_uses_relative_path(self) -> None:
        subprocess.run(["git", "init"], cwd=self.base, check=True, capture_output=True)
        folder = self.root / "nested"
        folder.mkdir()
        self.assertEqual(log_entry._working_folder(folder), f"{self.base.name}/bundle/nested")
        self.assertEqual(log_entry._working_folder(self.base), self.base.name)

    def test_non_git_folder_rendering_uses_tilde_or_absolute_path(self) -> None:
        actual = log_entry._working_folder(self.root)
        expected = str(self.root)
        home = str(Path.home())
        if expected.startswith(home + "/"):
            expected = "~" + expected[len(home):]
        self.assertEqual(actual, expected)

    def test_cli_return_codes_and_error_output(self) -> None:
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(log_entry.main(["idea", "CLI idea", "--cwd", str(self.root)]), 0)
        self.assertTrue(output.getvalue().strip().endswith("ideas.md"))
        output, errors = io.StringIO(), io.StringIO()
        empty = self.base / "empty"
        empty.mkdir()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(log_entry.main(["idea", "No target", "--cwd", str(empty)]), 1)
        self.assertIn("no bundle", errors.getvalue())
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            self.assertEqual(log_entry.main(["other", "Bad kind"]), 1)


if __name__ == "__main__":
    unittest.main()

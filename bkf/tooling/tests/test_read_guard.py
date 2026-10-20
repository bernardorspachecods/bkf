from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import read_guard


class ReadGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.state = self.root / "state"
        self.file = self.root / "large.md"
        self.write_document()

    def write_document(self, navigation: str | None = None) -> None:
        navigation = navigation if navigation is not None else (
            "## Navigation map\n\n"
            "| If you need to... | See |\n"
            "| --- | --- |\n"
            "| Find purpose | [Purpose](#purpose) |\n"
            "| Find steps | [First](#repeat) and [Second](#repeat-1) |\n"
            "| Find numbered | [Numbered](#2-details) |\n"
            "| Find broken | [Missing](#missing) |\n"
            "| Find other | [Other](/other.md#part) |\n\n"
        )
        body = (
            "# Large\n\n" + navigation +
            "## Purpose\n" + "purpose content\n" * 3 +
            "## Repeat\n" + "repeat content\n" * 2 +
            "## Repeat\n" + "repeat content\n" * 2 +
            "## 2 Details\n" + "numbered content\n" * 2 +
            "## Last\n" + "last content\n" * 1000
        )
        self.file.write_text(body, encoding="utf-8")

    def read(self, *, session: str = "s", file: Path | None = None, **tool_input: object) -> dict | None:
        data = {
            "session_id": session,
            "cwd": str(self.root),
            "tool_name": "Read",
            "tool_input": {"file_path": str(file or self.file), **tool_input},
        }
        return read_guard.guard(data, self.state)

    def bash(self, command: str, *, session: str = "s") -> dict | None:
        return read_guard.guard(
            {"session_id": session, "cwd": str(self.root), "tool_name": "Bash", "tool_input": {"command": command}},
            self.state,
        )

    def reason(self, result: dict) -> str:
        return result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_read_denies_once_with_resolved_section_ranges(self) -> None:
        result = self.read()
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        reason = self.reason(result)
        self.assertIn("was not read", reason)
        self.assertIn("Find purpose -> Purpose, lines", reason)
        self.assertIn("Find steps -> Repeat, lines", reason)
        self.assertIn("Find steps -> Repeat, lines 20-22", reason)
        self.assertIn("Find numbered -> 2 Details, lines", reason)
        self.assertIn("Find broken -> unresolved", reason)
        self.assertIn("[Other](/other.md#part)", reason)
        self.assertIsNone(self.read())

    def test_read_with_offset_or_limit_is_allowed(self) -> None:
        self.assertIsNone(self.read(offset=1))
        self.assertIsNone(self.read(limit=20))

    def test_small_or_unmapped_file_is_allowed(self) -> None:
        small = self.root / "small.md"
        small.write_text("## Navigation map\n| A | B |\n", encoding="utf-8")
        self.assertIsNone(self.read(file=small))
        self.file.write_text("# Large\n" + "x\n" * 1000, encoding="utf-8")
        self.assertIsNone(self.read())

    def test_threshold_is_body_lines_and_words_not_bytes(self) -> None:
        table = "## Navigation map\n\n| If you need to... | See |\n| --- | --- |\n| Find it | [Last](#last) |\n\n## Last\n"
        wide = "---\nbkf: document\ndescription: Wide.\ntags: [t]\n---\n" + table + "wide line " + "é" * 9000 + "\n"
        self.file.write_text(wide, encoding="utf-8")
        self.assertIsNone(self.read())
        self.file.write_text(table + "x\n" * 350, encoding="utf-8")
        self.assertIsNotNone(self.read(session="lines"))
        self.file.write_text(table + "word " * 2001 + "\n", encoding="utf-8")
        self.assertIsNotNone(self.read(session="words"))

    def test_frontmatter_does_not_count_toward_threshold(self) -> None:
        table = "## Navigation map\n\n| If you need to... | See |\n| --- | --- |\n| Find it | [Last](#last) |\n\n## Last\n"
        frontmatter = "---\nbkf: document\ndescription: Long.\ntags: [t]\nnotes: |\n" + "  note\n" * 400 + "---\n"
        self.file.write_text(frontmatter + table + "x\n" * 100, encoding="utf-8")
        self.assertIsNone(self.read())

    def test_cat_and_cd_cat_deny_once(self) -> None:
        result = self.bash(f"cat {self.file.name}")
        self.assertIsNotNone(result)
        self.assertIsNone(self.bash(f"cat {self.file.name}"))
        self.assertIsNone(self.read())
        self.assertIsNotNone(self.bash(f"cd {self.root} && cat {self.file.name}", session="other"))
        self.assertIsNone(self.bash(f"cd {self.root} && cat {self.file.name}", session="other"))

    def test_other_bash_commands_are_allowed(self) -> None:
        for command in (
            f"sed -n '1,5p' {self.file.name}",
            f"head {self.file.name}",
            f"cat {self.file.name} | head",
            f"cat {self.file.name} other.md",
            f"cat $(printf {self.file.name})",
            f"\ncat {self.file.name}",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command, session=command))

    def test_fenced_map_heading_and_heading_are_ignored(self) -> None:
        self.write_document(
            "```markdown\n## Navigation map\n| A | [Fake](#fake) |\n## Fake\n```\n"
            "## Navigation map\n| If you need to... | See |\n| --- | --- |\n| Real | [Actual](#actual) |\n\n"
        )
        with self.file.open("a", encoding="utf-8") as handle:
            handle.write("## Actual\nactual content\n")
        result = self.read()
        self.assertIsNotNone(result)
        reason = self.reason(result)
        self.assertIn("Real -> Actual, lines", reason)
        self.assertNotIn("Fake", reason)

    def test_unreadable_or_missing_file_is_allowed(self) -> None:
        self.assertIsNone(self.read(file=self.root / "missing.md"))
        with patch.object(Path, "read_text", side_effect=PermissionError("unreadable")):
            self.assertIsNone(self.read())

    def test_state_is_per_session_and_tracks_resolved_paths(self) -> None:
        self.assertIsNotNone(self.read(session="one"))
        self.assertIsNotNone(self.read(session="two"))
        self.assertIsNone(self.read(session="one"))
        state = json.loads((self.state / "one.guard").read_text(encoding="utf-8"))
        self.assertEqual(state, [str(self.file.resolve())])

    def test_corrupt_state_is_reset_instead_of_failing(self) -> None:
        self.state.mkdir(parents=True)
        (self.state / "s.guard").write_text("{not json", encoding="utf-8")
        self.assertIsNotNone(self.read())
        self.assertIsNone(self.read())

    def test_underscore_in_heading_keeps_its_anchor(self) -> None:
        self.write_document(
            "## Navigation map\n\n| If you need to... | See |\n| --- | --- |\n"
            "| Find it | [My section](#my_section) |\n\n"
            "## My_Section\nbody\n"
        )
        self.assertIn("Find it -> My_Section, lines", self.reason(self.read()))

    def test_heading_ending_in_hash_keeps_it(self) -> None:
        self.write_document(
            "## Navigation map\n\n| If you need to... | See |\n| --- | --- |\n"
            "| Find it | [Sharp](#c) |\n\n"
            "## C#\nbody\n## Closed ##\nbody\n"
        )
        self.assertIn("Find it -> C#, lines", self.reason(self.read()))

    def test_reason_respects_reason_limit(self) -> None:
        huge = "## Navigation map\n\n| If you need to... | See |\n| --- | --- |\n" + "| x | [" + "a" * 100 + "](##purpose) |\n" * 100
        self.write_document(huge)
        result = self.read()
        self.assertLessEqual(len(self.reason(result)), read_guard.REASON_LIMIT)


if __name__ == "__main__":
    unittest.main()

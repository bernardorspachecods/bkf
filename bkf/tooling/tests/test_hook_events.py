from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import generate_inventory
import hook_events

MAP = (
    '---\nbkf_version: "0.1"\ndescription: A test bundle.\n---\n\n# Map\n\n## Member inventory\n\n'
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
DOC = "---\nbkf: document\ndescription: A guide.\ntags: [test]\n---\n\n# Guide\n"


class HookEventsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.state = self.base / "state"
        self.root = self.base / "bundle"
        self.root.mkdir()
        (self.root / "MAP.md").write_text(MAP)
        (self.root / "guide.md").write_text(DOC)
        (self.root / "ideas.md").write_text("---\nbkf: ideas\ndescription: User ideas.\n---\n\n# Ideas\n")
        (self.root / "feedback.md").write_text("---\nbkf: feedback\ndescription: User feedback.\n---\n\n# Feedback\n")
        self.write_inventory()

    def write_inventory(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(generate_inventory.main([str(self.root), "--write"]), 0)

    def touch(self, *paths: Path, session: str = "s") -> None:
        for path in paths:
            hook_events.record(
                {"session_id": session, "cwd": str(self.base), "tool_name": "Edit", "tool_input": {"file_path": str(path)}},
                self.state,
            )

    def stop(self, session: str = "s", cwd: Path | None = None) -> dict | None:
        return hook_events.stop({"session_id": session, "cwd": str(cwd or self.base)}, self.state)

    def init_git(self) -> None:
        subprocess.run(["git", "init"], cwd=self.base, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.base, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.base, check=True)
        subprocess.run(["git", "add", "."], cwd=self.base, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.base, check=True, capture_output=True)

    def snapshot(self, session: str = "s") -> None:
        hook_events.snapshot({"session_id": session, "cwd": str(self.base)}, self.state)

    def invoke(self, event: str, data: dict) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(hook_events, "STATE_DIR", self.state), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(data))
            try:
                code = hook_events.main([event])
            finally:
                sys.stdin = stdin
        return code, stdout.getvalue(), stderr.getvalue()

    def test_last_saves_and_overwrites_and_ignores_empty_input(self) -> None:
        touched = self.state / "s.touched"
        touched.parent.mkdir(parents=True)
        touched.write_text("keep")
        hook_events.last({"session_id": "s", "last_assistant_message": "first"}, self.state)
        hook_events.last({"session_id": "s", "last_assistant_message": "second"}, self.state)
        hook_events.last({"session_id": "s", "last_assistant_message": "  "}, self.state)
        self.assertEqual((self.state / "s.last").read_text(), "second")
        self.assertEqual(touched.read_text(), "keep")

    def test_i_logs_and_returns_continue_false_using_saved_last_message(self) -> None:
        hook_events.last({"session_id": "s", "last_assistant_message": "Previous answer"}, self.state)
        code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "i: A new idea"})
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertFalse(result["continue"])
        self.assertIn("Logged idea in", result["stopReason"])
        self.assertIn("> Previous answer", (self.root / "ideas.md").read_text())

    def test_i_uses_transcript_when_saved_message_is_missing(self) -> None:
        transcript = self.base / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Earlier"}, {"type": "text", "text": "response"}]}}) + "\n"
        )
        self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "i: Idea", "transcript_path": str(transcript)})
        self.assertIn("> Earlier\n> \n> response", (self.root / "ideas.md").read_text())

    def test_i_works_without_context(self) -> None:
        code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "i: No context"})
        self.assertEqual(code, 0)
        self.assertFalse((self.root / "ideas.md").read_text().count("Just before"))
        self.assertIn("Logged idea", json.loads(output)["stopReason"])

    def test_dash_prefixes_log_without_the_last_message(self) -> None:
        hook_events.last({"session_id": "s", "last_assistant_message": "Previous answer"}, self.state)
        for prompt, name, label in (("i-: Unrelated idea", "ideas.md", "idea"), ("F- : Unrelated feedback", "feedback.md", "feedback")):
            code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": prompt})
            self.assertEqual(code, 0)
            self.assertIn(f"Logged {label} in", json.loads(output)["stopReason"])
            text = (self.root / name).read_text()
            self.assertIn(prompt.split(":", 1)[1].strip(), text)
            self.assertNotIn("Previous answer", text)

    def test_f_logs_silently_and_does_not_reach_the_model(self) -> None:
        code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "f: Fix the answer"})
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertFalse(result["continue"])
        self.assertIn("Logged feedback in", result["stopReason"])
        self.assertNotIn("hookSpecificOutput", result)
        self.assertIn(": Fix the answer\n", (self.root / "feedback.md").read_text())

    def test_log_failures_use_the_requested_output_formats(self) -> None:
        with patch("log_entry.write_entry", side_effect=ValueError("no matching file")):
            code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "i: idea"})
            self.assertEqual(code, 0)
            result = json.loads(output)
            self.assertFalse(result["continue"])
            self.assertEqual(result["stopReason"], "Not logged: no matching file")
            self.assertIn("systemMessage", result)
            code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "f: correction"})
            self.assertEqual(code, 0)
            result = json.loads(output)
            self.assertFalse(result["continue"])
            self.assertEqual(result["stopReason"], "Not logged: no matching file")
            self.assertIn("systemMessage", result)

    def test_prefix_matching_is_case_insensitive_and_rejects_other_text(self) -> None:
        code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "I: Uppercase"})
        self.assertEqual(code, 0)
        self.assertIn("Logged idea", json.loads(output)["stopReason"])
        for prompt in ("name: x", "nothing", "Please i: idea", "i:   ", "i-:  ", "i--: x", "w: implement", "t: talk"):
            before = (self.root / "ideas.md").read_text()
            code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": prompt})
            self.assertEqual((code, output), (0, ""))
            self.assertEqual((self.root / "ideas.md").read_text(), before)

    def test_n_prefix_no_longer_logs_or_emits_output(self) -> None:
        before = (self.root / "ideas.md").read_text()
        code, output, _ = self.invoke("log", {"session_id": "s", "cwd": str(self.root), "prompt": "n: not an idea hook"})
        self.assertEqual((code, output), (0, ""))
        self.assertEqual((self.root / "ideas.md").read_text(), before)

    def test_edited_paths_from_each_tool_shape(self) -> None:
        self.assertEqual(hook_events.edited_paths({"tool_name": "Write", "tool_input": {"file_path": "/a.md"}}), ["/a.md"])
        self.assertEqual(hook_events.edited_paths({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/n.ipynb"}}), ["/n.ipynb"])
        patch = "*** Begin Patch\n*** Update File: a.md\n*** Move to: b.md\n*** Add File: c.md\n*** Delete File: d.md\n*** End Patch"
        self.assertEqual(
            hook_events.edited_paths({"tool_name": "apply_patch", "tool_input": {"command": patch}}),
            ["a.md", "b.md", "c.md", "d.md"],
        )
        self.assertEqual(hook_events.edited_paths({"tool_name": "Bash", "tool_input": {"command": "ls"}}), [])

    def test_record_resolves_relative_paths_against_cwd(self) -> None:
        hook_events.record(
            {"session_id": "s", "cwd": str(self.root), "tool_name": "Edit", "tool_input": {"file_path": "guide.md"}},
            self.state,
        )
        self.assertEqual((self.state / "s.touched").read_text().strip(), str(self.root / "guide.md"))

    def test_nothing_touched_does_nothing(self) -> None:
        self.assertIsNone(self.stop())

    def test_clean_bundle_passes_and_clears_the_list(self) -> None:
        self.touch(self.root / "guide.md")
        self.assertIsNone(self.stop())
        self.assertFalse((self.state / "s.touched").exists())

    def test_files_outside_any_bundle_are_ignored(self) -> None:
        outside = self.base / "notes.txt"
        outside.write_text("x")
        self.touch(outside)
        self.assertIsNone(self.stop())

    def test_stale_inventory_blocks_with_the_fix(self) -> None:
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.touch(self.root / "new.md")
        result = self.stop()
        self.assertEqual(result["decision"], "block")
        self.assertIn("bkf inventory", result["reason"])
        self.assertIn("--write", result["reason"])

    def test_invalid_document_blocks_via_the_validator(self) -> None:
        (self.root / "guide.md").write_text("---\nbkf: document\ntags: [test]\n---\n\n# Guide\n")
        self.touch(self.root / "guide.md")
        result = self.stop()
        self.assertEqual(result["decision"], "block")
        self.assertIn("bkf validate", result["reason"])

    def test_blocks_at_most_twice_then_lets_the_session_stop(self) -> None:
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.touch(self.root / "new.md")
        self.assertEqual(self.stop()["decision"], "block")
        self.assertEqual(self.stop()["decision"], "block")
        self.assertIsNone(self.stop())
        self.assertFalse((self.state / "s.touched").exists())

    def test_fixing_the_problem_passes(self) -> None:
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.touch(self.root / "new.md")
        self.assertEqual(self.stop()["decision"], "block")
        self.write_inventory()
        self.assertIsNone(self.stop())

    def test_deleted_file_still_finds_its_bundle(self) -> None:
        (self.root / "guide.md").unlink()
        self.touch(self.root / "guide.md")
        result = self.stop()
        self.assertEqual(result["decision"], "block")

    def test_sessions_are_independent(self) -> None:
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.touch(self.root / "new.md", session="a")
        self.assertIsNone(self.stop(session="b"))
        self.assertEqual(self.stop(session="a")["decision"], "block")

    def test_run_entrypoint_reads_stdin_and_prints_the_block(self) -> None:
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.touch(self.root / "new.md")
        original = hook_events.STATE_DIR
        hook_events.STATE_DIR = self.state
        self.addCleanup(setattr, hook_events, "STATE_DIR", original)
        stdin, stdout = sys.stdin, io.StringIO()
        sys.stdin = io.StringIO(json.dumps({"session_id": "s"}))
        try:
            with contextlib.redirect_stdout(stdout):
                code = hook_events.main(["stop"])
        finally:
            sys.stdin = stdin
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["decision"], "block")

    def test_garbage_input_never_fails_the_host(self) -> None:
        stdin, sys.stdin = sys.stdin, io.StringIO("not json")
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(hook_events.main(["record"]), 0)
        finally:
            sys.stdin = stdin
        self.assertIn("systemMessage", json.loads(stdout.getvalue()))
        self.assertIn("record", stderr.getvalue())

    def test_handler_exceptions_are_reported_once_and_never_block(self) -> None:
        cases = (
            ("record", {"session_id": "s"}, "record"),
            ("snapshot", {"session_id": "s"}, "snapshot"),
            ("last", {"session_id": "s"}, "last"),
            ("stop", {"session_id": "s"}, "stop"),
        )
        for event, data, message in cases:
            with self.subTest(event=event):
                with patch.object(hook_events, event, side_effect=OSError(message)):
                    code, output, stderr = self.invoke(event, data)
                self.assertEqual(code, 0)
                self.assertEqual(len(output.splitlines()), 1)
                self.assertIn(event, json.loads(output)["systemMessage"])
                self.assertIn(event, stderr)

    def test_crashing_bundle_check_keeps_recorded_state_for_retry(self) -> None:
        touched = self.state / "s.touched"
        touched.parent.mkdir(parents=True)
        touched.write_text(str(self.root / "guide.md"))
        with patch.object(hook_events, "problems", side_effect=OSError("validator crashed")):
            code, output, stderr = self.invoke("stop", {"session_id": "s", "cwd": str(self.base)})
        self.assertEqual(code, 0)
        self.assertIn("validation did not run", json.loads(output)["systemMessage"])
        self.assertTrue(touched.exists())
        self.assertIn("stop", stderr)

    def test_unknown_event_is_reported_without_blocking(self) -> None:
        stdin, sys.stdin = sys.stdin, io.StringIO("{}")
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = hook_events.main(["mystery"])
        finally:
            sys.stdin = stdin
        self.assertEqual(code, 0)
        self.assertIn("mystery", json.loads(stdout.getvalue())["systemMessage"])
        self.assertIn("mystery", stderr.getvalue())

    def test_probe_imports_and_answers_without_writing_state(self) -> None:
        for event in hook_events.EVENTS:
            with self.subTest(event=event):
                code, output, stderr = self.invoke(event, {"hook_event_name": "BKFProbe", "probe": True})
                self.assertEqual(code, 0)
                self.assertEqual(output.strip(), '{"probe":"ok"}')
                self.assertEqual(stderr, "")
                self.assertFalse(self.state.exists())

    def test_guard_event_emits_pre_tool_use_deny(self) -> None:
        target = self.root / "large.md"
        target.write_text(
            "## Navigation map\n\n| Need | See |\n| --- | --- |\n| Purpose | [Purpose](#purpose) |\n\n"
            "## Purpose\n" + "content\n" * 1200,
            encoding="utf-8",
        )
        code, output, stderr = self.invoke(
            "guard",
            {"session_id": "s", "cwd": str(self.root), "hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": str(target)}},
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(output)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_shell_change_blocks_without_a_recorder_call(self) -> None:
        self.init_git()
        self.snapshot()
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.assertEqual(self.stop()["decision"], "block")

    def test_dirty_unchanged_at_baseline_does_not_trigger_a_check(self) -> None:
        self.init_git()
        (self.root / "guide.md").write_text(DOC.replace("# Guide", "# Changed Guide"))
        self.snapshot()
        self.assertIsNone(self.stop())

    def test_baseline_dirty_file_changed_later_is_checked(self) -> None:
        self.init_git()
        (self.root / "guide.md").write_text(DOC.replace("A guide.", "A changed guide."))
        self.snapshot()
        (self.root / "guide.md").write_text("---\nbkf: document\ntags: [test]\n---\n\n# Guide\n")
        self.assertEqual(self.stop()["decision"], "block")

    def test_deleted_tracked_file_is_checked(self) -> None:
        self.init_git()
        self.snapshot()
        (self.root / "guide.md").unlink()
        self.assertEqual(self.stop()["decision"], "block")

    def test_commit_after_baseline_is_checked_by_head_comparison(self) -> None:
        self.init_git()
        self.snapshot()
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        subprocess.run(["git", "add", "bundle/new.md"], cwd=self.base, check=True)
        subprocess.run(["git", "commit", "-m", "add document"], cwd=self.base, check=True, capture_output=True)
        self.assertEqual(self.stop()["decision"], "block")

    def test_committed_rename_checks_both_bundle_inventories(self) -> None:
        other = self.base / "b2"
        other.mkdir()
        (other / "MAP.md").write_text(MAP)
        (other / "guide.md").write_text(DOC.replace("A guide.", "A different guide."))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(generate_inventory.main([str(other), "--write"]), 0)

        self.init_git()
        self.snapshot()
        subprocess.run(["git", "mv", "bundle/guide.md", "b2/moved-guide.md"], cwd=self.base, check=True)
        subprocess.run(["git", "commit", "-m", "move guide"], cwd=self.base, check=True, capture_output=True)

        result = self.stop()
        self.assertEqual(result["decision"], "block")
        self.assertIn(str(self.base / "bundle"), result["reason"])
        self.assertIn(str(self.base / "b2"), result["reason"])

    def test_passing_stop_refreshes_baseline(self) -> None:
        self.init_git()
        self.snapshot()
        (self.root / "guide.md").write_text(DOC.replace("# Guide", "# Changed Guide"))
        self.assertIsNone(self.stop())
        self.assertIsNone(self.stop())

    def test_block_leaves_baseline_unchanged(self) -> None:
        self.init_git()
        self.snapshot()
        baseline = (self.state / "s.base.json").read_bytes()
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.assertEqual(self.stop()["decision"], "block")
        self.assertEqual((self.state / "s.base.json").read_bytes(), baseline)

    def test_second_snapshot_does_not_overwrite_baseline(self) -> None:
        self.init_git()
        self.snapshot()
        baseline = (self.state / "s.base.json").read_bytes()
        (self.root / "guide.md").write_text(DOC.replace("A guide.", "A changed guide."))
        self.snapshot()
        self.assertEqual((self.state / "s.base.json").read_bytes(), baseline)

    def test_more_than_2000_dirty_paths_skips_snapshot(self) -> None:
        self.init_git()
        for index in range(2001):
            (self.base / f"dirty-{index}.txt").write_text("x")
        self.snapshot()
        self.assertFalse((self.state / "s.base.json").exists())

    def test_no_repo_skips_baseline_and_recorder_still_works(self) -> None:
        self.snapshot()
        self.assertFalse((self.state / "s.base.json").exists())
        self.touch(self.root / "new.md")
        self.assertEqual((self.state / "s.touched").read_text().strip(), str(self.root / "new.md"))

    def test_recorded_paths_are_unioned_with_snapshot_changes(self) -> None:
        self.init_git()
        self.snapshot()
        (self.root / "new.md").write_text(DOC.replace("A guide.", "A new guide."))
        self.touch(self.root / "guide.md")
        self.assertEqual(self.stop()["decision"], "block")

    def test_recorder_alone_selects_a_bundle_when_git_comparison_is_unavailable(self) -> None:
        self.init_git()
        self.snapshot()
        outside = self.base / "outside-repo"
        bundle = outside / "bundle"
        bundle.mkdir(parents=True)
        (bundle / "MAP.md").write_text(MAP)
        (bundle / "guide.md").write_text(DOC)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(generate_inventory.main([str(bundle), "--write"]), 0)
        (bundle / "guide.md").write_text("---\nbkf: document\ntags: [test]\n---\n\n# Guide\n")
        hook_events.record(
            {"session_id": "s", "cwd": str(outside), "tool_name": "Edit", "tool_input": {"file_path": str(bundle / "guide.md")}},
            self.state,
        )
        self.assertEqual(self.stop(cwd=outside)["decision"], "block")


if __name__ == "__main__":
    unittest.main()

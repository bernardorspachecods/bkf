from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import context_hook
import hook_events


class ContextHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.transcript = self.home / "transcript.jsonl"

    def assistant(self, tokens: int, **usage: int) -> dict:
        totals = {"input_tokens": tokens, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        totals.update(usage)
        return {"type": "assistant", "message": {"usage": totals}}

    def warning(self, **extra) -> dict | None:
        data = {
            "hook_event_name": "PostToolUse",
            "session_id": "session/one",
            "transcript_path": str(self.transcript),
        }
        data.update(extra)
        return context_hook.handle(data, self.home)

    def write_transcript(self, *entries: dict) -> None:
        self.transcript.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")

    def test_config_defaults_and_overrides_independently(self) -> None:
        self.assertEqual(context_hook.load_config(self.home), {
            "warn_percent": 40, "compact_percent": 55, "window_tokens": 200_000,
        })
        config = self.home / ".agent-hooks" / "context.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"warn_percent": 30, "compact_percent": "bad", "window_tokens": 1000}))
        self.assertEqual(context_hook.load_config(self.home), {
            "warn_percent": 30, "compact_percent": 55, "window_tokens": 1000,
        })

    def test_below_threshold_is_silent_and_threshold_warns_once(self) -> None:
        self.write_transcript(self.assistant(79_999))
        self.assertIsNone(self.warning())
        self.write_transcript(self.assistant(80_000))
        output = self.warning()
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        message = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("40%", message)
        self.assertIn("55%", message)
        self.assertIn(str(self.home / ".agent-hooks" / "continue" / "session_one.md"), message)
        self.assertIsNone(self.warning())

    def test_usage_adds_cache_tokens_and_subagent_is_ignored(self) -> None:
        self.write_transcript(self.assistant(60_000, cache_creation_input_tokens=10_000, cache_read_input_tokens=10_000))
        self.assertIsNone(self.warning(agent_id="subagent"))
        self.assertFalse((self.home / ".agent-hooks" / "state").exists())
        output = self.warning()
        self.assertIn("40%", output["hookSpecificOutput"]["additionalContext"])

    def test_sidechain_and_precompact_assistant_are_ignored(self) -> None:
        self.write_transcript(
            self.assistant(150_000),
            {"type": "system", "subtype": "compact_boundary"},
            {**self.assistant(180_000), "isSidechain": True},
        )
        self.assertIsNone(self.warning())
        self.write_transcript(
            self.assistant(150_000),
            {"type": "system", "subtype": "compact_boundary"},
            {**self.assistant(70_000), "isSidechain": True},
            self.assistant(80_000),
        )
        self.assertIsNotNone(self.warning())

    def test_resume_injects_content_moves_file_and_clears_mark(self) -> None:
        continue_dir = self.home / ".agent-hooks" / "continue"
        continue_dir.mkdir(parents=True)
        continuation = continue_dir / "session_one.md"
        continuation.write_text("Continue by finishing the parser.", encoding="utf-8")
        state = self.home / ".agent-hooks" / "state"
        mark = hook_events._state("session/one", "context-warned", state)
        mark.parent.mkdir(parents=True)
        mark.write_text("warned\n")
        output = context_hook.handle({"hook_event_name": "SessionStart", "source": "compact", "session_id": "session/one"}, self.home)
        payload = output["hookSpecificOutput"]
        self.assertEqual(payload["hookEventName"], "SessionStart")
        self.assertIn("just compacted", payload["additionalContext"])
        self.assertIn("Continue by finishing the parser.", payload["additionalContext"])
        moved = list((continue_dir / "used").glob("session_one.*.md"))
        self.assertEqual(len(moved), 1)
        self.assertFalse(continuation.exists())
        self.assertFalse(mark.exists())

    def test_resume_without_continuation_after_warning_reports_system_message(self) -> None:
        state = self.home / ".agent-hooks" / "state"
        mark = hook_events._state("s", "context-warned", state)
        mark.parent.mkdir(parents=True)
        mark.write_text("warned\n")
        output = context_hook.handle({"hook_event_name": "SessionStart", "source": "compact", "session_id": "s"}, self.home)
        self.assertEqual(output, {"systemMessage": "bkf context: compacted without a continuation message"})
        self.assertFalse(mark.exists())

    def test_noncompact_session_start_and_malformed_transcript_are_silent(self) -> None:
        self.assertIsNone(context_hook.handle({"hook_event_name": "SessionStart", "source": "startup", "session_id": "s"}, self.home))
        self.transcript.write_text('{"type":"assistant"}\nnot json\n')
        self.assertIsNone(self.warning())

    def test_dispatch_routes_context_event_and_probe_imports(self) -> None:
        self.assertIn("context", hook_events.EVENTS)
        with patch.object(context_hook, "handle", return_value={"systemMessage": "routed"}) as handle:
            with patch.object(hook_events, "STATE_DIR", self.home / ".agent-hooks" / "state"):
                from io import StringIO
                import contextlib

                out = StringIO()
                with patch.object(sys, "stdin", StringIO(json.dumps({"hook_event_name": "SessionStart", "source": "other"}))), contextlib.redirect_stdout(out):
                    self.assertEqual(hook_events.main(["context"]), 0)
                self.assertEqual(json.loads(out.getvalue()), {"systemMessage": "routed"})
                handle.assert_called_once()
        with patch("importlib.import_module", wraps=__import__("importlib").import_module) as importer:
            hook_events._probe("context")
            importer.assert_called_once_with("context_hook")


if __name__ == "__main__":
    unittest.main()

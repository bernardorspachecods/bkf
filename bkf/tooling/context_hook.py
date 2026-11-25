"""Warn before context compaction and restore the agent's continuation note."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import hook_events

DEFAULT_WARN_PERCENT = 45
DEFAULT_COMPACT_PERCENT = 55
DEFAULT_WINDOW_TOKENS = 1_000_000
# The final warning comes this many points before compaction, when the note must match the current state.
FINAL_MARGIN_PERCENT = 3
TITLE_TAIL_BYTES = hook_events.TITLE_TAIL_BYTES


def load_config(home: Path) -> dict[str, int]:
    """Load context thresholds, falling back independently for invalid values."""
    defaults = {
        "warn_percent": DEFAULT_WARN_PERCENT,
        "compact_percent": DEFAULT_COMPACT_PERCENT,
        "window_tokens": DEFAULT_WINDOW_TOKENS,
    }
    try:
        configured = json.loads((home / ".agent-hooks" / "context.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return defaults
    if not isinstance(configured, dict):
        return defaults
    for key, maximum in (("warn_percent", 100), ("compact_percent", 100), ("window_tokens", None)):
        value = configured.get(key)
        valid = type(value) is int and value > 0 if key == "window_tokens" else type(value) is int and 0 <= value <= maximum
        if valid:
            defaults[key] = value
    return defaults


def _tail_lines(transcript: Path) -> list[str] | None:
    try:
        with transcript.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            start = max(0, handle.tell() - TITLE_TAIL_BYTES)
            at_line_start = start == 0
            if start:
                handle.seek(start - 1)
                at_line_start = handle.read(1) in {b"\n", b"\r"}
            handle.seek(start)
            content = handle.read().decode("utf-8")
    except (OSError, UnicodeError):
        return None
    lines = content.splitlines()
    # The first line can be a partial JSON record when the byte tail starts mid-line.
    if start and not at_line_start and lines:
        lines = lines[1:]
    return lines


def _latest_usage(transcript: Path) -> dict | None:
    lines = _tail_lines(transcript)
    if lines is None:
        return None
    entries: list[dict] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            # A partial record at the tail boundary was discarded above.
            return None
        if isinstance(entry, dict):
            entries.append(entry)
    boundary = max(
        (index for index, entry in enumerate(entries)
         if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary"),
        default=-1,
    )
    for entry in reversed(entries[boundary + 1:]):
        if entry.get("type") != "assistant" or entry.get("isSidechain") is True:
            continue
        message = entry.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            return None
        if "input_tokens" not in usage:
            return None
        parts = [usage["input_tokens"], usage.get("cache_creation_input_tokens", 0), usage.get("cache_read_input_tokens", 0)]
        if any(type(part) is not int or part < 0 for part in parts):
            return None
        return {"input_tokens": sum(parts)}
    return None


def _context_path(home: Path, session_id: str) -> Path:
    return hook_events._state(session_id, "md", home / ".agent-hooks" / "continue")


def handle(data: dict, home: Path | None = None) -> dict | None:
    """Handle context warning events and compact-triggered session resumes."""
    home = (home or Path.home()).expanduser().resolve()
    event = data.get("hook_event_name")
    session_id = data.get("session_id", "")
    state_dir = home / ".agent-hooks" / "state"
    warned = hook_events._state(session_id, "context-warned", state_dir)
    final = hook_events._state(session_id, "context-final", state_dir)

    if event == "SessionStart":
        if data.get("source") != "compact":
            return None
        continuation = _context_path(home, session_id)
        try:
            content = continuation.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            content = ""
        output = None
        if content:
            used = home / ".agent-hooks" / "continue" / "used"
            used.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            destination = used / f"{continuation.stem}.{timestamp}.md"
            continuation.replace(destination)
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "This session was just compacted. The following message, written by the agent before compaction, "
                        "says how to continue:\n\n" + content
                    ),
                }
            }
        elif warned.exists():
            output = {"systemMessage": "bkf context: compacted without a continuation message"}
        warned.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        hook_events._prune(state_dir)
        return output

    if event not in {"PostToolUse", "UserPromptSubmit"} or data.get("agent_id"):
        return None
    transcript = data.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return None
    usage = _latest_usage(Path(transcript))
    if usage is None:
        return None
    config = load_config(home)
    percent = usage["input_tokens"] / config["window_tokens"] * 100
    final_percent = config["compact_percent"] - FINAL_MARGIN_PERCENT
    if percent < config["warn_percent"]:
        return None
    continuation = _context_path(home, session_id)
    if not warned.exists():
        message = (
            f"BKF context hook: context is at {round(percent)}% of the window. This session will be compacted "
            f"automatically at about {config['compact_percent']}%. At the next safe point (not in the middle of an edit), "
            "read ~/.claude/skills/before-context-loss/SKILL.md and follow its automatic mode: write to documents what "
            f"the work needs to continue, then write the continuation message to {continuation} (absolute path). A "
            "second warning comes just before compaction to bring it up to date. Then carry on with the task; do not "
            "ask the user to compact."
        )
        marks = [warned, final] if percent >= final_percent else [warned]
    elif percent >= final_percent and not final.exists():
        message = (
            f"BKF context hook: context is at {round(percent)}% of the window; compaction at about "
            f"{config['compact_percent']}% is a few turns away. At the next safe point, rewrite the continuation "
            f"message at {continuation} so it matches the current state: what is done, what is in progress, and the "
            "next step, pointing to the documents that hold the details. Then carry on with the task."
        )
        marks = [final]
    else:
        return None
    for mark in marks:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text("warned\n", encoding="utf-8")
    hook_events._prune(state_dir)
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}

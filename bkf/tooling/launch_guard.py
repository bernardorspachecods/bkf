"""Refuse a long-run launcher started in the foreground or backgrounded by hand."""

from __future__ import annotations

import os
import re
import shlex

LAUNCHERS = {
    "plan-run.sh": {"start", "resume"},
    "review-run.sh": {"start", "resume"},
    "council-run.sh": {"start", "resume"},
    "research-run.sh": {"start", "resume"},
    "run-codex.sh": None,
}
WRAPPERS = {"bash", "sh", "zsh", "env", "nohup", "time", "exec", "command", "setsid"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SEPARATORS = {"&&", "||", ";", "|", "&", "\n"}
REASON = (
    "Launch it with run_in_background: true so the state is visible in the session. "
    "A call that starts a run script, or `codex exec`, must not run in the foreground, "
    "and must not be backgrounded by hand with nohup or a trailing &."
)


HEREDOC = re.compile(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_]*))")


def _without_heredoc_bodies(command: str) -> str:
    """Drop the text a heredoc feeds to a command: it is data, not a command that runs."""
    kept: list[str] = []
    ending: str | None = None
    for line in command.split("\n"):
        if ending is not None:
            if line.strip() == ending:
                ending = None
            continue
        kept.append(line)
        match = HEREDOC.search(line)
        if match:
            ending = next(group for group in match.groups() if group)
    return "\n".join(kept)


def _segments(command: str) -> list[tuple[list[str], str]]:
    """Split a command into (words, the separator that followed it)."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
    except ValueError:
        return []
    segments: list[tuple[list[str], str]] = []
    current: list[str] = []
    for word in words:
        if word and set(word) <= set(";&|") and word in SEPARATORS | {";;", "|&"}:
            segments.append((current, word))
            current = []
        else:
            current.append(word)
    segments.append((current, ""))
    return segments


def _program(words: list[str]) -> tuple[str, list[str]] | None:
    """The program a segment runs and its arguments, skipping assignments and wrappers."""
    rest = list(words)
    while rest:
        head = rest[0]
        if ASSIGNMENT.match(head):
            rest = rest[1:]
        elif os.path.basename(head) in WRAPPERS:
            rest = rest[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[1:]
        else:
            return os.path.basename(head), rest[1:]
    return None


def _launch(words: list[str]) -> bool:
    found = _program(words)
    if found is None:
        return False
    name, args = found
    if name == "codex":
        return bool(args) and args[0] == "exec"
    if name not in LAUNCHERS:
        return False
    allowed = LAUNCHERS[name]
    return allowed is None or bool(args and args[0] in allowed)


def check(data: dict) -> dict | None:
    """Return the PreToolUse deny payload for a launcher that is not run in the background."""
    if data.get("tool_name") != "Bash":
        return None
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    segments: list[tuple[list[str], str]] = []
    for line in _without_heredoc_bodies(command).replace("\\\n", " ").split("\n"):
        segments.extend(_segments(line))
    launches = [index for index, (words, _) in enumerate(segments) if _launch(words)]
    if not launches:
        return None
    by_hand = False
    for index in launches:
        words, separator = segments[index]
        if "nohup" in [os.path.basename(word) for word in words[:3]] or separator == "&":
            by_hand = True
    if tool_input.get("run_in_background") is True and not by_hand:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON,
    }}

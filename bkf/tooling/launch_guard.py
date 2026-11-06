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
    "delegate-run.sh": None,
}
WRAPPERS = {"bash", "sh", "zsh", "env", "nohup", "time", "exec", "command", "setsid"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SEPARATORS = {"&&", "||", ";", "|", "&", "\n"}
# Words that open a command inside a compound: `do cmd`, `then cmd`, `( cmd`, `{ cmd`.
OPENERS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "(", "time"}
LOOPS = {"for", "while", "until", "select"}
FANOUT = {"xargs", "parallel"}
SHELLS = {"bash", "sh", "zsh"}
REASON = (
    "Launch it with run_in_background: true so the state is visible in the session. "
    "A call that starts a run script, or `codex exec`, must not run in the foreground, "
    "must not be backgrounded by hand (nohup, a trailing &, a subshell), must not sit in a loop, "
    "xargs or parallel, and must start only one run: use one Bash call per run, "
    "several in the same response for runs in parallel."
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
    """The program a segment runs and its arguments, skipping assignments, wrappers and compound openers."""
    rest = list(words)
    while rest:
        head = rest[0]
        stripped = head.lstrip("({")
        if stripped != head:
            rest = ([stripped] if stripped else []) + rest[1:]
        elif head in OPENERS:
            rest = rest[1:]
        elif ASSIGNMENT.match(head):
            rest = rest[1:]
        elif os.path.basename(head) in WRAPPERS:
            rest = rest[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[1:]
        else:
            return os.path.basename(head), rest[1:]
    return None


def _expand_shell_strings(segments: list[tuple[list[str], str]]) -> list[tuple[list[str], str]]:
    """Add the commands inside `bash -c '...'` and `eval '...'` as segments, so they are judged too."""
    expanded = list(segments)
    for words, outer in segments:
        for position, word in enumerate(words):
            code = None
            if word == "-c" and position + 1 < len(words) and any(os.path.basename(w) in SHELLS for w in words[:position]):
                code = words[position + 1]
            elif word == "eval" and position + 1 < len(words):
                code = " ".join(words[position + 1:])
            if code:
                for line in code.replace("\\\n", " ").split("\n"):
                    inner = _segments(line)
                    if outer == "&" and inner:
                        inner[-1] = (inner[-1][0], "&")
                    expanded.extend(inner)
    return expanded


def _launch(words: list[str]) -> bool:
    found = _program(words)
    if found is None:
        return False
    name, args = found
    if name == "codex":
        return bool(args) and args[0] == "exec"
    if name in FANOUT:
        return any(os.path.basename(arg) in LAUNCHERS or arg == "codex" for arg in args)
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
    segments = _expand_shell_strings(segments)
    launches = [index for index, (words, _) in enumerate(segments) if _launch(words)]
    if not launches:
        return None
    by_hand = len(launches) > 1
    for index in launches:
        words, separator = segments[index]
        if "nohup" in [os.path.basename(word) for word in words[:3]] or separator == "&":
            by_hand = True
        program = _program(words)
        if program is not None and program[0] in FANOUT:
            by_hand = True
    if any(words and words[0] in LOOPS for words, _ in segments):
        by_hand = True
    if tool_input.get("run_in_background") is True and not by_hand:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON,
    }}

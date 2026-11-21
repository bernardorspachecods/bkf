"""Ask the user before an agent runs a git command that discards work."""

from __future__ import annotations

from launch_guard import _expand_shell_strings, _program, _segments, _without_heredoc_bodies

WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
REASON = (
    "This git command can discard work that is not on the default branch. "
    "Approve it only if the user asked for it or the work is already merged."
)


def _subcommand(args: list[str]) -> tuple[str, list[str]] | None:
    """The git subcommand and its arguments, after the global options."""
    rest = list(args)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in WITH_VALUE else rest[1:]
    return (rest[0], rest[1:]) if rest else None


def _flags(args: list[str]) -> set[str]:
    """Option letters and long options in args, so `-fd` counts as `-f` and `-d`."""
    found: set[str] = set()
    for arg in args:
        if arg.startswith("--"):
            found.add(arg.split("=", 1)[0])
        elif arg.startswith("-") and len(arg) > 1:
            found.update(f"-{letter}" for letter in arg[1:])
    return found


def _discards(words: list[str]) -> bool:
    found = _program(words)
    if found is None or found[0] != "git":
        return False
    sub = _subcommand(found[1])
    if sub is None:
        return False
    name, args = sub
    flags = _flags(args)
    if name == "branch":
        return "-D" in flags or ("--force" in flags or "-f" in flags) and ("-d" in flags or "--delete" in flags)
    if name == "worktree":
        return bool(args) and args[0] == "remove" and bool(flags & {"-f", "--force"})
    if name == "clean":
        return True
    if name == "reset":
        return "--hard" in flags
    if name == "push":
        return bool(flags & {"-f", "--force", "--force-with-lease", "--force-if-includes"})
    return False


def check(data: dict) -> dict | None:
    """Return the PreToolUse ask payload for a git command that discards work."""
    if data.get("tool_name") != "Bash":
        return None
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return None
    segments: list[tuple[list[str], str]] = []
    for line in _without_heredoc_bodies(command).replace("\\\n", " ").split("\n"):
        segments.extend(_segments(line))
    if not any(_discards(words) for words, _ in _expand_shell_strings(segments)):
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": REASON,
    }}

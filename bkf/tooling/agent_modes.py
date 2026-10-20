#!/usr/bin/env python3
"""Prompt-prefix modes for Claude Code and Codex hooks.

  w: <prompt>  implement right away
  t: <prompt>  talk / brainstorm only (mutating tools are blocked)
  (no prefix)  free

Same script handles UserPromptSubmit (detect prefix, inject instruction, save
mode per session) and PreToolUse (deny mutating tools while mode is talk).
"""
import json
import re
import shlex
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".agent-hooks" / "state"
PREFIX = re.compile(r"^\s*([wt])\s*:", re.IGNORECASE)

INSTRUCTIONS = {
    "w": (
        "MODE: IMPLEMENT (the user prefixed the prompt with 'w:', ignore the prefix itself). "
        "Implement right away. Do not ask for confirmation or present options first; "
        "pick sensible defaults, state them briefly, and do the work."
    ),
    "t": (
        "MODE: TALK / BRAINSTORM (the user prefixed the prompt with 't:', ignore the prefix itself). "
        "Discuss only. Do not implement anything: no file edits, no commands that change state. "
        "A hook blocks mutating tools in this mode. Reading and searching files is fine, and so is Bash when every command in it is read-only (ls, cat, rg, git log, psql with a single SELECT). "
        "Explore the idea, give opinions, compare approaches, ask questions."
    ),
}

READONLY_CMDS = {
    # inspect
    "ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "fd", "find", "tree",
    "file", "stat", "du", "df", "less", "more", "nl", "od", "xxd", "strings", "column",
    "base64", "shasum", "md5", "md5sum", "sha256sum", "diff", "cmp", "jq", "yq", "awk",
    # path / text helpers
    "pwd", "basename", "dirname", "realpath", "readlink", "sort", "uniq", "cut", "tr",
    "echo", "printf", "true", "false", "date", "env", "printenv",
    # lookup
    "which", "type", "command", "whoami", "id", "hostname", "uname", "ps", "lsof",
    # navigation / conditions
    "cd", "pushd", "popd", "test", "[", "[[",
}
READONLY_GIT = {
    "status", "log", "diff", "show", "remote", "rev-parse", "ls-files", "blame",
    "describe", "ls-tree", "cat-file", "shortlog", "reflog", "rev-list", "merge-base",
    "grep", "name-rev", "for-each-ref",
}
# git subcommands that only read when given one of these first arguments or flags
GIT_READ_ONLY_WHEN = {
    "branch": {"--list", "-l", "-a", "-r", "--all", "--remotes", "--show-current", "--contains", "--merged", "--no-merged", "-v", "-vv"},
    "tag": {"--list", "-l", "--contains", "--points-at"},
    "config": {"--get", "--get-all", "--get-regexp", "--list", "-l"},
    "stash": {"list", "show"},
    "worktree": {"list"},
}
GIT_REMOTE_WRITE = {"add", "remove", "rm", "rename", "set-url", "prune", "set-head"}
GH_READ = {
    "pr": {"view", "list", "diff", "status", "checks"},
    "issue": {"view", "list", "status"},
    "repo": {"view", "list"},
    "run": {"view", "list"},
    "release": {"view", "list"},
}
BKF_READ = {"validate", "search", "orient"}
MUTATING_TOOLS = {"Edit", "Write", "NotebookEdit", "apply_patch", "MultiEdit"}

HARMLESS_REDIRECT = re.compile(r"\d*>>?\s*/dev/null|&>\s*/dev/null|\d*>&\d+|\d*<\s*\S+")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1([^\n]*)\n.*?\n\s*\2\s*(?:\n|$)", re.S)


def state_file(session_id):
    return STATE_DIR / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', session_id or 'unknown')}.json"


def gh_api_is_readonly(args):
    """gh api reads unless it sets a non-GET method or sends a body (-f/-F/--input make it POST)."""
    for i, arg in enumerate(args):
        if arg in ("-f", "-F", "--field", "--raw-field", "--input") or arg.startswith(("-f", "-F", "--field=", "--raw-field=", "--input=")):
            return False
        if arg.startswith("--method=") or arg.startswith("-X") or arg == "--method":
            method = arg.split("=", 1)[1] if "=" in arg else (arg[2:] if arg.startswith("-X") and len(arg) > 2 else (args[i + 1] if i + 1 < len(args) else ""))
            if method.upper() != "GET":
                return False
    return True


PSQL_ARG_LETTERS = set("dhpUPRTFvcfoL")
PSQL_WRITE_ARGS = {"-f", "-o", "-L", "--file", "--output", "--log-file"}
PSQL_META = re.compile(r"\\(d\S*|l\+?|sf\+?|sv\+?|conninfo)(\s[^\\;]*)?$")
SQL_READ_START = re.compile(r"(select|show|table|values|explain)\b")
SQL_FORBIDDEN = re.compile(
    r"\b(into|analyze|analyse|nextval|setval|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|"
    r"dblink\w*|lo_import|lo_export|copy)\b|[;\\]"
)


def psql_sql_is_readonly(sql):
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    if sql.startswith("\\"):
        return bool(PSQL_META.match(sql))
    lowered = sql.lower()
    return bool(SQL_READ_START.match(lowered)) and not SQL_FORBIDDEN.search(lowered)


def psql_is_readonly(args):
    """psql reads when every -c is a single SELECT/SHOW/EXPLAIN or a \\d-style meta-command.

    Anything that reads stdin or a file, writes an output file, or has no -c is not read-only.
    """
    commands = []
    i = 0
    while i < len(args):
        word = args[i]
        i += 1
        if word in PSQL_WRITE_ARGS or word.startswith(("--file=", "--output=", "--log-file=")):
            return False
        if word == "--command" or word.startswith("--command="):
            if "=" in word:
                commands.append(word.split("=", 1)[1])
            elif i < len(args):
                commands.append(args[i])
                i += 1
            continue
        if word.startswith("-") and not word.startswith("--") and len(word) > 1:
            for pos, letter in enumerate(word[1:], start=1):
                if letter in PSQL_ARG_LETTERS:
                    value = word[pos + 1:]
                    if not value and i < len(args):
                        value = args[i]
                        i += 1
                    if letter in "foL":
                        return False
                    if letter == "c":
                        commands.append(value)
                    break
    return bool(commands) and all(psql_sql_is_readonly(command) for command in commands)


def segment_is_readonly(words):
    name = words[0].rsplit("/", 1)[-1]
    rest = words[1:]
    if name == "git":
        # skip global options such as -C <dir> / -c k=v before the subcommand
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in ("-C", "-c") else 1
        sub = rest[i] if i < len(rest) else ""
        args = rest[i + 1:]
        if sub == "remote":
            return not (GIT_REMOTE_WRITE & set(args))
        if sub in GIT_READ_ONLY_WHEN:
            return bool(GIT_READ_ONLY_WHEN[sub] & set(args)) or (sub == "branch" and not args)
        return sub in READONLY_GIT
    if name == "gh":
        if rest[:1] == ["api"]:
            return gh_api_is_readonly(rest[1:])
        return len(rest) >= 2 and rest[1] in GH_READ.get(rest[0], set())
    if name == "bkf":
        sub = rest[0] if rest else ""
        if sub == "inventory":
            return "--write" not in rest
        return sub in BKF_READ
    if name == "psql":
        return psql_is_readonly(rest)
    if name == "sed":
        return not any(w.startswith("-i") or w == "--in-place" for w in rest)
    if name == "find":
        return not any(w in ("-delete", "-exec", "-execdir", "-ok", "-fprint", "-fprintf") for w in rest)
    if name == "sort":
        return not any(w == "-o" or w.startswith("--output") for w in rest)
    if name == "awk":
        return not re.search(r"system\s*\(|getline|print[^;}]*>", " ".join(rest))
    return name in READONLY_CMDS


def _substitution_end(command, start):
    """Return the closing parenthesis for a command substitution, if present."""
    frames = [{"depth": 1, "quote": None}]
    index = start + 2
    while index < len(command):
        frame = frames[-1]
        quote = frame["quote"]
        char = command[index]
        if char == "\\":
            index += 2
            continue
        if quote == "'":
            if char == "'":
                frame["quote"] = None
            index += 1
            continue
        if quote == '"':
            if char == '"':
                frame["quote"] = None
                index += 1
                continue
            if command.startswith("$(", index):
                frames.append({"depth": 1, "quote": None})
                index += 2
                continue
            if char == "`":
                end = _backtick_end(command, index + 1)
                if end is None:
                    return None
                index = end + 1
                continue
            index += 1
            continue
        if char in "'\"":
            frame["quote"] = char
            index += 1
            continue
        if command.startswith("$(", index):
            frames.append({"depth": 1, "quote": None})
            index += 2
            continue
        if char == "`":
            end = _backtick_end(command, index + 1)
            if end is None:
                return None
            index = end + 1
            continue
        if char == "(":
            frame["depth"] += 1
        elif char == ")":
            frame["depth"] -= 1
            if frame["depth"] == 0:
                frames.pop()
                if not frames:
                    return index
        index += 1
    return None


def _backtick_end(command, start):
    """Return the next unescaped backtick, if present."""
    escaped = False
    for index in range(start, len(command)):
        if escaped:
            escaped = False
        elif command[index] == "\\":
            escaped = True
        elif command[index] == "`":
            return index
    return None


def _shell_segments(command):
    """Split shell commands outside quotes and check substitutions recursively."""
    segments = []
    current = []
    writes = []
    has_write = False
    quote = None
    index = 0

    def finish() -> None:
        nonlocal current, has_write
        segments.append("".join(current))
        writes.append(has_write)
        current = []
        has_write = False

    while index < len(command):
        char = command[index]
        if quote == "'":
            current.append(char)
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == "\\" and index + 1 < len(command):
                current.extend(command[index:index + 2])
                index += 2
                continue
            if char == '"':
                current.append(char)
                quote = None
                index += 1
                continue
            if command.startswith("$(", index):
                end = _substitution_end(command, index)
                if end is None or not bash_is_readonly(command[index + 2:end]):
                    return None
                current.append("x")
                index = end + 1
                continue
            if char == "`":
                end = _backtick_end(command, index + 1)
                if end is None or not bash_is_readonly(command[index + 1:end]):
                    return None
                current.append("x")
                index = end + 1
                continue
            current.append(char)
            index += 1
            continue

        if char == "\\" and index + 1 < len(command):
            current.extend(command[index:index + 2])
            index += 2
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            index += 1
            continue
        if command.startswith(("<(", ">("), index):
            return None
        harmless = HARMLESS_REDIRECT.match(command, index)
        if harmless:
            current.append(" ")
            index = harmless.end()
            continue
        if command.startswith("$(", index):
            end = _substitution_end(command, index)
            if end is None or not bash_is_readonly(command[index + 2:end]):
                return None
            current.append("x")
            index = end + 1
            continue
        if char == "`":
            end = _backtick_end(command, index + 1)
            if end is None or not bash_is_readonly(command[index + 1:end]):
                return None
            current.append("x")
            index = end + 1
            continue
        if char == ">":
            has_write = True
            current.append(char)
            index += 1
            continue
        if char in ";|&\n":
            finish()
            if char in "&|" and index + 1 < len(command) and command[index + 1] == char:
                index += 2
            else:
                index += 1
            continue
        current.append(char)
        index += 1

    if quote is not None:
        return None
    finish()
    return list(zip(segments, writes))


def bash_is_readonly(command):
    command = HEREDOC.sub(r"\3\n", command)
    segments = _shell_segments(command)
    if segments is None:
        return False
    for segment, has_write in segments:
        if has_write or re.search(r"\btee\b", segment):
            return False
        try:
            words = shlex.split(segment)
        except ValueError:
            return False
        if words and not segment_is_readonly(words):
            return False
    return True


def git_stash_writes(command):
    """True if the command runs git stash other than `list` or `show`."""
    segments = _shell_segments(HEREDOC.sub(r"\3\n", command))
    if segments is None:
        return bool(re.search(r"\bgit\b[^;&|\n]*\bstash\b(?!\s+(list|show)\b)", command))
    for segment, _ in segments:
        try:
            words = shlex.split(segment)
        except ValueError:
            continue
        if not words or words[0].rsplit("/", 1)[-1] != "git":
            continue
        rest = words[1:]
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in ("-C", "-c") else 1
        if rest[i:i + 1] == ["stash"] and rest[i + 1:i + 2] not in (["list"], ["show"]):
            return True
    return False


def on_prompt(data):
    path = state_file(data.get("session_id"))
    match = PREFIX.match(data.get("prompt", ""))
    if not match:
        path.unlink(missing_ok=True)
        return
    mode = match.group(1).lower()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mode": mode}))
    print(INSTRUCTIONS[mode])


def on_tool(data):
    command = data.get("tool_input", {}).get("command", "")
    if data.get("tool_name") == "Bash" and git_stash_writes(command):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "git stash is blocked: the checkout is shared, and stashing moves other agents' "
                "uncommitted changes. Ask the user; they can run it themselves with '! git stash'."
            ),
        }}))
        return
    try:
        mode = json.loads(state_file(data.get("session_id")).read_text()).get("mode")
    except (OSError, ValueError):
        return
    if mode != "t":
        return
    tool = data.get("tool_name", "")
    blocked = tool in MUTATING_TOOLS or (
        tool == "Bash" and not bash_is_readonly(data.get("tool_input", {}).get("command", ""))
    )
    if blocked:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Talk mode (t:) is active: this call was not shown to be read-only, so it is blocked. "
                "Read-only Bash still runs (ls, cat, rg, git log, psql with a single SELECT); "
                "split a mixed command or rewrite it as reads. The allowed commands are listed in "
                "bkf/tooling/agent_modes.py (READONLY_CMDS). Otherwise discuss, or ask the user to "
                "resend with 'w:' to implement."
            ),
        }}))


def main():
    try:
        data = json.load(sys.stdin)
        event = data.get("hook_event_name")
        if event == "UserPromptSubmit":
            on_prompt(data)
        elif event == "PreToolUse":
            on_tool(data)
    except Exception as exc:
        detail = " ".join(str(exc).split()) or "no details"
        message = f"bkf hook modes failed: {type(exc).__name__}: {detail}"
        if len(message) > 300:
            message = message[:299] + "…"
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        print(message, file=sys.stderr)


if __name__ == "__main__":
    main()

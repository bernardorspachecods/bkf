"""Heuristic lint for plan briefs.

The checks can misread prose that mentions handoffs or file boundaries, miss
commands hidden behind shell wrappers or variables, and warn about files that
another command creates earlier in the same gate, unless a unit declares it
under Creates. Python options with separate
values are recognized for -W and -X; other options that take separate values
can still be mistaken for the script path. They are hints for a coordinator,
not proof that a brief is valid.
"""
import json
import re
import shlex
from pathlib import Path


_GATE_START = re.compile(r"```gate[ \t]*\Z")
_FENCE_END = re.compile(r"```[ \t]*\Z")
_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$")
_HANDOFF_PROHIBITION = re.compile(
    r"\bhandoff\b[^.;:!?]*\b(?:do|does|did|must|should|shall|will|can|may)\s+not\b"
    r"|\b(?:do|does|did|must|should|shall|will|can|may)\s+not\b[^.;:!?]*\bhandoff\b",
    re.IGNORECASE,
)
_FILE_COMMANDS = {"bash", "sh", "node", "python", "python3"}
_MISSING_FILE_MESSAGE = "does not exist now: a unit before this one must create it"
_REMOVED_MESSAGE = "gate uses {0}, which this plan removes before the gate runs"
_BACKTICKED = re.compile(r"`([^`]+)`")


def _sections(text):
    section = None
    lines = []
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            if section is not None:
                yield section, lines
            section = heading.group(1).strip().casefold()
            lines = []
        elif section is not None:
            lines.append(line)
    if section is not None:
        yield section, lines


def declared_paths(text, section):
    """Return the backticked paths listed in a brief's Removes or Creates section."""
    paths = []
    for name, lines in _sections(text):
        if name == section:
            for line in lines:
                paths.extend(_normalize(path) for path in _BACKTICKED.findall(line))
    return paths


def _normalize(path):
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def _covers(entries, path):
    return any(path == entry or (entry.endswith("/") and path.startswith(entry)) for entry in entries)


def apply_declarations(gone, made, text):
    """Return (gone, made) after a brief's Removes and Creates."""
    removes = declared_paths(text, "removes")
    creates = declared_paths(text, "creates")
    gone = frozenset(path for path in gone if path not in creates) | frozenset(removes)
    made = frozenset(path for path in made if not _covers(removes, path)) | frozenset(creates)
    return gone, made


def _gate_commands(text):
    active = False
    for line in text.splitlines():
        if _GATE_START.fullmatch(line):
            active = True
        elif active and _FENCE_END.fullmatch(line):
            active = False
        elif active:
            command = line.strip()
            if command and not command.startswith("#"):
                yield command


def _command_segments(command):
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    segments = []
    current = []
    for token in tokens:
        if token and all(character in ";&|" for character in token):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _script_path(tokens, repo):
    command = tokens[0]
    if command in _FILE_COMMANDS:
        args = tokens[1:]
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in ("-c", "-m", "-e", "--eval", "--print"):
                return None
            if arg == "--":
                return args[index + 1] if index + 1 < len(args) else None
            if arg in ("-W", "-X"):
                index += 2
                continue
            if arg.startswith("-"):
                index += 1
                continue
            return arg
        return None
    if command.startswith("./"):
        return command
    return None


def _package_script(tokens, scripts):
    command = tokens[0]
    if command not in ("pnpm", "npm"):
        return None
    args = tokens[1:]
    if not args or args[0] in ("exec", "dlx", "install", "i", "add", "remove", "uninstall"):
        return None
    if args[0] == "run":
        if len(args) > 1 and not args[1].startswith("-"):
            return args[1]
        return None
    if command == "npm" and args[0] in ("test", "start", "stop", "restart"):
        return args[0]
    if not args[0].startswith("-"):
        return args[0]
    return None


def _package_scripts(repo):
    package = Path(repo) / "package.json"
    if not package.is_file():
        return None
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _gate_problems(command, repo, scripts, gone, made):
    problems = []
    for tokens in _command_segments(command):
        if not tokens:
            continue
        for token in tokens[1:]:
            path = _normalize(token)
            if _covers(gone, path) and ("removed", path) not in problems:
                problems.append(("removed", path))
        target = _script_path(tokens, repo)
        if target is not None:
            target = _normalize(target)
            if not _covers(gone, target) and target not in made and not (Path(repo) / target).is_file():
                problems.append(("missing", target))
        script = _package_script(tokens, scripts)
        if script is not None and scripts is not None and script not in scripts:
            problems.append(("missing", script))
    return problems


def lint_brief(path, repo, gone=frozenset(), made=frozenset()):
    """Return heuristic (level, message) diagnostics for a plan brief.

    gone and made are the paths that earlier steps of the plan removed and
    created; the brief's own Removes and Creates apply before its gate is read.
    """
    text = Path(path).read_text(encoding="utf-8")
    diagnostics = []
    for section, lines in _sections(text):
        if section == "criteria":
            for line in lines:
                if re.search(r"\bhandoff\b", line, re.IGNORECASE) and not _HANDOFF_PROHIBITION.search(line):
                    diagnostics.append(("error", "Criteria must not use the handoff as proof"))
                    break
        elif section == "out of scope":
            for line in lines:
                if re.search(r"\bonly\s+touch(?:es)?\b|\bthe\s+diff\s+only\b|\bmay\s+only\s+change\b", line, re.IGNORECASE):
                    diagnostics.append(("error", "write the scope by exclusion"))
                    break
    gone, made = apply_declarations(gone, made, text)
    scripts = _package_scripts(repo)
    for command in _gate_commands(text):
        for kind, name in _gate_problems(command, repo, scripts, gone, made):
            if kind == "removed":
                diagnostics.append(("error", _REMOVED_MESSAGE.format(name)))
            else:
                diagnostics.append(("warning", _MISSING_FILE_MESSAGE))
    return list(dict.fromkeys(diagnostics))

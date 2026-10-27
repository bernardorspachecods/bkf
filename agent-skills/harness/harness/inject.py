"""Add role-guide requested rule text to a prompt."""

import os
import re
import stat
import tempfile


_MARKER = b"<!-- rules injected by the script -->"
_GUIDE_PATTERN = re.compile(rb".*role guide: (/[^ ]*\.md).*")
_DIRECTIVE_PATTERN = re.compile(rb"^<!-- inject: (.*) -->$")


class InjectionError(Exception):
    """A role guide requests a rule file that cannot be injected."""


def _lines(data):
    """Return line records like sed and awk, without their LF separators."""
    return data.split(b"\n")[:-1] if data.endswith(b"\n") else data.split(b"\n")


def _guide_paths(prompt):
    found = []
    for line in _lines(prompt):
        match = _GUIDE_PATTERN.match(line)
        if match:
            guide = os.fsdecode(match.group(1))
            if guide not in found:
                found.append(guide)
    return found


def _requested_files(guide_path):
    try:
        with open(guide_path, "rb") as guide:
            lines = _lines(guide.read())
    except OSError:
        return []
    directory = os.path.dirname(guide_path)
    requested = []
    for line in lines:
        match = _DIRECTIVE_PATTERN.match(line)
        if match:
            relative = os.fsdecode(match.group(1))
            requested.append((relative, (directory or ".") + "/" + relative))
    return requested


def _body_without_frontmatter(content):
    output = []
    in_frontmatter = False
    for index, line in enumerate(_lines(content), 1):
        if index == 1 and line == b"---":
            in_frontmatter = True
            continue
        if in_frontmatter and line == b"---":
            in_frontmatter = False
            continue
        if not in_frontmatter:
            output.append(line + b"\n")
    return b"".join(output).rstrip(b"\n")


def _rule_addition(prompt):
    if _MARKER in prompt:
        return b""

    seen = set()
    additions = []
    for guide in _guide_paths(prompt):
        if not os.path.isfile(guide):
            continue
        for relative, path in _requested_files(guide):
            if not relative.endswith(".md"):
                raise InjectionError(
                    "Error: {0} asks to inject {1}, which is not a Markdown file".format(
                        guide, relative
                    )
                )
            if not os.path.isfile(path):
                raise InjectionError(
                    "Error: {0} asks to inject {1}, which does not exist".format(guide, path)
                )
            key = os.path.join(os.path.abspath(os.path.dirname(path)), os.path.basename(path))
            if key in seen:
                continue
            seen.add(key)
            try:
                with open(path, "rb") as rule:
                    content = rule.read()
            except OSError:
                raise InjectionError(
                    "Error: {0} asks to inject {1}, which does not exist".format(guide, path)
                )
            basename = os.path.basename(path)
            name = basename[:-3] if basename.endswith(".md") else basename
            header = (
                b"\n\n---\n## Rules from "
                + os.fsencode(name)
                + b"\nThe script added this text from "
                + os.fsencode(relative)
                + b", as the role guide asked."
            )
            additions.append(header + b"\n" + _body_without_frontmatter(content))
    if not additions:
        return b""
    return b"".join(additions)


def _replace_atomically(path, original, appended):
    target = os.path.realpath(path)
    directory = os.path.dirname(target) or "."
    mode = stat.S_IMODE(os.stat(target).st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix=".inject-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(original)
            output.write(appended)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def inject_rules(prompt_path):
    """Append the requested rule text once, preserving the shell script's bytes."""
    with open(prompt_path, "rb") as prompt_file:
        original = prompt_file.read()
    addition = _rule_addition(original)
    if not addition:
        return
    _replace_atomically(prompt_path, original, addition + b"\n\n" + _MARKER + b"\n")

"""Small heuristics for recognizing repeated gate and review failures.

Gate signatures compare failed commands in order and normalized output lines
containing common failure markers. They cannot identify semantic equivalence:
different wording, omitted output, marker-free failures, or a genuinely distinct
failure with the same normalized text may compare incorrectly. Normalization
removes digits, temporary paths and durations, which can also hide meaningful
differences. Review file extraction only sees backticked file-looking tokens
inside the first ``## Problems`` section; it does not resolve paths or infer
files described in prose.
"""
import re


_FAILURE = re.compile(r"FAIL|FAILED|Error|not ok|ERROR")
_TEMP_PATH = re.compile(r"(?:/tmp|/private/tmp|/var/folders|/private/var/folders)/\S+")
_DURATION = re.compile(r"\b\d+(?:\.\d+)?\s*(?:seconds?|secs?|milliseconds?|ms|minutes?|mins?)\b", re.I)
_BACKTICK = re.compile(r"`([^`]+)`")
_FILE_TOKEN = re.compile(r"(?:^|[/\\])[^\s`]+\.[A-Za-z0-9]{1,12}$|^[^\s`]+/[^\s`]+$")


def _normalize(text):
    text = _TEMP_PATH.sub("<TMP>", text)
    text = _DURATION.sub("<DURATION>", text)
    return re.sub(r"\d+", "#", text)


def gate_signature(gate_text):
    """Return (ordered failed commands, distinct normalized failure lines)."""
    sections = re.split(r"(?m)^### `(.*)`\s*$", gate_text)
    failed = []
    output_lines = set()
    for index in range(1, len(sections), 2):
        command, body = sections[index], sections[index + 1]
        exit_match = re.search(r"(?m)^exit code: (-?\d+)", body)
        if not exit_match or int(exit_match.group(1)) == 0:
            continue
        failed.append(command)
        if "~~~~" in body:
            output = body.split("~~~~", 1)[1].rsplit("~~~~", 1)[0]
            for line in output.splitlines():
                if _FAILURE.search(line):
                    output_lines.add(_normalize(line.strip()))
    return tuple(failed), frozenset(output_lines)


def problem_files(problems_text):
    """Return backticked file-like tokens in the first ``## Problems`` section."""
    match = re.search(r"(?m)^## Problems\s*$", problems_text)
    if not match:
        return set()
    section = problems_text[match.end():]
    section = re.split(r"(?m)^##?\s+", section, maxsplit=1)[0]
    result = set()
    for token in _BACKTICK.findall(section):
        token = token.strip()
        if _FILE_TOKEN.search(token):
            result.add(token)
    return result

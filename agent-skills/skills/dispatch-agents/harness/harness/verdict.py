"""Read verdicts and check review notes in dispatch-agents reports."""


def read_verdict(path):
    """Return the verdict on the last non-empty line, or None if invalid."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as source:
            last = None
            for line in source:
                if line.strip(" \t\n"):
                    last = line
    except OSError:
        return None
    if last is None:
        return None
    value = "".join(last.split())
    verdicts = {
        "VERDICT:pass": "pass",
        "VERDICT:back": "back",
        "VERDICT:escalate": "escalate",
        "VERDICT:brief": "brief",
    }
    return verdicts.get(value)


def read_blocked(path):
    """Return the reason on a last non-empty BLOCKED line, or None."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as source:
            last = None
            for line in source:
                if line.strip(" \t\n"):
                    last = line
    except OSError:
        return None
    if last is None or not last.startswith("BLOCKED:"):
        return None
    return last[len("BLOCKED:"):].strip()


def _checked_ok(path, minimum):
    if minimum <= 0:
        return True
    with open(path, "r", encoding="utf-8", newline="") as source:
        in_section = False
        count = 0
        for line in source:
            if line.startswith("## What I checked"):
                in_section = True
                continue
            if in_section and line.startswith("#"):
                hashes = len(line) - len(line.lstrip("#"))
                if line[hashes:].startswith(" "):
                    break
            if in_section and line.strip(" \t\n"):
                count += 1
    return count >= minimum


def checked_ok(path, minimum):
    """Return whether the checked section contains at least minimum content lines."""
    try:
        return _checked_ok(path, minimum)
    except OSError:
        return False

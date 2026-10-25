"""Hook handlers: snapshot and record session changes, then check their bundles at stop."""

from __future__ import annotations

import contextlib
import io
import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from validate_bundle import Validator

STATE_DIR = Path.home() / ".agent-hooks" / "state"
MAX_BLOCKS = 2
STATE_MAX_AGE = 14 * 24 * 3600
REASON_LIMIT = 2500
LOG_PREFIX = re.compile(r"^\s*([if])(-?)\s*:", re.IGNORECASE)
AUDIT_PREFIX = re.compile(r"^\s*bkf\s*:", re.IGNORECASE)
REPORT_DIR = Path.home() / ".agent-hooks" / "reports"
PASTE_TAG = re.compile(r"^[ \t]*</?pasted_content\b[^>\n]*>[ \t]*\n?|</?pasted_content\b[^>\n]*>", re.MULTILINE)
PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.MULTILINE)
EVENTS = {"record", "snapshot", "last", "log", "stop", "guard", "audit", "warnings"}


def report_failure(event: str, exc: Exception, fields: dict | None = None) -> None:
    """Show a one-line hook failure to the user without blocking the host."""
    detail = " ".join(str(exc).split()) or "no details"
    message = f"bkf hook {event} failed: {type(exc).__name__}: {detail}"
    if len(message) > 300:
        message = message[:299] + "…"
    payload = {"systemMessage": message}
    payload.update(fields or {})
    payload["systemMessage"] = message
    print(json.dumps(payload, ensure_ascii=False))
    print(message, file=sys.stderr)


def _prompt_kind(prompt: object) -> str | None:
    if not isinstance(prompt, str):
        return None
    match = LOG_PREFIX.match(prompt)
    return match.group(1).lower() if match else None


def _probe(event: str) -> None:
    if event == "guard":
        importlib.import_module("read_guard")
        importlib.import_module("launch_guard")
    elif event == "log":
        importlib.import_module("log_entry")
    elif event == "audit":
        importlib.import_module("audit")
    elif event == "stop":
        for module in ("generate_inventory", "validate_bundle", "bkf_common", "navigation_map"):
            importlib.import_module(module)
    elif event not in {"record", "snapshot", "last", "warnings"}:
        raise ValueError(f"unknown event {event!r}")
    print(json.dumps({"probe": "ok"}, separators=(",", ":")))


def _state(session_id: str, suffix: str, state_dir: Path | None = None) -> Path:
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
    return (state_dir or STATE_DIR) / f"{name}.{suffix}"


def _git(repo: Path, *args: str) -> bytes | None:
    try:
        result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def _repo(cwd: str | Path) -> Path | None:
    found = _git(Path(cwd), "rev-parse", "--show-toplevel")
    if found is None:
        return None
    return Path(os.fsdecode(found.rstrip(b"\r\n"))).resolve()


def _snapshot(repo: Path) -> dict | None:
    status = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status is None:
        return None
    entries = status.split(b"\0")
    paths: list[str] = []
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        paths.append(os.fsdecode(entry[3:]))
        if entry[:2].find(b"R") >= 0 or entry[:2].find(b"C") >= 0:
            index += 1
            if index < len(entries) and entries[index]:
                paths.append(os.fsdecode(entries[index]))
        index += 1
    paths = list(dict.fromkeys(paths))
    if len(paths) > 2000:
        return None

    files: dict[str, str | None] = {}
    existing: list[str] = []
    for path in paths:
        target = repo / path
        if target.exists() or target.is_symlink():
            existing.append(path)
        else:
            files[path] = None
    if existing:
        hashes = _git(repo, "hash-object", "--", *existing)
        values = hashes.splitlines() if hashes is not None else []
        if hashes is None or len(values) != len(existing):
            return None
        files.update({path: os.fsdecode(value) for path, value in zip(existing, values)})
    head_output = _git(repo, "rev-parse", "HEAD")
    head = os.fsdecode(head_output.rstrip(b"\r\n")) if head_output is not None else None
    return {"repo": str(repo), "head": head, "files": files}


def snapshot(data: dict, state_dir: Path | None = None) -> None:
    """Write the session's initial git snapshot once, when cwd is in a repo."""
    target = _state(data.get("session_id", ""), "base.json", state_dir)
    if target.exists():
        return
    repo = _repo(data.get("cwd") or ".")
    current = _snapshot(repo) if repo is not None else None
    if current is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(current, sort_keys=True) + "\n")


def _baseline_paths(baseline: dict, current: dict, repo: Path) -> set[Path]:
    changed: set[Path] = set()
    before = baseline.get("files", {})
    after = current.get("files", {})
    for path in before.keys() | after.keys():
        if before.get(path, object()) != after.get(path, object()):
            changed.add(repo / path)
    if baseline.get("head") != current.get("head") and baseline.get("head"):
        output = _git(repo, "diff", "--name-only", "--no-renames", str(baseline["head"]), "HEAD")
        if output is not None:
            changed.update(repo / os.fsdecode(path) for path in output.splitlines() if path)
    return changed


def edited_paths(data: dict) -> list[str]:
    """Return the file paths an editing tool call wrote, as given by the tool."""
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    paths = [tool_input[key] for key in ("file_path", "notebook_path") if isinstance(tool_input.get(key), str)]
    patch = tool_input.get("command")
    if data.get("tool_name") == "apply_patch" and isinstance(patch, str):
        paths += [first or second for first, second in PATCH_FILE.findall(patch)]
    return paths


def record(data: dict, state_dir: Path | None = None) -> None:
    cwd = Path(data.get("cwd") or ".")
    resolved = [str((cwd / path).resolve()) for path in edited_paths(data)]
    if not resolved:
        return
    target = _state(data.get("session_id", ""), "touched", state_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(resolved) + "\n")
    _prune(target.parent)


def _prune(directory: Path) -> None:
    cutoff = time.time() - STATE_MAX_AGE
    for stale in directory.glob("*"):
        if stale.is_file() and stale.stat().st_mtime < cutoff:
            stale.unlink(missing_ok=True)


def last(data: dict, state_dir: Path | None = None) -> None:
    """Save the last assistant message for a later logging prompt."""
    message = data.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return
    target = _state(data.get("session_id", ""), "last", state_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(message, encoding="utf-8")
    _prune(target.parent)


def _transcript_message(path: str) -> str | None:
    """Return the latest assistant transcript record containing text."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict) or record.get("type") != "assistant":
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        pieces = [item["text"] for item in content if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str) and item["text"]]
        if pieces:
            return "\n\n".join(pieces)
    return None


def _log_context(data: dict, state_dir: Path | None) -> str | None:
    saved = _state(data.get("session_id", ""), "last", state_dir)
    try:
        value = saved.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        value = ""
    if value.strip():
        return value
    transcript = data.get("transcript_path")
    return _transcript_message(transcript) if isinstance(transcript, str) and transcript else None


def log(data: dict, state_dir: Path | None = None) -> dict | None:
    """Log an i: idea or f: feedback prompt without involving a model; the prompt never reaches it.

    The i-: and f-: forms log the entry without the agent's last message.
    """
    prompt = data.get("prompt")
    kind = _prompt_kind(prompt)
    if kind is None:
        return None
    match = LOG_PREFIX.match(prompt)
    text = PASTE_TAG.sub("", prompt[match.end():]).strip()
    if not text:
        return None
    from log_entry import display_path, write_entry

    cwd = Path(data.get("cwd") or ".").expanduser()
    context = None if match.group(2) else _log_context(data, state_dir)
    path = write_entry("idea" if kind == "i" else "feedback", text, cwd, context)
    rendered = display_path(path, cwd)
    return {"continue": False, "stopReason": f"Logged {'idea' if kind == 'i' else 'feedback'} in {rendered}"}


def audit(data: dict, report_dir: Path | None = None) -> dict | None:
    """Answer a `bkf:` prompt with a structure audit of the whole repository.

    The prompt still reaches the model; the audit summary and the path of the full report are added as context.
    """
    prompt = data.get("prompt")
    match = AUDIT_PREFIX.match(prompt) if isinstance(prompt, str) else None
    if match is None:
        return None
    import audit as audit_report

    result = audit_report.run(Path(data.get("cwd") or ".").expanduser())
    if result is None:
        context = "BKF audit skipped: the working directory is not inside a git repository."
    else:
        path = audit_report.write_report(result, report_dir or REPORT_DIR)
        context = (
            "The user prefixed the prompt with 'bkf:' (ignore the prefix itself) to request a structure audit. "
            "Present the findings below first; read the full report only for detail the summary omits. "
            "Do not fix anything unless the rest of the prompt asks.\n\n"
            + audit_report.summary(result, path)
        )
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}


def pending_warnings(data: dict, state_dir: Path | None = None) -> dict | None:
    """Give the model the warnings the last Stop found, once, with the next prompt."""
    pending = _state(data.get("session_id", ""), "warnings", state_dir)
    if not pending.exists():
        return None
    notes = json.loads(pending.read_text(encoding="utf-8"))
    pending.unlink(missing_ok=True)
    if not isinstance(notes, list) or not notes or any(not isinstance(note, str) for note in notes):
        return None
    from navigation_map import GUIDANCE, WARNING_CODES

    context = "BKF warnings for files changed in this session. Fix them when the work allows:\n" + "\n".join(notes)
    if any(note.startswith(WARNING_CODES) for note in notes):
        context += "\n" + GUIDANCE
    return {
        "systemMessage": "BKF warnings given to the agent:\n" + "\n".join(notes),
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context},
    }


def bundle_root_of(path: Path) -> Path | None:
    """Return the nearest enclosing directory whose MAP.md declares `bkf_version`."""
    from bkf_common import MAP_NAME, is_bundle_root_map

    for directory in (path, *path.parents):
        if directory.is_dir() and (directory / MAP_NAME).is_file() and is_bundle_root_map(directory / MAP_NAME):
            return directory
    return None


def _run(main, argv: list[str]) -> tuple[int, str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            code = main(argv)
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else 2
    return code, output.getvalue().strip()


def problems(roots: list[Path], validators: dict[Path, Validator] | None = None) -> list[str]:
    """Return failed checks; each validator that ran is stored in `validators` for `warnings`."""
    import generate_inventory
    import validate_bundle

    found: list[str] = []
    for root in roots:
        validator = validate_bundle.Validator(root)
        validator.validate()
        if validators is not None:
            validators[root] = validator
        code, text = _run(lambda _argv: validate_bundle.validate_one(root, validator), [])
        validation_failed = code == 1
        if code == 1:
            found.append(f"bkf validate {root}\n{text}")
        elif code != 0:
            raise RuntimeError(f"bkf validate {root} exited with code {code}: {text}")
        if validation_failed and "MAP_INVENTORY_STALE" not in text:
            continue
        code, text = _run(generate_inventory.main, [str(root), "--check"])
        if code == 1:
            found.append(f"bkf inventory {root} --check (stale; fix with `bkf inventory {root} --write`)\n{text}")
        elif code != 0:
            raise RuntimeError(f"bkf inventory {root} --check exited with code {code}: {text}")
    return found


def warnings(roots: list[Path], paths: set[Path], validators: dict[Path, Validator] | None = None) -> list[str]:
    """Return validation warnings for the files this session changed, reusing validators that already ran."""
    from validate_bundle import Validator

    changed = {path.resolve() for path in paths}
    found: list[str] = []
    for root in roots:
        validator = (validators or {}).get(root)
        if validator is None:
            validator = Validator(root)
            validator.validate()
        found.extend(
            f"{finding.code} {finding.path}: {finding.message}"
            for finding in validator.findings
            if finding.severity == "WARNING" and (root / finding.path).resolve() in changed
        )
    return found


def stop(data: dict, state_dir: Path | None = None) -> dict | None:
    session_id = data.get("session_id", "")
    touched = _state(session_id, "touched", state_dir)
    blocks = _state(session_id, "blocks", state_dir)
    baseline_path = _state(session_id, "base.json", state_dir)
    baseline: dict | None = None
    if baseline_path.exists():
        candidate = json.loads(baseline_path.read_text(encoding="utf-8"))
        if not isinstance(candidate, dict) or not isinstance(candidate.get("files"), dict):
            raise ValueError(f"invalid git snapshot: {baseline_path}")
        baseline = candidate
    if not touched.exists() and baseline is None:
        return None

    paths = {Path(line) for line in touched.read_text(encoding="utf-8").splitlines() if line} if touched.exists() else set()
    current: dict | None = None
    current_repo = _repo(data.get("cwd") or ".")
    if baseline is not None and current_repo is not None:
        current = _snapshot(current_repo)
        if current is not None and str(current_repo) == baseline.get("repo"):
            paths.update(_baseline_paths(baseline, current, current_repo))
    roots = sorted({root for path in paths if (root := bundle_root_of(path)) is not None})
    validators: dict[Path, Validator] = {}
    found = problems(roots, validators) if roots else []

    count = int(blocks.read_text()) if blocks.exists() else 0
    if not found or count >= MAX_BLOCKS:
        if current_repo is not None:
            fresh = current if current is not None and current.get("repo") == str(current_repo) else _snapshot(current_repo)
            if fresh is not None:
                baseline_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = baseline_path.with_name(baseline_path.name + ".tmp")
                temporary.write_text(json.dumps(fresh, sort_keys=True) + "\n", encoding="utf-8")
                temporary.replace(baseline_path)
        touched.unlink(missing_ok=True)
        blocks.unlink(missing_ok=True)
        notes = warnings(roots, paths, validators) if roots else []
        if notes:
            pending = _state(session_id, "warnings", state_dir)
            pending.parent.mkdir(parents=True, exist_ok=True)
            pending.write_text(json.dumps(notes, ensure_ascii=False) + "\n", encoding="utf-8")
            _prune(pending.parent)
        return None

    blocks.write_text(str(count + 1))
    reason = "BKF check failed for files changed in this session. Fix these before finishing:\n\n" + "\n\n".join(found)
    return {"decision": "block", "reason": reason[:REASON_LIMIT]}


def main(argv: list[str]) -> int:
    """Run one hook event from the JSON on stdin. Never fails the host tool."""
    event = argv[0] if argv else ""
    if event not in EVENTS:
        report_failure(event or "unknown", ValueError(f"unknown event {event!r}"))
        return 0
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("hook input must be a JSON object")
    except Exception as exc:
        report_failure(event, exc)
        return 0

    if data.get("hook_event_name") == "BKFProbe" and data.get("probe") is True:
        try:
            _probe(event)
        except Exception as exc:
            report_failure(event, exc)
        return 0

    kind = _prompt_kind(data.get("prompt")) if event == "log" else None
    try:
        output = None
        if event == "record":
            record(data)
        elif event == "snapshot":
            snapshot(data)
        elif event == "last":
            last(data)
        elif event == "log":
            output = log(data)
        elif event == "audit":
            output = audit(data)
        elif event == "warnings":
            output = pending_warnings(data)
        elif event == "stop":
            output = stop(data)
        elif event == "guard":
            from launch_guard import check
            from read_guard import guard

            output = guard(data) or check(data)
    except Exception as exc:
        if event == "stop":
            exc = RuntimeError(f"validation did not run: {exc}")
        if event == "log" and kind is not None:
            reason = " ".join(str(exc).split()) or "no details"
            report_failure(event, exc, {"continue": False, "stopReason": f"Not logged: {reason}"})
        else:
            report_failure(event, exc)
        return 0
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0

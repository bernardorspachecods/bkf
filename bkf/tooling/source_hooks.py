"""Look up and capture sources during Claude Code web tool calls."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import search
import source_store as store
from bkf_common import BKFInputError, parse_markdown
from source_record import manual_snapshot_command


SEARCHES = Path("searches")
ADMISSION_AGE = 24 * 60 * 60


def _result_urls(response: object) -> list[str]:
    results = response.get("results") if isinstance(response, dict) else response
    if not isinstance(results, list):
        return []
    found: dict[str, None] = {}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        for result in content if isinstance(content, list) else [entry]:
            url = result.get("url") if isinstance(result, dict) else None
            if not isinstance(url, str):
                continue
            url = store.encode_url(url)
            try:
                store.normalize_url(url)
            except ValueError:
                continue
            found[url] = None
    return list(found)


def _log_search(
    root: Path, query: str, session_id: str, agent_id: str | None, response: object,
) -> None:
    entry = {"session_id": session_id, "query": query, "urls": _result_urls(response)}
    if agent_id is not None:
        entry["agent_id"] = agent_id
    with store.store_lock(root):
        now = datetime.now().astimezone()
        day = now.date().isoformat()
        entry["time"] = now.isoformat()
        relative_path = SEARCHES / f"{day}.jsonl"
        path = root / relative_path
        path.parent.mkdir(exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        store.commit_files(root, f"Record web search on {day}", relative_path)


def _latest_search(root: Path, matches: Callable[[dict], bool]) -> dict | None:
    with store.store_lock(root, shared=True):
        for path in sorted((root / SEARCHES).glob("????-??-??.jsonl"), reverse=True):
            latest = None
            with path.open(encoding="utf-8") as log:
                for number, line in enumerate(log, start=1):
                    try:
                        entry = json.loads(line)
                        if not isinstance(entry, dict) or not isinstance(entry.get("query"), str):
                            raise ValueError("expected a JSON object with a query")
                        if matches(entry):
                            latest = entry
                    except ValueError as exc:
                        print(f"bkf hook sources: {path}:{number}: {exc}", file=sys.stderr)
            if latest is not None:
                return latest
    return None


def _context(event: str, message: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def _pre_search(root: Path, query: str) -> dict | None:
    lines = []
    hits = search.search_bundle(root, query, scope=root / "records", limit=5, unique_paths=True,
                                on_document_error=store._warn)
    for section, _ in hits:
        path = root / section.path.lstrip("/")
        try:
            metadata = parse_markdown(path).frontmatter
        except BKFInputError as exc:
            store._warn(f"{path}: {exc}")
            continue
        ext = metadata.get("ext")
        if isinstance(ext, dict) and ext.get("type") == "source":
            source_id, status = ext.get("id"), ext.get("status")
            if not isinstance(source_id, str) or not isinstance(status, str):
                store._warn(f"{path}: source record needs ext.id and ext.status")
                continue
            lines.append(f"- {source_id} ({status}) | {section.description} | {path}")
    if lines:
        lines.insert(0, "Registered sources matching this query:")
    key = " ".join(query.casefold().split())
    earlier = _latest_search(root, lambda entry: " ".join(entry.get("query", "").casefold().split()) == key)
    if earlier is not None:
        urls = earlier["urls"]
        lines.append(
            f"Previous identical search: {earlier['time']}, session {earlier['session_id']}, "
            f"{len(urls)} URLs returned."
        )
        lines.extend(f"- {url}" for url in urls[:10])
    return _context("PreToolUse", "\n".join(lines)) if lines else None


def _finish_instructions(source_id: str, *, has_snapshot: bool) -> str:
    prefix = f"bkf sources finish {source_id}"
    instructions = (
        f'{prefix} --status used --description "<description>" [--id NEW]\n'
        f'or {prefix} --status discarded --description "<description>" --reason "<reason>" [--id NEW]'
    )
    if not has_snapshot:
        instructions += (
            "\nBefore marking it as used, restore a missing web snapshot by fetching the URL again. "
            f"For a record with snapshot: none or manual, save the source text with {manual_snapshot_command(source_id)}"
        )
    return instructions


def _fetch_identity(
    session_id: str | None, agent_id: str | None, tool_use_id: object,
) -> store.FetchIdentity | None:
    if session_id is None or not isinstance(tool_use_id, str) or not tool_use_id:
        return None
    return session_id, agent_id, tool_use_id


def _admission_path(root: Path, url: str, identity: store.FetchIdentity | None) -> Path | None:
    if identity is None:
        return None
    token = hashlib.sha256(json.dumps([*identity, store.normalize_url(url)]).encode()).hexdigest()
    return root / store.HOOK_STATE / "admitted" / token


def _remember_admission(path: Path, source_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - ADMISSION_AGE
    for entry in path.parent.iterdir():
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
    path.write_text(source_id, encoding="utf-8")


def _take_admission(path: Path, source_id: str) -> bool:
    try:
        granted = path.read_text(encoding="utf-8") == source_id and time.time() - path.stat().st_mtime < ADMISSION_AGE
        path.unlink()
    except FileNotFoundError:
        return False
    return granted


def _pre_fetch(root: Path, url: str, identity: store.FetchIdentity | None) -> dict | None:
    with store.store_lock(root):
        match = store._lookup_url(root, url)
        if match is None:
            return None
        granted = store.reserve_completion(root, match.id, identity)
        missing_snapshot = granted is None and not match.has_snapshot
        if missing_snapshot and (admission := _admission_path(root, url, identity)):
            _remember_admission(admission, match.id)
        if granted or missing_snapshot:
            return _context("PreToolUse", f"This URL is registered as {match.id}. This fetch will refresh it.")
    registered = f"This URL is registered as {match.id}."
    read = f"Read the snapshot at {match.path.with_suffix('.txt')} and the record at {match.path}."
    reopen = f'Run this command to reopen it on purpose.\nbkf sources complete {match.id} --why "<reason>"'
    state = store.grant_state(root, match.id)
    if state is not None and state[0] == "reserved":
        reason = (
            f"{registered} Its completion grant is reserved by another WebFetch call until {state[1]}. "
            "That call has not reported back: it may still be running, or the permission prompt, another "
            f"hook or an interrupt stopped it. {read} The reservation ends at {state[1]}."
        )
    elif state is not None and state[0] == "used":
        reason = (
            f"{registered} Its completion grant was already used and would have expired at {state[1]}. "
            f"{read} {reopen}"
        )
    else:
        reason = f"{registered} {read} {reopen}"
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason,
    }}


def _post_fetch(
    root: Path, url: str, identity: store.FetchIdentity | None,
    session_id: str | None, agent_id: str | None, *, succeeded: bool,
) -> dict | None:
    with store.store_lock(root):
        match = store._lookup_url(root, url)
        if match is not None:
            granted = store.settle_completion(root, match.id, identity, succeeded=succeeded)
            admission = _admission_path(root, url, identity)
            admitted = admission is not None and _take_admission(admission, match.id)
            refresh = granted is True or (granted is None and (admitted or not match.has_snapshot))
    if not succeeded:
        return None
    event = "PostToolUse"
    if match is not None:
        if refresh:
            changes = store.refresh(root, match.id, url)
            return _context(event, f"Refreshed {match.id}: {', '.join(changes) or 'no changes'}.")
        return None
    if not session_id:
        return None
    previous = _latest_search(
        root, lambda entry: entry.get("session_id") == session_id and entry.get("agent_id") == agent_id,
    )
    registration = store.register(
        url, directory=root, via=previous["query"] if previous else "direct fetch",
        session_id=session_id, agent_id=agent_id,
    )
    if registration.already_registered:
        return _context(event, f"Already registered as {registration.id}.")
    instructions = _finish_instructions(registration.id, has_snapshot=registration.has_snapshot)
    warning = f"\n{registration.redirect_warning}" if registration.redirect_warning else ""
    return _context(
        event, f"Registered as {registration.id} (pending). Close it with {instructions}\n"
        f"Add Key claims to the record before closing it as used.{warning}",
    )


def handle(data: dict) -> dict | None:
    event, tool = data.get("hook_event_name"), data.get("tool_name")
    session_id, agent_id = data.get("session_id"), data.get("agent_id")
    if not isinstance(session_id, str) or not session_id.strip():
        session_id = None
    if not isinstance(agent_id, str) or not agent_id.strip():
        agent_id = None
    if event in ("Stop", "SubagentStop"):
        if data.get("stop_hook_active") or not session_id or (event == "SubagentStop" and not agent_id):
            return None
        if (root := store.open_store()) is None:
            return None
        pending = store.pending_sources(root, session_id, agent_id=agent_id if event == "SubagentStop" else None)
        if pending:
            commands = "\n\n".join(_finish_instructions(match.id, has_snapshot=match.has_snapshot) for match in pending)
            return {"decision": "block", "reason": (
                "Close the pending sources created in this session. Add Key claims before marking a source as used.\n\n"
                + commands
            )}
        return None
    if event not in ("PreToolUse", "PostToolUse", "PostToolUseFailure") or tool not in ("WebSearch", "WebFetch"):
        return None
    if (root := store.open_store()) is None:
        return None
    inputs = data.get("tool_input")
    value = inputs.get("url" if tool == "WebFetch" else "query") if isinstance(inputs, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    if tool == "WebFetch":
        value = store.encode_url(value)
        identity = _fetch_identity(session_id, agent_id, data.get("tool_use_id"))
        if event == "PreToolUse":
            return _pre_fetch(root, value, identity)
        return _post_fetch(root, value, identity, session_id, agent_id, succeeded=event == "PostToolUse")
    if event == "PreToolUse":
        return _pre_search(root, value)
    if session_id and event == "PostToolUse":
        _log_search(root, value, session_id, agent_id, data.get("tool_response"))
    return None

"""Give an interactive Claude session the name <repo><N>, such as bkf1, bkf2.

Claude Code names a session after its folder plus two random characters (bkf-1a). The
`tabname` hook replaces that derived name on the session's first prompt with the
repository name and the lowest number no other live session holds. A name the user chose
(/rename, --name) is never touched.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import subprocess
import time
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
STATE_DIR = Path.home() / ".agent-hooks" / "state"
CLAIM_SECONDS = 60


def repo_name(cwd: Path) -> str | None:
    """Return the repository's name: the folder of its main checkout, also from a worktree."""
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=cwd, capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        name = common.parent.name if common.name == ".git" else common.name.removesuffix(".git")
    else:
        name = cwd.name
    name = re.sub(r"[^\w.-]+", "-", name).strip("-")
    return name or None


def _alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _registry(sessions_dir: Path) -> list[dict]:
    entries = []
    for path in sessions_dir.glob("*.json"):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _taken(entries: list[dict], claims: dict, own_session: str, own_pid: object, now: float) -> set[str]:
    """Names held by live sessions, plus names claimed a moment ago whose session has not registered yet."""
    taken = {e["name"] for e in entries if e.get("sessionId") != own_session and _alive(e.get("pid")) and isinstance(e.get("name"), str)}
    for name, claim in claims.items():
        if isinstance(claim, list) and len(claim) == 2 and claim[0] != own_pid and _alive(claim[0]) and now - claim[1] < CLAIM_SECONDS:
            taken.add(name)
    return taken


def pick(repo: str, taken: set[str]) -> str:
    """Return the first <repo><N> from N=1 that is not taken."""
    number = 1
    while f"{repo}{number}" in taken:
        number += 1
    return f"{repo}{number}"


def session_name(data: dict, sessions_dir: Path = SESSIONS_DIR, state_dir: Path = STATE_DIR) -> str | None:
    """Return the name to give this session, or None when it keeps the one it has."""
    session_id = data.get("session_id")
    if data.get("hook_event_name") != "UserPromptSubmit" or not isinstance(session_id, str):
        return None
    own = next((e for e in _registry(sessions_dir) if e.get("sessionId") == session_id), None)
    if own is None or own.get("kind") != "interactive" or own.get("nameSource") != "derived":
        return None
    repo = repo_name(Path(data.get("cwd") or ".").expanduser())
    if repo is None or re.fullmatch(re.escape(repo) + r"\d+", str(own.get("name"))):
        return None

    state_dir.mkdir(parents=True, exist_ok=True)
    claims_path = state_dir / "session-names.json"
    with (state_dir / "session-names.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            claims = {}
        if not isinstance(claims, dict):
            claims = {}
        now = time.time()
        name = pick(repo, _taken(_registry(sessions_dir), claims, session_id, own.get("pid"), now))
        claims = {k: v for k, v in claims.items() if isinstance(v, list) and len(v) == 2 and _alive(v[0]) and now - v[1] < CLAIM_SECONDS}
        claims[name] = [own["pid"], now]
        temporary = claims_path.with_name(claims_path.name + ".tmp")
        temporary.write_text(json.dumps(claims), encoding="utf-8")
        temporary.replace(claims_path)
    return name


def rename_window(name: str) -> None:
    """Name the tmux window of this session now, instead of at the next event."""
    pane = os.environ.get("TMUX_PANE")
    if pane:
        with contextlib.suppress(OSError):
            subprocess.run(["tmux", "rename-window", "-t", pane, name], capture_output=True)

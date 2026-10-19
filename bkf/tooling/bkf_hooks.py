"""Preview, install, and report the deterministic agent hooks for Claude Code and Codex."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import agent_modes


SCRIPT_NAME = "mode.py"
HOOK_NAMES = ("modes", "orient", "check", "log", "rules", "guard", "audit")
EDIT_TOOLS = "Edit|Write|NotebookEdit|MultiEdit|apply_patch"
TIMEOUT = 10
RULES_LIMIT = 4000


@dataclass(frozen=True)
class Target:
    name: str
    directory: str
    file: str

    def config_path(self, home: Path) -> Path:
        return home / self.directory / self.file


TARGETS = (
    Target("claude", ".claude", "settings.json"),
    Target("codex", ".codex", "hooks.json"),
)


@dataclass(frozen=True)
class Registration:
    hook: str
    event: str
    matcher: str | None
    command: str
    owns: re.Pattern[str]
    timeout: int = TIMEOUT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf hooks", description=__doc__)
    parser.add_argument("action", choices=("install", "status", "run"))
    parser.add_argument("event", nargs="?", help="with run: the hook event to handle (used by the registered hooks)")
    parser.add_argument("--write", action="store_true", help="apply the install (the default is a preview)")
    parser.add_argument("--only", choices=HOOK_NAMES, help="act on one hook instead of both")
    parser.add_argument("--home", type=Path, help="home directory to act on (defaults to the real one)")
    return parser


def installed_script(home: Path) -> Path:
    return home / ".agent-hooks" / SCRIPT_NAME


def bkf_command(home: Path) -> str:
    found = shutil.which("bkf")
    if found:
        return found
    local = home / ".local" / "bin" / "bkf"
    return str(local) if local.exists() else "bkf"


def registrations(home: Path, only: str | None) -> list[Registration]:
    modes_command = f"python3 {installed_script(home)}"
    modes_owner = re.compile(r"\.agent-hooks/mode\.py$")
    orient_owner = re.compile(r"(^|/)bkf orient$")
    wanted = [
        Registration("modes", "UserPromptSubmit", None, modes_command, modes_owner),
        Registration("modes", "PreToolUse", "*", modes_command, modes_owner),
        Registration("guard", "PreToolUse", "Read|Bash", f"{bkf_command(home)} hooks run guard", re.compile(r"(^|/)bkf hooks run guard$")),
        Registration("orient", "SessionStart", None, f"{bkf_command(home)} orient", orient_owner),
        Registration("rules", "SessionStart", None, f"{bkf_command(home)} hooks run rules", re.compile(r"(^|/)bkf hooks run rules$")),
        Registration("check", "SessionStart", None, f"{bkf_command(home)} hooks run snapshot", re.compile(r"(^|/)bkf hooks run snapshot$")),
        Registration("check", "PostToolUse", EDIT_TOOLS, f"{bkf_command(home)} hooks run record", re.compile(r"(^|/)bkf hooks run record$")),
        Registration("check", "Stop", None, f"{bkf_command(home)} hooks run stop", re.compile(r"(^|/)bkf hooks run stop$"), 60),
        Registration("log", "UserPromptSubmit", None, f"{bkf_command(home)} hooks run log", re.compile(r"(^|/)bkf hooks run log$")),
        Registration("audit", "UserPromptSubmit", None, f"{bkf_command(home)} hooks run audit", re.compile(r"(^|/)bkf hooks run audit$"), 60),
        Registration("log", "Stop", None, f"{bkf_command(home)} hooks run last", re.compile(r"(^|/)bkf hooks run last$")),
    ]
    return [item for item in wanted if only in (None, item.hook)]


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return config


def find_hook(config: dict, registration: Registration) -> dict | None:
    """Return the existing hook entry that this registration owns, if any."""
    for group in config.get("hooks", {}).get(registration.event, []):
        for entry in group.get("hooks", []):
            if entry.get("type") == "command" and registration.owns.search(entry.get("command", "")):
                return entry
    return None


def state_of(config: dict, registration: Registration) -> str:
    entry = find_hook(config, registration)
    if entry is None:
        return "missing"
    return "ok" if entry["command"] == registration.command else "differs"


def apply_registration(config: dict, registration: Registration) -> None:
    entry = find_hook(config, registration)
    if entry is not None:
        entry["command"] = registration.command
        return
    group: dict = {"hooks": [{"type": "command", "command": registration.command, "timeout": registration.timeout}]}
    if registration.matcher is not None:
        group = {"matcher": registration.matcher, **group}
    config.setdefault("hooks", {}).setdefault(registration.event, []).append(group)


def script_state(home: Path) -> str:
    destination = installed_script(home)
    if not destination.exists():
        return "missing"
    source = Path(agent_modes.__file__).read_bytes()
    return "ok" if destination.read_bytes() == source else "differs"


def rules_file(home: Path) -> Path:
    return home / ".agent-hooks" / "rules.md"


def default_rules() -> Path:
    return Path(__file__).with_name("default_rules.txt")


def run_rules(home: Path) -> int:
    try:
        content = rules_file(home).read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0
    if not content:
        return 0
    if len(content) <= RULES_LIMIT:
        sys.stdout.write(content)
        return 0
    boundary = content.rfind("\n", 0, RULES_LIMIT)
    prefix = content[:boundary + 1] if boundary >= 0 else ""
    sys.stdout.write(prefix)
    if prefix and not prefix.endswith(("\n", "\r")):
        sys.stdout.write("\n")
    sys.stdout.write("... rules.md truncated\n")
    return 0


def rules_file_status(home: Path) -> str:
    path = rules_file(home)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"missing  rules   file              {path}"
    except (OSError, UnicodeError):
        return f"exists   rules   file              {path} (size unreadable)"
    return f"exists   rules   file              {path} ({len(content)} characters)"


def write_json(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".bkf-tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _probe_command(command: str, registration: Registration, home: Path) -> str | None:
    """Return a short failure reason when a registered command cannot run."""
    if registration.hook == "modes":
        probe_input = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "bkf-probe", "prompt": "probe"})
    elif registration.hook == "orient" or registration.hook == "rules":
        probe_input = ""
    else:
        probe_input = json.dumps({"hook_event_name": "BKFProbe", "probe": True})

    try:
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env["HOME"] = directory
            env["USERPROFILE"] = directory
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                input=probe_input,
                capture_output=True,
                timeout=TIMEOUT,
                cwd=directory,
                env=env,
            )
    except subprocess.TimeoutExpired:
        return "timed out"
    except OSError as exc:
        return str(exc) or type(exc).__name__

    combined = result.stdout + result.stderr
    if result.returncode != 0:
        return f"exit code {result.returncode}"
    if "Traceback (most recent call last)" in combined:
        return "traceback"
    if "systemMessage" in combined:
        try:
            message = json.loads(result.stdout).get("systemMessage")
        except (ValueError, AttributeError):
            message = None
        return str(message or "systemMessage")

    if registration.hook in {"check", "log", "guard", "audit"}:
        if result.stdout.strip() != '{"probe":"ok"}':
            return "no probe answer (stale install?)" if not result.stdout.strip() else "unexpected probe answer"
        if result.stderr:
            return result.stderr.strip().splitlines()[-1]
    elif result.stdout or result.stderr:
        return (result.stderr or result.stdout).strip().splitlines()[-1]
    return None


def report(home: Path, only: str | None, *, probe: bool = False) -> tuple[list[str], list[tuple[Target, Path, dict]], bool]:
    """Return report lines, the configs that need changes, and whether everything is current."""
    lines: list[str] = []
    pending: list[tuple[Target, Path, dict]] = []
    current = True

    if only in (None, "modes"):
        state = script_state(home)
        current &= state == "ok"
        lines.append(f"{state:<8} script  {installed_script(home)}")

    for target in TARGETS:
        path = target.config_path(home)
        if not (home / target.directory).is_dir():
            lines.append(f"skipped  {target.name}  {home / target.directory} not found")
            continue
        config = load_config(path)
        changed = False
        for registration in registrations(home, only):
            state = state_of(config, registration)
            entry = find_hook(config, registration)
            reason = _probe_command(entry["command"], registration, home) if probe and entry is not None else None
            if reason is not None:
                state = "broken"
            current &= state == "ok"
            line_command = entry["command"] if entry is not None else registration.command
            suffix = f" ({reason})" if reason is not None else ""
            lines.append(f"{state:<8} {target.name:<7} {registration.event:<17} {line_command}{suffix}")
            if state != "ok":
                apply_registration(config, registration)
                changed = True
        if changed:
            pending.append((target, path, config))
    return lines, pending, current


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.action == "run":
        handler = None
        try:
            if args.event == "rules":
                home = (args.home or Path.home()).expanduser().resolve()
                return run_rules(home)
            import hook_events as handler

            return handler.main([args.event or ""])
        except Exception as exc:
            if handler is not None:
                handler.report_failure(args.event or "unknown", exc)
            else:
                message = " ".join(str(exc).split()) or "no details"
                text = f"bkf hook {args.event or 'unknown'} failed: {type(exc).__name__}: {message}"
                if len(text) > 300:
                    text = text[:299] + "…"
                print(json.dumps({"systemMessage": text}, ensure_ascii=False))
                print(text, file=sys.stderr)
            return 0
    home = (args.home or Path.home()).expanduser().resolve()
    try:
        lines, pending, current = report(home, args.only, probe=args.action == "status")
        if args.only in (None, "rules"):
            lines.append(rules_file_status(home))
    except (OSError, ValueError) as exc:
        print(f"bkf hooks: {exc}", file=sys.stderr)
        return 1

    if args.action == "status":
        print("\n".join(lines))
        return 0 if current else 1

    copy_script = args.only in (None, "modes") and script_state(home) != "ok"
    copy_rules = args.only in (None, "rules") and not rules_file(home).exists()
    changes = bool(pending) or copy_script or copy_rules
    print("\n".join(lines))
    if not changes:
        print("\nnothing to do")
        if args.action == "install" and args.write:
            try:
                probe_lines, _, _ = report(home, args.only, probe=True)
            except (OSError, ValueError) as exc:
                print(f"bkf hooks: {exc}", file=sys.stderr)
                return 1
            broken = [line for line in probe_lines if line.startswith("broken")]
            if broken:
                print("\n".join(broken))
                return 1
        return 0
    if not args.write:
        print("\npreview only; run with --write to apply")
        return 0

    if copy_script:
        installed_script(home).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(agent_modes.__file__, installed_script(home))
    if copy_rules:
        rules_file(home).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(default_rules(), rules_file(home))
    for _, path, config in pending:
        write_json(path, config)
    print("\napplied")
    try:
        probe_lines, _, _ = report(home, args.only, probe=True)
    except (OSError, ValueError) as exc:
        print(f"bkf hooks: {exc}", file=sys.stderr)
        return 1
    broken = [line for line in probe_lines if line.startswith("broken")]
    if broken:
        print("\n".join(broken))
    if any(target.name == "codex" for target, _, _ in pending):
        print("Codex: run /hooks once to review and trust the new hooks")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())

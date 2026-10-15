"""Dispatch the installed ``bkf`` command to its focused tool modules."""

from __future__ import annotations

import importlib
import sys


# The single source of the real command list: name -> (module, what it does, when to use it).
COMMANDS = {
    "inventory": (
        "generate_inventory",
        "Generate, check, or update map inventories",
        "after adding, removing, or re-describing a tracked document, to refresh its map",
    ),
    "skills": (
        "skills",
        "Check or regenerate shared skill lists and catalog",
        "after changing a skill or a library module a skill lists",
    ),
    "validate": (
        "validate_bundle",
        "Validate a BKF bundle",
        "after editing a bundle's documents, maps, or links",
    ),
    "updates": (
        "updates",
        "Print the BKF format updates needed by a bundle",
        "when validate reports an older bundle version, or to see what an upgrade needs",
    ),
    "orient": (
        "orient",
        "Print session-start bundle orientation",
        "at session start (the orient hook runs it) or to re-read the map chain",
    ),
    "search": (
        "search",
        "Search indexed bundle sections",
        "before writing or moving a rule, to see where it already lives",
    ),
    "log": (
        "log_entry",
        "Append an idea or feedback entry to the nearest bundle file",
        "to record an idea or a problem without acting on it now",
    ),
    "hooks": (
        "bkf_hooks",
        "Preview, install, or check the agent prefix-mode and orientation hooks",
        "on a new machine, or when a hook seems missing or stale",
    ),
    "sync": (
        "workflow_sync",
        "Preview or synchronize workflow files with a declaration",
        "after creating or changing a workflow declaration",
    ),
}

HELP_COMMAND = (
    "help",
    "List the commands, or show one command's options",
    "to discover what bkf can do: 'bkf help' or 'bkf help <command>'",
)


def _usage() -> str:
    lines = ["usage: bkf <command> [arguments]", "", "commands:"]
    entries = [
        (name, summary, when)
        for name, (_, summary, when) in COMMANDS.items()
    ]
    entries.append(HELP_COMMAND)
    width = max(map(len, (name for name, _, _ in entries)))
    for name, description, when in entries:
        lines.append(f"  {name.ljust(width)}  {description}")
        lines.append(f"  {' ' * width}  use: {when}")
    lines.extend(["", "Run 'bkf help <command>' or 'bkf <command> --help' for options."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help"}:
        sys.stdout.write(_usage())
        return 0

    if arguments[0] == "help":
        if len(arguments) == 1:
            sys.stdout.write(_usage())
            return 0
        if len(arguments) > 2 or arguments[1] == "help" or arguments[1] not in COMMANDS:
            print(f"bkf: no help for {' '.join(arguments[1:])!r}\n", file=sys.stderr)
            sys.stderr.write(_usage())
            return 2
        arguments = [arguments[1], "--help"]

    command = arguments.pop(0)
    selected = COMMANDS.get(command)
    if selected is None:
        print(f"bkf: unknown command {command!r}\n", file=sys.stderr)
        sys.stderr.write(_usage())
        return 2

    hook_run = command == "hooks" and bool(arguments) and arguments[0] == "run"
    try:
        module = importlib.import_module(selected[0])
        return module.main(arguments)
    except Exception as exc:
        if not hook_run:
            raise
        event = arguments[1] if len(arguments) > 1 else "unknown"
        try:
            import hook_events
        except Exception:
            detail = " ".join(str(exc).split()) or "no details"
            message = f"bkf hook {event} failed: {type(exc).__name__}: {detail}"
            if len(message) > 300:
                message = message[:299] + "…"
            import json

            print(json.dumps({"systemMessage": message}, ensure_ascii=False))
            print(message, file=sys.stderr)
        else:
            hook_events.report_failure(event, exc)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

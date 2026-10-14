"""Dispatch the installed ``bkf`` command to its focused tool modules."""

from __future__ import annotations

import importlib
import sys


COMMANDS = {
    "inventory": ("generate_inventory", "Generate, check, or update map inventories"),
    "validate": ("validate_bundle", "Validate a BKF bundle"),
    "updates": ("updates", "Print the BKF format updates needed by a bundle"),
    "orient": ("orient", "Print session-start bundle orientation"),
    "search": ("search", "Search indexed bundle sections"),
    "log": ("log_entry", "Append an idea or feedback entry to the nearest bundle file"),
    "hooks": ("bkf_hooks", "Preview, install, or check the agent prefix-mode and orientation hooks"),
    "sync": ("workflow_sync", "Preview or synchronize workflow files with a declaration"),
}


def _usage() -> str:
    lines = ["usage: bkf <command> [arguments]", "", "commands:"]
    width = max(map(len, COMMANDS))
    lines.extend(
        f"  {name.ljust(width)}  {description}"
        for name, (_, description) in COMMANDS.items()
    )
    lines.extend(["", "Run 'bkf <command> --help' for command options."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help"}:
        sys.stdout.write(_usage())
        return 0 if arguments else 2

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

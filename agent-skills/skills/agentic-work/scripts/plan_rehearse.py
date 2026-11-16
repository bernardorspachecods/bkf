"""Run a plan's gate commands as an informational rehearsal."""
import os
import subprocess
import sys
import tempfile

from harness.gate import run_gate
from harness.engine.run import RunError

import plan_inputs


_USAGE = "usage: rehearse <plan.txt|name>"
_EXPECTATION = (
    "Lines that fail here are expected only for behavior the unit itself creates; "
    "read the others before start."
)


def _repository_root():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        universal_newlines=True,
        check=False,
    )
    if result.returncode != 0:
        raise RunError("rehearse must run inside a git repository")
    return result.stdout.rstrip("\n")


def rehearse_command(args):
    """Run each unit's gates and report their results without deciding the plan."""
    if len(args) != 1:
        print("Error: {0}".format(_USAGE), file=sys.stderr)
        return 2
    try:
        steps = plan_inputs.resolve_plan(args[0])
    except RunError as error:
        print("Error: {0}".format(error), file=sys.stderr)
        return 2
    entries = []
    for step in steps:
        for unit_name, brief_path in step:
            entries.extend(
                (unit_name, command)
                for command in plan_inputs.gate_commands([brief_path])
            )

    if entries:
        # Identical commands (such as the repository-wide check repeated in every
        # unit) run once: the checkout is the same for all of them.
        commands = list(dict.fromkeys(command for _, command in entries))
        timeout = float(os.environ.get("PLAN_GATE_TIMEOUT", "900"))
        with tempfile.TemporaryDirectory(prefix="plan-rehearse-") as output:
            result = run_gate(_repository_root(), timeout, output, commands)
        exit_codes = {
            command: command_result["exit_code"]
            for command, command_result in zip(commands, result["commands"])
        }
        for unit_name, command in entries:
            if exit_codes[command] == 0:
                print("PASS {0} {1}".format(unit_name, command))
            else:
                print("FAIL {0} {1} (exit {2})".format(
                    unit_name, command, exit_codes[command]
                ))
    print(_EXPECTATION)
    return 0

import json
import math
import os
import signal
import subprocess
import time


_TERM_GRACE_SECONDS = 2.0
_POLL_SECONDS = 0.05


def _group_exists(process_group):
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _stop_group(process, process_group):
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        pass

    deadline = time.monotonic() + _TERM_GRACE_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        if not _group_exists(process_group):
            break
        time.sleep(_POLL_SECONDS)

    if _group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some sandboxed systems deny SIGKILL after TERM has already ended
            # the group but before the kernel clears its process-group entry.
            pass

    process.wait()
    while _group_exists(process_group):
        time.sleep(_POLL_SECONDS)


def _run_command(command, cwd, timeout, log_path):
    started = time.monotonic()
    timed_out = False
    with open(log_path, "wb") as log_file:
        process = subprocess.Popen(
            ["bash", "-c", command],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _stop_group(process, process.pid)
            exit_code = 124
        else:
            _stop_group(process, process.pid)
    return {
        "command": command,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "seconds": time.monotonic() - started,
        "log": os.path.basename(log_path),
    }


def _tail(log_path, count=100):
    with open(log_path, "rb") as log_file:
        lines = log_file.read().splitlines(keepends=True)[-count:]
    return b"".join(lines).decode("utf-8", errors="replace")


def _timeout_text(timeout):
    return "{0:g}".format(timeout)


def _write_markdown(path, cwd, timeout, commands, notes, red):
    with open(path, "w", encoding="utf-8", newline="") as output:
        output.write("# Gate\n\n")
        output.write("The harness ran these commands in {0}, outside any agent.\n".format(cwd))
        if not commands:
            output.write("No gate commands were given, so no checks were run. This is a gap, not a pass.\n")
            return
        for note in notes:
            output.write(note + "\n")
        output.write("\n")
        if red:
            output.write(
                "Result: RED, {0} of {1} commands failed. A reviewer cannot override a red result.\n\n".format(
                    red, len(commands)
                )
            )
        else:
            output.write("Result: all green ({0} commands).\n\n".format(len(commands)))
        for index, item in enumerate(commands):
            if index:
                output.write("\n")
            output.write("### `{0}`\n\n".format(item["command"]))
            if item["timed_out"]:
                output.write(
                    "exit code: 124 (timed out after {0} seconds)\n\n".format(_timeout_text(timeout))
                )
            else:
                output.write("exit code: {0}\n\n".format(item["exit_code"]))
            output.write("~~~~\n")
            tail = _tail(os.path.join(os.path.dirname(path), item["log"]))
            output.write(tail)
            if tail and not tail.endswith("\n"):
                output.write("\n")
            output.write("~~~~\n")


def run_gate(cwd, timeout, out, commands, notes=None):
    """Run commands sequentially and write the gate logs and reports."""
    cwd = os.path.abspath(cwd)
    timeout = float(timeout)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite number greater than zero")
    os.makedirs(out, exist_ok=True)
    out = os.path.abspath(out)
    notes = list(notes or [])
    results = []
    for index, command in enumerate(commands, 1):
        log_name = "gate-{0}.log".format(index)
        results.append(_run_command(command, cwd, timeout, os.path.join(out, log_name)))
    red = sum(1 for item in results if item["exit_code"] != 0)
    _write_markdown(os.path.join(out, "gate.md"), cwd, timeout, results, notes, red)
    data = {"cwd": cwd, "timeout": timeout, "commands": results, "red": red}
    with open(os.path.join(out, "gate.json"), "w", encoding="utf-8", newline="") as output:
        json.dump(data, output, ensure_ascii=False)
        output.write("\n")
    return data

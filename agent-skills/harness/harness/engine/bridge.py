"""Serve the plan runner's narrow command bridge during implementation."""
import contextlib
import errno
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import threading
import time


_POLL_SECONDS = 0.3
_TERM_GRACE_SECONDS = 2.0
_OUTPUT_LIMIT = 200000


def porteiro_ponte_script():
    """Return the request client used by plan-run.sh, byte for byte."""
    return '''#!/usr/bin/env bash
# Asks the runner to run an allowed command outside the sandbox. Usage: .plan-porteiro/ponte <command> [args...]
d=$(cd "$(dirname "$0")" && pwd)
[ "$#" -gt 0 ] || { echo "usage: .plan-porteiro/ponte <command> [args...]" >&2; exit 2; }
id=$(date +%s)-$$-$RANDOM
mkdir -p "$d/req" "$d/res"
printf '%s\\0' "$@" >"$d/req/.$id.tmp"
mv "$d/req/.$id.tmp" "$d/req/$id"
limit=$(( ${PORTEIRO_WAIT:-1800} * 2 )); n=0
while [ ! -e "$d/res/$id.done" ]; do
  sleep 0.5; n=$((n + 1))
  [ "$n" -lt "$limit" ] || { echo "ponte: no answer from the runner" >&2; exit 124; }
done
cat "$d/res/$id.out"
code=$(cat "$d/res/$id.done")
rm -f "$d/res/$id.out" "$d/res/$id.done"
exit "$code"
'''


def _tree_file(checkout, base_file, name):
    try:
        tree = pathlib.Path(base_file).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not tree:
        return None
    try:
        return subprocess.check_output(
            ["git", "-C", os.fspath(checkout), "show", "{0}:{1}".format(tree, name)],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def _json_bytes(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _pnpm_patterns(checkout, base_file):
    raw = _tree_file(checkout, base_file, ".plan-run.json")
    if raw is None:
        return None, "no .plan-run.json at the unit's base: only gate commands run"
    config = _json_bytes(raw)
    if not isinstance(config, dict):
        return None, "the .plan-run.json at the unit's base is not usable: only gate commands run"
    bridge_config = config.get("bridge")
    if not isinstance(bridge_config, dict):
        return None, "the .plan-run.json at the unit's base is not usable: only gate commands run"
    patterns = bridge_config.get("pnpmScripts")
    if not isinstance(patterns, list) or any(not isinstance(item, str) for item in patterns):
        return None, "the .plan-run.json at the unit's base is not usable: only gate commands run"
    try:
        for pattern in patterns:
            re.compile(pattern)
    except re.error:
        return None, "the .plan-run.json at the unit's base is not usable: only gate commands run"
    return patterns, ""


def _package_script(raw, script):
    package = _json_bytes(raw)
    if not isinstance(package, dict):
        return None
    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        return None
    value = scripts.get(script)
    return value if isinstance(value, str) else None


def porteiro_script_allowed(checkout, base_file, script):
    """Return whether a base-listed pnpm script is unchanged and safe to invoke."""
    if re.fullmatch(r"[A-Za-z0-9:_-]+", script) is None:
        return False, "{0} has characters that are not allowed".format(script)
    patterns, reason = _pnpm_patterns(checkout, base_file)
    if patterns is None:
        return False, reason
    try:
        matched = any(re.fullmatch(pattern, script) is not None for pattern in patterns)
    except re.error:
        return False, "the .plan-run.json at the unit's base is not usable: only gate commands run"
    if not matched:
        return False, "{0} is not in the pnpm scripts that .plan-run.json allows".format(script)

    base_package = _tree_file(checkout, base_file, "package.json")
    was = _package_script(base_package, script)
    if not was:
        return False, "{0} is not a script of the unit's base".format(script)
    try:
        current_package = (pathlib.Path(checkout) / "package.json").read_bytes()
    except OSError:
        current_package = None
    now = _package_script(current_package, script)
    if now != was:
        return False, "{0} was changed in this unit".format(script)
    return True, ""


def porteiro_allowed(checkout, base_file, gate_commands, argv):
    """Return (mode, reason) using the plan runner's allow rules."""
    argv = list(argv)
    if not argv:
        return None, "empty request"
    line = " ".join(argv)
    if line in gate_commands:
        return "shell", ""
    if argv[0] == "pnpm" and len(argv) >= 2:
        allowed, reason = porteiro_script_allowed(checkout, base_file, argv[1])
        if not allowed:
            return None, reason
        return "argv", ""
    return None, (
        "not allowed: only the pnpm scripts listed in .plan-run.json at the unit's base "
        "and the gate commands of the brief"
    )


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
    while _group_exists(process_group) and time.monotonic() < deadline:
        time.sleep(0.05)
    if _group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
    process.wait()


def _timeout_value():
    value = os.environ.get("PLAN_PORTEIRO_TIMEOUT", "900")
    try:
        timeout = float(value)
    except ValueError:
        timeout = 900.0
        value = "900"
    return timeout, value


def _tail(path, limit=_OUTPUT_LIMIT):
    with open(path, "rb") as output:
        output.seek(0, os.SEEK_END)
        size = output.tell()
        output.seek(max(0, size - limit), os.SEEK_SET)
        return output.read()


def _log(log_path, unit, status, argv):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    with open(log_path, "a", encoding="utf-8", newline="") as output:
        output.write("{0}\t{1}\t{2}\t{3}\n".format(stamp, unit, status, " ".join(argv)))


def _request_argv(path):
    data = pathlib.Path(path).read_bytes().split(b"\0")
    if data and data[-1] == b"":
        data.pop()
    return [item.decode("utf-8", errors="surrogateescape") for item in data]


def porteiro_handle(checkout, unit, base_file, gate_commands, request_file, log_path):
    """Handle a NUL-delimited request and publish its output and exit code."""
    checkout = pathlib.Path(checkout)
    request_file = pathlib.Path(request_file)
    response_dir = checkout / ".plan-porteiro" / "res"
    identifier = request_file.name
    argv = _request_argv(request_file)
    mode, reason = porteiro_allowed(checkout, base_file, gate_commands, argv)
    output_path = response_dir / (identifier + ".run")
    response_path = response_dir / (identifier + ".out")
    done_path = response_dir / (identifier + ".done")
    exit_code = 126
    if mode is None:
        refusal = (
            "ponte: refused ({0}).\nAllowed: the pnpm scripts listed in .plan-run.json and "
            "the commands of the brief's gate, exactly as written.\n"
        ).format(reason)
        response_path.write_text(refusal, encoding="utf-8")
        _log(log_path, unit, "REFUSED ({0})".format(reason), argv)
    else:
        timeout, timeout_text = _timeout_value()
        started = time.time()
        command = ["bash", "-c", " ".join(argv)] if mode == "shell" else argv
        with output_path.open("wb") as output:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=os.fspath(checkout),
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except OSError as error:
                exit_code = 127 if error.errno == errno.ENOENT else 126
                diagnostic = "{0}: {1}\n".format(command[0], error)
                output.write(diagnostic.encode("utf-8", errors="replace"))
            else:
                try:
                    exit_code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _stop_group(process, process.pid)
                    exit_code = 142
                    with output_path.open("ab") as output:
                        output.write("ponte: timed out after {0}s\n".format(timeout_text).encode("utf-8"))
                else:
                    _stop_group(process, process.pid)
        elapsed = int(time.time() - started)
        response_path.write_bytes(_tail(output_path))
        output_path.unlink()
        _log(log_path, unit, "ALLOWED exit={0} {1}s".format(exit_code, elapsed), argv)
    done_tmp = response_dir / (identifier + ".done.tmp")
    done_tmp.write_text(str(exit_code) + "\n", encoding="ascii")
    os.replace(str(done_tmp), str(done_path))


def _add_exclude(checkout):
    exclude_path = subprocess.check_output(
        ["git", "-C", os.fspath(checkout), "rev-parse", "--git-path", "info/exclude"],
        stderr=subprocess.DEVNULL,
    ).decode("utf-8").strip()
    exclude = pathlib.Path(exclude_path)
    if not exclude.is_absolute():
        exclude = pathlib.Path(checkout) / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if ".plan-porteiro/" not in existing.splitlines():
        with exclude.open("a", encoding="utf-8", newline="") as output:
            if existing and not existing.endswith("\n"):
                output.write("\n")
            output.write(".plan-porteiro/\n")


@contextlib.contextmanager
def porteiro(checkout, unit, base_file, gate_commands, log_path):
    """Create and serve the plan runner bridge for one implementation round."""
    checkout = pathlib.Path(checkout).resolve()
    bridge_dir = checkout / ".plan-porteiro"
    shutil.rmtree(str(bridge_dir), ignore_errors=True)
    (bridge_dir / "req").mkdir(parents=True)
    (bridge_dir / "res").mkdir()
    script = bridge_dir / "ponte"
    script.write_bytes(porteiro_ponte_script().encode("utf-8"))
    script.chmod(0o755)
    _add_exclude(checkout)
    pathlib.Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            requests = sorted((bridge_dir / "req").iterdir())
            for request_file in requests:
                if stop.is_set():
                    break
                if request_file.name.startswith(".") or not request_file.is_file():
                    continue
                porteiro_handle(
                    checkout, unit, base_file, gate_commands, request_file, log_path
                )
                try:
                    request_file.unlink()
                except FileNotFoundError:
                    pass
            stop.wait(_POLL_SECONDS)

    thread = threading.Thread(target=serve, name="plan-porteiro-{0}".format(unit), daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        shutil.rmtree(str(bridge_dir), ignore_errors=True)

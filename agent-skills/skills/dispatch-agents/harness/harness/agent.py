"""Run an agent backend with a prepared prompt and captured output files."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Optional

from .inject import InjectionError, inject_rules


_LIVE_PROCESSES = set()

# Set while a handled signal is cleaning up, so an agent that was starting in a worker thread ends too.
stopping = threading.Event()


def terminate_children(grace=2.0):
    """Terminate and reap every agent process currently owned by this module."""
    processes = list(_LIVE_PROCESSES)
    for process in processes:
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + grace
    for process in processes:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            process.wait()
        finally:
            _LIVE_PROCESSES.discard(process)


class Backend:
    """Base class for agent command argument builders."""

    executable = None

    def arguments(self, directory, model, effort, sandbox, tier, last_message, web=False):
        raise NotImplementedError

    def quota_text(self, events_path) -> Optional[str]:
        return None

    def finish(self, events_path, last_message_path):
        """Called after the agent exits; a backend that does not write the last message itself does it here."""


def _is_error_event(line):
    """False for a typed event that is not a failure: the phrase there is quoted text, such as a file the agent printed."""
    try:
        event = json.loads(line)
    except ValueError:
        return True
    if not isinstance(event, dict) or "type" not in event:
        return True
    return event["type"] in ("turn.failed", "error")


class CodexBackend(Backend):
    """Build the Codex CLI arguments used by scripts/lib-codex.sh."""

    executable = "codex"

    def arguments(self, directory, model, effort, sandbox, tier, last_message, web=False):
        command = ["exec"]
        if tier:
            command.extend(["-c", 'service_tier="{0}"'.format(tier)])
        command.extend(
            [
                "--skip-git-repo-check",
                "-C",
                directory,
                "-m",
                model,
                "-c",
                'model_reasoning_effort="{0}"'.format(effort),
                "-s",
                sandbox,
                "--json",
                "-o",
                last_message,
                "-",
            ]
        )
        return command

    def quota_text(self, events_path) -> Optional[str]:
        try:
            with open(events_path, "r", encoding="utf-8") as events:
                for line in events:
                    if "hit your usage limit" not in line:
                        continue
                    if not _is_error_event(line):
                        continue
                    marker = "try again at "
                    if marker in line:
                        text = line.rsplit(marker, 1)[1]
                    else:
                        marker = '"message":"'
                        text = line.rsplit(marker, 1)[1] if marker in line else line
                    return text.rsplit('"', 1)[0]
        except (OSError, UnicodeError):
            return None
        return None


_CLAUDE_SANDBOX = json.dumps(
    {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False}}
)


class ClaudeBackend(Backend):
    """Run `claude -p` with the prompt on stdin and the stream of events on stdout.

    The Codex sandbox names map to permissions: `workspace-write` allows Write and Edit only under the
    working directory (path rules) and Bash inside Claude's sandbox, which confines its writes to the
    working directory and the temporary folders (checked with a Haiku model outside /tmp: a redirect
    to ../ was refused); any other sandbox, `read-only` included, allows only Read, Glob and Grep.
    A tool outside the list is denied, never asked (`dontAsk`), so a run never waits for an answer.
    """

    executable = "claude"

    def arguments(self, directory, model, effort, sandbox, tier, last_message, web=False):
        command = [
            "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
            "--model", model, "--effort", effort, "--permission-mode", "dontAsk",
        ]
        if sandbox == "workspace-write":
            command.extend(["--settings", _CLAUDE_SANDBOX])
            tools = "Read,Glob,Grep,Write(./**),Edit(./**),Bash"
        else:
            tools = "Read,Glob,Grep"
        if web:
            tools += ",WebFetch,WebSearch"
        command.extend(["--allowedTools", tools])
        return command

    def finish(self, events_path, last_message_path):
        """Write the text of the final `result` event as the last message."""
        text = None
        try:
            with open(events_path, "r", encoding="utf-8") as events:
                for line in events:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(event, dict) and event.get("type") == "result" and isinstance(event.get("result"), str):
                        text = event["result"]
            if text is not None:
                with open(last_message_path, "w", encoding="utf-8", newline="") as message:
                    message.write(text)
        except (OSError, UnicodeError):
            return

    def quota_text(self, events_path) -> Optional[str]:
        """The reset time of a `rate_limit_event` that is not `allowed`, or the text of a limit error."""
        try:
            with open(events_path, "r", encoding="utf-8") as events:
                for line in events:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get("type") == "rate_limit_event":
                        info = event.get("rate_limit_info")
                        if isinstance(info, dict) and info.get("status") not in (None, "allowed", "allowed_warning"):
                            reset = info.get("resetsAt")
                            if isinstance(reset, (int, float)):
                                moment = time.localtime(reset)
                                return "resets at {0}".format(time.strftime("%Y-%m-%d %H:%M", moment))
                            return "the limit is reached ({0})".format(info.get("status"))
                    if event.get("type") == "result" and event.get("is_error") and isinstance(event.get("result"), str):
                        if "limit" in event["result"].lower():
                            return event["result"].strip()
        except (OSError, UnicodeError):
            return None
        return None


BACKENDS = {"codex": CodexBackend, "claude": ClaudeBackend}


def resolve_backend(name):
    """The backend named, else HARNESS_BACKEND, else codex."""
    return name or os.environ.get("HARNESS_BACKEND") or "codex"


def get_backend(name):
    return BACKENDS.get(resolve_backend(name))


def _spawn(command, directory, stdin, stdout, stderr):
    """Start the backend and register it so a handled signal can end it."""

    def popen(**extra):
        return subprocess.Popen(
            command, cwd=directory, stdin=stdin, stdout=stdout, stderr=stderr, **extra
        )

    if threading.current_thread() is not threading.main_thread():
        # Python runs signal handlers only in the main thread: there is nothing to mask here,
        # and preexec_fn is not safe where other threads run.
        process = popen()
        _LIVE_PROCESSES.add(process)
        if stopping.is_set():
            process.terminate()
        return process

    # A signal between the start and the registration would leave the agent running,
    # so the handled signals wait until it is registered; the agent itself must not inherit that.
    handled_signals = {signal.SIGTERM, signal.SIGINT, signal.SIGHUP}
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, handled_signals)
    try:
        process = popen(
            preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        )
        _LIVE_PROCESSES.add(process)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    return process


def run_agent(
    directory,
    prompt_file,
    out_prefix,
    model,
    effort,
    sandbox="workspace-write",
    tier=None,
    backend=None,
    web=False,
):
    """Inject prompt rules, run a backend in the foreground, and return its status."""
    backend_class = get_backend(backend)
    if backend_class is None:
        print("backend not implemented: {0}".format(resolve_backend(backend)), file=sys.stderr)
        return 2

    try:
        inject_rules(prompt_file)
    except InjectionError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError as error:
        print(str(error), file=sys.stderr)
        return 1

    events_path = out_prefix + ".events.jsonl"
    stderr_path = out_prefix + ".stderr.log"
    last_message_path = out_prefix + ".last-message.md"
    command = [backend_class.executable] + backend_class().arguments(
        directory, model, effort, sandbox, tier, last_message_path, web
    )
    try:
        with open(prompt_file, "rb") as prompt, open(events_path, "wb") as events, open(
            stderr_path, "wb"
        ) as errors:
            process = _spawn(command, directory, prompt, events, errors)
            try:
                status = process.wait()
            finally:
                _LIVE_PROCESSES.discard(process)
    except OSError as error:
        print("harness: {0}".format(error), file=sys.stderr)
        return 2
    backend_class().finish(events_path, last_message_path)
    if status < 0:
        return 128 + -status
    return status

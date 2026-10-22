"""Run an agent backend with a prepared prompt and captured output files."""

import subprocess
import sys

from .inject import InjectionError, inject_rules


class Backend:
    """Base class for agent command argument builders."""

    executable = None

    def arguments(self, directory, model, effort, sandbox, tier, last_message):
        raise NotImplementedError


class CodexBackend(Backend):
    """Build the Codex CLI arguments used by scripts/lib-codex.sh."""

    executable = "codex"

    def arguments(self, directory, model, effort, sandbox, tier, last_message):
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


BACKENDS = {"codex": CodexBackend}


def run_agent(
    directory,
    prompt_file,
    out_prefix,
    model,
    effort,
    sandbox="workspace-write",
    tier=None,
    backend="codex",
):
    """Inject prompt rules, run a backend in the foreground, and return its status."""
    backend_class = BACKENDS.get(backend)
    if backend_class is None:
        print("backend not implemented: {0}".format(backend), file=sys.stderr)
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
        directory, model, effort, sandbox, tier, last_message_path
    )
    try:
        with open(prompt_file, "rb") as prompt, open(events_path, "wb") as events, open(
            stderr_path, "wb"
        ) as errors:
            process = subprocess.Popen(
                command,
                cwd=directory,
                stdin=prompt,
                stdout=events,
                stderr=errors,
            )
            status = process.wait()
    except OSError as error:
        print("harness: {0}".format(error), file=sys.stderr)
        return 2
    if status < 0:
        return 128 + -status
    return status

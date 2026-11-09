"""Run one agent step or a parallel group of agents."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple, Optional

from .. import agent


class StepResult(NamedTuple):
    ok: bool
    reason: str
    quota: Optional[str]


def tier_from_environment(environ=None):
    environment = os.environ if environ is None else environ
    if "HARNESS_CODEX_TIER" not in environment:
        return "fast"
    return environment["HARNESS_CODEX_TIER"] or None


def _load_session(path, backend, directory):
    """The saved conversation id, when it is for this backend and folder; None otherwise."""
    try:
        with open(path, "r", encoding="utf-8") as source:
            data = json.load(source)
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not data["id"]:
        return None
    if data.get("backend") != agent.resolve_backend(backend) or data.get("directory") != os.fspath(directory):
        return None
    return data["id"]


def _save_session(path, backend, directory, backend_class, events_path):
    identifier = backend_class().session_id(events_path)
    if not identifier:
        return
    try:
        with open(path, "w", encoding="utf-8", newline="") as output:
            json.dump({"backend": agent.resolve_backend(backend), "id": identifier,
                       "directory": os.fspath(directory)}, output)
            output.write("\n")
    except OSError:
        pass


def run_agent_step(
    run,
    label,
    directory,
    prompt_file,
    out_prefix,
    model,
    effort,
    sandbox,
    tier,
    reason_when_not_quota,
    backend=None,
    web=False,
    session=None,
    continuation=None,
):
    """Run one agent. With ``session`` (a file) the agent's conversation is kept there across runs: when the file holds
    a conversation for this backend and folder and ``continuation`` (a prompt file) is given, the agent resumes it with
    that prompt instead of starting over with ``prompt_file``; a conversation that cannot be resumed is started anew."""
    events_path = out_prefix + ".events.jsonl"
    backend_class = agent.get_backend(backend)
    status = None
    if session is not None and continuation is not None and backend_class is not None:
        identifier = _load_session(session, backend, directory)
        if identifier:
            status = agent.run_agent(
                directory, continuation, out_prefix, model, effort, sandbox, tier, backend, web,
                resume_id=identifier, track=True,
            )
            if status != 0 and status != agent.STALLED_EXIT and not backend_class().started(events_path) \
                    and backend_class().quota_text(events_path) is None:
                run.note("{0}: the conversation {1} could not be resumed; starting a new one".format(label, identifier))
                status = None
    if status is None:
        status = agent.run_agent(
            directory, prompt_file, out_prefix, model, effort, sandbox, tier, backend, web,
            track=session is not None,
        )
    if session is not None and backend_class is not None:
        _save_session(session, backend, directory, backend_class, events_path)
    if status == 0:
        return StepResult(True, "", None)

    if status == agent.STALLED_EXIT:
        reason = "{0}: STALLED: the agent wrote nothing for {1:g} minutes and was ended (see {2})".format(
            label, agent.stall_seconds() / 60, events_path
        )
        run.note(reason)
        return StepResult(False, reason, None)

    quota = backend_class().quota_text(events_path) if backend_class is not None else None
    if quota is not None:
        quota = quota.rstrip("\r\n")
        run.note("QUOTA: {0}".format(quota))
        return StepResult(
            False,
            "{0}: usage limit reached. QUOTA: {1} (see {2})".format(
                label, quota, events_path
            ),
            quota,
        )
    return StepResult(False, reason_when_not_quota.replace("<exit>", str(status)), None)


def run_agents(phase_dir, output_file, folders, model, effort, tier, backend=None):
    phase_path = os.fspath(phase_dir)
    pending = [
        folder
        for folder in folders
        if not os.path.isfile(os.path.join(phase_path, folder, output_file))
        or os.path.getsize(os.path.join(phase_path, folder, output_file)) == 0
    ]

    def run_folder(folder):
        directory = os.path.join(phase_path, folder)
        out_prefix = os.path.join(directory, "run")
        status = agent.run_agent(
            directory,
            os.path.join(directory, "brief.md"),
            out_prefix,
            model,
            effort,
            "workspace-write",
            tier,
            backend,
        )
        if status != 0:
            failed_path = os.path.join(directory, "failed")
            if status == agent.STALLED_EXIT:
                failure = "STALLED: the agent wrote nothing for {0:g} minutes and was ended (see {1})".format(
                    agent.stall_seconds() / 60, os.path.join(directory, "run.events.jsonl")
                )
            else:
                failure = "exit={0} (see {1})".format(status, os.path.join(directory, "run.stderr.log"))
            with open(failed_path, "w", encoding="utf-8", newline="") as failed:
                failed.write(failure + "\n")

    with ThreadPoolExecutor(max_workers=max(1, len(pending))) as executor:
        futures = [executor.submit(run_folder, folder) for folder in pending]
        for future in futures:
            future.result()

    bad = []
    for folder in folders:
        directory = os.path.join(phase_path, folder)
        output_path = os.path.join(directory, output_file)
        if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            failed_path = os.path.join(directory, "failed")
            if os.path.isfile(failed_path):
                with open(failed_path, "r", encoding="utf-8") as failed:
                    failure = failed.read().rstrip("\n")
            else:
                failure = "wrote no {0}".format(output_file)
            bad.append("{0}: {1}; ".format(folder, failure))
        failed_path = os.path.join(directory, "failed")
        if os.path.exists(failed_path):
            os.remove(failed_path)
    return StepResult(not bad, "".join(bad), None)

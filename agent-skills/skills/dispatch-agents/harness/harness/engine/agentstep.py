"""Run one agent step or a parallel group of agents."""

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
):
    status = agent.run_agent(
        directory, prompt_file, out_prefix, model, effort, sandbox, tier, backend
    )
    if status == 0:
        return StepResult(True, "", None)

    backend_class = agent.get_backend(backend)
    events_path = out_prefix + ".events.jsonl"
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
            with open(failed_path, "w", encoding="utf-8", newline="") as failed:
                failed.write(
                    "exit={0} (see {1})".format(
                        status, os.path.join(directory, "run.stderr.log")
                    )
                    + "\n"
                )

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

"""Apply a parallel group's patches and review their combined result."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import NamedTuple

from .agentstep import run_agent_step
from .diffbase import make_patch, snapshot_base
from .loop import run_gate_round, run_review_round


class IntegrationResult(NamedTuple):
    ok: bool
    reason: str


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as output:
        output.write(text)


def _read(path):
    with open(path, "r", encoding="utf-8", newline="") as source:
        return source.read()


def _apply_patch(repo, patch, error_path):
    with open(error_path, "w", encoding="utf-8", newline="") as errors:
        checked = subprocess.run(
            ["git", "-C", os.fspath(repo), "apply", "--check", os.fspath(patch)],
            stdout=subprocess.DEVNULL, stderr=errors, check=False,
        )
        if checked.returncode:
            return False
        applied = subprocess.run(
            ["git", "-C", os.fspath(repo), "apply", os.fspath(patch)],
            stdout=subprocess.DEVNULL, stderr=errors, check=False,
        )
        return applied.returncode == 0


def run_integration(
    run, repo, step, units, *, hooks, settings, tier, limits, goal_path,
    brief_check, brief_differs, gate_differs,
):
    """Run the integration rounds for a parallel group."""
    units = list(units)
    label = "S{0}-integration".format(step)
    directory = Path(run.path) / label
    try:
        brief_check(run.path, units)
    except Exception as error:
        return IntegrationResult(False, "{0}: {1}".format(label, error))
    goal_path = Path(goal_path)
    if not goal_path.is_file() or goal_path.stat().st_size == 0:
        return IntegrationResult(False, "{0}: the goal {1} is missing or empty".format(label, goal_path))

    goal_text = _read(goal_path)
    for unit in units:
        if gate_differs(run.path, unit):
            run.note("{0}: the gate of {1} was changed after it passed: it passed against another gate, and the integration runs the current one".format(label, unit))
        elif brief_differs(run.path, unit):
            run.note("{0}: the brief of {1} differs from the one its implementer received".format(label, unit))

    directory.mkdir(parents=True, exist_ok=True)
    base = directory / "base"
    rounds_path = directory / "rounds"
    if base.is_file():
        if rounds_path.is_dir():
            shutil.move(str(rounds_path), str(directory / "rounds.attempt-{0}".format(int(time.time()))))
    else:
        snapshot_base(directory, repo)
    rounds_path.mkdir(parents=True, exist_ok=True)
    brief_path = directory / "brief.md"
    _write(brief_path, hooks.integration_brief(run.path, units, goal_text))

    round_number = 0
    reviews = 0
    gate_fails = 0
    previous_problems = ""
    previous_handoff = ""
    while True:
        round_number += 1
        round_dir = rounds_path / str(round_number)
        round_dir.mkdir(parents=True, exist_ok=True)
        failed = ""
        if round_number == 1:
            hooks.progress("S{0} integração · ronda {1} · aplicar diffs".format(step, round_number))
            run.note("{0}: apply the diffs".format(label))
            for unit in units:
                marker = directory / (".applied-" + unit)
                if marker.exists():
                    continue
                patch = Path(run.path) / unit / "final.patch"
                error_path = round_dir / ("apply-" + unit + ".err")
                if _apply_patch(repo, patch, error_path):
                    marker.touch()
                else:
                    failed += "- {0}: {1}\n".format(unit, patch)
                    run.note("{0}: {1} did not apply (see {2})".format(label, unit, error_path))

        if failed or round_number > 1:
            _write(directory / "status", "integrating round {0}\n".format(round_number))
            hooks.progress("S{0} integração · ronda {1} · integrar".format(step, round_number))
            run.note("{0} round {1}: integrate".format(label, round_number))
            prompt_path = round_dir / "integrate-prompt.md"
            _write(prompt_path, hooks.integrate_prompt(brief_path, failed, previous_problems, previous_handoff))
            prefix = round_dir / "integrate"
            result = run_agent_step(
                run, label, repo, os.fspath(prompt_path), os.fspath(prefix), settings.model, settings.effort,
                "workspace-write", tier,
                "{0}: integrator exit=<exit> (see {1}/integrate.stderr.log)".format(label, round_dir),
            )
            if not result.ok:
                return IntegrationResult(False, result.reason)
            message = Path(str(prefix) + ".last-message.md")
            if not message.is_file() or message.stat().st_size == 0:
                return IntegrationResult(False, "{0}: integrator left no handoff".format(label))
            handoff = round_dir / "handoff.md"
            shutil.copyfile(message, handoff)
            shutil.copyfile(handoff, directory / "handoff.md")
            for unit in units:
                (directory / (".applied-" + unit)).touch()

        diff_path = round_dir / "diff.patch"
        make_patch(directory, diff_path, repo)
        if diff_path.stat().st_size == 0:
            return IntegrationResult(False, "{0}: the combined diff is empty".format(label))

        commands = hooks.gate_commands(brief_path)
        gate_file = ""
        if commands:
            gate_file = str(round_dir / "gate.md")
            passed, gate_fails, reason = run_gate_round(
                run, label, repo, round_dir, commands, hooks, limits, gate_fails,
                "S{0} integração · ronda {1}".format(step, round_number),
            )
            if not passed:
                if reason:
                    return IntegrationResult(False, reason)
                previous_problems = str(round_dir / "problems.md")
                previous_handoff = str(round_dir / "handoff.md")
                continue

        reviews += 1
        verdict, reason = run_review_round(
            run, label, repo, round_dir, hooks, settings, tier, limits,
            previous_problems, gate_file,
            "S{0} integração · ronda {1}".format(step, round_number),
        )
        if verdict is None:
            return IntegrationResult(False, reason)
        if verdict == "pass":
            _write(directory / "status", "passed\n")
            hooks.progress("S{0} integração · ronda {1} · passou".format(step, round_number))
            return IntegrationResult(True, "")
        if verdict == "escalate":
            _write(directory / "status", "escalated\n")
            hooks.progress("S{0} integração · ronda {1} · escalada".format(step, round_number))
            return IntegrationResult(False, "{0}: the reviewer escalated (see {1})".format(label, round_dir / "problems.md"))
        hooks.progress("S{0} integração · ronda {1} · devolvida".format(step, round_number))
        if reviews >= limits.max_rounds:
            _write(directory / "status", "escalated\n")
            hooks.progress("S{0} integração · ronda {1} · escalada".format(step, round_number))
            return IntegrationResult(False, "{0}: round cap {1} reached (see {2})".format(label, limits.max_rounds, round_dir / "problems.md"))
        previous_problems = str(round_dir / "problems.md")
        previous_handoff = str(round_dir / "handoff.md")

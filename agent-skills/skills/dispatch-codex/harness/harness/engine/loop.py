"""Run the implementation, gate, and review loop for one workflow unit."""
import os
import shutil
import time
from contextlib import contextmanager
from typing import NamedTuple

from ..gate import run_gate
from .agentstep import run_agent_step
from .diffbase import make_patch, snapshot_base
from .metrics import record_metrics
from .review import run_review


class LoopResult(NamedTuple):
    ok: bool
    reason: str


class UnitHooks:
    """Workflow supplied prompts, gate commands, progress, and implement context."""

    def implement_prompt(self, brief, round_number, resumed, previous_problems, previous_handoff):
        raise NotImplementedError

    def review_prompt(self, brief, patch, previous_problems, attempt, gate_file):
        raise NotImplementedError

    def gate_commands(self, brief):
        raise NotImplementedError

    def progress(self, text):
        raise NotImplementedError

    @contextmanager
    def around_implement(self, checkout, unit, base, brief):
        yield


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as output:
        output.write(text)


def _read(path):
    with open(path, "r", encoding="utf-8", newline="") as source:
        return source.read()


def _gate_problems(round_dir):
    gate_text = _read(os.path.join(round_dir, "gate.md"))
    return (
        "## What I checked\n\n"
        "- The script ran the brief's gate in the checkout; a command failed, so no reviewer ran (a failing command is not a matter of opinion).\n"
        "- The results are in gate.md of this round.\n"
        "- Each failing command below must pass.\n\n"
        "## Problems\n\n"
        + gate_text
        + "\nVERDICT: back\n"
    )


def run_unit_loop(
    run,
    unit,
    checkout,
    *,
    source_brief,
    hooks,
    settings,
    tier,
    limits,
    step=None,
    base_from=None
):
    """Run implementation rounds until review passes or the unit must stop."""
    directory = os.path.join(os.fspath(run.path), unit)
    checkout = os.fspath(checkout)
    source_brief = os.fspath(source_brief)
    round_count = 0
    reviews = 0
    gate_fails = 0
    resumed = 0
    previous_problems = ""
    previous_handoff = ""
    step_prefix = "S{0}".format(step if step is not None else 0)

    os.makedirs(directory, exist_ok=True)
    base_path = os.path.join(directory, "base")
    rounds_path = os.path.join(directory, "rounds")
    if os.path.isfile(base_path):
        resumed = 1
        if os.path.isdir(rounds_path):
            old_rounds = os.path.join(directory, "rounds.attempt-{0}".format(int(time.time())))
            shutil.move(rounds_path, old_rounds)

    if base_from is not None:
        shutil.copyfile(os.fspath(base_from), base_path)
        _write(os.path.join(directory, "base-format"), "tree\n")
    elif not resumed:
        snapshot_base(directory, checkout)

    os.makedirs(rounds_path, exist_ok=True)
    brief_path = os.path.join(directory, "brief.md")
    shutil.copyfile(source_brief, brief_path)
    commands = hooks.gate_commands(brief_path)

    while True:
        round_count += 1
        round_dir = os.path.join(rounds_path, str(round_count))
        os.makedirs(round_dir, exist_ok=True)
        _write(os.path.join(directory, "status"), "implementing round {0}\n".format(round_count))
        hooks.progress("{0} unidade {1} · ronda {2} · implementação".format(step_prefix, unit, round_count))
        run.note("{0} round {1}: implement".format(unit, round_count))

        prompt_path = os.path.join(round_dir, "implement-prompt.md")
        prompt = hooks.implement_prompt(
            brief_path, round_count, resumed, previous_problems, previous_handoff
        )
        _write(prompt_path, prompt)
        start_epoch = int(time.time())
        result_prefix = os.path.join(round_dir, "implement")
        with hooks.around_implement(checkout, unit, base_path, brief_path):
            step_result = run_agent_step(
                run, unit, checkout, prompt_path, result_prefix,
                settings.model, settings.effort, "workspace-write", tier,
                "{0}: implementer exit=<exit> (see {1}/implement.stderr.log)".format(unit, round_dir),
            )
        if not step_result.ok:
            return LoopResult(False, step_result.reason)

        handoff_result = os.path.join(round_dir, "implement.last-message.md")
        if not os.path.isfile(handoff_result) or os.path.getsize(handoff_result) == 0:
            return LoopResult(False, "{0}: implementer left no handoff".format(unit))
        round_handoff = os.path.join(round_dir, "handoff.md")
        shutil.copyfile(handoff_result, round_handoff)
        shutil.copyfile(round_handoff, os.path.join(directory, "handoff.md"))
        diff_path = os.path.join(round_dir, "diff.patch")
        make_patch(directory, diff_path, checkout)
        record_metrics(run.path, unit, round_count, round_dir, start_epoch)
        if os.path.getsize(diff_path) == 0:
            return LoopResult(
                False,
                "{0}: the diff is empty after round {1}, so nothing was changed".format(unit, round_count),
            )

        gate_file = ""
        if commands:
            _write(os.path.join(directory, "status"), "gate round {0}\n".format(round_count))
            run.note("{0} round {1}: gate".format(unit, round_count))
            gate_result = run_gate(checkout, limits.gate_timeout, round_dir, commands)
            gate_file = os.path.join(round_dir, "gate.md")
            if gate_result["red"] == 0:
                hooks.progress("{0} unidade {1} · ronda {2} · gate PASS".format(step_prefix, unit, round_count))
                run.note("{0} round {1}: gate passed".format(unit, round_count))
            else:
                _write(os.path.join(round_dir, "problems.md"), _gate_problems(round_dir))
                _write(os.path.join(round_dir, "verdict"), "back\n")
                hooks.progress("{0} unidade {1} · ronda {2} · gate FAIL".format(step_prefix, unit, round_count))
                gate_fails += 1
                run.note("{0}: round {1}: gate failed (see {2})".format(unit, round_count, gate_file))
                if gate_fails >= limits.max_gate_rounds:
                    _write(os.path.join(directory, "status"), "escalated\n")
                    hooks.progress("{0} unidade {1} · ronda {2} · escalada".format(step_prefix, unit, round_count))
                    return LoopResult(
                        False,
                        "{0}: the gate still fails after {1} rounds (see {2})".format(unit, gate_fails, gate_file),
                    )
                previous_problems = os.path.join(round_dir, "problems.md")
                previous_handoff = round_handoff
                continue

        reviews += 1
        _write(os.path.join(directory, "status"), "reviewing round {0}\n".format(round_count))
        hooks.progress("{0} unidade {1} · ronda {2} · revisão".format(step_prefix, unit, round_count))
        run.note("{0} round {1}: review".format(unit, round_count))

        def build_prompt(attempt):
            return hooks.review_prompt(
                brief_path, diff_path, previous_problems, attempt,
                gate_file if gate_file and os.path.getsize(gate_file) else "",
            )

        review_result = run_review(
            run, unit, checkout, round_dir, build_prompt, settings.model,
            settings.review_effort, tier, limits.min_checked, previous_problems or None,
        )
        if review_result.verdict is None:
            return LoopResult(False, review_result.reason)
        verdict = review_result.verdict
        if verdict == "pass":
            _write(os.path.join(directory, "status"), "passed\n")
            hooks.progress("{0} unidade {1} · ronda {2} · passou".format(step_prefix, unit, round_count))
            shutil.copyfile(diff_path, os.path.join(directory, "final.patch"))
            return LoopResult(True, "")
        if verdict == "escalate":
            _write(os.path.join(directory, "status"), "escalated\n")
            hooks.progress("{0} unidade {1} · ronda {2} · escalada".format(step_prefix, unit, round_count))
            return LoopResult(False, "{0}: the reviewer escalated (see {1})".format(unit, os.path.join(round_dir, "problems.md")))

        hooks.progress("{0} unidade {1} · ronda {2} · devolvida".format(step_prefix, unit, round_count))
        if reviews >= limits.max_rounds:
            _write(os.path.join(directory, "status"), "escalated\n")
            hooks.progress("{0} unidade {1} · ronda {2} · escalada".format(step_prefix, unit, round_count))
            return LoopResult(
                False,
                "{0}: round cap {1} reached (see {2})".format(unit, limits.max_rounds, os.path.join(round_dir, "problems.md")),
            )
        previous_problems = os.path.join(round_dir, "problems.md")
        previous_handoff = round_handoff

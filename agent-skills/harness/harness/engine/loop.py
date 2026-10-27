"""Run the implementation, gate, and review loop for one workflow unit."""
import os
import shutil
import time
from contextlib import contextmanager
from typing import NamedTuple

from ..gate import run_gate
from ..verdict import read_blocked
from .converge import gate_signature, problem_files
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


def run_gate_round(run, label, checkout, round_dir, commands, hooks, limits,
                   gate_fails, progress_prefix, previous_signature=None):
    """Run one shared gate stage and return (passed, failures, reason)."""
    _write(os.path.join(os.path.dirname(os.path.dirname(round_dir)), "status"),
           "gate round {0}\n".format(os.path.basename(round_dir)))
    run.note("{0} round {1}: gate".format(label, os.path.basename(round_dir)))
    result = run_gate(checkout, limits.gate_timeout, round_dir, commands)
    gate_file = os.path.join(round_dir, "gate.md")
    if result["red"] == 0:
        hooks.progress("{0} · gate PASS".format(progress_prefix))
        run.note("{0} round {1}: gate passed".format(label, os.path.basename(round_dir)))
        return True, gate_fails, ""
    failed_commands = [item["command"] for item in result["commands"] if item["exit_code"] != 0]
    repeat_dir = os.path.join(round_dir, "gate-repeat")
    repeated = run_gate(checkout, limits.gate_timeout, repeat_dir, failed_commands)
    if repeated["red"] == 0:
        round_number = os.path.basename(round_dir)
        command_text = ", ".join(failed_commands)
        with open(gate_file, "a", encoding="utf-8", newline="") as output:
            output.write("\nRepeat result: the failed commands passed on one repeat; this round is flaky.\n")
        run.note("{0} round {1}: gate was red once and green on repeat (flaky): {2}".format(
            label, round_number, command_text
        ))
        hooks.progress("{0} · gate PASS".format(progress_prefix))
        run.note("{0} round {1}: gate passed".format(label, round_number))
        return True, gate_fails, ""
    signature = gate_signature(_read(gate_file))
    if signature == previous_signature:
        _write(os.path.join(os.path.dirname(os.path.dirname(round_dir)), "status"), "escalated\n")
        failed_text = ", ".join(signature[0])
        return False, gate_fails, (
            "{0}: the gate fails the same way in two rounds in a row ({1}); "
            "the brief may ask for something that cannot pass at this step (see {2})"
        ).format(label, failed_text, gate_file)
    _write(os.path.join(round_dir, "problems.md"), _gate_problems(round_dir))
    _write(os.path.join(round_dir, "verdict"), "back\n")
    hooks.progress("{0} · gate FAIL".format(progress_prefix))
    gate_fails += 1
    run.note("{0}: round {1}: gate failed (see {2})".format(label, os.path.basename(round_dir), gate_file))
    if gate_fails >= limits.max_gate_rounds:
        _write(os.path.join(os.path.dirname(os.path.dirname(round_dir)), "status"), "escalated\n")
        hooks.progress("{0} · escalada".format(progress_prefix))
        return False, gate_fails, "{0}: the gate still fails after {1} rounds (see {2})".format(label, gate_fails, gate_file)
    return False, gate_fails, ""


def run_review_round(run, label, checkout, round_dir, hooks, settings, tier,
                     limits, previous_problems, gate_file, progress_prefix):
    """Run one shared review stage and return its validated verdict and reason."""
    _write(os.path.join(os.path.dirname(os.path.dirname(round_dir)), "status"),
           "reviewing round {0}\n".format(os.path.basename(round_dir)))
    hooks.progress("{0} · revisão".format(progress_prefix))
    run.note("{0} round {1}: review".format(label, os.path.basename(round_dir)))

    def build_prompt(attempt):
        return hooks.review_prompt(
            os.path.join(os.path.dirname(os.path.dirname(round_dir)), "brief.md"),
            os.path.join(round_dir, "diff.patch"), previous_problems, attempt,
            gate_file if gate_file and os.path.getsize(gate_file) else "",
        )

    result = run_review(
        run, label, checkout, round_dir, build_prompt, settings.model,
        settings.review_effort, tier, limits.min_checked,
        previous_problems or None,
        allow_brief=True,
    )
    return result.verdict, result.reason


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
    previous_gate_signature = None
    previous_review_files = set()
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
        blocked_reason = read_blocked(round_handoff)
        if blocked_reason is not None:
            reason = "{0}: blocked by the implementer: {1} (see {2})".format(
                unit, blocked_reason, round_handoff
            )
            _write(os.path.join(directory, "status"), "blocked\n")
            hooks.progress("{0} unidade {1} · ronda {2} · bloqueada".format(
                step_prefix, unit, round_count
            ))
            run.note(reason)
            return LoopResult(False, reason)
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
            gate_file = os.path.join(round_dir, "gate.md")
            passed, gate_fails, reason = run_gate_round(
                run, unit, checkout, round_dir, commands, hooks, limits,
                gate_fails, "{0} unidade {1} · ronda {2}".format(step_prefix, unit, round_count),
                previous_gate_signature,
            )
            previous_gate_signature = gate_signature(_read(gate_file)) if not passed else None
            if not passed:
                if reason:
                    return LoopResult(False, reason)
                previous_problems = os.path.join(round_dir, "problems.md")
                previous_handoff = round_handoff
                continue

        reviews += 1
        verdict, review_reason = run_review_round(
            run, unit, checkout, round_dir, hooks, settings, tier, limits,
            previous_problems, gate_file,
            "{0} unidade {1} · ronda {2}".format(step_prefix, unit, round_count),
        )
        if verdict is None:
            return LoopResult(False, review_reason)
        if verdict == "pass":
            _write(os.path.join(directory, "status"), "passed\n")
            hooks.progress("{0} unidade {1} · ronda {2} · passou".format(step_prefix, unit, round_count))
            shutil.copyfile(diff_path, os.path.join(directory, "final.patch"))
            return LoopResult(True, "")
        if verdict == "escalate":
            _write(os.path.join(directory, "status"), "escalated\n")
            hooks.progress("{0} unidade {1} · ronda {2} · escalada".format(step_prefix, unit, round_count))
            return LoopResult(False, "{0}: the reviewer escalated (see {1})".format(unit, os.path.join(round_dir, "problems.md")))
        if verdict == "brief":
            _write(os.path.join(directory, "status"), "escalated\n")
            hooks.progress("{0} unidade {1} · ronda {2} · escalada".format(step_prefix, unit, round_count))
            return LoopResult(
                False,
                "{0}: the reviewer says the brief is the problem (see {1})".format(
                    unit, os.path.join(round_dir, "problems.md")
                ),
            )

        hooks.progress("{0} unidade {1} · ronda {2} · devolvida".format(step_prefix, unit, round_count))
        current_review_files = problem_files(_read(os.path.join(round_dir, "problems.md")))
        if current_review_files and current_review_files == previous_review_files:
            _write(os.path.join(directory, "status"), "escalated\n")
            files = ", ".join(sorted(current_review_files))
            return LoopResult(
                False,
                "{0}: the reviewer sent the unit back twice for the same files ({1}); "
                "the brief may be the cause (see {2})".format(
                    unit, files, os.path.join(round_dir, "problems.md")
                ),
            )
        if reviews >= limits.max_rounds:
            _write(os.path.join(directory, "status"), "escalated\n")
            hooks.progress("{0} unidade {1} · ronda {2} · escalada".format(step_prefix, unit, round_count))
            return LoopResult(
                False,
                "{0}: round cap {1} reached (see {2})".format(unit, limits.max_rounds, os.path.join(round_dir, "problems.md")),
            )
        previous_problems = os.path.join(round_dir, "problems.md")
        previous_handoff = round_handoff
        previous_review_files = current_review_files

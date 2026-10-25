"""Sequential plan workflow for the harness pipeline."""
import os
import shutil
from pathlib import Path
from typing import NamedTuple

from harness.engine.agentstep import run_agent_step
from harness.engine.diffbase import make_patch, snapshot_base, snapshot_tree
from harness.engine.loop import UnitHooks, run_unit_loop
from harness.engine.workflow import Step, Stop, Workflow
from harness.engine.run import RunError

import plan_inputs
import plan_board


class _Limits(NamedTuple):
    max_rounds: int
    max_gate_rounds: int
    gate_timeout: float
    min_checked: int


def _env_int(name, default):
    return int(os.environ.get(name, str(default)))


def _limits():
    return _Limits(
        _env_int("PLAN_MAX_ROUNDS", 3),
        _env_int("PLAN_MAX_GATE_ROUNDS", 5),
        float(os.environ.get("PLAN_GATE_TIMEOUT", "900")),
        _env_int("PLAN_MIN_CHECKED", 3),
    )


def _review_effort(settings):
    return settings.review_effort or settings.effort


def _plan_tier():
    return os.environ.get("PLAN_CODEX_TIER", "fast") or None


class _UnitHooks(UnitHooks):
    def __init__(self, ctx, step):
        self.ctx = ctx
        self.step = step

    def implement_prompt(self, brief, round_number, resumed, previous_problems, previous_handoff):
        return plan_inputs.implement_prompt(
            os.environ.get("PLAN_GUIDES") or plan_inputs.guides_path(os.environ, self.ctx.repo),
            brief, round_number, resumed, previous_problems, previous_handoff,
        )

    def review_prompt(self, brief, patch, previous_problems, attempt, gate_file):
        return plan_inputs.review_prompt(
            os.environ.get("PLAN_GUIDES") or plan_inputs.guides_path(os.environ, self.ctx.repo),
            brief, patch, previous_problems, attempt, gate_file,
        )

    def gate_commands(self, brief):
        return plan_inputs.gate_commands([brief])

    def progress(self, text):
        self.ctx.progress(text)


class PlanWorkflow(Workflow):
    name = "plan"
    command = "plan-run.sh"
    usage_start = "usage: start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>"
    repo_hint = "run start inside the repository the plan changes"

    def validate_start(self, args):
        if len(args) != 2:
            raise RunError(self.usage_start)
        goal, plan = args
        if not os.path.isfile(goal) or os.path.getsize(goal) == 0:
            raise RunError("missing or empty goal: {0}".format(goal))
        if not os.path.isfile(plan) or os.path.getsize(plan) == 0:
            raise RunError("missing or empty plan: {0}".format(plan))
        steps = plan_inputs.parse_plan(plan)
        del steps
        if shutil.which("codex") is None:
            raise RunError("codex not found")
        guides = plan_inputs.guides_path(os.environ, Path(__file__).resolve().parents[1])
        if not os.path.isdir(guides):
            raise RunError("no role guides at {0} (set PLAN_GUIDES)".format(guides))

    def start(self, ctx, args):
        goal, plan = args
        steps = plan_inputs.parse_plan(plan)
        plan_inputs.write_inputs(ctx.run.path, goal, steps)
        base = ctx.run.path / "plan-base"
        base.mkdir(parents=True, exist_ok=True)
        snapshot_base(base, ctx.repo)
        unit_count = len(steps)
        ctx.note(
            "start {0} ({1} {2}, review {3}, max {4} rounds, {5} step(s), {6} unit(s), repo {7})".format(
                ctx.run.name, ctx.settings.model, ctx.settings.effort,
                _review_effort(ctx.settings), _limits().max_rounds,
                unit_count, unit_count, ctx.repo,
            )
        )
        units = (ctx.run.path / "00-input" / "order").read_text(encoding="utf-8").splitlines()
        for unit in units:
            if not plan_inputs.gate_commands([plan_inputs.brief_current(ctx.run.path, unit)]):
                ctx.note("unit {0} has no gate: only a reviewer checks it".format(unit))

    def steps(self, ctx):
        order_path = ctx.run.path / "00-input" / "order"
        units = [line.rstrip("\r\n") for line in order_path.read_text(encoding="utf-8").splitlines()]
        steps = []
        for index, unit in enumerate(units, 1):
            def run_step(step_ctx, step_number=index, step_unit=unit):
                step_ctx.progress("S{0} início · unidade {1}".format(step_number, step_unit))
                if (step_ctx.run.path / (".done-" + step_unit)).exists():
                    return
                base_from = None
                if step_number > 1:
                    candidate = step_ctx.run.path / "state-after-S{0}".format(step_number - 1)
                    if candidate.is_file():
                        base_from = candidate
                else:
                    candidate = step_ctx.run.path / "plan-base" / "base"
                    base_format = step_ctx.run.path / "plan-base" / "base-format"
                    if candidate.is_file() and base_format.is_file() and base_format.read_text(encoding="utf-8").strip() == "tree":
                        base_from = candidate
                result = run_unit_loop(
                    step_ctx.run, step_unit, step_ctx.repo,
                    source_brief=plan_inputs.brief_current(step_ctx.run.path, step_unit),
                    hooks=_UnitHooks(step_ctx, step_number),
                    settings=step_ctx.settings._replace(
                        review_effort=_review_effort(step_ctx.settings)
                    ),
                    tier=_plan_tier(),
                    limits=_limits(),
                    step=step_number,
                    base_from=base_from,
                )
                if not result.ok:
                    raise Stop(result.reason)
                (step_ctx.run.path / (".done-" + step_unit)).touch()

            steps.append(Step(index, unit, run_step))
        return steps

    def after_step(self, ctx, step):
        path = ctx.run.path / "state-after-S{0}".format(step.number)
        try:
            tree = snapshot_tree(ctx.repo)
            path.write_text(tree + "\n", encoding="utf-8")
        except (OSError, RunError):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def final_step(self, ctx):
        run = ctx.run

        def report(_ctx):
            order_path = run.path / "00-input" / "order"
            units = [unit for line in order_path.read_text(encoding="utf-8").splitlines() for unit in line.split()]
            try:
                plan_inputs.check_briefs(run.path, units)
            except RunError as error:
                raise Stop(str(error))
            make_patch(run.path / "plan-base", run.path / "cumulative.patch", ctx.repo)
            prompt = plan_inputs.report_prompt(
                run.path,
                os.environ.get("PLAN_GUIDES") or plan_inputs.guides_path(os.environ, ctx.repo),
            )
            prompt_path = run.path / "report-prompt.md"
            with prompt_path.open("w", encoding="utf-8", newline="") as output:
                output.write(prompt)
            result = run_agent_step(
                run, "final review", ctx.repo, str(prompt_path), str(run.path / "report"),
                ctx.settings.model, _review_effort(ctx.settings), "read-only",
                _plan_tier(),
                "final review exit=<exit> (see {0}/report.stderr.log)".format(run.path),
            )
            if not result.ok:
                raise Stop(result.reason)
            last_message = run.path / "report.last-message.md"
            if not last_message.is_file() or last_message.stat().st_size == 0:
                raise Stop("final review wrote no report")
            shutil.copyfile(last_message, run.path / "report.md")

        return Step("final", "review", report)

    def ready_path(self, ctx):
        return str(ctx.run.path / "report.md")

    def fix_hint(self, ctx):
        return "Read the rounds in {0}, fix the cause (the briefs in {0}/00-input/units/, or the checkout), then: plan-run.sh resume {1}".format(
            ctx.run.path, ctx.run.name
        )

    def board(self, ctx):
        return plan_board.board(ctx.run)

    def finish(self, ctx):
        return plan_board.finish(ctx)

    def commands(self):
        return {"gates": plan_inputs.gates_command}


WORKFLOW = PlanWorkflow()

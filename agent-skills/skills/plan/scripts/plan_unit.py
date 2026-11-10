"""Check one unit of a plan that the conversation agent implements itself.

`begin` saves the checkout as the unit's base. After the agent implements, `check` runs the brief's `gate` commands
(code decides), and only if they pass starts a new reviewer process (read-only, on its own model and backend) that sees
the brief and the diff. The reviewer is never the implementer and never shared between units. The result is one verdict
and an exit code: 0 pass, 1 back (fix and run `check` again), 2 escalate or brief (stop and ask), 3 the check itself
failed.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plan  # noqa: E402  (limits and tier: one source with the script-run plan)
import plan_inputs  # noqa: E402
from harness.engine.backend import require_backend  # noqa: E402
from harness.engine.diffbase import make_patch, snapshot_base  # noqa: E402
from harness.engine.pipeline import _check_reviewer  # noqa: E402
from harness.engine.review import run_review  # noqa: E402
from harness.engine.run import RunError  # noqa: E402
from harness.gate import run_gate  # noqa: E402

PASS, BACK, ESCALATE, ERROR = 0, 1, 2, 3
_EXIT = {"pass": PASS, "back": BACK, "escalate": ESCALATE, "brief": ESCALATE}


class _Notes:
    """The little of a run that the review step needs: a place to write notes."""

    def __init__(self, path):
        self.path = Path(path)

    def note(self, text):
        with self.path.open("a", encoding="utf-8", newline="") as output:
            output.write("{0}\t{1}\n".format(time.strftime("%Y-%m-%dT%H:%M:%S"), text))


def _checkout():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RunError("run plan-unit inside the repository the unit changes")
    return result.stdout.strip()


def _unit_dir(args):
    return Path(args.dir) / (args.unit or Path(args.brief).stem)


def begin(args):
    brief = Path(args.brief)
    if not brief.is_file() or brief.stat().st_size == 0:
        raise RunError("missing or empty brief: {0}".format(brief))
    unit_dir = _unit_dir(args)
    if unit_dir.exists():
        if not args.restart:
            raise RunError("unit already begun: {0} (use --restart to start it over)".format(unit_dir))
        shutil.rmtree(unit_dir)
    unit_dir.mkdir(parents=True)
    snapshot_base(unit_dir, _checkout())
    shutil.copyfile(brief, unit_dir / "brief.md")
    print("unit {0}: base saved in {1}".format(unit_dir.name, unit_dir))
    return PASS


def _round_dir(unit_dir):
    rounds = unit_dir / "rounds"
    number = len(list(rounds.iterdir())) + 1 if rounds.is_dir() else 1
    path = rounds / str(number)
    path.mkdir(parents=True)
    return number, path


def _gate_problems(gate_file, red, total):
    return "The gate failed: {0} of {1} command(s) did not pass. Fix the code, not the gate.\n\n{2}".format(
        red, total, gate_file.read_text(encoding="utf-8")
    )


def _finish(unit_name, number, patch, gate_text, verdict, problems):
    print("unit {0} · round {1}".format(unit_name, number))
    print("patch: {0}".format(patch))
    print("gate: {0}".format(gate_text))
    if verdict is not None:
        print("VERDICT: {0}".format(verdict))
    if problems is not None:
        print("problems: {0}".format(problems))
    return _EXIT.get(verdict, PASS)


def check(args):
    checkout = _checkout()
    unit_dir = _unit_dir(args)
    brief = unit_dir / "brief.md"
    if not (unit_dir / "base").is_file() or not brief.is_file():
        raise RunError("run begin first: no base saved for unit {0}".format(unit_dir.name))
    if not args.gate_only:
        if not args.review_model:
            raise RunError("--review-model is required (or --gate-only when you review the diff yourself)")
        _check_reviewer(args.review_model, args.review_backend)
        require_backend(args.review_backend)

    number, round_dir = _round_dir(unit_dir)
    notes = _Notes(unit_dir / "status.log")
    patch = round_dir / "diff.patch"
    make_patch(unit_dir, patch, checkout)

    commands = plan_inputs.gate_commands([str(brief)])
    gate_file = ""
    gate_text = "none (only the reviewer checks this unit)"
    if commands:
        data = run_gate(checkout, plan._limits().gate_timeout, str(round_dir / "gate"), commands)
        gate_file = round_dir / "gate" / "gate.md"
        if data["red"]:
            problems = round_dir / "problems.md"
            problems.write_text(_gate_problems(gate_file, data["red"], len(commands)), encoding="utf-8")
            (round_dir / "verdict").write_text("back\n", encoding="utf-8")
            notes.note("round {0}: gate failed".format(number))
            return _finish(unit_dir.name, number, patch,
                           "FAIL ({0} of {1}; see {2})".format(data["red"], len(commands), gate_file),
                           "back", problems)
        gate_text = "pass ({0} command(s))".format(len(commands))
    if args.gate_only:
        return _finish(unit_dir.name, number, patch, gate_text, None, None)

    previous = unit_dir / "rounds" / str(number - 1) / "problems.md"
    previous = str(previous) if number > 1 and previous.is_file() else ""
    guides = os.environ.get("PLAN_GUIDES") or plan_inputs.guides_path(os.environ)
    session = unit_dir / "session-review.json"

    def build_prompt(attempt):
        return plan_inputs.review_prompt(guides, str(brief), str(patch), previous, attempt, str(gate_file))

    def build_continuation(attempt):
        return plan_inputs.review_continuation(
            str(brief), False, str(patch), previous or None, attempt,
            str(gate_file) if gate_file else "", previous or None,
        )

    result = run_review(
        notes, unit_dir.name, checkout, str(round_dir), build_prompt, args.review_model, args.review_effort,
        plan._plan_tier(), plan._limits().min_checked, previous or None, allow_brief=True,
        session=str(session), build_continuation=build_continuation if session.is_file() else None,
        backend=args.review_backend,
    )
    if result.verdict is None:
        print(result.reason)
        return ERROR
    return _finish(unit_dir.name, number, patch, gate_text, result.verdict, round_dir / "problems.md")


def _parser():
    parser = argparse.ArgumentParser(prog="plan-unit.sh", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("begin", "check"):
        sub = commands.add_parser(name)
        sub.add_argument("brief")
        sub.add_argument("--dir", required=True, help="folder that holds the unit's files (diffs, gate logs, reviews)")
        sub.add_argument("--unit", help="unit name (default: the brief's file name without extension)")
        if name == "begin":
            sub.add_argument("--restart", action="store_true", help="start an already begun unit over")
        else:
            sub.add_argument("--review-model", help="the reviewer's model")
            sub.add_argument("--review-backend", choices=("codex", "claude"),
                             help="the reviewer's backend (default: HARNESS_BACKEND, else codex)")
            sub.add_argument("-r", "--review-effort", default="high")
            sub.add_argument("--gate-only", action="store_true",
                             help="run the gate and write the diff only; you review the diff yourself")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        return begin(args) if args.command == "begin" else check(args)
    except RunError as error:
        print("plan-unit: {0}".format(error), file=sys.stderr)
        return ERROR


if __name__ == "__main__":
    sys.exit(main())

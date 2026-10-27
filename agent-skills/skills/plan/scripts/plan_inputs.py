import glob
import os
import re
import shutil
import subprocess
from pathlib import Path

from harness.engine.layout import find_run
from harness.engine.run import RunError
import plan_lint


_UNIT_NAME = re.compile(r"[A-Za-z0-9._-]+\Z")


def _valid_name(name):
    return bool(_UNIT_NAME.fullmatch(name) and name not in (".", ".."))


def _read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as source:
        return source.read()


def _words(line):
    words = []
    for word in re.findall(r"[^ \t\n]+", line):
        matches = glob.glob(word)
        words.extend(matches or [word])
    return words


def parse_plan(plan_path):
    """Read and validate plan.txt, returning (unit name, brief path) pairs."""
    plan_path = Path(plan_path)
    plan_dir = plan_path.parent.absolute()
    steps = []
    with open(plan_path, "r", encoding="utf-8", newline="") as source:
        for line in source:
            words = _words(line.split("#", 1)[0])
            if not words:
                continue
            units = []
            for word in words:
                brief_path = Path(word)
                if not brief_path.is_absolute():
                    brief_path = plan_dir / brief_path
                if not brief_path.is_file() or brief_path.stat().st_size == 0:
                    raise RunError("missing or empty unit brief: {0}".format(word))
                name = brief_path.name[:-3] if brief_path.name.endswith(".md") else brief_path.name
                if not _valid_name(name):
                    raise RunError("bad unit name (from the file name): {0}".format(word))
                units.append((name, str(brief_path)))
            steps.append(units)
    if not steps:
        raise RunError("plan.txt has no step")
    return steps


def write_inputs(run_path, goal_path, steps):
    """Copy the goal and unit briefs into a run's input folder."""
    run_path = Path(run_path)
    units_path = run_path / "00-input" / "units"
    units_path.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(goal_path, run_path / "00-input" / "goal.md")
    order = []
    index = 0
    for step in steps:
        step_units = []
        for name, brief_path in step:
            index += 1
            unit_name = "{0:02d}-{1}".format(index, name)
            shutil.copyfile(brief_path, units_path / (unit_name + ".md"))
            step_units.append(unit_name)
        order.append(" ".join(step_units))
    with open(run_path / "00-input" / "order", "w", encoding="utf-8", newline="") as output:
        output.write("".join(name + "\n" for name in order))


def gate_commands(brief_paths):
    """Return unique commands from all tagged gate fences, in encounter order."""
    commands = []
    seen = set()
    for brief_path in brief_paths:
        active = False
        with open(brief_path, "r", encoding="utf-8", newline="") as source:
            for line in source:
                line = line.rstrip("\r\n")
                if re.fullmatch(r"```gate[ \t]*", line):
                    active = True
                    continue
                if active and re.fullmatch(r"```[ \t]*", line):
                    active = False
                    continue
                if active:
                    command = line.strip()
                    if command and not command.startswith("#") and command not in seen:
                        seen.add(command)
                        commands.append(command)
    return commands


def _run_path(name, environ=None):
    return find_run("plan", name, _current_repo(), environ)


def _current_repo():
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, universal_newlines=True, check=False)
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def gates_command(args):
    """Print gates for a plan path or named run; return the shell command status."""
    if isinstance(args, str):
        args = [args]
    if len(args) != 1:
        raise RunError("usage: gates <plan.txt|name>")
    target = args[0]
    files = []
    if os.path.isfile(target):
        plan_path = Path(target)
        plan_dir = plan_path.parent.absolute()
        with open(plan_path, "r", encoding="utf-8", newline="") as source:
            for line in source:
                for word in _words(line.split("#", 1)[0]):
                    brief_path = Path(word)
                    if not brief_path.is_absolute():
                        brief_path = plan_dir / brief_path
                    if not brief_path.is_file() or brief_path.stat().st_size == 0:
                        raise RunError("missing or empty unit brief: {0}".format(word))
                    files.append(brief_path)
    else:
        if not _valid_name(target):
            raise RunError("bad run name: {0}".format(target))
        run_path = _run_path(target)
        if not run_path.is_dir():
            raise RunError("no such run: {0}".format(run_path))
        units_path = run_path / "00-input" / "units"
        with open(run_path / "00-input" / "order", "r", encoding="utf-8", newline="") as source:
            for line in source:
                name = line.rstrip("\r\n").split()
                files.extend(units_path / (unit + ".md") for unit in name)
    if not files:
        raise RunError("no unit")
    missing = False
    has_errors = False
    for brief_path in files:
        print(brief_path.name[:-3] if brief_path.name.endswith(".md") else brief_path.name)
        commands = gate_commands([brief_path])
        if commands:
            for command in commands:
                print("  $ " + command)
        else:
            print("  NO GATE: only a reviewer checks this unit")
            missing = True
        for level, message in plan_lint.lint_brief(brief_path, Path.cwd()):
            prefix = "! error" if level == "error" else "? warning"
            print("  {0}: {1}".format(prefix, message))
            if level == "error":
                has_errors = True
        print()
    return 1 if missing or has_errors else 0


def brief_current(run_path, unit):
    return str(Path(run_path) / "00-input" / "units" / (unit + ".md"))


def check_briefs(run_path, units):
    for unit in units:
        path = brief_current(run_path, unit)
        if not Path(path).is_file() or Path(path).stat().st_size == 0:
            raise RunError("{0}: the current brief {1} is missing or empty".format(unit, path))


def brief_differs(run_path, unit):
    received = Path(run_path) / unit / "brief.md"
    current = Path(brief_current(run_path, unit))
    return received.is_file() and (not current.is_file() or current.read_bytes() != received.read_bytes())


def gate_differs(run_path, unit):
    if not brief_differs(run_path, unit):
        return False
    current = brief_current(run_path, unit)
    received = Path(run_path) / unit / "brief.md"
    return gate_commands([current]) != gate_commands([received])


def print_unit_brief(run_path, unit, heading_marks):
    current = Path(brief_current(run_path, unit))
    text = _read_text(current)
    if brief_differs(run_path, unit):
        received = _read_text(Path(run_path) / unit / "brief.md")
        text += (
            "\n\n{0} Brief received by the implementer (differs from the current one)\n\n"
            "The current brief defines the intent. The copy below is what the implementer received. "
            "Judge against the current brief. If the unit meets the copy but not the current brief, "
            "say so: the deviation comes from the change of brief, not from the unit. If it fails "
            "both, the unit failed.\n\n{1}"
        ).format(heading_marks, received)
    return text


def integration_brief(run_path, units, goal_text):
    """Build the current integration brief, including the frozen plan goal."""
    text = (
        '# Integration of a parallel group\n\nThe units below were implemented apart, each in its own copy of the repository, '
        'and their diffs were brought together in this checkout. Check the combined result against every brief and against each other: '
        'contradictions between units, a "Receives" that the other unit did not leave ready as stated, duplicated or clashing names, '
        'and each unit\'s own criteria. Use the section "The integration review" of the review guide.\n'
        '\n## The goal of the plan\n\nThis is the goal of the whole plan, read from 00-input/goal.md when this integration started. '
        'Use it to judge how the units fit together and what is out of scope, and to read any note the coordinator left in it about how '
        'the run was carried out. It adds no criteria to the briefs.\n\n'
    )
    text += re.sub(r"(?m)^```gate", "``` gate", goal_text)
    text += "\n"
    for unit in units:
        text += "\n## Unit {0}\n\n{1}\n".format(unit, print_unit_brief(run_path, unit, "###"))
    return text


def integrate_prompt(guides, brief, failed_patches, previous_problems, previous_handoff):
    """Build the integration agent prompt using the plan role guide."""
    text = _read_text(brief)
    text += (
        "\n\n---\n## Role\nOpen and follow the role guide: {0}/plan-integration.md (read-only). "
        "It says how to bring the units of a parallel group together and what the handoff holds.\n"
        "\n## Rules\n- The current directory is the repository: work here.\n"
        "- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n"
        "- Do not write the handoff to a file. Your final message is the handoff, and nothing else.\n"
    ).format(guides)
    if failed_patches:
        text += (
            "\n## What to do\nThe diffs of these units did not apply to the checkout. Bring what each one meant into the checkout, "
            "resolving the conflict, and change nothing else:\n{0}\n"
        ).format(failed_patches)
    if previous_problems:
        handoff = _read_text(previous_handoff) if previous_handoff and os.path.isfile(previous_handoff) else ""
        text += (
            "\nA reviewer found problems in the combined result. Fix those and only those, then verify again.\n\n"
            "Problems from the review:\n\n{0}\n\nYour handoff from the previous round, for you to resume from:\n\n{1}\n"
        ).format(_read_text(previous_problems), handoff)
    text += "\nIf the brief cannot be followed because a command cannot pass at this step or a rule forbids what the result requires, make your last line `BLOCKED: <the sentence of the brief that conflicts and what you saw>` instead of repeating the attempt.\n"
    return text


def integration_review_prompt(guides, brief, patch, previous_problems, attempt, gate_file):
    """Build the read-only review prompt for a group's combined diff."""
    text = review_prompt(guides, brief, patch, previous_problems, attempt, gate_file)
    text = text.replace(
        "Open and follow the role guide: {0}/plan-review.md (read-only). You are not the author of the work.".format(guides),
        'Open and follow the role guide: {0}/plan-review.md (read-only), section "The integration review". You are not the author of the work.'.format(guides),
    )
    return text


def implement_prompt(guides, brief, round_number, resumed, previous_problems, previous_handoff):
    text = _read_text(brief)
    text += (
        "\n\n---\n## Role\nOpen and follow the role guide: {0}/plan-implementation.md (read-only). "
        "It says how to work inside the brief, what to verify and what the handoff holds.\n"
        "\n## Rules\n- The current directory is the repository: do the work here.\n"
        "- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n"
        "- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.\n"
    ).format(guides)
    if gate_commands([brief]):
        text += "- The brief has a `gate`. After you finish, the script runs those commands itself and sends the work back, without a review, if any fails. Run them yourself first when you can.\n"
    if round_number == 1 and resumed:
        text += "\nAn earlier attempt at this unit was stopped. The checkout may already hold its work. Judge it against the brief, keep what is right and fix the rest.\n"
    if previous_problems:
        text += (
            "\nThe script's gate or a reviewer sent your work back. The work from the earlier round is in the checkout. "
            "Fix the problems below and only those, keeping what was fine, and verify again.\n\n"
            "Problems from the gate or the review:\n\n{0}\n\n"
            "Your handoff from the previous round, for you to resume from:\n\n{1}\n"
        ).format(_read_text(previous_problems), _read_text(previous_handoff))
    text += "\nIf the brief cannot be followed because a command cannot pass at this step or a rule forbids what the result requires, make your last line `BLOCKED: <the sentence of the brief that conflicts and what you saw>` instead of repeating the attempt.\n"
    return text


def review_prompt(guides, brief, patch, previous_problems, attempt, gate_file):
    text = "# Review\n\n## The brief\n\n" + _read_text(brief)
    text += (
        "\n\n---\n## Inputs (read-only)\n- The diff, new files included: {0}\n"
        "- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.\n"
        "- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.\n"
    ).format(patch)
    if gate_file:
        text += (
            "- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: {0}. "
            "They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.\n"
        ).format(gate_file)
    text += "\n## Role\nOpen and follow the role guide: {0}/plan-review.md (read-only). You are not the author of the work.\n".format(guides)
    if previous_problems:
        text += "\nThe problems you listed in the previous round are below. The work was corrected; check whether they are gone.\n\n{0}\n".format(_read_text(previous_problems))
    text += (
        '\n---\nYour final message is the review, and nothing else. Begin it with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:\n'
        "VERDICT: pass\nVERDICT: back\nVERDICT: escalate\n"
    )
    if attempt > 1:
        text += 'Your previous attempt left no usable review (no "## What I checked" section, or no verdict line). Follow the form this time.\n'
    text += "The reviewer may end with `VERDICT: brief` when the diff is fine but the brief asks for something contradictory or impossible.\n"
    return text


def report_prompt(run_path, guides):
    run_path = Path(run_path)
    order_path = run_path / "00-input" / "order"
    with open(order_path, "r", encoding="utf-8", newline="") as source:
        units = [name for line in source for name in line.split()]
    check_briefs(run_path, units)
    text = "# Final review of the plan\n\n## The goal\n\n"
    text += _read_text(run_path / "00-input" / "goal.md")
    text += "\n\n## The unit briefs, in order\n"
    for unit in units:
        text += "\n### {0}\n\n{1}\n".format(unit, print_unit_brief(run_path, unit, "####"))
    text += "\n## Inputs (read-only)\n- The diff of the whole plan, new files included: {0}\n- The reviews of each unit and of each parallel group: ".format(run_path / "cumulative.patch")
    for unit in units:
        text += "{0}/{1}/rounds/*/problems.md ".format(run_path, unit)
    text += "{0}/S*-integration/rounds/*/problems.md".format(run_path)
    text += "\n- The repository is your current directory. Open it read-only. Do not change anything. Do not open the handoffs.\n"
    text += "\n## Role\nOpen and follow the role guide: {0}/plan-review.md (read-only), section \"The final review\". You are not the author of the work.\n".format(guides)
    text += "\n---\nYour final message is the report, and nothing else.\n"
    return text


def guides_path(environ):
    return environ.get("PLAN_GUIDES") or str(Path(__file__).resolve().parents[1] / "roles")

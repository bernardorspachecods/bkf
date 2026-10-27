"""Run five independent council advisors, anonymized reviews and report checks."""
import os
import random
import shutil
import sys
from pathlib import Path

from harness.engine.backend import require_backend
from harness.engine.agentstep import run_agents, tier_from_environment
from harness.engine.lock import acquire
from harness.engine.record import keep_record
from harness.engine.review import run_review
from harness.engine.run import RunDir, RunError, valid_name
from harness.engine.stepboard import render_steps
from harness.engine.workflow import Context, Step, Stop, Workflow
from harness.engine.pipeline import _root
from harness.template import render_file


_PERSPECTIVES = ("contrarian", "first-principles", "expansionist", "outsider", "executor")
_BRIEFS = Path(__file__).resolve().parents[1] / "briefs"
_ADVISORS = "01-advisors"
_PACKET = "02-packet"
_REVIEWERS = "03-review"


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        raise RunError("{0} must be an integer".format(name))


def _guides():
    return os.environ.get("COUNCIL_GUIDES") or str(Path(__file__).resolve().parents[1] / "roles")


def _brief(template, /, **values):
    return render_file(_BRIEFS / template, values)


def _brief_body(path):
    with open(path, "r", encoding="utf-8", newline="") as source:
        return "".join(line for line in source if not line.startswith("# "))


class CouncilWorkflow(Workflow):
    name = "council"
    command = "council-run.sh"
    usage_start = "usage: start [-m model] [-e effort] <name> <brief.md>"
    repo_hint = "run start inside the repository the council goes to"

    def validate_start(self, args):
        if len(args) != 1:
            raise RunError(self.usage_start)
        brief = args[0]
        if not os.path.isfile(brief) or os.path.getsize(brief) == 0:
            raise RunError("missing or empty brief: {0}".format(brief))
        require_backend()
        guides = _guides()
        if not os.path.isdir(guides):
            raise RunError("no role guides at {0} (set COUNCIL_GUIDES)".format(guides))

    def start(self, ctx, args):
        inputs = ctx.run.path / "00-input"
        inputs.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args[0], str(inputs / "brief.md"))
        ctx.note("start {0} ({1} {2})".format(ctx.run.name, ctx.settings.model, ctx.settings.effort))

    def _advisor_brief(self, ctx, perspective):
        title = {
            "contrarian": "Contrarian", "first-principles": "First principles",
            "expansionist": "Expansionist", "outsider": "Outsider", "executor": "Executor",
        }[perspective]
        return _brief("advisor.md", question=_brief_body(ctx.run.path / "00-input" / "brief.md"),
                      perspective=title, guides=_guides())

    def _reviewer_brief(self, ctx):
        return _brief("reviewer.md", guides=_guides())

    def _run_advisors(self, ctx):
        directory = ctx.run.path / _ADVISORS
        for perspective in _PERSPECTIVES:
            agent_dir = directory / perspective
            agent_dir.mkdir(parents=True, exist_ok=True)
            if not (agent_dir / "advice.md").is_file() or not (agent_dir / "advice.md").stat().st_size:
                (agent_dir / "brief.md").write_text(self._advisor_brief(ctx, perspective), encoding="utf-8")
        result = run_agents(directory, "advice.md", _PERSPECTIVES, ctx.settings.model,
                            ctx.settings.effort, tier_from_environment())
        if not result.ok:
            raise Stop(result.reason)

    def _make_packet(self, ctx):
        run = ctx.run.path
        directory = run / _PACKET
        directory.mkdir(parents=True, exist_ok=True)
        for perspective in _PERSPECTIVES:
            advice = run / _ADVISORS / perspective / "advice.md"
            if not advice.is_file() or not advice.stat().st_size:
                raise Stop("{0} has no advice, so the packet is not made".format(perspective))
        perspectives = list(_PERSPECTIVES)
        random.SystemRandom().shuffle(perspectives)
        with (directory / "key.md").open("w", encoding="utf-8", newline="") as key, \
                (directory / "packet.md").open("w", encoding="utf-8", newline="") as packet:
            packet.write("# The question\n")
            packet.write(_brief_body(run / "00-input" / "brief.md"))
            packet.write("\n")
            for index, perspective in enumerate(perspectives):
                label = "ABCDE"[index]
                key.write("{0}: {1}\n".format(label, perspective))
                packet.write("\n---\n\n# Response {0}\n\n".format(label))
                advice_path = run / _ADVISORS / perspective / "advice.md"
                text = advice_path.read_text(encoding="utf-8")
                packet.write(text)
                packet.write("\n")
                if perspective in text.lower() or perspective.replace("-", " ") in text.lower():
                    ctx.note("packet: response {0} may name its own perspective ({1}); anonymization is weaker".format(label, perspective))

    def _run_reviewers(self, ctx):
        run = ctx.run.path
        directory = run / _REVIEWERS
        packet = run / _PACKET / "packet.md"
        for number in range(1, 6):
            agent_dir = directory / str(number)
            agent_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(packet), str(agent_dir / "packet.md"))
            output = agent_dir / "review.md"
            if not output.is_file() or not output.stat().st_size:
                (agent_dir / "brief.md").write_text(self._reviewer_brief(ctx), encoding="utf-8")
        result = run_agents(directory, "review.md", [str(number) for number in range(1, 6)],
                            ctx.settings.model, ctx.settings.effort, tier_from_environment())
        if not result.ok:
            raise Stop(result.reason)

    def steps(self, ctx):
        return [
            Step(1, "Conselheiros", self._run_advisors),
            Step(2, "Pacote anónimo", self._make_packet),
            Step(3, "Revisores", self._run_reviewers),
        ]

    def _ready(self, ctx):
        run = ctx.run.path
        print("READY\nAdvice: {0}/01-advisors/<perspective>/advice.md\nKey: {0}/02-packet/key.md\nReviews: {0}/03-review/<n>/review.md".format(run))

    def final_step(self, ctx):
        return Step("ready", "READY", self._ready)

    def after_step(self, ctx, step):
        marker = {1: "advisors", 2: "packet", 3: "review"}[step.number]
        (ctx.run.path / (".done-" + marker)).touch()

    def board(self, ctx):
        run = ctx.run.path
        status = (run / "status.log").read_text(encoding="utf-8")
        result = render_steps(run, [
            "advisors|Conselheiros|01-advisors|{0}|advice.md".format(" ".join(_PERSPECTIVES)),
            "packet|Pacote anónimo|02-packet||",
            "review|Revisores|03-review|1 2 3 4 5|review.md",
        ], title="Conselho")
        running = None
        for line in status.splitlines():
            event = line.split("\t", 1)[-1]
            if event == "resume" or event.startswith("done step ") or event.startswith("STOPPED at step "):
                running = None
            elif event.startswith("start step "):
                try:
                    running = int(event.split(" ", 3)[2].rstrip(":"))
                except ValueError:
                    running = None
        active = {1: ("Conselheiros", _PERSPECTIVES),
                  2: ("Pacote anónimo", ()),
                  3: ("Revisores", tuple(str(number) for number in range(1, 6)))}
        if running in active:
            label, agents = active[running]
            if not (run / (".done-S{0}".format(running))).exists():
                result = result.replace("○ {0}\n".format(label), "◐ {0}\n".format(label), 1)
                for agent in agents:
                    result = result.replace("    ○ {0}\n".format(agent), "    ◐ {0}\n".format(agent), 1)
        for number, label in ((1, "Conselheiros"), (2, "Pacote anónimo"), (3, "Revisores")):
            if "STOPPED at step {0}:".format(number) in status:
                result = result.replace("○ {0}\n".format(label), "✗ {0}\n".format(label), 1)
        return result

    def ready_path(self, ctx):
        return str(ctx.run.path / ".done-review")

    def finish(self, ctx):
        run = ctx.run.path
        report = run / "report.md"
        if not report.is_file() or not report.stat().st_size:
            raise RunError("there is no report in this run: nothing to keep")
        keep_record(run, ctx.run.repo, "councils", ctx.run.name, exclusions=(
            "*.events.jsonl", "*.stderr.log", "*.last-message.md", ".*", "settings", "status.log", "repo", "pause",
        ))

    def commands(self):
        return {"check": self._check_command}

    def _check_command(self, args):
        model = effort = None
        index = 0
        while index < len(args) and args[index] in ("-m", "-e"):
            if index + 1 >= len(args):
                raise RunError("usage: check [-m model] [-e effort] <name> <report.md>")
            if args[index] == "-m":
                model = args[index + 1]
            else:
                effort = args[index + 1]
            index += 2
        rest = args[index:]
        if len(rest) != 2:
            raise RunError("usage: check [-m model] [-e effort] <name> <report.md>")
        name, report_path = rest
        if not valid_name(name):
            raise RunError("bad run name: {0}".format(name))
        if not os.path.isfile(report_path) or os.path.getsize(report_path) == 0:
            raise RunError("missing or empty report: {0}".format(report_path))
        root = _root(self)
        run = RunDir.load(root, name)
        if not run.is_done("review"):
            raise RunError("the council has not reached READY")
        require_backend()
        settings = run.settings
        model = model or settings.model
        effort = effort or settings.effort
        try:
            with acquire(run.path, "harness"):
                return self._check(run, report_path, model, effort)
        except RunError:
            raise

    def _check(self, run, report_path, model, effort):
        round_root = run.path / "04-check" / "rounds"
        round_root.mkdir(parents=True, exist_ok=True)
        for path in round_root.iterdir():
            if path.is_dir() and not (path / "problems.md").is_file():
                shutil.rmtree(str(path))
        rounds = sorted((int(path.name) for path in round_root.iterdir()
                         if path.is_dir() and path.name.isdigit()))
        number = (rounds[-1] if rounds else 0) + 1
        round_dir = round_root / str(number)
        review_dir = round_dir / "review"
        review_dir.mkdir(parents=True)
        shutil.copyfile(report_path, str(run.path / "report.md"))
        shutil.copyfile(report_path, str(review_dir / "report.md"))
        shutil.copyfile(str(run.path / "00-input" / "brief.md"), str(review_dir / "question.md"))
        shutil.copyfile(str(run.path / _PACKET / "key.md"), str(review_dir / "key.md"))
        for perspective in _PERSPECTIVES:
            shutil.copyfile(str(run.path / _ADVISORS / perspective / "advice.md"),
                            str(review_dir / ("advice-" + perspective + ".md")))
        for reviewer in range(1, 6):
            shutil.copyfile(str(run.path / _REVIEWERS / str(reviewer) / "review.md"),
                            str(review_dir / ("review-{0}.md".format(reviewer))))
        previous = round_root / str(number - 1) / "problems.md" if number > 1 else None
        if previous is not None and previous.is_file():
            shutil.copyfile(str(previous), str(review_dir / "previous-problems.md"))
        brief = _brief("completeness.md", guides=_guides())
        (round_dir / "review-brief.md").write_text(brief, encoding="utf-8")
        min_checked = _env_int("COUNCIL_MIN_CHECKED", 3)
        previous_text = previous.read_text(encoding="utf-8") if previous is not None and previous.is_file() else ""

        def build_prompt(attempt):
            parts = [brief]
            if previous_text:
                parts.append("\n" + _brief("completeness-previous.md"))
            parts.append("\n---\n" + _brief("completeness-instructions.md"))
            if attempt > 1:
                parts.append(_brief("completeness-retry.md"))
            return "".join(parts)

        result = run_review(run, "council check", review_dir, round_dir, build_prompt,
                            model, effort, tier_from_environment(), min_checked,
                            previous_problems=previous_text)
        if result.verdict is None:
            print(result.reason, file=sys.stderr)
            return 1
        verdict = result.verdict
        max_rounds = _env_int("COUNCIL_MAX_ROUNDS", 3)
        if verdict == "back" and number >= max_rounds:
            verdict = "escalate"
            run.note("check: round cap {0} reached".format(max_rounds))
            (round_dir / "verdict").write_text("escalate\n", encoding="utf-8")
        run.note("check round {0} ({1} {2}): {3}".format(number, model, effort, verdict))
        print("Completeness check, round {0}: {1}\nProblems: {2}/problems.md".format(
            number, verdict, round_dir
        ))
        return {"pass": 0, "back": 1, "escalate": 2}[verdict]


WORKFLOW = CouncilWorkflow()

"""Review a pinned repository diff against standards and an optional spec."""
import os
import shutil
import subprocess
from pathlib import Path

from harness.engine.backend import require_backend
from harness.engine.agentstep import run_agents, tier_from_environment
from harness.engine.record import keep_record
from harness.engine.run import RunError
from harness.engine.stepboard import render_steps
from harness.engine.workflow import Step, Stop, Workflow
from harness import agent
from harness.gate import run_gate


def _repository():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, universal_newlines=True, check=False,
    )
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def _git_diff(repo, args):
    return subprocess.run(
        ["git", "-C", os.fspath(repo), "diff"] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, cwd=os.fspath(repo),
    )


def _pin_diff(repo, target):
    if target == "working-tree":
        tracked = _git_diff(repo, ["HEAD"])
        if tracked.returncode != 0:
            raise RunError("git diff HEAD failed: check the repository")
        chunks = [tracked.stdout]
        untracked = subprocess.run(
            ["git", "-C", os.fspath(repo), "ls-files", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        if untracked.returncode != 0:
            raise RunError("could not list untracked files in the repository")
        for raw_path in untracked.stdout.splitlines():
            path = raw_path.decode("utf-8", errors="surrogateescape")
            result = _git_diff(repo, ["--no-index", "--", "/dev/null", path])
            if result.returncode not in (0, 1):
                raise RunError("could not include untracked file in the diff: {0}".format(path))
            chunks.append(result.stdout)
        diff = b"".join(chunks)
    else:
        result = _git_diff(repo, [target])
        if result.returncode != 0:
            raise RunError("git diff {0} failed: check that the refs resolve".format(target))
        diff = result.stdout
    if not diff:
        raise RunError("the diff for {0} is empty".format(target))
    commits = ""
    if target != "working-tree":
        result = subprocess.run(
            ["git", "-C", os.fspath(repo), "log", "--oneline", target],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
            check=False,
        )
        if result.returncode == 0:
            commits = result.stdout
    return diff, commits


def _guides():
    return os.environ.get("REVIEW_GUIDES") or str(Path(__file__).resolve().parents[1] / "roles")


class ReviewWorkflow(Workflow):
    name = "review"
    command = "review-run.sh"
    usage_start = "usage: start [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... [-g command]... <name> <target>"
    repo_hint = "run start inside the repository under review"

    def __init__(self):
        self._start_data = None

    def _parse_start(self, args):
        spec = ""
        standards = []
        gates = []
        second = False
        positional = []
        index = 0
        while index < len(args):
            value = args[index]
            if value == "-2":
                second = True
                index += 1
            elif value in ("-s", "-d", "-g"):
                if index + 1 >= len(args):
                    raise RunError(self.usage_start)
                option_value = args[index + 1]
                if value == "-s":
                    spec = option_value
                elif value == "-d":
                    standards.append(option_value)
                else:
                    gates.append(option_value)
                index += 2
            elif value.startswith("-"):
                raise RunError(self.usage_start)
            else:
                positional.append(value)
                index += 1
        if len(positional) != 1:
            raise RunError(self.usage_start)
        return spec, standards, gates, second, positional[0]

    def validate_start(self, args):
        spec, standards, gates, second, target = self._parse_start(args)
        if spec and (not os.path.isfile(spec) or os.path.getsize(spec) == 0):
            raise RunError("missing or empty spec: {0}".format(spec))
        for path in standards:
            if not os.path.isfile(path) or os.path.getsize(path) == 0:
                raise RunError("missing or empty standards file: {0}".format(path))
        if not spec and not standards:
            raise RunError("no criteria: give a spec (-s), standards (-d), or both")
        require_backend()
        repo = _repository()
        if repo is None:
            raise RunError(self.repo_hint)
        guides = _guides()
        if not os.path.isdir(guides):
            raise RunError("no role guides at {0} (set REVIEW_GUIDES)".format(guides))
        diff, commits = _pin_diff(repo, target)
        self._start_data = {
            "spec": spec, "standards": standards, "gates": gates,
            "second": second, "target": target, "repo": Path(repo),
            "guides": guides, "diff": diff, "commits": commits,
        }

    def start(self, ctx, args):
        if self._start_data is None:
            self.validate_start(args)
        data = self._start_data
        run = ctx.run.path
        inputs = run / "00-input"
        inputs.mkdir(parents=True, exist_ok=True)
        (inputs / "diff.patch").write_bytes(data["diff"])
        (inputs / "target").write_text(data["target"] + "\n", encoding="utf-8")
        if data["commits"]:
            (inputs / "commits.txt").write_text(data["commits"], encoding="utf-8")
        if data["spec"]:
            shutil.copyfile(data["spec"], str(inputs / "spec.md"))
        if data["standards"]:
            standards_dir = inputs / "standards"
            standards_dir.mkdir()
            for path in data["standards"]:
                shutil.copyfile(path, str(standards_dir / os.path.basename(path)))
        (run / "repo").write_text(str(data["repo"]) + "\n", encoding="utf-8")
        (run / "second").write_text("{0}\n".format(int(data["second"])), encoding="utf-8")
        ctx.note("start {0} ({1} {2}, target {3}, second reviewer {4})".format(
            ctx.run.name, ctx.settings.model, ctx.settings.effort, data["target"],
            int(data["second"]),
        ))
        notes = []
        if data["gates"]:
            head = subprocess.run(
                ["git", "-C", str(data["repo"]), "rev-parse", "--short", "HEAD"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
                check=False,
            ).stdout.strip() or "unknown"
            notes.append("Gate target: HEAD {0} of the repository.".format(head))
            if data["target"] != "working-tree":
                notes.append("The target is a revision range, so the commands ran in the current checkout, which may not be the target.")
        ctx.note("gate: {0} commands".format(len(data["gates"])))
        run_gate(
            str(data["repo"]), os.environ.get("REVIEW_GATE_TIMEOUT", "900"),
            str(inputs), data["gates"], notes,
        )
        self._start_data = None

    def _axes(self, ctx):
        inputs = ctx.run.path / "00-input"
        result = []
        if (inputs / "standards").is_dir():
            result.append("standards")
        if (inputs / "spec.md").is_file() and (inputs / "spec.md").stat().st_size:
            result.append("spec")
        return result

    def _axis_title(self, axis):
        return {"standards": "Standards", "spec": "Spec"}[axis]

    def _axis_brief(self, ctx, axis):
        run = ctx.run.path
        repo = ctx.run.repo
        guides = _guides()
        lines = [
            "# Brief: {0} review\n\n## What to review\nThe diff is `diff.patch` in the current directory (read-only)".format(self._axis_title(axis)),
        ]
        if (run / "00-input" / "commits.txt").is_file():
            lines.append(", and the commits in `commits.txt`")
        lines.append(".\n\n## Gate\nThe script ran the repository's own checks before you started: their commands, output and exit codes are in `gate.md` here (read-only). Take them as given.\n")
        if axis == "standards":
            lines.append("\n## Criteria\nThe documented standards are the files in `standards/` here (read-only).\n")
        else:
            lines.append("\n## Criteria\nThe originating spec is `spec.md` here (read-only).\n")
        lines.append("\n## The repository\nIt is at {0}. Open it read-only to see the code around the diff. Change nothing in it.\n".format(repo))
        lines.append("\n## Role\nOpen and follow the role guide: {0}/code-review-axis.md (read-only), the section \"{1}\". You are not the author of the change.\n".format(guides, self._axis_title(axis)))
        lines.append("\n## Rules\n- Write your report to report.md in the current directory. Write nothing else.\n- Open only files in the current directory, the repository and the role guide. Other folders under the run folder are not for you.\n- Do not run git commands that change state.\n")
        return "".join(lines)

    def _check_brief(self, ctx, axis):
        title = self._axis_title(axis)
        guides = _guides()
        lines = ["# Brief: check of the {0} findings\n\n## Inputs (read-only, in the current directory)\n- diff.patch: the diff under review\n".format(title)]
        lines.append("- standards/: the documented standards\n" if axis == "standards" else "- spec.md: the originating spec\n")
        lines.append("- gate.md: the repository's own checks, run by the script before the review\n- reports/: the findings of the reviewer(s) of this axis\n")
        lines.append("\n## The repository\nIt is at {0}. Open it read-only to see the code around a hunk. Change nothing in it.\n".format(ctx.run.repo))
        lines.append("\n## Role\nOpen and follow the role guide: {0}/code-review-check.md (read-only). You are not the author of the findings.\n".format(guides))
        lines.append("\n## Rules\n- Write your result to checked.md in the current directory. Write nothing else.\n- Open only files in the current directory, the repository and the role guide.\n- Do not run git commands that change state.\n")
        return "".join(lines)

    def _prepare_review(self, ctx):
        run = ctx.run.path
        review_dir = run / "01-review"
        inputs = run / "00-input"
        for axis in self._axes(ctx):
            names = [axis]
            if (run / "second").read_text(encoding="utf-8").strip() == "1":
                names.append(axis + "-2")
            for name in names:
                directory = review_dir / name
                directory.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(inputs / "diff.patch"), str(directory / "diff.patch"))
                shutil.copyfile(str(inputs / "gate.md"), str(directory / "gate.md"))
                commits = inputs / "commits.txt"
                if commits.is_file() and commits.stat().st_size:
                    shutil.copyfile(str(commits), str(directory / "commits.txt"))
                if axis == "standards":
                    shutil.rmtree(str(directory / "standards"), ignore_errors=True)
                    shutil.copytree(str(inputs / "standards"), str(directory / "standards"))
                else:
                    shutil.copyfile(str(inputs / "spec.md"), str(directory / "spec.md"))
                if not (directory / "report.md").is_file() or not (directory / "report.md").stat().st_size:
                    (directory / "brief.md").write_text(self._axis_brief(ctx, axis), encoding="utf-8")

    def _run_review_axis(self, ctx, axis):
        run = ctx.run.path
        names = [axis]
        if (run / "second").read_text(encoding="utf-8").strip() == "1":
            names.append(axis + "-2")
        result = run_agents(
            run / "01-review", "report.md", names, ctx.settings.model,
            ctx.settings.effort, tier_from_environment(),
        )
        if not result.ok:
            for name in names:
                output = run / "01-review" / name / "report.md"
                if not output.is_file() or not output.stat().st_size:
                    (run / "01-review" / name / "failed").write_text(result.reason + "\n", encoding="utf-8")
            backend = agent.get_backend(None)
            if backend is not None:
                for name in names:
                    events = run / "01-review" / name / "run.events.jsonl"
                    quota = backend().quota_text(str(events))
                    if quota is not None:
                        quota = quota.rstrip("\r\n")
                        ctx.run.note("QUOTA: {0}".format(quota))
                        raise Stop("{0}: usage limit reached. QUOTA: {1} (see {2})".format(
                            name, quota, events
                        ))
            raise Stop(result.reason)

    def _run_check_axis(self, ctx, axis):
        run = ctx.run.path
        source = run / "00-input"
        directory = run / "02-check" / axis
        (directory / "reports").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source / "diff.patch"), str(directory / "diff.patch"))
        shutil.copyfile(str(source / "gate.md"), str(directory / "gate.md"))
        if axis == "standards":
            shutil.rmtree(str(directory / "standards"), ignore_errors=True)
            shutil.copytree(str(source / "standards"), str(directory / "standards"))
        else:
            shutil.copyfile(str(source / "spec.md"), str(directory / "spec.md"))
        shutil.copyfile(str(run / "01-review" / axis / "report.md"), str(directory / "reports" / "reviewer-1.md"))
        if (run / "second").read_text(encoding="utf-8").strip() == "1":
            shutil.copyfile(str(run / "01-review" / (axis + "-2") / "report.md"), str(directory / "reports" / "reviewer-2.md"))
        if not (directory / "checked.md").is_file() or not (directory / "checked.md").stat().st_size:
            (directory / "brief.md").write_text(self._check_brief(ctx, axis), encoding="utf-8")

    def _run_check(self, ctx):
        ctx.run.note("start S2 check")
        ctx.progress("check · início")
        for axis in self._axes(ctx):
            self._run_check_axis(ctx, axis)
        result = run_agents(
            ctx.run.path / "02-check", "checked.md", self._axes(ctx),
            ctx.settings.model, ctx.settings.effort, tier_from_environment(),
        )
        if not result.ok:
            for axis in self._axes(ctx):
                output = ctx.run.path / "02-check" / axis / "checked.md"
                if not output.is_file() or not output.stat().st_size:
                    (ctx.run.path / "02-check" / axis / "failed").write_text(result.reason + "\n", encoding="utf-8")
            raise Stop(result.reason)
        ctx.run.note("done S2 check")

    def steps(self, ctx):
        run = ctx.run.path
        if ctx.run.is_done("S1") and any(
            not (run / "01-review" / name / "report.md").is_file()
            or not (run / "01-review" / name / "report.md").stat().st_size
            for axis in self._axes(ctx)
            for name in ([axis, axis + "-2"] if (run / "second").read_text(encoding="utf-8").strip() == "1" else [axis])
        ):
            (run / ".done-S1").unlink()
            (run / ".done-S2").unlink(missing_ok=True)
        if ctx.run.is_done("S2") and any(
            not (run / "02-check" / axis / "checked.md").is_file()
            or not (run / "02-check" / axis / "checked.md").stat().st_size
            for axis in self._axes(ctx)
        ):
            (run / ".done-S2").unlink()
        if not (run / "report.md").is_file() or not (run / "report.md").stat().st_size:
            (run / ".done-report").unlink(missing_ok=True)

        def review(ctx):
            ctx.run.note("start S1 review")
            ctx.progress("review · início")
            self._prepare_review(ctx)
            axes = self._axes(ctx)
            if len(axes) == 2:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(self._run_review_axis, ctx, axis) for axis in axes]
                    for future in futures:
                        future.result()
            elif axes:
                self._run_review_axis(ctx, axes[0])
            ctx.run.note("done S1 review")

        def run_check(ctx):
            try:
                self._run_check(ctx)
            except Stop as stopped:
                ctx.run.note("STOPPED at S2: {0}".format(stopped.reason))
                raise

        return [Step(1, "Revisores", review), Step(2, "Verificação", run_check)]

    def _write_report(self, ctx):
        run = ctx.run.path
        output = [
            "# Code review\n\nTarget: {0}\n\n".format((run / "00-input" / "target").read_text(encoding="utf-8").rstrip("\n")),
            "> The checkers confirm the findings below against the diff. They do not show what the reviewers missed: a clean axis is not a clean diff.\n\n",
            "## Gate\n\n",
        ]
        gate = (run / "00-input" / "gate.md").read_text(encoding="utf-8").splitlines(keepends=True)
        output.extend(line.replace("### ", "#### ", 1) if line.startswith("### ") else line for line in gate[2:])
        output.append("\n")
        for axis in ("standards", "spec"):
            output.append("## {0}\n\n".format(self._axis_title(axis)))
            checked = run / "02-check" / axis / "checked.md"
            if checked.is_file() and checked.stat().st_size:
                output.append(checked.read_text(encoding="utf-8"))
            elif axis == "standards":
                output.append("Not run: no standards sources were given.\n")
            else:
                output.append("Not run: no spec available.\n")
            output.append("\n")
        with (run / "report.md").open("w", encoding="utf-8", newline="") as report:
            report.write("".join(output))

    def final_step(self, ctx):
        return Step("report", "Report", self._write_report)

    def board(self, ctx):
        run = ctx.run.path
        review_agents = []
        check_agents = []
        for axis in self._axes(ctx):
            review_agents.append(axis)
            if (run / "second").is_file() and (run / "second").read_text(encoding="utf-8").strip() == "1":
                review_agents.append(axis + "-2")
            check_agents.append(axis)
        result = render_steps(run, [
            "S1|Revisores|01-review|{0}|report.md".format(" ".join(review_agents)),
            "S2|Verificação|02-check|{0}|checked.md".format(" ".join(check_agents)),
        ], title="Revisão")
        stopped = ""
        for line in (run / "status.log").read_text(encoding="utf-8").splitlines():
            event = line.split("\t", 1)[-1]
            if event == "resume":
                stopped = ""
            elif event.startswith("STOPPED at step 1:"):
                stopped = "Revisores"
            elif event.startswith("STOPPED at step 2:"):
                stopped = "Verificação"
        if stopped:
            result = result.replace("○ {0}\n".format(stopped), "✗ {0}\n".format(stopped), 1)
        return result

    def after_step(self, ctx, step):
        marker = ".done-review" if step.number == 1 else ".done-check"
        (ctx.run.path / marker).touch()

    def full_board(self, ctx):
        return self.board(ctx)

    def ready_path(self, ctx):
        return str(ctx.run.path / "report.md")

    def finish(self, ctx):
        report = ctx.run.path / "report.md"
        if not report.is_file() or not report.stat().st_size:
            raise RunError("there is no report in this run: nothing to keep")
        current = _repository()
        if current is None or Path(current).resolve() != Path(ctx.run.repo).resolve():
            raise RunError("run finish inside the reviewed repository: {0}".format(ctx.run.repo))
        keep_record(ctx.run.path, ctx.run.repo, "reviews", ctx.run.name, exclusions=(
            "*.events.jsonl", "*.stderr.log", "*.last-message.md", ".*", "repo", "second",
            "settings", "status.log", "pause",
        ))


WORKFLOW = ReviewWorkflow()

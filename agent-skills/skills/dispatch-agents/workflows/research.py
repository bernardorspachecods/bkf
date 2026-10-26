"""Research workflow: map sources, collect evidence, review a digest and delivery."""
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from harness.engine.agentstep import run_agent_step
from harness.engine.phase import join_phase, run_phase
from harness.engine.record import RecordError, keep_record
from harness.engine.review import run_review
from harness.engine.run import RunError, valid_name
from harness.engine.stepboard import render_steps
from harness.engine.workflow import Context, Step, Stop, Workflow


def _limits():
    try:
        rounds = int(os.environ.get("RESEARCH_MAX_ROUNDS", "3"))
        checked = int(os.environ.get("RESEARCH_MIN_CHECKED", "3"))
    except ValueError as error:
        raise RunError("research round limits must be integers") from error
    return rounds, checked


def _guides(repo):
    return os.environ.get("RESEARCH_GUIDES") or str(
        Path(repo) / "agent-skills" / "skills" / "research" / "roles"
    )


def _objective_body(path):
    with open(str(path), "r", encoding="utf-8", newline="") as source:
        return "".join(line for line in source if not line.startswith("# "))


def _niche_numbers(path):
    numbers = []
    with open(str(path), "r", encoding="utf-8") as source:
        for line in source:
            match = re.match(r"^([0-9]+)\. ", line)
            if match:
                numbers.append(int(match.group(1)))
    return numbers


def _niche_lines(path, selected):
    with open(str(path), "r", encoding="utf-8") as source:
        return [line for line in source if re.match(r"^[0-9]+\. ", line)
                and int(line.split(".", 1)[0]) in selected]


def _write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="") as output:
        output.write(text)


def _copy(source, destination):
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source), str(destination))


def _archive(path):
    path = Path(path)
    if not path.exists():
        return
    epoch = int(time.time())
    target = Path(str(path) + ".attempt-" + str(epoch))
    while target.exists():
        epoch += 1
        target = Path(str(path) + ".attempt-" + str(epoch))
    path.rename(target)


def _numbered_rounds(path):
    try:
        return sorted((child for child in Path(path).iterdir()
                       if child.is_dir() and child.name.isdigit()), key=lambda child: int(child.name))
    except OSError:
        return []


class ResearchWorkflow(Workflow):
    name = "research"
    command = "research-run.sh"
    usage_start = "usage: start [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>"
    repo_hint = "run start inside the repository the research goes to"

    def validate_start(self, args):
        if len(args) != 3:
            raise RunError(self.usage_start)
        for path in args:
            if not os.path.isfile(path) or os.path.getsize(path) == 0:
                raise RunError("missing or empty input: {0}".format(path))
        if shutil.which("codex") is None:
            raise RunError("codex not found")
        guides = _guides(Path(__file__).resolve().parents[4])
        if not os.path.isdir(guides):
            raise RunError("no role guides at {0} (set RESEARCH_GUIDES)".format(guides))
        _limits()

    def start(self, ctx, args):
        ctx.progress = lambda text: self._progress(ctx, text)
        inputs = ctx.run.path / "00-input"
        inputs.mkdir(parents=True, exist_ok=True)
        for source, name in zip(args, ("objective.md", "sourcemap.md", "collectors.txt")):
            _copy(source, inputs / name)
        ctx.note("start {0} ({1} {2}, max {3} rounds)".format(
            ctx.run.name, ctx.settings.model, ctx.settings.effort, _limits()[0]
        ))

    def _progress(self, ctx, text):
        match = re.fullmatch(r"S([123]) (map|collection|digest)", text)
        if match:
            text = match.group(2) + " · início"
        else:
            match = re.fullmatch(r"S([123]) concluído", text)
            if match:
                text = {"1": "map", "2": "collection", "3": "digest"}[match.group(1)] + " · concluído"
            else:
                match = re.fullmatch(r"S([123]) parou", text)
                if match:
                    text = {"1": "map", "2": "collection", "3": "digest"}[match.group(1)] + " · parou"
        print("[research] {0}\n".format(text), file=sys.stderr)
        ctx.print_board(sys.stderr)

    def _brief_collector(self, ctx, name, niches):
        return (
            "# Brief: collection (collector {0})\n\n## Objective\n{1}\n"
            "\n## Where to look\nThese are your niches. Another collector covers the rest, so stay inside these. "
            "\"Counterweight\" means look here for evidence against the common view; \"(agent)\" only says who suggested the niche and does not change what you do.\n\n{2}"
            "\n## Role\nOpen and follow the role guide: {3}/research-collection.md (read-only). It says how to collect, what to record and when to stop. The objective above is the filter for what is relevant.\n"
            "\n## Rules\n- You need web access to open sources. If you cannot open web pages at all, stop and say so in your output; do not fill in from memory.\n"
            "- Do not run git commands that change state, and do not edit any file other than your output file.\n"
        ).format(name, _objective_body(ctx.run.path / "00-input" / "objective.md"), "".join(niches), _guides(ctx.repo))

    def _brief_collection_review(self, ctx, name, niches):
        return (
            "# Brief: review of the collection (collector {0})\n\n## Objective\n{1}\n"
            "\n## Map of sources for the collector you review\nThese are the niches the collector was told to search. \"(agent)\" marks niches a cheap agent added to the map. \"Counterweight\" marks niches where evidence against the common view was to be sought.\n\n{2}"
            "\n## Role\nOpen and follow the role guide: {3}/research-review-collection.md (read-only). You are not the author of the collected file. Do not reopen the sources to check whether findings are true; check the four questions against the objective.\n"
        ).format(name, _objective_body(ctx.run.path / "00-input" / "objective.md"), "".join(niches), _guides(ctx.repo))

    def _brief_digest(self, ctx):
        run = ctx.run.path
        return (
            "# Brief: digest\n\n## Objective\n{0}\n"
            "\n## Inputs (read-only)\n- The collected sources, joined in one file, one heading per collector: {1}\n"
            "- The notes of the reviews of the collection: {2}\n  They record limits the reviewers accepted; carry them into the weak points.\n"
            "\n## Role\nOpen and follow the role guide: {3}/research-digest.md (read-only). You do not search for new sources.\n"
        ).format(_objective_body(run / "00-input" / "objective.md"), run / "02-collection" / "joined.md",
                 run / "02-collection" / "review-notes.md", _guides(ctx.repo))

    def _brief_digest_review(self, ctx):
        run = ctx.run.path
        return (
            "# Brief: review of the digest\n\n## Objective\n{0}\n"
            "\n## Inputs (read-only)\n- The collected sources, joined in one file: {1}\n\n"
            "## Role\nOpen and follow the role guide: {2}/research-review-digest.md (read-only). You are not the author of the digest. You do not search for new sources.\n"
        ).format(_objective_body(run / "00-input" / "objective.md"), run / "02-collection" / "joined.md", _guides(ctx.repo))

    def _map(self, ctx):
        run = ctx.run.path
        source_map = run / "00-input" / "sourcemap.md"
        numbers = _niche_numbers(source_map)
        if not numbers:
            raise Stop("sourcemap.md has no numbered niche lines")
        directory = run / "01-map"
        directory.mkdir(parents=True, exist_ok=True)
        prompt = (
            "# Brief: complete the source map\n\n## Objective\n{0}\n\n"
            "## Input\nThe list so far (read-only): {1}\n\n"
            "## Task\nComplete the list with more niches and example sites where the objective's question can be answered, without collecting findings. Bring counterweight: independent voices, critics, people who use the thing, issue trackers, since the list leans toward those who speak for themselves. Limit additions to what serves the priorities in the objective, or the list grows without end. Judge a source by the question it answers, not by type of site; leave out copies and derived content and point to origins. Do a few web searches only to check that a niche exists; do not read pages in depth.\n"
            "\n---\nWrite only the new niches to additions.md in the current directory, one niche per line, numbered continuing from {2}, in the style of the list: a bold name, example sites, why it serves the objective, \"Counterweight.\" where it applies, and ending with \"(agent)\". No other text, no headings.\n"
        ).format(_objective_body(run / "00-input" / "objective.md"), source_map, max(numbers) + 1)
        _write(directory / "prompt.md", prompt)
        (directory / "work").mkdir(parents=True, exist_ok=True)
        step = run_agent_step(ctx.run, "map", str(directory / "work"), str(directory / "prompt.md"),
                              str(directory / "run"), ctx.settings.model, ctx.settings.effort,
                              "workspace-write", None, "map agent exit=<exit> (see {0}/run.stderr.log)".format(directory),
                              web=True)
        if not step.ok:
            raise Stop(step.reason)
        additions = directory / "work" / "additions.md"
        if not additions.is_file() or not additions.stat().st_size:
            raise Stop("map agent wrote no additions.md")
        new_numbers = _niche_numbers(additions)
        if any(number <= max(numbers) for number in new_numbers):
            raise Stop("additions.md reuses niche numbers up to {0}".format(max(numbers)))
        if not new_numbers:
            raise Stop("additions.md has no numbered niche lines")
        original = source_map.read_text(encoding="utf-8")
        added_lines = [line for line in additions.read_text(encoding="utf-8").splitlines(True)
                       if re.match(r"^[0-9]+\. ", line)]
        final_map = directory / "sourcemap.md"
        _write(final_map, original + "\n" + "".join(added_lines))
        ctx.note("map: {0} niche(s) added by the agent".format(len(new_numbers)))

    def _collection(self, ctx):
        run = ctx.run.path
        original_max = max(_niche_numbers(run / "00-input" / "sourcemap.md"))
        source_map = run / "01-map" / "sourcemap.md"
        collectors = []
        for line in (run / "00-input" / "collectors.txt").read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            name, separator, raw = line.partition(":")
            name, raw = name.strip(), raw.strip().replace(" ", "")
            if not valid_name(name):
                raise Stop("bad collector name in collectors.txt: {0}".format(name))
            if not separator or not re.fullmatch(r"[0-9]+(,[0-9]+)*", raw):
                raise Stop("bad niche list for {0} in collectors.txt: {1}".format(name, raw))
            collectors.append((name, [int(value) for value in raw.split(",")]))
        if not collectors:
            raise Stop("collectors.txt has no collector")
        for niche in _niche_numbers(run / "00-input" / "sourcemap.md"):
            if not any(niche in assigned for _, assigned in collectors):
                raise Stop("niche {0} is not assigned to any collector".format(niche))
        additions = sorted(number for number in _niche_numbers(source_map) if number > original_max)
        for index, number in enumerate(additions):
            collectors[index % len(collectors)][1].append(number)
        briefs = run / ".briefs" / "collection"
        if briefs.exists():
            shutil.rmtree(str(briefs))
        briefs.mkdir(parents=True)
        agents = []
        for name, assigned in collectors:
            niches = _niche_lines(source_map, set(assigned))
            agent_brief = briefs / (name + "-brief.md")
            review_brief = briefs / (name + "-review.md")
            _write(agent_brief, self._brief_collector(ctx, name, niches))
            _write(review_brief, self._brief_collection_review(ctx, name, niches))
            agents.append((name, str(agent_brief), str(review_brief)))
        phase = run / "02-collection"
        result_holder = []

        def collect():
            try:
                result_holder.append(run_phase(
                    ctx.run, phase, agents, ctx.settings.model, ctx.settings.effort,
                    outfile="sources.md", max_rounds=_limits()[0], min_checked=_limits()[1], web=True
                ))
            except Exception as error:
                result_holder.append(error)

        worker = threading.Thread(target=collect)
        worker.start()
        niches = _niche_numbers(source_map)
        reported = set()

        def report_finished_niches():
            for niche in niches:
                assigned_names = [name for name, assigned in collectors if niche in assigned]
                if not assigned_names or niche in reported:
                    continue
                statuses = []
                for name in assigned_names:
                    status_path = phase / name / "status"
                    statuses.append(status_path.read_text(encoding="utf-8").strip()
                                    if status_path.is_file() else "")
                if all(status == "passed" for status in statuses):
                    ctx.progress("collection · nicho {0} · concluído".format(niche))
                    reported.add(niche)

        while worker.is_alive():
            report_finished_niches()
            worker.join(0.05)
        worker.join()
        report_finished_niches()
        result = result_holder[0]
        if isinstance(result, Exception):
            raise result
        self._phase_summary(ctx, "02-collection")
        if not result.ok:
            raise Stop("collection did not pass for every collector: {0}".format(result.reason))
        join_phase(phase)
        notes = []
        for name, _ in collectors:
            for round_path in _numbered_rounds(phase / name / "rounds"):
                problems = round_path / "problems.md"
                if problems.is_file():
                    notes.append("# Review of {0}, round {1}\n\n{2}\n\n".format(
                        name, round_path.name, problems.read_text(encoding="utf-8")))
        _write(phase / "review-notes.md", "".join(notes))

    def _digest(self, ctx):
        run = ctx.run.path
        briefs = run / ".briefs" / "digest"
        briefs.mkdir(parents=True, exist_ok=True)
        _write(briefs / "brief.md", self._brief_digest(ctx))
        _write(briefs / "review.md", self._brief_digest_review(ctx))
        result = run_phase(ctx.run, run / "03-digest", [
            ("digest", str(briefs / "brief.md"), str(briefs / "review.md"))
        ], ctx.settings.model, ctx.settings.effort, outfile="digest.md",
           max_rounds=_limits()[0], min_checked=_limits()[1])
        self._phase_summary(ctx, "03-digest")
        if not result.ok:
            raise Stop("digest did not pass: {0}".format(result.reason))
        _copy(run / "03-digest" / "digest" / "work" / "digest.md", run / "03-digest" / "digest.md")

    def _phase_summary(self, ctx, directory):
        path = ctx.run.path / directory
        names = path / "names"
        if not names.is_file():
            return
        rows = []
        for name in names.read_text(encoding="utf-8").splitlines():
            status = (path / name / "status").read_text(encoding="utf-8").strip()
            rows.append("{0}={1} ({2} round(s))".format(name, status, len(_numbered_rounds(path / name / "rounds"))))
        ctx.note("{0}: {1}; ".format(directory, "; ".join(rows)))

    def steps(self, ctx):
        specs = ((1, "map", "01-map", self._map), (2, "collection", "02-collection", self._collection),
                 (3, "digest", "03-digest", self._digest))
        steps = []
        for number, label, directory, action in specs:
            def runner(step_ctx, stage=label, folder=directory, function=action):
                _archive(step_ctx.run.path / folder)
                step_ctx.note("start {0} ({1} {2})".format(stage, step_ctx.settings.model, step_ctx.settings.effort))
                try:
                    function(step_ctx)
                except Stop:
                    raise
                except Exception as error:
                    raise Stop(str(error))
            steps.append(Step(number, label, runner))
        return steps

    def board(self, ctx):
        run = ctx.run.path
        agents = []
        try:
            for line in (run / "00-input" / "collectors.txt").read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.lstrip().startswith("#"):
                    agents.append(line.split(":", 1)[0].strip())
        except OSError:
            pass
        view = run / ".research-board" / run.name
        view.mkdir(parents=True, exist_ok=True)
        translated = []
        for line in (run / "status.log").read_text(encoding="utf-8").splitlines():
            if "\t" not in line:
                translated.append(line)
                continue
            stamp, event = line.split("\t", 1)
            start = re.match(r"start step ([123]): (map|collection|digest) ", event)
            done = re.match(r"done step ([123])$", event)
            stopped = re.match(r"STOPPED at step ([123]):", event)
            if start:
                event = "start {0} (".format(start.group(2))
            elif done:
                event = "done {0}".format({"1": "map", "2": "collection", "3": "digest"}[done.group(1)])
            elif stopped:
                event = "STOPPED at {0}:".format({"1": "map", "2": "collection", "3": "digest"}[stopped.group(1)])
            translated.append(stamp + "\t" + event)
        _write(view / "status.log", "\n".join(translated) + "\n")
        for folder in ("01-map", "02-collection", "03-digest"):
            link = view / folder
            if link.is_symlink() or link.exists():
                if link.is_dir() and not link.is_symlink():
                    shutil.rmtree(str(link))
                else:
                    link.unlink()
            target = run / folder
            if target.exists():
                link.symlink_to(target, target_is_directory=True)
        for source, marker in ((".done-S1", ".done-map"), (".done-S2", ".done-collection"), (".done-S3", ".done-digest")):
            target = run / source
            link = view / marker
            if link.exists() or link.is_symlink():
                link.unlink()
            if target.exists():
                link.symlink_to(target)
        return render_steps(view, [
            "map|Mapa|01-map||",
            "collection|Recolha|02-collection|{0}|work/sources.md".format(" ".join(agents)),
            "digest|Digest|03-digest||",
        ], title="Pesquisa")

    def final_step(self, ctx):
        return None

    def ready_path(self, ctx):
        return str(ctx.run.path / "03-digest" / "digest.md")

    def finish(self, ctx):
        only = os.environ.get("RESEARCH_FINISH_DELIVERY_ONLY") == "1"
        keep = os.environ.get("RESEARCH_FINISH_KEEP_ATTEMPTS") == "1"
        self._finish(ctx, [only, keep])

    def commands(self):
        return {"deliver": self._deliver}

    def _deliver(self, args):
        model, effort = None, None
        index = 0
        while index < len(args) and args[index] in ("-m", "-e"):
            if index + 1 >= len(args):
                raise RunError("usage: deliver [-m model] [-e effort] <name> <delivery.md>")
            if args[index] == "-m":
                model = args[index + 1]
            else:
                effort = args[index + 1]
            index += 2
        rest = args[index:]
        if len(rest) != 2:
            raise RunError("usage: deliver [-m model] [-e effort] <name> <delivery.md>")
        run = self._load_run(rest[0])
        saved = run.settings
        model = model or (saved.model if saved else "gpt-6-luna")
        effort = effort or (saved.effort if saved else "xhigh")
        if not Path(rest[1]).is_file() or Path(rest[1]).stat().st_size == 0:
            raise RunError("missing or empty delivery: {0}".format(rest[1]))
        digest = run.path / "03-digest" / "digest.md"
        if not digest.is_file() or not digest.stat().st_size:
            raise RunError("there is no digest yet: the run has not reached READY")
        if shutil.which("codex") is None:
            raise RunError("codex not found")
        ctx = Context(run, self)
        directory = run.path / "04-delivery-review"
        rounds = directory / "rounds"
        rounds.mkdir(parents=True, exist_ok=True)
        for round_path in list(rounds.iterdir()):
            if round_path.is_dir() and not (round_path / "problems.md").is_file():
                shutil.rmtree(str(round_path))
        existing = _numbered_rounds(rounds)
        number = max([int(path.name) for path in existing] or [0]) + 1
        round_path = rounds / str(number)
        review = round_path / "review"
        review.mkdir(parents=True)
        _copy(rest[1], run.path / "delivery.md")
        _copy(run.path / "delivery.md", review / "delivery.md")
        _copy(digest, review / "digest.md")
        previous = rounds / str(number - 1) / "problems.md"
        previous_path = None
        if number > 1 and previous.is_file():
            previous_path = previous
            _copy(previous, review / "previous-problems.md")
        objective = _objective_body(run.path / "00-input" / "objective.md")
        review_brief = (
            "# Brief: review of the delivery\n\n## Objective\n{0}\n"
            "\n## Inputs (read-only, in your working directory)\n- digest.md: the digest the delivery was written from\n- delivery.md: the delivery to review\n"
            "\n## Role\nOpen and follow the role guide: {1}/research-review-delivery.md (read-only). You are not the author of either file. Do not reopen the sources.\n"
        ).format(objective, _guides(run.repo))
        _write(round_path / "review-brief.md", review_brief)
        def prompt(attempt):
            text = review_brief
            if previous_path is not None:
                text += "\nThe cuts you listed in the previous round are in previous-problems.md; the delivery was corrected, check whether they are gone.\n"
            text += (
                "\n---\nBegin problems.md with a section headed \"## What I checked\": one line per part of the digest you went through and where you found it in the delivery. Then list what was left out or cut. Write it to problems.md. Its last line must be exactly one of:\n"
                "VERDICT: pass\nVERDICT: back\nVERDICT: escalate\nDo not edit any other file.\n"
            )
            if attempt > 1:
                text += "Your previous attempt left no usable problems.md (missing, or without a \"## What I checked\" section). Write the file this time.\n"
            return text
        result = run_review(run, "delivery", str(review), str(round_path), prompt, model, effort,
                            None, _limits()[1], str(previous_path) if previous_path else None)
        ctx = Context(run, self)
        if result.verdict is None:
            ctx.progress("delivery · parou")
            raise RunError(result.reason)
        _copy(review / "problems.md", round_path / "problems.md")
        verdict = result.verdict
        if verdict == "back" and number >= _limits()[0]:
            verdict = "escalate"
            run.note("delivery review: round cap {0} reached".format(_limits()[0]))
        _write(round_path / "verdict", verdict + "\n")
        run.note("delivery review round {0} ({1} {2}): {3}".format(number, model, effort, verdict))
        print("Review of the delivery, round {0}: {1}\nProblems: {2}".format(number, verdict, round_path / "problems.md"))
        ctx.progress("delivery · ronda {0} · {1}".format(number, {"pass": "passou", "back": "devolvida", "escalate": "escalada"}[verdict]))
        if verdict == "pass":
            return 0
        if verdict == "back":
            return 1
        ctx.progress("delivery · parou")
        return 2

    def _load_run(self, name):
        from harness.engine.run import RunDir
        root = os.environ.get("HARNESS_RUNS_DIR") or os.environ.get("RESEARCH_RUNS_DIR") or str(Path.home() / ".research-runs")
        return RunDir.load(root, name)

    def _finish(self, ctx, options):
        only, keep = options if options else (False, False)
        run = ctx.run.path
        delivery = run / "delivery.md"
        if not delivery.is_file() or not delivery.stat().st_size:
            raise RunError("there is no delivery in this run: nothing to keep")
        destination = Path(ctx.run.repo) / "records" / "research" / ctx.run.name
        if destination.exists():
            raise RunError("already exists: {0}".format(destination))
        status = run / "status.md"
        _write_summary(ctx)
        if only:
            destination.mkdir(parents=True)
            _copy(delivery, destination / "delivery.md")
            if delivery.read_bytes() != (destination / "delivery.md").read_bytes():
                raise RunError("copy to {0} does not match; nothing deleted".format(destination))
            shutil.rmtree(str(run))
            print("Kept in {0}; removed {1}".format(destination, run))
            return
        excludes = ["*.events.jsonl", "*.stderr.log", "*.last-message.md", "review", ".briefs", ".research-board",
                    ".done-*", "names", "outfile", "settings", "status", "status.log"]
        if not keep:
            excludes.append("*.attempt-*")
        try:
            keep_record(run, ctx.run.repo, "research", ctx.run.name, exclusions=excludes)
        except RecordError as error:
            raise RunError(str(error))


def _write_summary(ctx):
    run = ctx.run.path
    log = (run / "status.log").read_text(encoding="utf-8")
    events = [line.split("\t", 1)[1] for line in log.splitlines() if "\t" in line]
    rows = ["# Run summary\n\nRun: {0}\n\n| Phase | Model and effort | Result | Rounds | Notes |\n|---|---|---|---|---|\n".format(run.name)]
    for phase, directory, number in (("map", "01-map", 1), ("collection", "02-collection", 2), ("digest", "03-digest", 3)):
        matches = [event for event in events if event.startswith("start {0} (".format(phase))]
        settings = matches[-1].split("(", 1)[1].split(")", 1)[0] if matches else ""
        phase_path = run / directory
        names_file = phase_path / "names"
        rounds = "-"
        if names_file.is_file():
            items = []
            for name in names_file.read_text(encoding="utf-8").splitlines():
                items.append("{0}: {1}".format(name, len(_numbered_rounds(phase_path / name / "rounds"))))
            rounds = ", ".join(items)
        notes = ""
        if phase == "map":
            map_notes = [event[5:] for event in events if event.startswith("map: ")]
            notes = map_notes[-1] if map_notes else ""
        stopped = [event.split(":", 1)[1].strip() for event in events
                   if event.startswith("STOPPED at step {0}:".format(number))]
        if stopped:
            notes = "; ".join(([notes] if notes else []) + [
                "attempt {0} stopped: {1}".format(index, reason)
                for index, reason in enumerate(stopped, 1)
            ])
        if phase != "map":
            phase_names = names_file.read_text(encoding="utf-8").splitlines() if names_file.is_file() else []
            retries = sum(event.startswith(name + ": review attempt")
                          for event in events for name in phase_names)
            if retries:
                notes = "{0}{1}reviewer retried {2} time(s)".format(
                    notes, "; " if notes else "", retries
                )
        rows.append("| {0} | {1} | done | {2} | {3} |\n".format(directory, settings, rounds, notes))
    deliveries = [event for event in events if event.startswith("delivery review round ")]
    if deliveries:
        last = deliveries[-1]
        verdict = last.rsplit(": ", 1)[-1]
        settings = last.partition("(")[2].partition(")")[0]
        prior = []
        for event in deliveries[:-1]:
            round_number = event.partition("round ")[2].partition(" ")[0]
            prior.append("round {0}: {1}".format(round_number, event.rsplit(": ", 1)[-1]))
        notes = "; ".join(prior)
        retries = sum("delivery: review attempt" in event for event in events)
        if retries:
            notes = "{0}{1}reviewer retried {2} time(s)".format(notes, "; " if notes else "", retries)
        rows.append("| delivery review | {0} | {1} | {2} | {3} |\n".format(
            settings, verdict, len(deliveries), notes
        ))
    _write(run / "status.md", "".join(rows))


WORKFLOW = ResearchWorkflow()

"""Run or resume a parallel review phase.

    run_phase(run, phase_dir, agents, model, effort, tier=None, outfile="output.md",
              max_rounds=0, min_checked=0, backend="codex")
    join_phase(phase_dir)
    clean_phase(phase_dir)

``agents`` is an iterable of ``(name, agent_brief, review_brief)`` triples.
Each phase agent folder contains copied ``agent-brief.md`` and
``review-brief.md`` inputs. ``work/`` holds the agent's result files and
``review/`` holds snapshots of those files supplied to the reviewer, plus
``previous-problems.md`` when another round follows a back verdict.
``rounds/<n>/agent-prompt.md`` and ``rounds/<n>/review-prompt.md`` are the
exact prompts used for that round; ``rounds/<n>/problems.md`` records the
review problems, and ``rounds/<n>/verdict`` records the review decision.
Each round folder also holds the agent and reviewer execution files. The
agent folder's ``status`` records its current state (``working round N``,
``reviewing round N``, ``passed``, ``escalated`` or ``failed: <reason>``).
Prompts preserve the brief text and append the shell runner's instruction
text. At phase level, ``log.tsv`` records timestamped events,
``names`` lists the agents, ``outfile`` names their result file, and
``settings`` preserves phase configuration. When all agents pass,
``join_phase(phase_dir)`` writes ``joined.md`` with one heading and result per
agent.

The returned ``StepResult`` has ``ok``, ``reason`` and ``quota`` fields.
"""

import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from .agentstep import StepResult, run_agent_step
from .review import run_review


def _write(path, text):
    with open(str(path), "w", encoding="utf-8", newline="") as output:
        output.write(text)


def _log(phase_path, name, round_number, event):
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with (phase_path / "log.tsv").open("a", encoding="utf-8", newline="") as output:
        output.write("{0}\t{1}\t{2}\t{3}\n".format(stamp, name, round_number, event))


def _failed(run, phase_path, name, round_number, reason):
    agent_path = phase_path / name
    _write(agent_path / "status", "failed: {0}\n".format(reason))
    _log(phase_path, name, round_number, "failed: {0}".format(reason))
    run.note("{0}: {1}".format(name, reason))
    quota_match = re.search(r"QUOTA: (.*?)(?: \(see |$)", reason)
    return StepResult(False, reason, quota_match.group(1) if quota_match else None)


def _agent(run, phase_path, name, agent_brief, review_brief, model, effort, tier,
           outfile, max_rounds, min_checked, backend):
    directory = phase_path / name
    work = directory / "work"
    review = directory / "review"
    rounds = directory / "rounds"
    work.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)
    rounds.mkdir(parents=True, exist_ok=True)
    if (directory / "status").is_file() and (directory / "status").read_text(encoding="utf-8").strip() == "passed":
        return StepResult(True, "", None)

    shutil.copyfile(str(agent_brief), str(directory / "agent-brief.md"))
    shutil.copyfile(str(review_brief), str(directory / "review-brief.md"))
    previous = None
    existing = [int(path.name) for path in rounds.iterdir() if path.is_dir() and path.name.isdigit()]
    round_number = max(existing) if existing else 0
    if round_number:
        previous = rounds / str(round_number) / "problems.md"
    while True:
        round_number += 1
        round_path = rounds / str(round_number)
        round_path.mkdir(parents=True, exist_ok=True)
        _write(directory / "status", "working round {0}\n".format(round_number))
        _log(phase_path, name, round_number, "agent start")
        prompt = (directory / "agent-brief.md").read_text(encoding="utf-8")
        prompt += "\n\n---\nWrite your result to {0} in the current directory. Write nothing else.\n".format(outfile)
        if previous is not None and previous.is_file():
            prompt += ("\nA reviewer sent your file back. {0} already holds your previous round; "
                       "fix it so the problems below are gone, keeping what was fine.\n\n"
                       "Problems from the review:\n\n").format(outfile)
            prompt += previous.read_text(encoding="utf-8")
        prompt_path = round_path / "agent-prompt.md"
        _write(prompt_path, prompt)
        step = run_agent_step(
            run, name, str(work), str(prompt_path), str(round_path / "agent"),
            model, effort, "workspace-write", tier,
            "{0}: agent exit=<exit> (see {1}/agent.stderr.log)".format(name, round_path), backend,
        )
        if not step.ok:
            return _failed(run, phase_path, name, round_number, step.reason)
        output_path = work / outfile
        if not output_path.is_file() or output_path.stat().st_size == 0:
            return _failed(run, phase_path, name, round_number, "agent wrote no {0}".format(outfile))

        _write(directory / "status", "reviewing round {0}\n".format(round_number))
        _log(phase_path, name, round_number, "review start")
        review_output = review / outfile
        shutil.copyfile(str(output_path), str(review_output))
        previous_review = review / "previous-problems.md"
        if previous is not None and previous.is_file():
            shutil.copyfile(str(previous), str(previous_review))
        else:
            try:
                previous_review.unlink()
            except FileNotFoundError:
                pass

        def build_prompt(attempt):
            text = (directory / "review-brief.md").read_text(encoding="utf-8")
            text += "\n\n---\nThe file to review is {0} in the current directory. Do not edit it.\n".format(outfile)
            if previous is not None:
                text += "The problems you listed in the previous round are in previous-problems.md.\n"
            else:
                text += "This is the first round; there is no previous list.\n"
            if min_checked > 0:
                text += 'Begin problems.md with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems.\n'
            text += "Write your list of problems to problems.md. Its last line must be exactly one of:\nVERDICT: pass\nVERDICT: back\nVERDICT: escalate\n"
            if attempt > 1:
                text += 'Your previous attempt left no usable problems.md (missing, or without a "## What I checked" section). Write the file this time; the brief and the role guide hold everything you need.\n'
            return text

        result = run_review(run, name, str(review), str(round_path), build_prompt,
                            model, effort, tier, min_checked,
                            str(previous) if previous is not None else None)
        if result.verdict is None:
            return _failed(run, phase_path, name, round_number, result.reason)
        _log(phase_path, name, round_number, "verdict {0}".format(result.verdict))
        if result.verdict == "pass":
            _write(directory / "status", "passed\n")
            return StepResult(True, "", None)
        if result.verdict == "escalate":
            _write(directory / "status", "escalated\n")
            return StepResult(False, "{0}: escalated".format(name), None)
        if max_rounds > 0 and round_number >= max_rounds:
            _write(directory / "status", "escalated\n")
            _log(phase_path, name, round_number, "round cap {0} reached".format(max_rounds))
            return StepResult(False, "{0}: round cap {1} reached".format(name, max_rounds), None)
        previous = round_path / "problems.md"


def run_phase(run, phase_dir, agents, model, effort, tier=None, outfile="output.md",
              max_rounds=0, min_checked=0, backend="codex"):
    """Run a named parallel phase, resuming agents whose status is not passed."""
    agents = list(agents)
    names = [item[0] for item in agents]
    if len(set(names)) != len(names) or any(
        not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", "..") for name in names
    ):
        raise ValueError("agent names must be unique simple names")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", outfile) or outfile in (".", ".."):
        raise ValueError("output file must be a simple file name")
    for _, agent_brief, review_brief in agents:
        if not Path(agent_brief).is_file() or not Path(review_brief).is_file():
            raise ValueError("agent and review briefs must be files")
    phase_path = Path(phase_dir)
    phase_path.mkdir(parents=True, exist_ok=True)
    _write(phase_path / "names", "".join(name + "\n" for name in names))
    _write(phase_path / "outfile", outfile + "\n")
    _write(phase_path / "settings", "{0} {1}\n".format(model, effort))
    if not (phase_path / "log.tsv").exists():
        _write(phase_path / "log.tsv", "")
    with ThreadPoolExecutor(max_workers=max(1, len(agents))) as executor:
        futures = [executor.submit(_agent, run, phase_path, name, agent_brief, review_brief,
                                   model, effort, tier, outfile, max_rounds, min_checked, backend)
                   for name, agent_brief, review_brief in agents]
        results = [future.result() for future in futures]
    failures = [result for result in results if not result.ok]
    if failures:
        quota = next((result.quota for result in failures if result.quota), None)
        return StepResult(False, "".join(result.reason + "; " for result in failures), quota)
    return StepResult(True, "", None)


def join_phase(phase_dir):
    """Write and return ``joined.md`` after every named agent passed."""
    phase_path = Path(phase_dir)
    names = (phase_path / "names").read_text(encoding="utf-8").splitlines()
    outfile = (phase_path / "outfile").read_text(encoding="utf-8").strip()
    for name in names:
        status = (phase_path / name / "status").read_text(encoding="utf-8").strip()
        if status != "passed":
            raise ValueError("{0} is not passed: {1}".format(name, status))
    chunks = []
    for name in names:
        content = (phase_path / name / "work" / outfile).read_text(encoding="utf-8")
        chunks.append("# {0}\n\n{1}\n\n".format(name, content))
    joined = phase_path / "joined.md"
    _write(joined, "".join(chunks))
    return str(joined)


def clean_phase(phase_dir):
    """Remove a phase directory that contains its ``names`` marker."""
    phase_path = Path(phase_dir)
    if not (phase_path / "names").is_file():
        raise ValueError("not a phase run: {0}".format(phase_path))
    shutil.rmtree(str(phase_path))
    message = "removed {0}".format(phase_path)
    print(message)
    return message

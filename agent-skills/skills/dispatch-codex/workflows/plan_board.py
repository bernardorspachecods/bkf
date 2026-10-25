"""Board, summary and record helpers for sequential plan runs."""
import fnmatch
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


_EXCLUDES = (
    "*.events.jsonl", "*.stderr.log", "*.last-message.md", ".*", "*.attempt-*",
    "untracked-*.txt", "base", "plan-base", "*.worktree.log", "repo", "pause",
    "settings", "status", "status.log",
)


def _read(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return default


def _now_time():
    return datetime.now().strftime("%H:%M")


def _emit(icon, label, state, width):
    return "  {0} {1}{2}  {3}\n".format(icon, label, " " * max(0, width - len(label)), state)


def _round_count(directory):
    rounds = Path(directory) / "rounds"
    try:
        return sum(1 for path in rounds.glob("[0-9]*") if path.is_dir())
    except OSError:
        return 0


def _state_row(run_path, unit, step, step_done, step_stopped, width):
    directory = Path(run_path) / unit
    status = _read(directory / "status").rstrip("\r\n")
    rounds = _round_count(directory)
    icon, state = "○", "pendente"
    match = re.fullmatch(r"(implementing|gate|reviewing|integrating) round ([0-9]+)", status)
    if step_done or status == "passed":
        icon, state = "✓", "passou"
        if rounds == 1:
            state += " · 1 ronda"
        elif rounds > 1:
            state += " · {0} rondas".format(rounds)
    elif status == "escalated":
        icon, state = "✗", "escalada"
    elif match:
        phase, round_text = match.groups()
        round_number = int(round_text)
        current = _read(directory / "rounds" / round_text / "verdict").rstrip("\r\n")
        previous = _read(directory / "rounds" / str(round_number - 1) / "verdict").rstrip("\r\n") if round_number > 1 else ""
        back_round = round_number if current == "back" else (round_number - 1 if previous == "back" else None)
        if back_round is not None:
            gate = _read(directory / "rounds" / str(back_round) / "gate.md")
            icon = "↩"
            if re.search(r"^Result: RED", gate, re.MULTILINE):
                state = "gate falhou · ronda {0} a implementar".format(back_round + 1)
            else:
                state = "devolvida · ronda {0} a implementar".format(back_round + 1)
        elif current == "pass":
            icon, state = "✓", "passou"
            if rounds == 1:
                state += " · 1 ronda"
            elif rounds > 1:
                state += " · {0} rondas".format(rounds)
        elif current == "escalate":
            icon, state = "✗", "escalada"
        elif step_stopped:
            icon, state = "✗", "parou · ronda {0}".format(round_number)
        else:
            icon = "◐"
            state = {
                "implementing": "implementação",
                "gate": "gate",
                "reviewing": "revisão",
                "integrating": "integrar",
            }[phase] + " · ronda {0}".format(round_number)
    return _emit(icon, unit, state, width)


def _step_stopped(events, step):
    stopped = False
    prefix = "STOPPED at step {0}".format(step)
    for event in events:
        if event == "resume":
            stopped = False
        elif event.startswith(prefix + ":") or event.startswith(prefix + " "):
            stopped = True
    return stopped


def board(run):
    """Return the sequential plan board using only files in the run directory."""
    run_path = Path(run.path)
    order_path = run_path / "00-input" / "order"
    order_text = _read(order_path)
    lines = [line.split() for line in order_text.splitlines() if line.split()]
    units = [unit for line in lines for unit in line]
    width = max([13] + [len(unit) for unit in units])
    events = [line.split("\t", 1)[1] for line in _read(run_path / "status.log").splitlines()[1:] if "\t" in line]
    status_lines = _read(run_path / "status.log").splitlines()
    stamp = status_lines[1].split("\t", 1)[0] if len(status_lines) > 1 and "\t" in status_lines[1] else ""
    start_time = stamp.partition("T")[2][:5] or "--:--"
    result = "Plano {0} · {1} unidades · início {2} → agora {3}\n\n".format(
        run_path.name, len(units), start_time, _now_time()
    )
    for step, line in enumerate(lines, 1):
        result += "Passo {0}\n".format(step)
        step_done = (run_path / ".done-S{0}".format(step)).exists()
        stopped = _step_stopped(events, step)
        for unit in line:
            result += _state_row(run_path, unit, step, step_done, stopped, width)
        result += "\n"
    final_state = 0
    for event in events:
        if event.startswith("start final review"):
            final_state = 1
        elif event.startswith("STOPPED at the final review:"):
            final_state = 2
        elif event == "resume" and final_state == 2:
            final_state = 1
    if (run_path / "report.md").exists():
        final_icon, final_status = "✓", "passou"
    elif final_state == 2:
        final_icon, final_status = "✗", "parou"
    elif final_state == 1:
        final_icon, final_status = "◐", "revisão"
    else:
        final_icon, final_status = "○", "pendente"
    return result + _emit(final_icon, "Revisão final", final_status, width)


def _summary_rounds(directory):
    rounds_path = Path(directory) / "rounds"
    try:
        names = sorted(path.name for path in rounds_path.iterdir() if not path.name.startswith("."))
    except OSError:
        names = []
    # ls | sort -n orders numbered directories numerically and picks the last entry.
    names.sort(key=lambda value: (int(value) if value.isdigit() else 0, value))
    last = names[-1] if names else ""
    verdict = _read(rounds_path / last / "verdict").rstrip("\r\n") if last else "-"
    return len(names), verdict or "-"


def write_summary(run):
    run_path = Path(run.path)
    output = [
        "# Plan summary\n\nRun: {0}\n\n| Step | Unit | Rounds | Last verdict |\n|---|---|---|---|\n".format(run_path.name)
    ]
    order = _read(run_path / "00-input" / "order").splitlines()
    for index, line in enumerate(order, 1):
        for unit in line.split():
            count, verdict = _summary_rounds(run_path / unit)
            output.append("| {0} | {1} | {2} | {3} |\n".format(index, unit, count, verdict))
    metrics = run_path / "metrics.tsv"
    if metrics.is_file() and metrics.stat().st_size:
        output.append("\n## Implementation rounds\n\n| Unit | Round | Minutes | Steps | Files | Input tokens (k) |\n|---|---|---|---|---|---|\n")
        for line in _read(metrics).splitlines():
            fields = line.split("\t")
            fields += [""] * (6 - len(fields))
            try:
                tokens = int(float(fields[5])) // 1000
            except ValueError:
                tokens = 0
            output.append("| {0} | {1} | {2} | {3} | {4} | {5} |\n".format(*(fields[:5] + [tokens])))
    output.append("\nThe final review is in report.md.\n")
    with (run_path / "status.md").open("w", encoding="utf-8", newline="") as status:
        status.write("".join(output))


def _excluded(relative):
    return any(fnmatch.fnmatch(part, pattern) for part in relative.parts for pattern in _EXCLUDES)


def _copy_record(source, destination):
    for base, dirs, files in os.walk(str(source), topdown=True, followlinks=False):
        base_path = Path(base)
        relative_base = base_path.relative_to(source)
        kept_dirs = []
        for name in dirs:
            relative = relative_base / name
            if not _excluded(relative):
                kept_dirs.append(name)
                target = destination / relative
                if (base_path / name).is_symlink():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(os.readlink(str(base_path / name)))
                else:
                    target.mkdir(parents=True, exist_ok=True)
        dirs[:] = kept_dirs
        for name in files:
            relative = relative_base / name
            if _excluded(relative):
                continue
            origin, target = source / relative, destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if origin.is_symlink():
                target.symlink_to(os.readlink(str(origin)))
            else:
                shutil.copy2(str(origin), str(target))


def _repo_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, universal_newlines=True, check=False,
        )
    except OSError:
        return None
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def _record_matches(source, destination):
    def kept(root):
        result = set()
        for base, dirs, files in os.walk(str(root), topdown=True, followlinks=False):
            relative_base = Path(base).relative_to(root)
            dirs[:] = [name for name in dirs if not _excluded(relative_base / name)]
            for name in dirs + files:
                relative = relative_base / name
                if not _excluded(relative):
                    result.add(relative)
        return result

    source_paths, destination_paths = kept(source), kept(destination)
    if source_paths != destination_paths:
        return False
    for relative in source_paths:
        left, right = source / relative, destination / relative
        if left.is_symlink() or right.is_symlink():
            if not (left.is_symlink() and right.is_symlink() and os.readlink(str(left)) == os.readlink(str(right))):
                return False
        elif left.is_file() and right.is_file():
            if left.read_bytes() != right.read_bytes():
                return False
    return True


def finish(ctx):
    run = ctx.run
    run_path = run.path
    report = run_path / "report.md"
    if not report.is_file() or report.stat().st_size == 0:
        from harness.engine.run import RunError
        raise RunError("there is no final review in this run: nothing to keep")
    repo = Path(run.repo).resolve()
    current_repo = _repo_root()
    if current_repo is None or Path(current_repo).resolve() != repo:
        from harness.engine.run import RunError
        raise RunError("run finish inside the plan's repository: {0}".format(repo))
    destination = repo / "records" / "plans" / run.name
    if destination.exists():
        from harness.engine.run import RunError
        raise RunError("already exists: {0}".format(destination))
    destination.mkdir(parents=True)
    write_summary(run)
    try:
        _copy_record(run_path, destination)
        if not _record_matches(run_path, destination):
            from harness.engine.run import RunError
            raise RunError("copy to {0} does not match; nothing deleted".format(destination))
    except OSError:
        from harness.engine.run import RunError
        raise RunError("copy to {0} failed; nothing deleted".format(destination))
    shutil.rmtree(run_path)
    print("Kept in {0}; removed {1}".format(destination, run_path))
    agents = repo / "AGENTS.md"
    if "records/" not in _read(agents):
        print(
            "Note: {0}/AGENTS.md does not mention records/. Add a line saying records/ holds the history of past runs, not rules, to be opened only when asked.".format(repo)
        )

"""Run a workflow definition using persisted run state."""

import importlib.util
import os
import signal
import shutil
import subprocess
import sys
import threading
import traceback
from contextlib import contextmanager
from pathlib import Path

from .lock import acquire, is_active
from .run import RunDir, RunError, Settings, valid_name, valid_pause
from .workflow import Context, Stop
from .. import agent


class _RunInterrupted(BaseException):
    def __init__(self, signum, cleanup):
        self.signum = signum
        self.cleanup = cleanup


@contextmanager
def _handle_run_signals(ctx):
    previous = {}

    def interrupted(signum, frame):
        del frame
        name = signal.Signals(signum).name
        agent.stopping.set()
        ctx.note("INTERRUPTED by signal {0} during {1}".format(name, ctx._active_stage))
        cleanup = threading.Thread(
            target=agent.terminate_children, kwargs={"grace": 2.0}, daemon=True
        )
        cleanup.start()
        raise _RunInterrupted(signum, cleanup)

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        previous[signum] = signal.signal(signum, interrupted)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        agent.stopping.clear()


def _run_locked(run, workflow, operation):
    try:
        with acquire(run.path, "harness"):
            ctx = Context(run, workflow)
            ctx._active_stage = "step 1"
            try:
                with _handle_run_signals(ctx):
                    return operation(ctx)
            except _RunInterrupted as interrupted:
                interrupted.cleanup.join()
                return 128 + interrupted.signum
    except _RunInterrupted as interrupted:
        return 128 + interrupted.signum


def _record_crash(ctx, stage, error):
    run = ctx.run
    run.note("CRASHED: {0}: {1}".format(type(error).__name__, error))
    with open(run.path / "crash.log", "w", encoding="utf-8", newline="") as output:
        output.write(traceback.format_exc())
    if stage == "final review":
        print("CRASHED at the final review: {0}\nSee {1}/status.log".format(error, run.path))
    else:
        print("CRASHED at {0}: {1}\nSee {2}/status.log".format(stage, error, run.path))
    return 1


def _resume_detection(run):
    lines = (run.path / "status.log").read_text(encoding="utf-8").splitlines()
    events = []
    for line in lines:
        if line == "time\tevent":
            continue
        if "\t" in line:
            event = line.split("\t", 1)[1]
        else:
            event = line
        if event == "resume" or event.startswith("resume:"):
            continue
        events.append(event)
    if not events:
        return
    last = events[-1]
    terminal = ("STOPPED", "PAUSED", "READY", "INTERRUPTED", "CRASHED")
    starts = [
        index for index, event in enumerate(events)
        if event.startswith("start step ") or event.startswith("start final review")
    ]
    after_last_start = events[starts[-1] + 1:] if starts else events
    if any(event.startswith(terminal) for event in after_last_start):
        return
    if last.startswith("start ") and not any(
        event.startswith("start step ") or event.startswith("start final review")
        for event in events
    ):
        return
    run.note(
        "resume: the previous attempt ended without a STOPPED, PAUSED, READY, "
        "INTERRUPTED or CRASHED line: it was killed or crashed. Steps not marked "
        "done run again."
    )


def _load_workflow(definition_path):
    definition = os.path.abspath(os.fspath(definition_path))
    directory = os.path.dirname(definition)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location("harness_workflow_definition", definition)
    if spec is None or spec.loader is None:
        raise RunError("cannot load workflow definition: {0}".format(definition_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    workflow = getattr(module, "WORKFLOW", None)
    from .workflow import Workflow
    if not isinstance(workflow, Workflow):
        raise RunError("workflow definition must define WORKFLOW as a Workflow")
    return workflow


def _root(workflow):
    env_name = "{0}_RUNS_DIR".format(workflow.name.upper().replace("-", "_"))
    root = os.environ.get("HARNESS_RUNS_DIR") or os.environ.get(env_name)
    return Path(root) if root else Path.home() / ".{0}-runs".format(workflow.name)


def _repo():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, check=False,
        )
    except OSError:
        return None
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def _pipeline(ctx, workflow):
    run = ctx.run
    print("Run folder: {0}".format(run.path))
    stage = "step 1"
    try:
        steps = workflow.steps(ctx)
        for step in steps:
            key = step.number
            stage = "step {0}".format(key)
            ctx._active_stage = stage
            marker = "S{0}".format(key)
            if run.is_done(marker):
                continue
            ctx.note("start step {0}: {1} ({2} {3})".format(
                key, step.label, run.settings.model, run.settings.effort
            ))
            ctx.progress("{0} {1}".format(marker, step.label))
            try:
                step.run(ctx)
            except Stop as stopped:
                ctx.note("STOPPED at step {0}: {1}".format(key, stopped.reason))
                ctx.note(workflow.fix_hint(ctx))
                ctx.progress("{0} parou".format(marker))
                print("STOPPED at step {0} ({1}): {2}\nSee {3}/status.log".format(
                    key, step.label, stopped.reason, run.path
                ))
                return 1
            run.mark_done(marker)
            ctx.note("done step {0}".format(key))
            ctx.progress("{0} concluído".format(marker))
            workflow.after_step(ctx, step)
            if run.pause_here(key):
                run.mark_paused(key)
                ctx.note("PAUSED after step {0}: read {1}, then: {2} resume {3}".format(
                    key, run.path, workflow.command, run.name
                ))
                ctx.progress("{0} pausa".format(marker))
                print("PAUSED after step {0} ({1}). Read it in {2}, then: {3} resume {4}\nSee {2}/status.log".format(
                    key, step.label, run.path, workflow.command, run.name
                ))
                return 3

        stage = "final review"
        ctx._active_stage = stage
        final_step = workflow.final_step(ctx) if not run.is_done("report") else None
        if final_step is not None:
            ctx.note("start final review ({0} {1})".format(run.settings.model, run.settings.effort))
            ctx.progress("final · revisão")
            try:
                final_step.run(ctx)
            except Stop as stopped:
                ctx.note("STOPPED at the final review: {0}".format(stopped.reason))
                ctx.progress("final · parou")
                print("STOPPED at the final review: {0}\nSee {1}/status.log".format(stopped.reason, run.path))
                return 1
            run.mark_done("report")
            ctx.note("done final review")
            ctx.progress("final · concluído")
        ready = workflow.ready_path(ctx)
        ctx.note("READY: report at {0}".format(ready))
        print("READY: {0}\nSee {1}/status.log".format(ready, run.path))
        return 0
    except Exception as error:
        return _record_crash(ctx, stage, error)


def _options(args, defaults=None):
    values = dict(defaults or {})
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in ("-m", "-e", "-r", "-p") and index + 1 < len(args):
            key = {"-m": "model", "-e": "effort", "-r": "review_effort", "-p": "pause"}[option]
            values[key] = args[index + 1]
            index += 2
        else:
            break
    return values, args[index:]


def _check_pause(text):
    if text and not valid_pause(text):
        raise RunError("bad checkpoints: {0} (use each, none, or step numbers like 2,4)".format(text))


def _start(workflow, args):
    options, rest = _options(args, {"model": "gpt-6-luna", "effort": "xhigh", "review_effort": "", "pause": ""})
    if len(rest) < 1:
        raise RunError(workflow.usage_start)
    name, workflow_args = rest[0], rest[1:]
    if not valid_name(name):
        raise RunError("bad run name: {0}".format(name))
    _check_pause(options["pause"])
    workflow.validate_start(workflow_args)
    repo = _repo()
    if repo is None:
        raise RunError(workflow.repo_hint)
    path = _root(workflow) / name
    if path.exists():
        raise RunError("run already exists: {0} (finish it, or resume it)".format(path))
    run = RunDir.create(_root(workflow), name, repo, Settings(
        options["model"], options["effort"], options["review_effort"]
    ), options["pause"])

    def start(ctx):
        workflow.start(ctx, workflow_args)
        board = workflow.board(ctx)
        if board:
            print(board, end="" if board.endswith("\n") else "\n", file=sys.stderr)
        return _pipeline(ctx, workflow)
    return _run_locked(run, workflow, start)


def _resume(workflow, args):
    options, rest = _options(args)
    if len(rest) != 1:
        raise RunError("usage: resume [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name>")
    run = RunDir.load(_root(workflow), rest[0])

    def resume(ctx):
        if "pause" in options:
            _check_pause(options["pause"])
            run.set_pause(options["pause"])
        current = run.settings or Settings("gpt-6-luna", "xhigh", "")
        settings = Settings(
            options.get("model", current.model), options.get("effort", current.effort),
            options.get("review_effort", current.review_effort),
        )
        if _repo() != run.repo:
            raise RunError("run resume inside the {0}'s repository: {1}".format(workflow.name, run.repo))
        run.save_settings(settings)
        ctx.settings = settings
        _resume_detection(run)
        ctx.note("resume")
        return _pipeline(ctx, workflow)
    return _run_locked(run, workflow, resume)


def _finish(workflow, args):
    discard = bool(args and args[0] == "--discard")
    rest = args[1:] if discard else args
    if len(rest) != 1:
        raise RunError("usage: finish [--discard] <name>")
    run = RunDir.load(_root(workflow), rest[0])
    if is_active(run.path, "harness"):
        pid = (run.path / ".lock").read_text(encoding="ascii").rstrip("\n")
        raise RunError("run {0} is being worked on by pid {1}: finish it when it stops".format(rest[0], pid))
    if discard:
        shutil.rmtree(run.path)
        print("Removed {0}".format(run.path))
        return 0
    ctx = Context(run, workflow)
    if not Path(workflow.ready_path(ctx)).is_file():
        raise RunError("there is no final review in this run: nothing to keep")
    if _repo() != run.repo:
        raise RunError("run finish inside the {0}'s repository: {1}".format(workflow.name, run.repo))
    workflow.finish(ctx)
    return 0


def main(definition_path, argv):
    try:
        workflow = _load_workflow(definition_path)
        if not argv:
            raise RunError("usage: {0} start|resume|status|board|finish ...".format(workflow.command))
        command, args = argv[0], argv[1:]
        if command == "start":
            return _start(workflow, args)
        if command == "resume":
            return _resume(workflow, args)
        if command == "status":
            if len(args) != 1:
                raise RunError("usage: status <name>")
            run = RunDir.load(_root(workflow), args[0])
            sys.stdout.write((run.path / "status.log").read_text(encoding="utf-8"))
            return 0
        if command == "board":
            if len(args) != 1:
                raise RunError("usage: board <name>")
            run = RunDir.load(_root(workflow), args[0])
            board = workflow.board(Context(run, workflow))
            if board:
                sys.stdout.write(board)
            return 0
        if command == "finish":
            return _finish(workflow, args)
        extra = workflow.commands().get(command)
        if extra is not None:
            return extra(args)
        raise RunError("usage: {0} start|resume|status|board|finish ...".format(workflow.command))
    except RunError as error:
        print("Error: {0}".format(error), file=sys.stderr)
        return 1

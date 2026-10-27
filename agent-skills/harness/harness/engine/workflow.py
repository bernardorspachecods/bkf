"""Interfaces implemented by workflow definitions."""

import sys


class Stop(Exception):
    """A workflow step stopped and can be resumed after its cause is fixed."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class Step:
    """One numbered step or the workflow's final review."""

    def __init__(self, number, label, runner=None):
        self.number = number
        self.label = label
        self._runner = runner

    def run(self, ctx):
        if self._runner is None:
            raise NotImplementedError
        return self._runner(ctx)


class Context:
    """The run state and output helpers exposed to a workflow."""

    def __init__(self, run, workflow):
        self.run = run
        self.settings = run.settings
        self.repo = run.repo
        self.flags = frozenset()
        self.workflow = workflow

    @property
    def checkout(self):
        return self.run.checkout

    def progress(self, text):
        print("[{0}] {1}\n".format(self.workflow.name, text), file=sys.stderr)
        self.print_board(sys.stderr)

    def print_board(self, output):
        board = self.workflow.board(self)
        if board:
            full_board = self.workflow.full_board(self)
            with (self.run.path / "board.txt").open("w", encoding="utf-8", newline="") as board_file:
                board_file.write(full_board)
            print(board, end="" if board.endswith("\n") else "\n", file=output)
        return board

    def note(self, text):
        self.run.note(text)


class Workflow:
    """Base contract for a workflow definition."""

    name = None
    command = None
    usage_start = None
    start_flags = ()
    repo_hint = None

    def resolve_start_args(self, name, args, repo):
        """Complete the arguments of ``start`` when the workflow can find them itself (a pending plan)."""
        return args

    def validate_start(self, args):
        raise NotImplementedError

    def validate_resume(self, run):
        """Refuse a resume with a RunError before the run is touched; the default accepts every resume."""

    def start(self, ctx, args):
        raise NotImplementedError

    def steps(self, ctx):
        raise NotImplementedError

    def final_step(self, ctx):
        raise NotImplementedError

    def after_step(self, ctx, step):
        return None

    def board(self, ctx):
        return ""

    def full_board(self, ctx):
        return self.board(ctx)

    def fix_hint(self, ctx):
        return "Read the rounds in {0}, then: {1} resume {2}".format(
            ctx.run.path, self.command, ctx.run.name
        )

    def ready_path(self, ctx):
        raise NotImplementedError

    def finish(self, ctx):
        raise NotImplementedError

    def commands(self):
        return {}

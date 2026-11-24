"""Check one unit of a plan that the conversation agent implements itself.

`begin` saves the checkout as the unit's base. After the agent implements, `check` runs the brief's `gate` commands
(code decides), and only if they pass starts a new reviewer process (read-only, on its own model and backend) that sees
the brief and the diff. The reviewer is never the implementer and never shared between units. The result is one verdict
and an exit code: 0 pass, 1 back (fix and run `check` again), 2 escalate or brief (stop and ask), 3 the check itself
failed.

`gate` runs the gate alone and leaves a receipt: the checkout's tree, the gate commands and how many of them failed.
`check` skips the gate when the receipt is green and still matches the checkout and the brief's gate commands.

`worktree` begins a unit in a prepared, detached worktree based on the main checkout's current files. `gate` and
`check` use that worktree from any directory. `integrate` three-way merges its changes into the main checkout's
working files, saving the prior tree in `pre-integration` and any conflicting paths in `conflicts.txt`. It exits 0
for a clean merge, 1 for conflicts, or 3 on error. `discard` removes the worktree and keeps the unit's evidence.
"""
import argparse
import fcntl
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plan  # noqa: E402  (limits and tier: one source with the script-run plan)
import plan_inputs  # noqa: E402
from harness.engine.backend import require_backend  # noqa: E402
from harness.engine.checkout import add_worktree, prepare_tree, remove_worktree  # noqa: E402
from harness.engine.diffbase import make_patch, snapshot_base, snapshot_commit, write_base  # noqa: E402
from harness.engine.pipeline import _check_reviewer  # noqa: E402
from harness.engine.review import run_review  # noqa: E402
from harness.engine.run import RunError  # noqa: E402
from harness.gate import run_gate  # noqa: E402
from harness.receipt import forget_receipt, receipt_gate_file, receipt_passes, write_receipt  # noqa: E402

PASS, BACK, ESCALATE, ERROR = 0, 1, 2, 3
_EXIT = {"pass": PASS, "back": BACK, "escalate": ESCALATE, "brief": ESCALATE}


class _Notes:
    """The little of a run that the review step needs: a place to write notes."""

    def __init__(self, path):
        self.path = Path(path)

    def note(self, text):
        with self.path.open("a", encoding="utf-8", newline="") as output:
            output.write("{0}\t{1}\n".format(time.strftime("%Y-%m-%dT%H:%M:%S"), text))


def _checkout(directory=None):
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=directory, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RunError("run plan-unit inside the repository the unit changes")
    return result.stdout.strip()


def _unit_dir(args):
    return Path(args.dir) / (args.unit or Path(args.brief).stem)


def _require_begun(unit_dir):
    if not (unit_dir / "base").is_file() or not (unit_dir / "brief.md").is_file():
        raise RunError("run begin first: no base saved for unit {0}".format(unit_dir.name))


def _brief_commands(brief):
    if not Path(brief).is_file():
        raise RunError("missing brief: {0}".format(brief))
    return plan_inputs.gate_commands([str(brief)])


def _worktree_owner(unit_dir):
    return unit_dir / "worktree-checkout"


def _remove_unit_worktree(unit_dir):
    owner = _worktree_owner(unit_dir)
    if not owner.is_file():
        raise RunError("no worktree for unit {0}".format(unit_dir.name))
    remove_worktree(owner.read_text(encoding="utf-8").rstrip("\n"), unit_dir.resolve() / "worktree")
    owner.unlink()


def _start_unit(args):
    brief = Path(args.brief)
    if not brief.is_file() or brief.stat().st_size == 0:
        raise RunError("missing or empty brief: {0}".format(brief))
    unit_dir = _unit_dir(args)
    if unit_dir.exists():
        if not args.restart:
            raise RunError("unit already begun: {0} (use --restart to start it over)".format(unit_dir))
        if _worktree_owner(unit_dir).is_file():
            _remove_unit_worktree(unit_dir)
        shutil.rmtree(unit_dir)
    unit_dir.mkdir(parents=True)
    return unit_dir


def begin(args):
    unit_dir = _start_unit(args)
    snapshot_base(unit_dir, _checkout())
    shutil.copyfile(args.brief, unit_dir / "brief.md")
    print("unit {0}: base saved in {1}".format(unit_dir.name, unit_dir))
    return PASS


def _git(checkout, *args, exits=(0,), data=None):
    result = subprocess.run(
        ["git", "-C", os.fspath(checkout), *args], input=data, capture_output=True, check=False,
    )
    if result.returncode not in exits:
        raise RunError("git {0} failed: {1}".format(args[0], os.fsdecode(result.stderr).strip()))
    return result


def _revision(checkout, revision):
    return _git(checkout, "rev-parse", "--verify", revision).stdout.decode("ascii").strip()


def worktree(args):
    checkout = Path(_checkout()).resolve()
    unit_dir = _start_unit(args).resolve()
    try:
        timeout = float(os.environ.get("PLAN_PREPARE_TIMEOUT", "1800"))
    except ValueError as error:
        raise RunError("invalid PLAN_PREPARE_TIMEOUT") from error
    commit = snapshot_commit(checkout)
    base = _revision(checkout, commit + "^{tree}")
    tree = unit_dir / "worktree"
    owner = _worktree_owner(unit_dir)
    owner.write_text(str(checkout) + "\n", encoding="utf-8")
    try:
        add_worktree(checkout, tree, commit=commit)
        prepare_tree(unit_dir, checkout, tree, timeout)
        write_base(unit_dir, base)
        shutil.copyfile(args.brief, unit_dir / "brief.md")
    except (OSError, RunError):
        if (tree / ".git").is_file():
            _remove_unit_worktree(unit_dir)
        else:
            owner.unlink()
        raise
    print("worktree: {0}".format(tree))
    return PASS


def _unit_checkout(unit_dir):
    if not _worktree_owner(unit_dir).is_file():
        return _checkout()
    tree = unit_dir.resolve() / "worktree"
    if not tree.is_dir() or Path(_checkout(tree)).resolve() != tree:
        raise RunError("no worktree for unit {0}".format(unit_dir.name))
    return str(tree)


def _paths(output):
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def _file_stat(path):
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _file_identity(info):
    return (info.st_dev, info.st_ino, info.st_ctime_ns) if info is not None else None


def _backup_roots(checkout, paths):
    roots = set()
    for name in paths:
        path = checkout / name
        # Include a missing ancestor that git apply could create, and never follow a symlink.
        for parent in reversed(path.relative_to(checkout).parents):
            if parent == Path("."):
                continue
            ancestor = checkout / parent
            if ancestor.is_symlink() or not ancestor.is_dir():
                path = ancestor
                break
        roots.add(path)
    return sorted(path for path in roots if roots.isdisjoint(path.parents))


def _copy_path(source, target, mode):
    if stat.S_ISDIR(mode):
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target, follow_symlinks=False)


def _apply_integration_patch(checkout, paths, patch):
    args = ("apply", "--whitespace=nowarn")
    _git(checkout, *args, "--check", "--", data=patch)
    # Git checks the patch before writing, but a filesystem error can interrupt its writes.
    with tempfile.TemporaryDirectory(prefix="plan-unit-apply.", ignore_cleanup_errors=True) as temporary:
        backups = {}
        parents = {}
        for number, path in enumerate(_backup_roots(checkout, paths)):
            original = _file_stat(path)
            backup = Path(temporary) / str(number)
            if original is not None:
                _copy_path(path, backup, original.st_mode)
            backups[path] = (original, backup)
            for parent in path.parents:
                if parent == checkout:
                    break
                if parent not in parents:
                    parents[parent] = parent.stat()
        try:
            _git(checkout, *args, "--", data=patch)
        except (OSError, RunError):
            for path, (original, backup) in backups.items():
                current = _file_stat(path)
                if _file_identity(current) == _file_identity(original):
                    continue
                if current is not None and stat.S_ISDIR(current.st_mode):
                    shutil.rmtree(path)
                elif current is not None:
                    path.unlink()
                if original is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(backup, path)
            for parent, original in parents.items():
                if parent.stat().st_ino != original.st_ino:
                    parent.chmod(stat.S_IMODE(original.st_mode))
            raise


def _integrate(checkout, unit_dir):
    _require_begun(unit_dir)
    pre_integration = unit_dir / "pre-integration"
    if pre_integration.exists():
        raise RunError("unit already integrated: {0}".format(unit_dir.name))
    owner = _worktree_owner(unit_dir)
    if not owner.is_file():
        raise RunError("no worktree for unit {0}".format(unit_dir.name))
    if Path(owner.read_text(encoding="utf-8").rstrip("\n")).resolve() != checkout:
        raise RunError("run integrate from the checkout that created the unit")
    tree = _unit_checkout(unit_dir)
    base = (unit_dir / "base").read_text(encoding="utf-8").strip()
    ours = snapshot_commit(checkout)
    before = _revision(checkout, ours + "^{tree}")
    theirs = snapshot_commit(tree)
    merge = _git(checkout, "merge-tree", "--write-tree", "--merge-base=" + base,
                 "--name-only", "-z", ours, theirs, exits=(0, 1))
    merged, _, details = merge.stdout.partition(b"\0")
    after = merged.decode("ascii")
    conflicts = _paths(details.partition(b"\0\0")[0]) if merge.returncode else []
    diff = ("diff", "--no-renames", "--no-ext-diff", "--no-textconv")
    paths = _paths(_git(checkout, *diff, "--name-only", "-z", before, after, "--").stdout)
    patch = _git(checkout, *diff, "--binary", "--src-prefix=a/", "--dst-prefix=b/",
                 before, after, "--").stdout

    conflict_file = unit_dir / "conflicts.txt"
    try:
        pre_integration.write_text(before + "\n", encoding="utf-8")
        if conflicts:
            conflict_file.write_bytes(b"".join(os.fsencode(path) + b"\n" for path in conflicts))
        if patch:
            _apply_integration_patch(checkout, paths, patch)
    except (OSError, RunError):
        pre_integration.unlink(missing_ok=True)
        if conflicts:
            conflict_file.unlink(missing_ok=True)
        raise

    if merge.returncode:
        print("conflicts:")
        for path in conflicts:
            print(path)
        return BACK
    print("integrated: {0} file(s)".format(len(paths)))
    for path in paths:
        print(path)
    return PASS


def integrate(args):
    checkout = Path(_checkout()).resolve()
    git_dir = Path(os.fsdecode(_git(checkout, "rev-parse", "--absolute-git-dir").stdout).rstrip("\n"))
    # Serialize integrations into this checkout from snapshot through patch application.
    with (git_dir / "plan-unit-integration.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _integrate(checkout, _unit_dir(args).resolve())


def discard(args):
    _remove_unit_worktree(_unit_dir(args))
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


def gate(args):
    unit_dir = _unit_dir(args)
    _require_begun(unit_dir)
    checkout = _unit_checkout(unit_dir)
    commands = _brief_commands(args.brief)
    if not commands:
        forget_receipt(unit_dir)
        print("receipt: none (no gate commands)")
        return PASS
    data = write_receipt(unit_dir, checkout, commands, plan._limits().gate_timeout)
    if data["red"]:
        print("receipt: FAIL ({0} of {1})".format(data["red"], len(commands)))
        return BACK
    print("receipt: pass ({0} command(s))".format(len(commands)))
    return PASS


def check(args):
    unit_dir = _unit_dir(args)
    _require_begun(unit_dir)
    checkout = _unit_checkout(unit_dir)
    if _worktree_owner(unit_dir).is_file():
        unit_dir = unit_dir.resolve()
    brief = unit_dir / "brief.md"
    if not args.gate_only:
        if not args.review_model:
            raise RunError("--review-model is required (or --gate-only when you review the diff yourself)")
        _check_reviewer(args.review_model, args.review_backend)
        require_backend(args.review_backend)

    number, round_dir = _round_dir(unit_dir)
    notes = _Notes(unit_dir / "status.log")
    patch = round_dir / "diff.patch"
    make_patch(unit_dir, patch, checkout)

    commands = _brief_commands(args.brief)
    gate_file = ""
    gate_text = "none (only the reviewer checks this unit)"
    if commands and receipt_passes(unit_dir, checkout, commands):
        gate_file = receipt_gate_file(unit_dir)
        gate_text = "pass (receipt, {0} command(s))".format(len(commands))
    elif commands:
        data = run_gate(checkout, plan._limits().gate_timeout, str(round_dir / "gate"), commands)
        gate_file = round_dir / "gate" / "gate.md"
        if data["red"]:
            forget_receipt(unit_dir)
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
    descriptions = {
        "begin": "save the current checkout as the unit's base",
        "check": "write the diff, run the gate and start a reviewer",
        "gate": "run the gate and save a receipt",
        "worktree": "snapshot the main checkout and begin a unit in a prepared, detached worktree",
        "integrate": "three-way merge a unit's worktree into the main checkout's working files",
        "discard": "remove a unit's worktree and keep its evidence",
    }
    for name, description in descriptions.items():
        sub = commands.add_parser(name, help=description, description=description)
        if name == "integrate":
            sub.epilog = ("Saves the main checkout's prior tree in pre-integration. "
                          "Exits 0 for a clean merge, 1 with paths in conflicts.txt for conflicts, "
                          "or 3 on error. Run from the checkout that created the unit.")
        sub.add_argument("brief")
        sub.add_argument("--dir", required=True, help="folder that holds the unit's files (diffs, gate logs, reviews)")
        sub.add_argument("--unit", help="unit name (default: the brief's file name without extension)")
        if name in ("begin", "worktree"):
            sub.add_argument("--restart", action="store_true", help="start an already begun unit over")
        elif name == "check":
            sub.add_argument("--review-model", help="the reviewer's model")
            sub.add_argument("--review-backend", choices=("codex", "claude"),
                             help="the reviewer's backend (default: HARNESS_BACKEND, else codex)")
            sub.add_argument("-r", "--review-effort", default="high")
            sub.add_argument("--gate-only", action="store_true",
                             help="run the gate and write the diff only; you review the diff yourself")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    handlers = {"begin": begin, "gate": gate, "check": check,
                "worktree": worktree, "integrate": integrate, "discard": discard}
    try:
        return handlers[args.command](args)
    except (OSError, RunError) as error:
        print("plan-unit: {0}".format(error), file=sys.stderr)
        return ERROR


if __name__ == "__main__":
    sys.exit(main())

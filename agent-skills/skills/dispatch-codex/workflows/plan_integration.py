"""Recovery commands for plan integrations."""

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from harness.engine.group import remove_worktrees
from harness.engine.lock import is_active
from harness.engine.run import RunDir, RunError

import plan_inputs
from harness.engine.diffbase import snapshot_tree


def _git(repo, args, env=None, text=True, input_data=None):
    return subprocess.run(
        ["git", "-C", os.fspath(repo)] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        input=input_data,
        check=False,
        env=env,
    )


def _step_units(run_path, step):
    """Return the unit names on step's line in 00-input/order."""
    lines = (Path(run_path) / "00-input" / "order").read_text(encoding="utf-8").splitlines()
    number = int(step)
    return lines[number - 1].split() if 0 < number <= len(lines) else []


def _load_run(name, environ):
    path = plan_inputs._run_path(name, environ)
    return RunDir.load(path.parent, path.name)


def _check_active(run):
    if is_active(run.path, "harness"):
        pid = (run.path / ".lock").read_text(encoding="ascii").rstrip("\n")
        raise RunError("run {0} is being worked on by pid {1}: stop it first".format(run.name, pid))


def _check_repository(run, command):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
        )
    except OSError:
        result = None
    root = result.stdout.rstrip("\n") if result is not None and result.returncode == 0 else ""
    if root != run.repo:
        raise RunError("run {0} inside the plan's repository: {1}".format(command, run.repo))


def _group_units(run, step):
    units = _step_units(run.path, step)
    if len(units) <= 1:
        raise RunError("step {0} is not a parallel group: it has no integration".format(step))
    return units


def _temporary_index(repo):
    directory = tempfile.gettempdir()
    try:
        descriptor, index_path = tempfile.mkstemp(prefix="plan-run-rebase.", dir=directory)
        os.close(descriptor)
        os.unlink(index_path)
    except OSError as error:
        raise RunError("cannot create a temporary index: {0}".format(error))
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_path
    return index_path, env


def _read_tree(repo, tree, env, refusal):
    result = _git(repo, ["read-tree", tree], env=env)
    if result.returncode:
        raise RunError(refusal)


def _write_tree(repo, env, refusal):
    result = _git(repo, ["write-tree"], env=env)
    tree = result.stdout.strip()
    if result.returncode or not tree:
        raise RunError(refusal)
    return tree


def _normalize_paths(paths):
    """Normalize and validate paths using the recovery command's shell rules."""
    normalized = []
    for original in paths:
        path = original[2:] if original.startswith("./") else original
        path = path[:-1] if path.endswith("/") else path
        wrapped = "/{0}/".format(path)
        if wrapped.startswith("//") or "/../" in wrapped or "/./" in wrapped:
            raise RunError(
                "bad path (it must be relative to the repository, with no . or ..): {0}".format(original)
            )
        normalized.append(path)
    return normalized


def _patch_files(patch):
    """Return the sorted unique a/ and b/ paths named by diff headers."""
    files = set()
    for line in patch.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        match = re.match(r"^diff --git a/(.*) b/(.*)$", line)
        if match:
            files.add(match.group(1))
            files.add(match.group(2))
    return sorted(files)


def _patch_conflicts(run, units, paths):
    bad = []
    for unit in units:
        patch_path = run.path / unit / "final.patch"
        if not patch_path.is_file():
            continue
        files = _patch_files(patch_path.read_text(encoding="utf-8"))
        for file_path in files:
            if any(file_path == path or file_path.startswith(path + "/") for path in paths):
                bad.append("  {0}: {1}".format(unit, file_path))
    return bad


def _integrator_ran(integration):
    return any(integration.glob("rounds*/*/integrate.last-message.md"))


def _preserve_base(integration, tree):
    base = integration / "base"
    shutil.copyfile(base, integration / (".base.before-rebase-{0}".format(int(time.time()))))
    base.write_text(tree + "\n", encoding="utf-8")
    (integration / "base-format").write_text("tree\n", encoding="utf-8")


def _checkout_tree(repo):
    try:
        return snapshot_tree(repo)
    except RunError:
        raise RunError("cannot snapshot the checkout {0}".format(repo))


def _rebase_without_paths(run, step, units, integration, current, head):
    if _integrator_ran(integration):
        raise RunError(
            "the integrator already changed the checkout in step {0}, so its edits would become part of the base and hide from the reviewer. Name what to leave out of the diff: rebase-integration {1} {0} --paths <path>...".format(
                step, run.name
            )
        )
    applied = [unit for unit in units if (integration / (".applied-" + unit)).exists()]
    if not applied:
        raise RunError("no unit of step {0} was applied to the checkout: nothing to subtract".format(step))

    index_path, env = _temporary_index(run.repo)
    try:
        _read_tree(run.repo, current, env, "cannot read the checkout tree")
        for unit in reversed(applied):
            patch = run.path / unit / "final.patch"
            result = _git(run.repo, ["apply", "-R", "--cached", os.fspath(patch)], env=env)
            if result.returncode:
                detail = (result.stdout + result.stderr).strip()
                raise RunError(
                    "the diff of {0} cannot be taken back out of the checkout, so the checkout changed files it touches. Nothing was changed. Git says: {1}".format(
                        unit, detail
                    )
                )
        tree = _write_tree(run.repo, env, "cannot write the new base")
    finally:
        try:
            os.unlink(index_path)
        except FileNotFoundError:
            pass

    _preserve_base(integration, tree)
    run.note(
        "S{0}-integration: base moved to the checkout minus the diffs of {1} (HEAD {2})".format(
            step, " ".join(applied), head
        )
    )
    print(
        "The base of S{0}-integration is now the checkout minus the diffs of {1}.".format(
            step, " ".join(applied)
        )
    )


def _tree_entries(repo, tree, path):
    result = _git(repo, ["--literal-pathspecs", "ls-tree", "-r", "-z", tree, "--", path], text=False)
    if result.returncode:
        raise RunError("cannot list files under {0}".format(path))
    return [entry for entry in result.stdout.split(b"\0") if entry]


def _entry_path(entry):
    return entry.split(b"\t", 1)[1]


def _update_base_paths(repo, old, current, paths, env):
    for path in paths:
        old_entries = _tree_entries(repo, old, path)
        if old_entries:
            names = [os.fsdecode(_entry_path(entry)) for entry in old_entries]
            result = _git(
                repo, ["--literal-pathspecs", "update-index", "--force-remove", "--"] + names, env=env
            )
            if result.returncode:
                raise RunError("cannot update the base under {0}".format(path))

        current_entries = _tree_entries(repo, current, path)
        if current_entries:
            records = []
            for entry in current_entries:
                metadata, file_path = entry.split(b"\t", 1)
                mode, object_type, object_id = metadata.split(b" ", 2)
                del object_type
                records.append(mode + b" " + object_id + b"\t" + file_path + b"\0")
            result = _git(
                repo, ["update-index", "-z", "--index-info"], env=env,
                text=False, input_data=b"".join(records),
            )
            if result.returncode:
                raise RunError("cannot update the base under {0}".format(path))


def _rebase_paths(run, step, units, integration, old, current, head, paths):
    bad = _patch_conflicts(run, units, paths)
    if bad:
        raise RunError(
            "these paths hold files that a unit's diff changed, so leaving them out would hide that unit's work. Nothing was changed:\n{0}".format(
                "\n".join(bad)
            )
        )

    index_path, env = _temporary_index(run.repo)
    try:
        _read_tree(run.repo, old, env, "cannot read the base tree")
        _update_base_paths(run.repo, old, current, paths, env)
        tree = _write_tree(run.repo, env, "cannot write the new base")
    finally:
        try:
            os.unlink(index_path)
        except FileNotFoundError:
            pass

    result = _git(run.repo, ["diff", "--name-only", old, tree])
    hidden = result.stdout.rstrip("\n")
    if result.returncode:
        raise RunError("cannot compare the old and new bases")
    if not hidden:
        raise RunError("nothing under {0} differs from the base: nothing to do".format(" ".join(paths)))
    hidden_files = hidden.splitlines()
    _preserve_base(integration, tree)
    run.note(
        "S{0}-integration: base moved under {1}; {2} file(s) no longer in the diff: {3} (HEAD {4})".format(
            step, " ".join(paths), len(hidden_files), " ".join(hidden_files), head
        )
    )
    print(
        "The diff of S{0}-integration no longer shows these files (they stay in the checkout):\n{1}\n".format(
            step, hidden
        )
    )
    print("If one of them is an edit of the integrator, the reviewer will not see it either.")


def rebase_integration(args, environ=None):
    environ = os.environ if environ is None else environ
    usage = "usage: rebase-integration <name> <step> [--paths <path>...]"
    if len(args) < 2:
        raise RunError(usage)
    name, step = args[:2]
    paths = None
    rest = args[2:]
    if rest:
        if rest[0] != "--paths" or len(rest) < 2:
            raise RunError(usage)
        paths = rest[1:]
    if not re.fullmatch(r"[0-9]+", step):
        raise RunError("bad step: {0}".format(step))

    run = _load_run(name, environ)
    _check_active(run)
    _check_repository(run, "rebase-integration")
    units = _group_units(run, step)
    integration = run.path / ("S{0}-integration".format(step))
    base_path = integration / "base"
    if not base_path.is_file():
        raise RunError("the integration of step {0} has not started: there is no base to move".format(step))
    if (run.path / (".done-S{0}-integration".format(step))).exists():
        raise RunError("the integration of step {0} is already closed".format(step))
    try:
        base_format = (integration / "base-format").read_text(encoding="utf-8").strip()
    except OSError:
        base_format = ""
    if base_format != "tree":
        raise RunError("the integration of step {0} keeps an old-format base: finish it as it is".format(step))

    old = base_path.read_text(encoding="utf-8").strip()
    current = _checkout_tree(run.repo)
    head_result = _git(run.repo, ["rev-parse", "--short", "HEAD"])
    head = head_result.stdout.strip() if head_result.returncode == 0 else ""
    if paths is None:
        _rebase_without_paths(run, step, units, integration, current, head)
        return 0
    normalized = _normalize_paths(paths)
    _rebase_paths(run, step, units, integration, old, current, head, normalized)
    return 0


def accept_integration(args, environ=None):
    environ = os.environ if environ is None else environ
    usage = "usage: accept-integration <name> <step> --why <text>"
    if len(args) != 4 or args[2] != "--why":
        raise RunError(usage)
    name, step, _why_option, why = args
    if not why.strip():
        raise RunError(usage + " (the reason cannot be empty)")
    if not re.fullmatch(r"[0-9]+", step):
        raise RunError("bad step: {0}".format(step))

    run = _load_run(name, environ)
    _check_active(run)
    _check_repository(run, "accept-integration")
    units = _group_units(run, step)
    integration = run.path / ("S{0}-integration".format(step))
    if (run.path / (".done-S{0}-integration".format(step))).exists():
        raise RunError("the integration of step {0} is already closed".format(step))
    for unit in units:
        try:
            unit_status = (run.path / unit / "status").read_text(encoding="utf-8").strip()
        except OSError:
            unit_status = ""
        if not (run.path / (".done-" + unit)).exists() or unit_status != "passed":
            raise RunError("unit {0} has not passed: the integration cannot be closed over it".format(unit))
        if not (integration / (".applied-" + unit)).exists():
            raise RunError(
                "the diff of unit {0} was never applied to the checkout: the integration cannot be closed over it".format(unit)
            )
    head_result = _git(run.repo, ["rev-parse", "--short", "HEAD"])
    head = head_result.stdout.strip() if head_result.returncode == 0 else ""
    (integration / "status").write_text("passed\n", encoding="utf-8")
    (run.path / (".done-S{0}-integration".format(step))).touch()
    remove_worktrees(run, run.repo)
    user_result = subprocess.run(
        ["id", "-un"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, check=False,
    )
    user = user_result.stdout.rstrip("\n") if user_result.returncode == 0 else ""
    run.note(
        "S{0}-integration: closed by hand by {1} at HEAD {2}, without a review of the combined result. Reason: {3}".format(
            step, user, head, why
        )
    )
    print("S{0}-integration is closed. Continue with: plan-run.sh resume {1}".format(step, name))
    return 0

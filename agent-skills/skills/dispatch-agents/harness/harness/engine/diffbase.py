"""Checkout tree snapshots and patches for workflow runs."""
import os
import subprocess
import tempfile
from pathlib import Path

from .run import RunError


def _git(checkout, args, env, output=None):
    return subprocess.run(
        ["git", "-C", str(checkout)] + list(args),
        stdout=output if output is not None else subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=output is None,
        check=False,
        env=env,
    )


def snapshot_tree(checkout):
    """Return a tree id for tracked and untracked, non-ignored checkout files."""
    env = os.environ.copy()
    try:
        root_result = _git(checkout, ["rev-parse", "--show-toplevel"], env)
    except OSError as error:
        raise RunError("cannot snapshot the checkout {0}".format(checkout)) from error
    if root_result.returncode != 0:
        raise RunError("cannot snapshot the checkout {0}".format(checkout))
    repo_root = Path(root_result.stdout.strip()).resolve()
    temporary_directory = Path(tempfile.gettempdir()).resolve()
    try:
        temporary_directory.relative_to(repo_root)
        temporary_directory = repo_root.parent
    except ValueError:
        pass
    try:
        descriptor, index_path = tempfile.mkstemp(
            prefix="harness-run-index.", dir=str(temporary_directory)
        )
    except OSError as error:
        raise RunError("cannot snapshot the checkout {0}".format(checkout)) from error
    try:
        os.close(descriptor)
        os.unlink(index_path)
    except OSError as error:
        try:
            os.unlink(index_path)
        except OSError:
            pass
        raise RunError("cannot snapshot the checkout {0}".format(checkout)) from error
    env["GIT_INDEX_FILE"] = index_path
    try:
        result = _git(checkout, ["read-tree", "HEAD"], env)
        if result.returncode != 0:
            raise RunError("cannot snapshot the checkout {0}".format(checkout))
        result = _git(checkout, ["add", "-A"], env)
        if result.returncode != 0:
            raise RunError("cannot snapshot the checkout {0}".format(checkout))
        result = _git(checkout, ["write-tree"], env)
        tree = result.stdout.strip()
        if result.returncode != 0 or not tree:
            raise RunError("cannot snapshot the checkout {0}".format(checkout))
        return tree
    except OSError as error:
        raise RunError("cannot snapshot the checkout {0}".format(checkout)) from error
    finally:
        try:
            os.unlink(index_path)
        except FileNotFoundError:
            pass


def snapshot_commit(checkout):
    """Return a commit on HEAD containing a snapshot of the checkout tree."""
    try:
        tree = snapshot_tree(checkout)
        env = os.environ.copy()
        env.update({
            "GIT_AUTHOR_NAME": "plan-run",
            "GIT_AUTHOR_EMAIL": "plan-run@localhost",
            "GIT_COMMITTER_NAME": "plan-run",
            "GIT_COMMITTER_EMAIL": "plan-run@localhost",
        })
        result = _git(
            checkout,
            ["commit-tree", tree, "-p", "HEAD", "-m", "plan-run snapshot"],
            env,
        )
    except OSError as error:
        raise RunError("cannot snapshot the checkout {0}".format(checkout)) from error
    commit = result.stdout.strip()
    if result.returncode != 0 or not commit:
        raise RunError("cannot snapshot the checkout {0}".format(checkout))
    return commit


def snapshot_base(directory, checkout):
    """Write the tree id and its format marker to a round directory."""
    try:
        tree = snapshot_tree(checkout)
        directory = Path(directory)
        (directory / "base").write_text("{0}\n".format(tree), encoding="utf-8")
        (directory / "base-format").write_text("tree\n", encoding="utf-8")
    except (OSError, RunError) as error:
        raise RunError("cannot snapshot the checkout {0}".format(checkout)) from error


def make_patch(base_dir, out_file, checkout):
    """Write a tree-to-tree diff, including creating an empty output file."""
    base_dir = Path(base_dir)
    out_file = Path(out_file)
    try:
        base = (base_dir / "base").read_text(encoding="utf-8").rstrip("\n")
        current = snapshot_tree(checkout)
        env = os.environ.copy()
        with out_file.open("w", encoding="utf-8", newline="") as output:
            result = subprocess.run(
                ["git", "-C", str(checkout), "diff", "--no-ext-diff", base, current],
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )
        if result.returncode != 0:
            raise RunError("cannot make patch for the checkout {0}".format(checkout))
    except OSError as error:
        raise RunError("cannot make patch for the checkout {0}".format(checkout)) from error

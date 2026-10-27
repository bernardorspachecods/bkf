"""Where a workflow keeps its runs and its plans that are ready but not started.

By default a run lives in ``~/.<workflow>-runs/<repo>/<run>`` and a pending plan in
``~/.<workflow>-runs-pending/<repo>/<plan>``, ``<repo>`` being the name of the repository's folder. Runs
made before that layout lived in ``~/.<workflow>-runs/<run>`` and are still found there. An explicit
``HARNESS_RUNS_DIR`` or ``<WORKFLOW>_RUNS_DIR`` names the folder that holds the runs themselves.
"""
import os
from pathlib import Path

from .run import RunError, valid_name


def _variable(workflow_name, suffix):
    return "{0}_{1}".format(workflow_name.upper().replace("-", "_"), suffix)


def _environ(environ):
    return os.environ if environ is None else environ


def repo_slug(repo):
    """The folder name of a repository, the part of a path that tells repositories apart."""
    return Path(str(repo)).name


def _default_root(workflow_name):
    return Path.home() / ".{0}-runs".format(workflow_name)


def _explicit_root(workflow_name, environ):
    value = environ.get("HARNESS_RUNS_DIR") or environ.get(_variable(workflow_name, "RUNS_DIR"))
    return Path(value) if value else None


def new_run_parent(workflow_name, repo, environ=None):
    """The folder in which a new run of ``repo`` is created."""
    environ = _environ(environ)
    explicit = _explicit_root(workflow_name, environ)
    if explicit is not None:
        return explicit
    return _default_root(workflow_name) / repo_slug(repo)


def _repo_of(run_path):
    try:
        return (Path(run_path) / "repo").read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        return None


def find_run(workflow_name, name, repo=None, environ=None):
    """The folder of the run called ``name``, or where it would be when it does not exist.

    With a repository the run is looked up for it: first in its own folder, then in the old flat folder
    when that run belongs to the same repository. Without one (a command run outside any repository) it
    is looked up under every repository, and two runs with the same name are an error.
    """
    if not valid_name(name):
        raise RunError("bad run name: {0}".format(name))
    environ = _environ(environ)
    explicit = _explicit_root(workflow_name, environ)
    if explicit is not None:
        return explicit / name
    root = _default_root(workflow_name)
    if repo is not None:
        own = root / repo_slug(repo) / name
        if own.is_dir():
            return own
        legacy = root / name
        if legacy.is_dir() and _repo_of(legacy) == str(repo):
            return legacy
        return own
    found = [path for path in sorted(root.glob("*/" + name)) if (path / "repo").is_file()] if root.is_dir() else []
    legacy = root / name
    if legacy.is_dir() and (legacy / "repo").is_file():
        found.append(legacy)
    if len(found) > 1:
        raise RunError("more than one run is called {0} ({1}): run this inside the repository".format(
            name, ", ".join(str(path) for path in found)))
    return found[0] if found else root / name


def pending_root(workflow_name, environ=None):
    environ = _environ(environ)
    value = environ.get("HARNESS_PENDING_DIR") or environ.get(_variable(workflow_name, "PENDING_DIR"))
    return Path(value) if value else Path.home() / ".{0}-runs-pending".format(workflow_name)


def pending_dir(workflow_name, repo, name, environ=None):
    """The folder of the pending plan ``name`` of ``repo``."""
    if not valid_name(name):
        raise RunError("bad run name: {0}".format(name))
    return pending_root(workflow_name, environ) / repo_slug(repo) / name


def list_pending(workflow_name, repo, environ=None):
    """The names of the pending plans of ``repo``, sorted."""
    folder = pending_root(workflow_name, environ) / repo_slug(repo)
    if not folder.is_dir():
        return []
    return sorted(path.name for path in folder.iterdir() if path.is_dir())

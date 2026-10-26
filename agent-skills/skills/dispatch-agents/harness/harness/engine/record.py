"""Copy a run folder into a repository record and remove it after verification.

    keep_record(run_dir, repo, kind, name, exclusions=())

Exclusions are filename or path component patterns, such as ``*.events.jsonl``
and ``status.log``. The copy is compared with the source using the same patterns.
An existing destination or a failed comparison raises ``RecordError`` and leaves
the run folder intact. Success prints and returns ``Kept in <dest>; removed <run>``.
"""

import fnmatch
import os
import re
import shutil
from pathlib import Path


class RecordError(Exception):
    """A record could not be copied and verified."""


def _excluded(relative, patterns):
    return any(fnmatch.fnmatch(part, pattern) for part in relative.parts for pattern in patterns)


def _copy(source, destination, exclusions):
    for base, dirs, files in os.walk(str(source), topdown=True, followlinks=False):
        base_path = Path(base)
        relative_base = base_path.relative_to(source)
        kept = []
        for name in dirs:
            relative = relative_base / name
            if _excluded(relative, exclusions):
                continue
            kept.append(name)
            origin, target = base_path / name, destination / relative
            if origin.is_symlink():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(os.readlink(str(origin)))
            else:
                target.mkdir(parents=True, exist_ok=True)
        dirs[:] = kept
        for name in files:
            relative = relative_base / name
            if _excluded(relative, exclusions):
                continue
            origin, target = source / relative, destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if origin.is_symlink():
                target.symlink_to(os.readlink(str(origin)))
            else:
                shutil.copy2(str(origin), str(target))


def _paths(root, exclusions):
    result = set()
    for base, dirs, files in os.walk(str(root), topdown=True, followlinks=False):
        relative_base = Path(base).relative_to(root)
        dirs[:] = [name for name in dirs if not _excluded(relative_base / name, exclusions)]
        for name in dirs + files:
            relative = relative_base / name
            if not _excluded(relative, exclusions):
                result.add(relative)
    return result


def _matches(source, destination, exclusions):
    source_paths = _paths(source, exclusions)
    if source_paths != _paths(destination, exclusions):
        return False
    for relative in source_paths:
        left, right = source / relative, destination / relative
        if left.is_symlink() or right.is_symlink():
            if not (left.is_symlink() and right.is_symlink() and os.readlink(str(left)) == os.readlink(str(right))):
                return False
        elif left.is_file() and right.is_file() and left.read_bytes() != right.read_bytes():
            return False
    return True


def keep_record(run_dir, repo, kind, name, exclusions=()):
    """Keep a verified copy of ``run_dir`` at ``repo/records/kind/name``."""
    if any(not re.fullmatch(r"[A-Za-z0-9._-]+", value) or value in (".", "..")
           for value in (kind, name)):
        raise RecordError("kind and name must be simple path components")
    source = Path(run_dir)
    destination = Path(repo) / "records" / kind / name
    if destination.exists() or destination.is_symlink():
        raise RecordError("already exists: {0}".format(destination))
    destination.mkdir(parents=True)
    try:
        _copy(source, destination, tuple(exclusions))
        if not _matches(source, destination, tuple(exclusions)):
            raise RecordError("copy to {0} does not match; nothing deleted".format(destination))
    except OSError as error:
        raise RecordError("copy to {0} failed; nothing deleted: {1}".format(destination, error))
    shutil.rmtree(source)
    message = "Kept in {0}; removed {1}".format(destination, source)
    print(message)
    return message

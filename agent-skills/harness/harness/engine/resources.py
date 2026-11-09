"""Checks of system resources that a run can leave exhausted, so a unit does not fail later with a misleading error.

On macOS the System V shared-memory segments are limited (``kern.sysv.shmmni``, 32 by default). Test databases that
are killed before their teardown leave segments behind, and when none is free ``initdb`` fails with
``No space left on device``, which reads like a full disk.
"""
import os
import platform
import subprocess


def _limit():
    result = subprocess.run(["sysctl", "-n", "kern.sysv.shmmni"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            universal_newlines=True, check=False)
    return int(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip().isdigit() else None


def _segments():
    """The shared-memory segments as (id, attached processes) pairs, or None when they cannot be listed."""
    result = subprocess.run(["ipcs", "-m", "-a"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            universal_newlines=True, check=False)
    if result.returncode != 0:
        return None
    segments = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 9 and fields[0] == "m" and fields[1].isdigit() and fields[8].isdigit():
            segments.append((fields[1], int(fields[8])))
    return segments


def min_free_segments(environ=None):
    value = (environ if environ is not None else os.environ).get("HARNESS_SHM_MIN_FREE", "4")
    return int(value) if value.isdigit() else 4


def shm_problem(min_free=None):
    """A sentence saying what to do when too few shared-memory segments are free, or None when enough are.

    Only macOS is checked; elsewhere, and when the limit is 0 or the segments cannot be read, nothing is reported.
    The segments are never removed here: whether one still belongs to a running database is the owner's call.
    """
    min_free = min_free_segments() if min_free is None else min_free
    if min_free <= 0 or platform.system() != "Darwin":
        return None
    try:
        limit = _limit()
        segments = _segments()
    except OSError:
        return None
    if limit is None or segments is None or limit - len(segments) >= min_free:
        return None
    orphans = [identifier for identifier, attached in segments if attached == 0]
    text = (
        "only {0} of {1} System V shared-memory segments are free (a database test needs one, and `initdb` "
        "then fails with \"No space left on device\", which is not the disk)."
    ).format(limit - len(segments), limit)
    if orphans:
        text += " {0} have no process attached, which usually means test databases killed before cleanup; " \
                "if none of your databases is running, remove them with: ipcrm {1} .".format(
                    len(orphans), " ".join("-m " + identifier for identifier in orphans))
    else:
        text += " All of them still have a process attached: stop the databases that hold them."
    return text + " Set HARNESS_SHM_MIN_FREE=0 to skip this check."

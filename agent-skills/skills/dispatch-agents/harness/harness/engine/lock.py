import errno
import os
import re
import subprocess
from pathlib import Path

from .run import RunError


def _pid_text(run_path):
    try:
        with open(Path(run_path) / ".lock", "r", encoding="ascii", newline="") as source:
            return source.read().rstrip("\n")
    except OSError:
        return None


def _process_exists(pid):
    try:
        os.kill(pid, 0)
    except OSError as error:
        if error.errno == errno.EPERM:
            return True
        return False
    except OverflowError:
        return False
    return True


def is_active(run_path, marker):
    pid_text = _pid_text(run_path)
    if pid_text is None or not re.fullmatch(r"[0-9]+", pid_text):
        return False
    if not _process_exists(int(pid_text)):
        return False
    try:
        result = subprocess.run(
            ["ps", "-p", pid_text, "-o", "command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return any(marker in line for line in result.stdout.splitlines())


class Lock:
    """An exclusively created run lock owned by this process."""

    def __init__(self, run_path, pid):
        self.run_path = Path(run_path)
        self.pid = pid

    def release(self):
        lock_path = self.run_path / ".lock"
        if _pid_text(self.run_path) == str(self.pid):
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


def acquire(run_path, marker="harness"):
    run_path = Path(run_path)
    lock_path = run_path / ".lock"
    pid = os.getpid()
    for _ in range(2):
        try:
            descriptor = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            pid_text = _pid_text(run_path)
            if is_active(run_path, marker):
                raise RunError(
                    "run {0} is already being worked on by pid {1}".format(
                        run_path.name, pid_text
                    )
                )
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(descriptor, "w", encoding="ascii", newline="") as output:
            output.write("{0}\n".format(pid))
        return Lock(run_path, pid)
    raise RunError("cannot lock {0}".format(run_path))

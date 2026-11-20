"""The tmux layer of `bkf launch`: open a window for a ready shell command in tmux, iTerm2 or Terminal.app.

Inside tmux the window goes into the caller's session, grouped with the windows of the same repository:
right after the caller's window when the directory is in the caller's repository, else right after the last
window of its repository, else at the end of the session. It is created with `new-window -d`, so focus stays
on the caller. When iTerm2 is attached in control mode, the caller's iTerm2 window gets focus until the tab
appears, and the window focused before gets it back.

Outside tmux the window goes into the session of the repository (`repo_session_name`), created when missing,
and a terminal attaches to it: iTerm2 gets a window running `tmux -CC attach`, Terminal.app a window running
`tmux attach`. Anywhere else the caller gets `needs_attach` and a line on standard error with the command.

Every external call goes through `runner`, so tests replace it. Every tmux call is prefixed with
`-L $BKF_TMUX_SOCKET` when that variable is set: tests use it to run on a throwaway server and never touch
the user's tmux server.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


class TmuxError(RuntimeError):
    """A tmux step that failed, with the step and tmux's standard error on one line."""


class Result(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str], str | None], Result]


@dataclass(frozen=True)
class Window:
    session: str        # tmux session name
    window_id: str      # tmux window id, for example "@41"
    needs_attach: bool  # True when no terminal shows the session yet


SESSION_NAME_LIMIT = 48
ITERM_FOCUS_SCRIPT = """on run argv
  tell application "iTerm2"
    set focusedId to id of current window
    repeat with w in windows
      repeat with t in tabs of w
        if (variable of (current session of t) named "tmuxWindowPane") is (item 1 of argv) then
          set tabCount to count of tabs of w
          select w
          return (focusedId as text) & " " & (id of w) & " " & tabCount
        end if
      end repeat
    end repeat
  end tell
end run
"""
ITERM_RESTORE_SCRIPT = """on run argv
  tell application "iTerm2"
    repeat 30 times
      if (count of tabs of window id ((item 2 of argv) as integer)) > ((item 3 of argv) as integer) then exit repeat
      delay 0.1
    end repeat
    select window id ((item 1 of argv) as integer)
  end tell
end run
"""
ITERM_NEW_WINDOW_SCRIPT = """on run argv
  tell application "iTerm2"
    create window with default profile command (item 1 of argv)
  end tell
end run
"""
TERMINAL_DO_SCRIPT = """on run argv
  tell application "Terminal" to do script (item 1 of argv)
end run
"""


def default_runner(args: Sequence[str], stdin: str | None = None) -> Result:
    """Run a program with an argument list (never a shell); a missing program returns status 127."""
    try:
        done = subprocess.run(list(args), input=stdin, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return Result(127, "", f"{args[0]} is not installed or not on PATH")
    return Result(done.returncode, done.stdout, done.stderr)


def open_window(
    *,
    directory: str,
    command: str,
    window_name: str | None = None,
    environment: dict[str, str] | None = None,
    repo: str,
    size: tuple[int, int] | None = None,
    attach: bool = True,
    environ: Mapping[str, str] = os.environ,
    runner: Runner = default_runner,
) -> Window:
    """Open a window running `command` in `directory`, placed as described in the module docstring."""
    environment = environment or {}
    if environ.get("TMUX") and environ.get("TMUX_PANE"):
        return _open_inside_tmux(
            directory=directory, command=command, window_name=window_name,
            environment=environment, environ=environ, runner=runner,
        )
    if environ.get("TMUX"):
        raise TmuxError("TMUX is set without TMUX_PANE")
    return _open_outside_tmux(
        directory=directory, command=command, window_name=window_name, environment=environment,
        repo=repo, size=size, attach=attach, environ=environ, runner=runner,
    )


def _open_inside_tmux(
    *, directory: str, command: str, window_name: str | None, environment: dict[str, str],
    environ: Mapping[str, str], runner: Runner,
) -> Window:
    pane = environ["TMUX_PANE"]
    caller = _display(runner, environ, pane, "#{window_id}")
    session_id = _display(runner, environ, pane, "#{session_id}")
    session = _display(runner, environ, pane, "#{session_name}")

    clients = _tmux(runner, environ, "list-clients", "list-clients", "-t", session_id,
                    "-F", "#{client_control_mode}")
    focus = ""
    if any(line.strip() == "1" for line in clients.splitlines()):
        focus = _osascript(runner, ITERM_FOCUS_SCRIPT, pane.removeprefix("%")).stdout.strip()

    pane_path = _display(runner, environ, pane, "#{pane_current_path}")
    target_key = _repo_key(directory, runner)
    if _repo_key(pane_path, runner) == target_key:
        place = ["-a", "-t", caller]
    else:
        last, last_index, end = "", -1, -1
        listing = _tmux(runner, environ, "list-panes", "list-panes", "-s", "-t", session_id,
                        "-F", "#{window_id} #{window_index} #{pane_current_path}")
        for line in listing.splitlines():
            window_id, index_text, path = (line.split(" ", 2) + ["", ""])[:3]
            index = int(index_text)
            end = max(end, index)
            if window_id == caller or index <= last_index:
                continue
            if path and _repo_key(path, runner) == target_key:
                last, last_index = window_id, index
        place = ["-a", "-t", last] if last else ["-t", f"{session_id}:{end + 1}"]

    window_id = _new_window(runner, environ, place, directory, command, window_name, environment)
    if focus:
        _osascript(runner, ITERM_RESTORE_SCRIPT, *focus.split())
    return Window(session=session, window_id=window_id, needs_attach=False)


def _open_outside_tmux(
    *, directory: str, command: str, window_name: str | None, environment: dict[str, str],
    repo: str, size: tuple[int, int] | None, attach: bool, environ: Mapping[str, str], runner: Runner,
) -> Window:
    session = repo_session_name(repo)
    if _tmux_status(runner, environ, "has-session", "-t", f"={session}").returncode != 0:
        # A new session takes the requested window as its first window, so no bare shell remains.
        created = ["new-session", "-d", "-P", "-F", "#{window_id}", "-s", session]
        if size is not None:
            created += ["-x", str(size[0]), "-y", str(size[1])]
        created += _window_arguments(directory, window_name, environment, command)
        window_id = _tmux(runner, environ, "new-session", *created).strip()
    else:
        window_id = _new_window(runner, environ, ["-t", f"={session}:"], directory, command,
                                window_name, environment)

    # A client that already displays the session shows the new window too: no second terminal.
    clients = _tmux_status(runner, environ, "list-clients", "-t", f"={session}", "-F", "#{client_name}")
    if clients.returncode == 0 and clients.stdout.strip():
        return Window(session=session, window_id=window_id, needs_attach=False)
    if not attach:
        return Window(session=session, window_id=window_id, needs_attach=True)

    attached = _attach(runner, environ, session)
    if not attached:
        print(f"bkf: no terminal shows tmux session {session}; attach with: "
              f"{_attach_command(environ, session, control=False)}", file=sys.stderr)
    return Window(session=session, window_id=window_id, needs_attach=not attached)


def _attach(runner: Runner, environ: Mapping[str, str], session: str) -> bool:
    """Attach a terminal to the session: True when the terminal's AppleScript succeeded."""
    term = environ.get("TERM_PROGRAM")
    if term == "iTerm.app":
        script, control = ITERM_NEW_WINDOW_SCRIPT, True
    elif term == "Apple_Terminal":
        script, control = TERMINAL_DO_SCRIPT, False
    else:
        return False
    command = _attach_command(environ, session, control=control)
    return _osascript(runner, script, command).returncode == 0


def _attach_command(environ: Mapping[str, str], session: str, *, control: bool) -> str:
    socket = environ.get("BKF_TMUX_SOCKET")
    parts = ["tmux"] + (["-L", socket] if socket else []) + (["-CC"] if control else [])
    return " ".join(parts + ["attach", "-t", f"={session}"])


def _new_window(
    runner: Runner, environ: Mapping[str, str], place: list[str], directory: str, command: str,
    window_name: str | None, environment: dict[str, str],
) -> str:
    args = ["new-window", "-d", "-P", "-F", "#{window_id}", *place,
            *_window_arguments(directory, window_name, environment, command)]
    return _tmux(runner, environ, "new-window", *args).strip()


def _window_arguments(directory: str, window_name: str | None, environment: dict[str, str],
                      command: str) -> list[str]:
    """The name, directory, environment and command of a window, in the order tmux takes them."""
    args = ["-n", window_name] if window_name else []
    args += ["-c", directory]
    for key in sorted(environment):
        args += ["-e", f"{key}={environment[key]}"]
    return args + [f'{command}; exec "${{SHELL:-/bin/zsh}}" -l']


def repo_key(path: str) -> str:
    """The repository of a directory: the folder holding its git common dir; outside git, the directory itself."""
    return _repo_key(path, default_runner)


def repo_session_name(repo: str) -> str:
    """The tmux session of a repository: its folder name as a slug, then the first 6 hex characters of the SHA-1 of its path."""
    folder = Path(repo).name
    slug = re.sub(r"[^a-z0-9]+", "-", folder.lower()).strip("-")
    slug = slug[: SESSION_NAME_LIMIT - 7].rstrip("-") or "repo"
    digest = hashlib.sha1(repo.encode()).hexdigest()[:6]
    return f"{slug}-{digest}"


def _repo_key(path: str, runner: Runner) -> str:
    result = runner(["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir"], None)
    common = result.stdout.strip()
    if result.returncode == 0 and common:
        return os.path.dirname(common)
    return os.path.realpath(path)


def _tmux_args(environ: Mapping[str, str], args: Sequence[str]) -> list[str]:
    socket = environ.get("BKF_TMUX_SOCKET")
    return ["tmux", *(["-L", socket] if socket else []), *args]


def _tmux_status(runner: Runner, environ: Mapping[str, str], *args: str) -> Result:
    return runner(_tmux_args(environ, args), None)


def _tmux(runner: Runner, environ: Mapping[str, str], step: str, *args: str) -> str:
    """Run one tmux call and return its standard output; a failing call raises TmuxError."""
    result = _tmux_status(runner, environ, *args)
    if result.returncode != 0:
        detail = " ".join(result.stderr.split()) or "no error text"
        raise TmuxError(f"tmux {step} failed: {detail}")
    return result.stdout


def _display(runner: Runner, environ: Mapping[str, str], pane: str, fmt: str) -> str:
    return _tmux(runner, environ, "display-message", "display-message", "-p", "-t", pane, fmt).strip()


def _osascript(runner: Runner, script: str, *argv: str) -> Result:
    return runner(["osascript", "-", *argv], script)

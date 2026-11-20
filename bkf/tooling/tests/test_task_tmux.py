"""Tests task_tmux: the exact tmux, git and osascript calls with a fake runner, and placement on a throwaway tmux server."""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid

import task_tmux
from task_tmux import Result, TmuxError, default_runner, open_window, repo_key, repo_session_name


ENV = {"TERM_PROGRAM": "other"}


def wrapped(command: str) -> str:
    return f'{command}; exec "${{SHELL:-/bin/zsh}}" -l'


REPOS = {  # directory -> git common dir; the repository key is the folder holding it
    "/work/a": "/work/a/.git",
    "/work/a-wt": "/work/a/.git",
    "/work/b": "/work/b/.git",
}


class FakeTmux:
    """A runner that records every call and answers the calls the module makes."""

    def __init__(self, *, clients: str = "", attached_clients: str = "", pane_path: str = "/work/a",
                 listing: str = "", session_exists: bool = True, focus_output: str = "",
                 fail: dict[str, Result] | None = None):
        self.calls: list[tuple[list[str], str | None]] = []
        self.clients = clients
        self.attached_clients = attached_clients
        self.pane_path = pane_path
        self.listing = listing
        self.session_exists = session_exists
        self.focus_output = focus_output
        self.fail = fail or {}

    def __call__(self, args, stdin=None):
        args = list(args)
        self.calls.append((args, stdin))
        if args[0] == "git":
            common = REPOS.get(args[2])
            if common is None:
                return Result(128, "", "fatal: not a git repository")
            return Result(0, common + "\n", "")
        if args[0] == "osascript":
            return Result(0, self.focus_output + "\n", "")
        tmux_args = args[3:] if args[1] == "-L" else args[1:]
        command = tmux_args[0]
        if command in self.fail:
            return self.fail[command]
        if command == "display-message":
            fmt = tmux_args[-1]
            values = {"#{window_id}": "@1", "#{session_id}": "$0", "#{session_name}": "main",
                      "#{pane_current_path}": self.pane_path}
            return Result(0, values[fmt] + "\n", "")
        if command == "list-clients":
            return Result(0, self.attached_clients if "#{client_name}" in tmux_args else self.clients, "")
        if command == "list-panes":
            return Result(0, self.listing, "")
        if command == "has-session":
            return Result(0 if self.session_exists else 1, "", "")
        if command in ("new-window", "new-session"):
            return Result(0, "@9\n", "")
        return Result(0, "", "")

    def tmux_commands(self) -> list[list[str]]:
        return [args for args, _ in self.calls if args[0] == "tmux"]

    def osascript_calls(self) -> list[tuple[list[str], str | None]]:
        return [(args, stdin) for args, stdin in self.calls if args[0] == "osascript"]


INSIDE = {"TMUX": "/tmp/tmux-1/default,1,0", "TMUX_PANE": "%1"}


def open_inside(runner, *, directory="/work/a", environ=None, **kwargs):
    return open_window(directory=directory, command="crew", window_name="crew", repo=directory,
                       environ={**INSIDE, **(environ or {})}, runner=runner, **kwargs)


def new_window_args(runner: FakeTmux) -> list[str]:
    """The arguments of the new-window call, without the program and any socket prefix."""
    args = next(args for args in runner.tmux_commands() if "new-window" in args)
    return args[3:] if args[1] == "-L" else args[1:]


def place_of(args: list[str]) -> list[str]:
    """The placement arguments of a new-window call: after -F's format, before -n or -c."""
    return args[5:args.index("-n")] if "-n" in args else args[5:args.index("-c")]


class PlacementTests(unittest.TestCase):
    def test_inside_tmux_same_repository_goes_right_after_the_caller(self):
        runner = FakeTmux(pane_path="/work/a")
        window = open_inside(runner, directory="/work/a-wt")
        self.assertEqual(
            new_window_args(runner),
            ["new-window", "-d", "-P", "-F", "#{window_id}", "-a", "-t", "@1",
             "-n", "crew", "-c", "/work/a-wt", wrapped("crew")],
        )
        self.assertEqual(window.session, "main")
        self.assertEqual(window.window_id, "@9")
        self.assertFalse(window.needs_attach)

    def test_inside_tmux_other_repository_goes_after_the_last_window_of_its_repository(self):
        listing = "@1 0 /work/a\n@2 1 /work/b\n@3 2 /work/a\n@4 3 /work/b\n"
        runner = FakeTmux(pane_path="/work/a", listing=listing)
        open_inside(runner, directory="/work/b")
        self.assertEqual(place_of(new_window_args(runner)), ["-a", "-t", "@4"])

    def test_inside_tmux_repository_with_no_window_goes_to_the_end_of_the_session(self):
        listing = "@1 0 /work/a\n@2 1 /work/a\n"
        runner = FakeTmux(pane_path="/work/a", listing=listing)
        open_inside(runner, directory="/work/b")
        self.assertEqual(place_of(new_window_args(runner)), ["-t", "$0:2"])

    def test_inside_tmux_repository_of_the_caller_is_found_by_its_common_dir(self):
        runner = FakeTmux(pane_path="/work/a-wt")
        open_inside(runner, directory="/work/a")
        self.assertEqual(place_of(new_window_args(runner)), ["-a", "-t", "@1"])

    def test_focus_is_restored_only_around_a_control_mode_client(self):
        runner = FakeTmux(clients="1\n", focus_output="4 5 2")
        open_inside(runner, directory="/work/a")
        osascripts = runner.osascript_calls()
        self.assertEqual(len(osascripts), 2)
        self.assertEqual(osascripts[0][0], ["osascript", "-", "1"])
        self.assertEqual(osascripts[0][1], task_tmux.ITERM_FOCUS_SCRIPT)
        self.assertEqual(osascripts[1][0], ["osascript", "-", "4", "5", "2"])
        self.assertEqual(osascripts[1][1], task_tmux.ITERM_RESTORE_SCRIPT)
        positions = [i for i, (args, _) in enumerate(runner.calls) if args[0] == "osascript"]
        new_window_at = next(i for i, (args, _) in enumerate(runner.calls) if "new-window" in args)
        self.assertLess(positions[0], new_window_at)
        self.assertGreater(positions[1], new_window_at)

    def test_no_applescript_without_a_control_mode_client(self):
        runner = FakeTmux(clients="0\n")
        open_inside(runner, directory="/work/a")
        self.assertEqual(runner.osascript_calls(), [])

    def test_the_socket_prefix_and_environment_flags_sorted_by_key(self):
        runner = FakeTmux(pane_path="/work/a")
        open_inside(runner, directory="/work/a", environ={"BKF_TMUX_SOCKET": "sock-x"})
        self.assertEqual(runner.tmux_commands()[0][:3], ["tmux", "-L", "sock-x"])
        self.assertEqual(new_window_args(runner)[0], "new-window")

        runner = FakeTmux(pane_path="/work/a")
        open_window(directory="/work/a", command="crew", repo="/work/a", window_name=None,
                    environment={"Z_LAST": "1", "A_FIRST": "two"}, environ={**INSIDE},
                    runner=runner)
        args = new_window_args(runner)
        self.assertNotIn("-n", args)
        self.assertEqual(args[args.index("-e"):args.index("-e") + 4], ["-e", "A_FIRST=two", "-e", "Z_LAST=1"])
        self.assertEqual(args[-1], wrapped("crew"))

    def test_tmux_without_pane_is_an_error(self):
        with self.assertRaises(TmuxError):
            open_window(directory="/work/a", command="crew", repo="/work/a",
                        environ={"TMUX": "x"}, runner=FakeTmux())

    def test_outside_tmux_new_session_is_created_with_the_requested_window(self):
        runner = FakeTmux(session_exists=False)
        window = open_window(directory="/work/a", command="crew", repo="/work/a", size=(120, 40),
                             attach=False, environ=ENV, runner=runner, window_name="crew",
                             environment={"Z_LAST": "1", "A_FIRST": "two"})
        name = repo_session_name("/work/a")
        commands = runner.tmux_commands()
        self.assertEqual(commands[0], ["tmux", "has-session", "-t", f"={name}"])
        self.assertEqual(commands[1], ["tmux", "new-session", "-d", "-P", "-F", "#{window_id}",
                                       "-s", name, "-x", "120", "-y", "40", "-n", "crew",
                                       "-c", "/work/a", "-e", "A_FIRST=two", "-e", "Z_LAST=1",
                                       wrapped("crew")])
        self.assertFalse(any(args[1:2] == ["new-window"] for args in commands))
        self.assertEqual(window, task_tmux.Window(session=name, window_id="@9", needs_attach=True))

    def test_outside_tmux_new_session_without_size_name_or_environment(self):
        runner = FakeTmux(session_exists=False)
        open_window(directory="/work/a", command="crew", repo="/work/a", attach=False,
                    environ=ENV, runner=runner)
        self.assertEqual(runner.tmux_commands()[1],
                         ["tmux", "new-session", "-d", "-P", "-F", "#{window_id}",
                          "-s", repo_session_name("/work/a"), "-c", "/work/a", wrapped("crew")])

    def test_outside_tmux_existing_session_gets_the_window_at_its_end(self):
        runner = FakeTmux(session_exists=True)
        open_window(directory="/work/a", command="crew", repo="/work/a", attach=False,
                    environ=ENV, runner=runner)
        self.assertFalse(any("new-session" in args for args in runner.tmux_commands()))
        self.assertEqual(new_window_args(runner)[:7],
                         ["new-window", "-d", "-P", "-F", "#{window_id}", "-t",
                          f"={repo_session_name('/work/a')}:"])

    def test_outside_tmux_existing_session_with_a_client_gets_no_second_terminal(self):
        runner = FakeTmux(session_exists=True, attached_clients="/dev/ttys004\n")
        window = open_window(directory="/work/a", command="crew", repo="/work/a",
                             environ={"TERM_PROGRAM": "iTerm.app"}, runner=runner)
        self.assertEqual(runner.osascript_calls(), [])
        self.assertFalse(window.needs_attach)
        self.assertIn(["tmux", "list-clients", "-t", f"={repo_session_name('/work/a')}",
                       "-F", "#{client_name}"], runner.tmux_commands())

    def test_outside_tmux_existing_session_without_a_client_and_no_attach_needs_attach(self):
        runner = FakeTmux(session_exists=True)
        window = open_window(directory="/work/a", command="crew", repo="/work/a", attach=False,
                             environ={"TERM_PROGRAM": "iTerm.app"}, runner=runner)
        self.assertTrue(window.needs_attach)
        self.assertEqual(runner.osascript_calls(), [])

    def test_outside_tmux_new_session_with_a_client_gets_no_second_terminal(self):
        runner = FakeTmux(session_exists=False, attached_clients="/dev/ttys004\n")
        window = open_window(directory="/work/a", command="crew", repo="/work/a",
                             environ={"TERM_PROGRAM": "Apple_Terminal"}, runner=runner)
        self.assertEqual(runner.osascript_calls(), [])
        self.assertFalse(window.needs_attach)

    def test_iterm_attaches_with_control_mode_through_applescript(self):
        runner = FakeTmux(session_exists=True)
        window = open_window(directory="/work/a", command="crew", repo="/work/a",
                             environ={"TERM_PROGRAM": "iTerm.app"}, runner=runner)
        name = repo_session_name("/work/a")
        calls = runner.osascript_calls()
        self.assertEqual(calls, [(["osascript", "-", f"tmux -CC attach -t ={name}"],
                                  task_tmux.ITERM_NEW_WINDOW_SCRIPT)])
        self.assertFalse(window.needs_attach)

    def test_terminal_attaches_with_do_script(self):
        runner = FakeTmux(session_exists=True)
        window = open_window(directory="/work/a", command="crew", repo="/work/a",
                             environ={"TERM_PROGRAM": "Apple_Terminal"}, runner=runner)
        name = repo_session_name("/work/a")
        self.assertEqual(runner.osascript_calls(),
                         [(["osascript", "-", f"tmux attach -t ={name}"], task_tmux.TERMINAL_DO_SCRIPT)])
        self.assertFalse(window.needs_attach)

    def test_the_socket_is_part_of_the_attach_command(self):
        runner = FakeTmux(session_exists=True)
        open_window(directory="/work/a", command="crew", repo="/work/a",
                    environ={"TERM_PROGRAM": "Apple_Terminal", "BKF_TMUX_SOCKET": "s1"}, runner=runner)
        self.assertEqual(runner.osascript_calls()[0][0][2], f"tmux -L s1 attach -t ={repo_session_name('/work/a')}")

    def test_elsewhere_the_caller_gets_the_attach_line_on_standard_error(self):
        runner = FakeTmux(session_exists=True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            window = open_window(directory="/work/a", command="crew", repo="/work/a",
                                 environ={"TERM_PROGRAM": "xterm"}, runner=runner)
        name = repo_session_name("/work/a")
        self.assertTrue(window.needs_attach)
        self.assertIn(f"tmux attach -t ={name}", err.getvalue())
        self.assertEqual(runner.osascript_calls(), [])

    def test_a_failing_attach_falls_back_to_the_attach_line(self):
        class Refusing(FakeTmux):
            def __call__(self, args, stdin=None):
                if args[0] == "osascript":
                    self.calls.append((list(args), stdin))
                    return Result(1, "", "not allowed")
                return super().__call__(args, stdin)

        runner = Refusing(session_exists=True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            window = open_window(directory="/work/a", command="crew", repo="/work/a",
                                 environ={"TERM_PROGRAM": "iTerm.app"}, runner=runner)
        self.assertTrue(window.needs_attach)
        self.assertIn("tmux attach -t =", err.getvalue())

    def test_attach_false_does_not_touch_the_terminal(self):
        runner = FakeTmux(session_exists=True)
        window = open_window(directory="/work/a", command="crew", repo="/work/a", attach=False,
                             environ={"TERM_PROGRAM": "iTerm.app"}, runner=runner)
        self.assertTrue(window.needs_attach)
        self.assertEqual(runner.osascript_calls(), [])

    def test_a_failing_tmux_call_raises_with_the_step_and_stderr_on_one_line(self):
        runner = FakeTmux(fail={"new-window": Result(1, "", "no space\nfor window\n")})
        with self.assertRaises(TmuxError) as raised:
            open_inside(runner)
        self.assertEqual(str(raised.exception), "tmux new-window failed: no space for window")

    def test_a_missing_tmux_raises(self):
        def missing(args, stdin=None):
            return Result(127, "", "tmux is not installed or not on PATH")

        with self.assertRaisesRegex(TmuxError, "new-session failed"):
            open_window(directory="/work/a", command="crew", repo="/work/a", attach=False,
                        environ=ENV, runner=missing)

    def test_default_runner_reports_a_missing_program_without_raising(self):
        self.assertEqual(default_runner(["bkf-no-such-program-for-tests"]).returncode, 127)


class RepositoryNameTests(unittest.TestCase):
    def test_session_name_is_the_slug_and_the_hash_of_the_path(self):
        digest = hashlib.sha1("/work/My Repo.v2".encode()).hexdigest()[:6]
        self.assertEqual(repo_session_name("/work/My Repo.v2"), f"my-repo-v2-{digest}")

    def test_a_long_slug_is_cut_and_the_hash_kept(self):
        name = repo_session_name("/work/" + "x" * 60)
        digest = hashlib.sha1(("/work/" + "x" * 60).encode()).hexdigest()[:6]
        self.assertLessEqual(len(name), 48)
        self.assertEqual(name, "x" * 41 + f"-{digest}")

    def test_a_folder_without_a_name_is_called_repo(self):
        self.assertTrue(repo_session_name("/").startswith("repo-"))

    def test_repo_key_is_the_folder_holding_the_common_dir(self):
        self.assertEqual(task_tmux._repo_key("/work/a-wt", FakeTmux()), "/work/a")

    def test_repo_key_outside_git_is_the_directory_itself(self):
        plain = os.path.realpath("/work/plain")
        self.assertEqual(task_tmux._repo_key("/work/plain", FakeTmux()), plain)


@unittest.skipUnless(shutil.which("tmux"), "tmux is not on PATH")
class RealTmuxTests(unittest.TestCase):
    def setUp(self):
        self.sock = f"bkf-tmux-test-{uuid.uuid4().hex[:10]}"
        self.tmp = tempfile.TemporaryDirectory()
        root = os.path.realpath(self.tmp.name)
        self.repo_a = os.path.join(root, "a")
        self.repo_b = os.path.join(root, "b")
        self.repo_c = os.path.join(root, "c")
        self.worktree_a = os.path.join(root, "a-wt")
        self.plain1 = os.path.join(root, "plain1")
        self.plain2 = os.path.join(root, "plain2")
        for path in (self.repo_a, self.repo_b, self.repo_c, self.plain1, self.plain2):
            os.makedirs(path)
        for path in (self.repo_a, self.repo_b, self.repo_c):
            subprocess.run(["git", "-C", path, "init", "-q"], check=True)
            subprocess.run(["git", "-C", path, "-c", "user.name=t", "-c", "user.email=t@t",
                            "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        subprocess.run(["git", "-C", self.repo_a, "worktree", "add", "-q", self.worktree_a],
                       check=True, capture_output=True)
        self.environ = {"BKF_TMUX_SOCKET": self.sock, "TERM_PROGRAM": "other"}

    def tearDown(self):
        subprocess.run(["tmux", "-L", self.sock, "kill-server"], capture_output=True, check=False)
        self.tmp.cleanup()

    def tmux(self, *args: str) -> str:
        return subprocess.run(["tmux", "-L", self.sock, *args], capture_output=True, text=True,
                              check=True).stdout

    def wait_for(self, path: str) -> str:
        for _ in range(100):
            if os.path.exists(path) and os.path.getsize(path):
                break
            time.sleep(0.05)
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_outside_tmux_windows_of_a_repository_share_one_session(self):
        first = open_window(directory=self.repo_a, command="sleep 60", repo=self.repo_a,
                            attach=False, environ=self.environ)
        second = open_window(directory=self.worktree_a, command="sleep 60", repo=self.repo_a,
                             attach=False, environ=self.environ)
        name = repo_session_name(self.repo_a)
        self.assertEqual(first.session, name)
        self.assertEqual(second.session, name)
        ids = self.tmux("list-windows", "-t", f"={name}", "-F", "#{window_id}").split()
        self.assertIn(first.window_id, ids)
        self.assertIn(second.window_id, ids)
        self.assertTrue(first.needs_attach)

    def test_a_new_session_has_exactly_the_requested_window(self):
        window = open_window(directory=self.repo_b, command="sleep 60", window_name="crew",
                             repo=self.repo_b, attach=False, environ=self.environ)
        listed = self.tmux("list-windows", "-t", f"={window.session}", "-F",
                           "#{window_id} #{window_name}").split("\n")
        self.assertEqual([line for line in listed if line], [f"{window.window_id} crew"])

    def test_a_window_for_another_repository_gets_its_own_session(self):
        open_window(directory=self.repo_a, command="sleep 60", repo=self.repo_a,
                    attach=False, environ=self.environ)
        other = open_window(directory=self.repo_b, command="sleep 60", repo=self.repo_b,
                            attach=False, environ=self.environ)
        self.assertEqual(other.session, repo_session_name(self.repo_b))
        sessions = self.tmux("list-sessions", "-F", "#{session_name}").split()
        self.assertIn(repo_session_name(self.repo_a), sessions)
        self.assertIn(repo_session_name(self.repo_b), sessions)

    def test_the_environment_and_the_directory_reach_the_command(self):
        marker = os.path.join(self.tmp.name, "marker")
        window = open_window(directory=self.repo_c, repo=self.repo_c, attach=False, environ=self.environ,
                             environment={"BKF_TEST_VALUE": "visible"},
                             command=f'printf "%s %s\\n" "$BKF_TEST_VALUE" "$(pwd -P)" >"{marker}"')
        self.assertEqual(self.wait_for(marker), f"visible {self.repo_c}\n")
        self.assertEqual(self.tmux("list-windows", "-t", f"={window.session}", "-F", "#{window_id}").split(),
                         [window.window_id])

    def test_a_login_shell_stays_after_the_command(self):
        marker = os.path.join(self.tmp.name, "done")
        window = open_window(directory=self.repo_b, repo=self.repo_b, attach=False,
                             environ=self.environ, command=f'touch "{marker}"')
        for _ in range(100):
            if os.path.exists(marker):
                break
            time.sleep(0.05)
        self.assertTrue(os.path.exists(marker), "the command did not run")
        time.sleep(1)
        ids = self.tmux("list-windows", "-t", f"={window.session}", "-F", "#{window_id}").split()
        self.assertIn(window.window_id, ids)

    def placement(self, caller_dir: str, target: str, others: list[tuple[str, str]]) -> str:
        """Start a server whose caller window is in caller_dir, add the others, open a window for target."""
        subprocess.run(["tmux", "-L", self.sock, "kill-server"], capture_output=True, check=False)
        self.tmux("new-session", "-d", "-s", "main", "-n", "caller", "-c", caller_dir, "sleep 600")
        for name, directory in others:
            self.tmux("new-window", "-d", "-t", "main:", "-n", name, "-c", directory, "sleep 600")
        pane = self.tmux("display-message", "-p", "-t", "main:caller", "#{pane_id}").strip()
        open_window(directory=target, command="true", window_name="new", repo=target,
                    environ={"TMUX": "inside", "TMUX_PANE": pane, **self.environ}, attach=False)
        return ",".join(self.tmux("list-windows", "-t", "main", "-F", "#{window_name}").split())

    def test_inside_tmux_same_repository_goes_right_after_the_caller(self):
        self.assertEqual(self.placement(self.repo_a, self.repo_a,
                                        [("b1", self.repo_b), ("a2", self.repo_a)]),
                         "caller,new,b1,a2")

    def test_inside_tmux_a_worktree_of_the_repository_counts_as_the_same(self):
        self.assertEqual(self.placement(self.repo_a, self.worktree_a,
                                        [("b1", self.repo_b), ("a2", self.repo_a)]),
                         "caller,new,b1,a2")

    def test_inside_tmux_another_repository_goes_after_the_last_of_its_windows(self):
        self.assertEqual(self.placement(self.repo_a, self.repo_b,
                                        [("b1", self.repo_b), ("a2", self.repo_a),
                                         ("b2", self.repo_b), ("a3", self.repo_a)]),
                         "caller,b1,a2,b2,new,a3")

    def test_inside_tmux_a_repository_with_no_window_goes_to_the_end(self):
        self.assertEqual(self.placement(self.repo_a, self.repo_c,
                                        [("b1", self.repo_b), ("a2", self.repo_a)]),
                         "caller,b1,a2,new")

    def test_inside_tmux_a_subdirectory_belongs_to_its_repository(self):
        sub = os.path.join(self.repo_b, "sub")
        os.makedirs(sub)
        self.assertEqual(self.placement(self.repo_a, sub,
                                        [("b1", self.repo_b), ("a2", self.repo_a)]),
                         "caller,b1,new,a2")

    def test_inside_tmux_outside_git_the_directory_is_the_key(self):
        self.assertEqual(self.placement(self.plain1, self.plain2,
                                        [("p1", self.plain1), ("p2", self.plain2), ("p3", self.plain1)]),
                         "caller,p1,p2,new,p3")


if __name__ == "__main__":
    unittest.main()

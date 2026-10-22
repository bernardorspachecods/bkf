import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class GateCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()

    def run_cli(self, out, *commands, timeout="5", notes=()):
        args = [
            sys.executable,
            "-m",
            "harness",
            "gate",
            "run",
            "--cwd",
            str(self.cwd),
            "--timeout",
            str(timeout),
            "--out",
            str(out),
        ]
        for note in notes:
            args.extend(["--note", note])
        args.append("--")
        args.extend(commands)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT)
        return subprocess.run(args, cwd=str(PROJECT), env=env, text=True, capture_output=True)

    def test_green_exact_markdown_json_working_directory_and_closed_stdin(self):
        out = self.root / "output"
        command = "pwd; if read -r value; then echo stdin-open; else echo stdin-closed; fi"
        result = self.run_cli(out, command, notes=("first note", "second note"))

        self.assertEqual(result.returncode, 0, result.stderr)
        log = "\n".join([str(self.cwd.resolve()), "stdin-closed", ""])
        self.assertEqual((out / "gate-1.log").read_text(), log)
        expected = (
            "# Gate\n\n"
            "The harness ran these commands in {cwd}, outside any agent.\n"
            "first note\n"
            "second note\n\n"
            "Result: all green (1 commands).\n\n"
            "### `{command}`\n\n"
            "exit code: 0\n\n"
            "~~~~\n"
            "{log}"
            "~~~~\n"
        ).format(cwd=self.cwd, command=command, log=log)
        self.assertEqual((out / "gate.md").read_text(), expected)
        data = json.loads((out / "gate.json").read_text())
        self.assertEqual(data["cwd"], str(self.cwd))
        self.assertEqual(data["timeout"], 5.0)
        self.assertEqual(data["red"], 0)
        self.assertEqual(
            {key: value for key, value in data["commands"][0].items() if key != "seconds"},
            {
                "command": command,
                "exit_code": 0,
                "timed_out": False,
                "log": "gate-1.log",
            },
        )
        seconds = data["commands"][0]["seconds"]
        self.assertIsInstance(seconds, (int, float))
        self.assertGreaterEqual(seconds, 0)

    def test_red_preserves_code_tail_and_runs_later_command(self):
        out = self.root / "red"
        first = "echo before; echo failed >&2; exit 7"
        result = self.run_cli(out, first, "echo after")

        self.assertEqual(result.returncode, 1)
        self.assertEqual((out / "gate-1.log").read_text(), "before\nfailed\n")
        self.assertEqual((out / "gate-2.log").read_text(), "after\n")
        self.assertEqual(
            (out / "gate.md").read_text(),
            "# Gate\n\n"
            "The harness ran these commands in {cwd}, outside any agent.\n\n"
            "Result: RED, 1 of 2 commands failed. A reviewer cannot override a red result.\n\n"
            "### `{first}`\n\n"
            "exit code: 7\n\n"
            "~~~~\n"
            "before\nfailed\n"
            "~~~~\n\n"
            "### `echo after`\n\n"
            "exit code: 0\n\n"
            "~~~~\n"
            "after\n"
            "~~~~\n".format(cwd=self.cwd, first=first),
        )
        data = json.loads((out / "gate.json").read_text())
        self.assertEqual([entry["exit_code"] for entry in data["commands"]], [7, 0])
        self.assertEqual(data["red"], 1)

    def test_markdown_closing_fence_starts_after_unterminated_log_output(self):
        out = self.root / "unterminated"
        result = self.run_cli(out, "printf x")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            (out / "gate.md").read_text(),
            "# Gate\n\n"
            "The harness ran these commands in {cwd}, outside any agent.\n\n"
            "Result: all green (1 commands).\n\n"
            "### `printf x`\n\n"
            "exit code: 0\n\n"
            "~~~~\n"
            "x\n"
            "~~~~\n".format(cwd=self.cwd),
        )

    def test_log_keeps_all_output_but_markdown_has_only_last_100_lines(self):
        out = self.root / "tail"
        command = "seq 1 105"
        result = self.run_cli(out, command)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len((out / "gate-1.log").read_text().splitlines()), 105)
        markdown = (out / "gate.md").read_text()
        tail = markdown.split("~~~~\n", 1)[1].rsplit("\n~~~~", 1)[0].splitlines()
        self.assertEqual(len(tail), 100)
        self.assertEqual(tail[0], "6")
        self.assertEqual(tail[-1], "105")
        self.assertTrue(markdown.endswith("\n~~~~\n"))

    def test_no_commands_is_a_gap_and_passes(self):
        out = self.root / "empty"
        result = self.run_cli(out)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            (out / "gate.md").read_text(),
            "# Gate\n\nThe harness ran these commands in {cwd}, outside any agent.\n"
            "No gate commands were given, so no checks were run. This is a gap, not a pass.\n".format(
                cwd=self.cwd
            ),
        )
        data = json.loads((out / "gate.json").read_text())
        self.assertEqual(data["commands"], [])
        self.assertEqual(data["red"], 0)

    def test_non_finite_timeout_is_a_usage_error(self):
        out = self.root / "invalid-timeout"
        result = self.run_cli(out, "true", timeout="nan")

        self.assertEqual(result.returncode, 2)
        self.assertIn("--timeout must be a finite number greater than zero", result.stderr)
        self.assertFalse(out.exists())

    def test_timeout_kills_background_process_group_and_records_124(self):
        out = self.root / "timeout"
        child_pid_file = self.root / "child.pid"
        command = "sleep 30 & echo $! > {pidfile}; wait".format(pidfile=child_pid_file)
        result = self.run_cli(out, command, timeout="1")

        self.assertEqual(result.returncode, 1)
        child_pid = int(child_pid_file.read_text())
        self.assertFalse(_process_exists(child_pid), "timed-out background child is still alive")
        data = json.loads((out / "gate.json").read_text())
        entry = data["commands"][0]
        self.assertEqual(entry["exit_code"], 124)
        self.assertTrue(entry["timed_out"])
        self.assertEqual(
            (out / "gate.md").read_text(),
            "# Gate\n\n"
            "The harness ran these commands in {cwd}, outside any agent.\n\n"
            "Result: RED, 1 of 1 commands failed. A reviewer cannot override a red result.\n\n"
            "### `{command}`\n\n"
            "exit code: 124 (timed out after 1 seconds)\n\n"
            "~~~~\n~~~~\n".format(cwd=self.cwd, command=command),
        )

    def test_timeout_sends_term_to_background_child_before_escalation(self):
        out = self.root / "term-trap-child"
        marker_file = self.root / "term-received"
        marker = shlex.quote(str(marker_file))
        command = (
            "bash -c 'trap \"printf term > {marker}; exit 0\" TERM; "
            "while :; do sleep 0.1; done' & wait"
        ).format(marker=marker)

        result = self.run_cli(out, command, timeout="1")

        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            marker_file.exists(),
            "background child did not handle SIGTERM before the SIGKILL escalation",
        )
        data = json.loads((out / "gate.json").read_text())
        self.assertEqual(data["commands"][0]["exit_code"], 124)
        self.assertTrue(data["commands"][0]["timed_out"])

    def test_timeout_kills_child_that_ignores_term_after_escalation(self):
        out = self.root / "term-ignoring-child"
        child_pid_file = self.root / "term-ignoring-child.pid"
        process_group_file = self.root / "term-ignoring-child.pgid"
        command = (
            "echo $$ > {pgidfile}; "
            "bash -c 'trap \"\" TERM; echo $$ > {pidfile}; exec sleep 30' & wait"
        ).format(pgidfile=process_group_file, pidfile=child_pid_file)

        result = self.run_cli(out, command, timeout="1")

        self.assertEqual(result.returncode, 1)
        child_pid = int(child_pid_file.read_text())
        process_group = int(process_group_file.read_text())
        self.assertFalse(_process_exists(child_pid), "SIGTERM-ignoring child is still alive")
        self.assertFalse(_process_group_exists(process_group), "timed-out process group is still alive")
        data = json.loads((out / "gate.json").read_text())
        entry = data["commands"][0]
        self.assertEqual(entry["exit_code"], 124)
        self.assertTrue(entry["timed_out"])
        self.assertGreaterEqual(entry["seconds"], 2.9)

    def test_completed_shell_does_not_leave_its_background_child(self):
        out = self.root / "background"
        child_pid_file = self.root / "background-child.pid"
        command = "sleep 30 & echo $! > {pidfile}".format(pidfile=child_pid_file)

        result = self.run_cli(out, command)

        self.assertEqual(result.returncode, 0)
        child_pid = int(child_pid_file.read_text())
        self.assertFalse(_process_exists(child_pid), "completed command left a background child alive")


def _process_exists(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _process_group_exists(process_group):
    try:
        os.killpg(process_group, 0)
    except OSError:
        return False
    return True


if __name__ == "__main__":
    unittest.main()

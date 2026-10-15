from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

import bkf_cli


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                status = bkf_cli.main(list(arguments))
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def test_entry_points_list_all_commands_with_summary_and_use_line(self) -> None:
        expected_commands = [
            *(
                (name, summary, when)
                for name, (_, summary, when) in bkf_cli.COMMANDS.items()
            ),
            bkf_cli.HELP_COMMAND,
        ]
        width = max(len(name) for name, _, _ in expected_commands)
        for arguments in ((), ("help",), ("--help",)):
            with self.subTest(arguments=arguments):
                status, output, error = self.run_cli(*arguments)
                self.assertEqual(status, 0)
                self.assertEqual(error, "")
                for name, summary, when in expected_commands:
                    self.assertIn(f"  {name.ljust(width)}  {summary}", output)
                    self.assertIn(f"  {' ' * width}  use: {when}", output)

    def test_help_for_each_command_shows_bkf_usage(self) -> None:
        for name in bkf_cli.COMMANDS:
            with self.subTest(command=name):
                status, output, error = self.run_cli("help", name)
                self.assertEqual(status, 0)
                self.assertIn(f"usage: bkf {name}", output)
                self.assertEqual(error, "")

    def test_unknown_help_and_commands_exit_two(self) -> None:
        for arguments in (("help", "nope"), ("help", "help"), ("nope",)):
            with self.subTest(arguments=arguments):
                status, _, _ = self.run_cli(*arguments)
                self.assertEqual(status, 2)

    def test_every_command_has_a_documentation_heading(self) -> None:
        commands_doc = Path(__file__).resolve().parents[1] / "commands.md"
        content = commands_doc.read_text(encoding="utf-8")
        for name in bkf_cli.COMMANDS:
            with self.subTest(command=name):
                self.assertIn(f"## bkf {name}", content)


if __name__ == "__main__":
    unittest.main()

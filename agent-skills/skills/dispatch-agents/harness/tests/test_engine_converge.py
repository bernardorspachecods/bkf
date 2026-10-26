import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.engine.converge import gate_signature, problem_files


class ConvergeTests(unittest.TestCase):
    def gate(self, command, output, path="/tmp/run-123/file"):
        return (
            "# Gate\n\nResult: RED, 1 of 1 commands failed.\n\n"
            "### `{0}`\n\nexit code: 1\n\n~~~~\n{1} {2} after 12.5 seconds\n~~~~\n"
        ).format(command, output, path)

    def test_signature_ignores_numbers_and_temporary_paths(self):
        first = gate_signature(self.gate("pytest test_x.py", "FAILED test_x.py:12"))
        second = gate_signature(self.gate("pytest test_x.py", "FAILED test_x.py:98", "/private/tmp/other-456/x"))
        self.assertEqual(first, second)

    def test_signature_differs_for_another_failing_test(self):
        first = gate_signature(self.gate("pytest", "FAILED test_x.py:12"))
        second = gate_signature(self.gate("pytest", "FAILED test_y.py:12"))
        self.assertNotEqual(first, second)

    def test_signature_keeps_failed_command_order_and_commands_with_backticks(self):
        gate = (
            "### `echo `one``\n\nexit code: 1\n\n~~~~\nFAIL one\n~~~~\n"
            "### `echo two`\n\nexit code: 1\n\n~~~~\nERROR two\n~~~~\n"
        )
        self.assertEqual(
            gate_signature(gate),
            (("echo `one`", "echo two"), frozenset(("FAIL one", "ERROR two"))),
        )

    def test_problem_files_extracts_only_file_tokens_from_problems(self):
        text = (
            "## What I checked\n- `ignored.py`\n\n## Problems\n"
            "- Fix `src/one.py` and `README.md`; `not a file`\n\n"
            "## Notes\n- `later.txt`\n"
        )
        self.assertEqual(problem_files(text), {"src/one.py", "README.md"})


if __name__ == "__main__":
    unittest.main()

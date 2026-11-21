import sys
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))

from git_guard import check  # noqa: E402


def call(command, tool="Bash"):
    return check({"tool_name": tool, "tool_input": {"command": command}})


class GitGuardTests(unittest.TestCase):
    def test_discarding_commands_ask(self):
        for command in (
            "git branch -D old",
            "git -C /tmp/x branch -D old",
            "git branch -d -f old",
            "git branch --delete --force old",
            "git worktree remove --force ../wt",
            "git worktree remove -f ../wt",
            "git clean -fd",
            "git reset --hard HEAD~1",
            "git push --force origin main",
            "git push -f",
            "cd x && git branch -D old",
            "bash -c 'git branch -D old'",
        ):
            result = call(command)
            self.assertIsNotNone(result, command)
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "ask", command)

    def test_safe_commands_pass(self):
        for command in (
            "git branch -d merged",
            "git branch",
            "git branch -a",
            "git worktree remove ../wt",
            "git worktree list",
            "git reset HEAD file",
            "git push origin main",
            "git status",
            "echo git branch -D old",
            "grep 'git clean' notes.md",
        ):
            self.assertIsNone(call(command), command)

    def test_other_tools_pass(self):
        self.assertIsNone(call("git branch -D old", tool="Read"))


if __name__ == "__main__":
    unittest.main()

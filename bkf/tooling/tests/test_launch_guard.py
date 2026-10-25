import json
import sys
import unittest
import unittest.mock
from pathlib import Path

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))

from launch_guard import REASON, check  # noqa: E402


def call(command, background=False, tool="Bash"):
    return check({"tool_name": tool, "tool_input": {"command": command, "run_in_background": background}})


class LaunchGuardTests(unittest.TestCase):
    def assertBlocked(self, command, background=False):
        result = call(command, background)
        self.assertIsNotNone(result, command)
        output = result["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("run_in_background: true", output["permissionDecisionReason"])

    def assertAllowed(self, command, background=False):
        self.assertIsNone(call(command, background), command)

    def test_each_launcher_in_the_foreground_is_blocked(self):
        for command in (
            "plan-run.sh start r goal.md plan.txt",
            "plan-run.sh resume r",
            "review-run.sh start r main...x",
            "council-run.sh start r brief.md",
            "research-run.sh resume r",
            "run-codex.sh name brief.md",
            "codex exec -m m -",
            "~/.claude/skills/dispatch-codex/scripts/plan-run.sh start r g p",
            "cd /repo && /abs/plan-run.sh resume -p none r",
            "FOO=1 bash scripts/review-run.sh start a b",
            "CODEX_IN_PLACE=1 run-codex.sh n b",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_background_call_is_allowed(self):
        for command in (
            "plan-run.sh start r g p",
            "cd /repo && ~/.claude/skills/dispatch-codex/scripts/plan-run.sh resume -p none r",
            "run-codex.sh n b integration gpt-6-luna high",
            "codex exec -m m -",
        ):
            with self.subTest(command=command):
                self.assertAllowed(command, background=True)

    def test_backgrounding_by_hand_is_blocked_even_with_the_flag(self):
        self.assertBlocked("nohup plan-run.sh start r g p >o 2>&1 &", background=True)
        self.assertBlocked("plan-run.sh start r g p &", background=True)
        self.assertBlocked("sleep 1; plan-run.sh start r g p &", background=True)
        self.assertBlocked("nohup codex exec - < p.md > out &")

    def test_commands_that_only_read_or_mention_the_names_are_allowed(self):
        for command in (
            "plan-run.sh status r",
            "plan-run.sh board r",
            "plan-run.sh gates plan.txt",
            "plan-run.sh finish r",
            "grep -rn plan-run.sh .",
            "cat scripts/run-codex.sh",
            "ls -la | grep review-run.sh",
            "tail -f /tmp/x.log",
            "echo 'plan-run.sh start r'",
            "codex --help",
            "codex login status",
            "bash scripts/test-plan-run-gate.sh",
            "git log --oneline -3",
        ):
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_text_fed_to_a_command_by_a_heredoc_is_not_a_launch(self):
        command = (
            "cat > run.sh <<'EOF'\n"
            "bash plan-run.sh start x goal.md plan.txt\n"
            "codex exec -\n"
            "EOF\n"
            "echo done"
        )
        self.assertAllowed(command)
        self.assertBlocked(command + "\nbash plan-run.sh start x g p")

    def test_other_tools_and_bad_input_are_ignored(self):
        self.assertIsNone(call("plan-run.sh start r g p", tool="Read"))
        self.assertIsNone(check({"tool_name": "Bash"}))
        self.assertIsNone(check({"tool_name": "Bash", "tool_input": {"command": ""}}))
        self.assertIsNone(check({"tool_name": "Bash", "tool_input": {"command": "echo 'unterminated"}}))

    def run_event(self, data):
        import contextlib
        import io

        import hook_events

        stdout = io.StringIO()
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(data))), contextlib.redirect_stdout(stdout):
            status = hook_events.main(["guard"])
        return status, stdout.getvalue()

    def test_the_hook_entry_point_prints_the_deny_payload(self):
        data = {"tool_name": "Bash", "tool_input": {"command": "plan-run.sh start r g p"}, "session_id": "t"}
        status, output = self.run_event(data)
        self.assertEqual(status, 0)
        payload = json.loads(output)
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecisionReason"], REASON)

    def test_the_hook_entry_point_stays_silent_for_a_background_launch(self):
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "plan-run.sh start r g p", "run_in_background": True},
            "session_id": "t",
        }
        status, output = self.run_event(data)
        self.assertEqual(status, 0)
        self.assertEqual(output.strip(), "")


if __name__ == "__main__":
    unittest.main()

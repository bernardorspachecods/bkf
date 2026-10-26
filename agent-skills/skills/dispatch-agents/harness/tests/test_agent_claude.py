import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

from harness import agent

HARNESS = str(pathlib.Path(__file__).resolve().parents[1])

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ['ARG_LOG'], 'w') as output:
    json.dump(sys.argv[1:], output)
with open(os.environ['INPUT_LOG'], 'wb') as output:
    output.write(sys.stdin.buffer.read())
for line in os.environ.get('FAKE_EVENTS', '').split('\\n'):
    if line:
        print(line)
sys.exit(int(os.environ.get('FAKE_EXIT', '0')))
"""


class ClaudeBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE, encoding="utf-8")
        fake.chmod(0o755)
        self.work = self.root / "work"
        self.work.mkdir()
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("do the thing\n", encoding="utf-8")
        self.arg_log = self.root / "args.json"
        self.input_log = self.root / "input.bin"

    def tearDown(self):
        self.temp.cleanup()

    def run_agent(self, sandbox, events, exit_status=0, extra=()):
        env = dict(
            os.environ,
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            ARG_LOG=str(self.arg_log),
            INPUT_LOG=str(self.input_log),
            FAKE_EVENTS="\n".join(events),
            FAKE_EXIT=str(exit_status),
            PYTHONPATH=HARNESS,
        )
        return subprocess.run(
            [sys.executable, "-m", "harness", "agent", "run", "--dir", str(self.work), "--prompt", str(self.prompt),
             "--out-prefix", str(self.work / "run"), "--model", "haiku", "--effort", "high",
             "--sandbox", sandbox, "--backend", "claude", *extra],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def test_workspace_write_allows_writes_under_the_directory_and_a_sandboxed_bash(self):
        arguments = agent.ClaudeBackend().arguments("/d", "haiku", "high", "workspace-write", None, "/m")
        self.assertEqual(arguments[:3], ["-p", "--output-format", "stream-json"])
        self.assertIn("--no-session-persistence", arguments)
        self.assertEqual(arguments[arguments.index("--permission-mode") + 1], "dontAsk")
        allowed = arguments[arguments.index("--allowedTools") + 1].split(",")
        self.assertIn("Write(./**)", allowed)
        self.assertIn("Edit(./**)", allowed)
        self.assertIn("Bash", allowed)
        self.assertNotIn("Write", allowed)
        sandbox = json.loads(arguments[arguments.index("--settings") + 1])["sandbox"]
        self.assertTrue(sandbox["enabled"])
        self.assertFalse(sandbox["allowUnsandboxedCommands"])

    def test_read_only_allows_no_write_and_no_bash(self):
        arguments = agent.ClaudeBackend().arguments("/d", "haiku", "high", "read-only", None, "/m")
        self.assertEqual(arguments[arguments.index("--allowedTools") + 1], "Read,Glob,Grep")
        self.assertNotIn("--settings", arguments)

    def test_web_adds_only_the_two_web_tools_and_is_off_by_default(self):
        backend = agent.ClaudeBackend()
        plain = backend.arguments("/d", "haiku", "high", "workspace-write", None, "/m")
        self.assertNotIn("WebFetch", plain[plain.index("--allowedTools") + 1])
        for sandbox, base in (("workspace-write", "Read,Glob,Grep,Write(./**),Edit(./**),Bash"), ("read-only", "Read,Glob,Grep")):
            arguments = backend.arguments("/d", "haiku", "high", sandbox, None, "/m", web=True)
            self.assertEqual(arguments[arguments.index("--allowedTools") + 1], base + ",WebFetch,WebSearch")

    def test_the_web_flag_reaches_the_claude_command(self):
        events = [json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "x"})]
        result = self.run_agent("workspace-write", events, extra=("--web",))
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = json.loads(self.arg_log.read_text(encoding="utf-8"))
        self.assertTrue(arguments[arguments.index("--allowedTools") + 1].endswith(",WebFetch,WebSearch"))

    def test_the_prompt_goes_on_stdin_and_the_result_becomes_the_last_message(self):
        events = [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "the answer"}),
        ]
        result = self.run_agent("workspace-write", events)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"do the thing", self.input_log.read_bytes())
        self.assertEqual((self.work / "run.last-message.md").read_text(encoding="utf-8"), "the answer")
        self.assertTrue((self.work / "run.events.jsonl").is_file())

    def test_no_result_event_leaves_no_last_message(self):
        result = self.run_agent("workspace-write", [json.dumps({"type": "system"})], exit_status=1)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.work / "run.last-message.md").exists())

    def test_quota_text_reads_a_rate_limit_event_that_is_not_allowed(self):
        events = self.root / "events.jsonl"
        reset = time.mktime((2026, 10, 25, 23, 30, 0, 0, 0, -1))
        allowed = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "resetsAt": reset}}
        blocked = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": reset}}
        events.write_text(json.dumps(allowed) + "\n", encoding="utf-8")
        self.assertIsNone(agent.ClaudeBackend().quota_text(str(events)))
        events.write_text(json.dumps(allowed) + "\n" + json.dumps(blocked) + "\n", encoding="utf-8")
        self.assertEqual(agent.ClaudeBackend().quota_text(str(events)), "resets at 2026-10-25 23:30")

    def test_quota_text_reads_a_limit_error_result_and_ignores_other_errors(self):
        events = self.root / "events.jsonl"
        events.write_text(json.dumps({"type": "result", "is_error": True, "result": "Usage limit reached"}) + "\n", encoding="utf-8")
        self.assertEqual(agent.ClaudeBackend().quota_text(str(events)), "Usage limit reached")
        events.write_text(json.dumps({"type": "result", "is_error": True, "result": "bad model"}) + "\n", encoding="utf-8")
        self.assertIsNone(agent.ClaudeBackend().quota_text(str(events)))

    def test_the_backend_comes_from_the_name_then_the_environment_then_codex(self):
        saved = os.environ.pop("HARNESS_BACKEND", None)
        try:
            self.assertIs(agent.get_backend(None), agent.CodexBackend)
            os.environ["HARNESS_BACKEND"] = "claude"
            self.assertIs(agent.get_backend(None), agent.ClaudeBackend)
            self.assertIs(agent.get_backend("codex"), agent.CodexBackend)
        finally:
            os.environ.pop("HARNESS_BACKEND", None)
            if saved is not None:
                os.environ["HARNESS_BACKEND"] = saved

    def test_claude_is_a_registered_backend(self):
        self.assertIs(agent.get_backend("claude"), agent.ClaudeBackend)


if __name__ == "__main__":
    unittest.main()

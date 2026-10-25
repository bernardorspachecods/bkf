import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from harness import agent

HARNESS_DIR = pathlib.Path(__file__).resolve().parents[1]


class AgentCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.arg_log = self.root / "arguments.json"
        self.input_log = self.root / "input.bin"
        self.fake_codex = self.bin_dir / "codex"
        self.fake_codex.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, signal, sys\n"
            "arguments = sys.argv[1:]\n"
            "with open(os.environ['ARG_LOG'], 'w') as output:\n"
            "    json.dump(arguments, output)\n"
            "with open(os.environ['INPUT_LOG'], 'wb') as output:\n"
            "    output.write(sys.stdin.buffer.read())\n"
            "import time; time.sleep(float(os.environ.get('FAKE_SLEEP', '0')))\n"
            "with open(arguments[arguments.index('-o') + 1], 'w') as output:\n"
            "    output.write('last message')\n"
            "sys.stdout.write('{\\\"type\\\":\\\"event\\\"}\\n')\n"
            "sys.stderr.write('fake stderr\\n')\n"
            "if os.environ.get('KILL_SIGNAL'):\n"
            "    os.kill(os.getpid(), int(os.environ['KILL_SIGNAL']))\n"
            "sys.exit(int(os.environ.get('FAKE_EXIT', '0')))\n",
            encoding="utf-8",
        )
        self.fake_codex.chmod(0o755)
        self.guide = self.root / "guide.md"
        self.guide.write_text(
            "# Guide\n\n- Keep the directive.\n<!-- inject: rule.md -->\n",
            encoding="utf-8",
        )
        self.rule = self.root / "rule.md"
        self.rule.write_text("# Injected\n\n- Follow this directive.\n", encoding="utf-8")
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text(
            "# Prompt\n\nDo the work.\n\n"
            "Open and follow the role guide: {0} (read-only).\n".format(self.guide),
            encoding="utf-8",
        )
        self.prefix = self.root / "run"
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(HARNESS_DIR)
        self.env["PATH"] = str(self.bin_dir) + os.pathsep + self.env.get("PATH", "")
        self.env["ARG_LOG"] = str(self.arg_log)
        self.env["INPUT_LOG"] = str(self.input_log)

    def tearDown(self):
        self.temp.cleanup()

    def run_agent(self, *extra, backend="codex", env=None):
        arguments = [
            sys.executable,
            "-m",
            "harness",
            "agent",
            "run",
            "--dir",
            str(self.root),
            "--prompt",
            str(self.prompt),
            "--out-prefix",
            str(self.prefix),
            "--model",
            "gpt-test",
            "--effort",
            "high",
        ]
        if backend is not None:
            arguments.extend(["--backend", backend])
        arguments.extend(extra)
        return subprocess.run(
            arguments,
            cwd=str(HARNESS_DIR),
            env=env or self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def recorded_arguments(self):
        return json.loads(self.arg_log.read_text(encoding="utf-8"))

    def assert_outputs_created(self):
        self.assertTrue(pathlib.Path(str(self.prefix) + ".events.jsonl").is_file())
        self.assertTrue(pathlib.Path(str(self.prefix) + ".stderr.log").is_file())
        self.assertTrue(pathlib.Path(str(self.prefix) + ".last-message.md").is_file())

    def test_codex_arguments_without_tier(self):
        result = self.run_agent()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_arguments(),
            [
                "exec",
                "--skip-git-repo-check",
                "-C",
                str(self.root),
                "-m",
                "gpt-test",
                "-c",
                'model_reasoning_effort="high"',
                "-s",
                "workspace-write",
                "--json",
                "-o",
                str(self.prefix) + ".last-message.md",
                "-",
            ],
        )

    def test_codex_arguments_with_tier_and_non_default_sandbox(self):
        result = self.run_agent("--tier", "fast", "--sandbox", "read-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_arguments(),
            [
                "exec",
                "-c",
                'service_tier="fast"',
                "--skip-git-repo-check",
                "-C",
                str(self.root),
                "-m",
                "gpt-test",
                "-c",
                'model_reasoning_effort="high"',
                "-s",
                "read-only",
                "--json",
                "-o",
                str(self.prefix) + ".last-message.md",
                "-",
            ],
        )

    def test_prompt_is_injected_before_being_sent_on_stdin_and_outputs_are_named(self):
        result = self.run_agent()
        self.assertEqual(result.returncode, 0, result.stderr)
        received = self.input_log.read_bytes()
        self.assertIn(b"- Follow this directive.", received)
        self.assertIn(b"<!-- rules injected by the script -->", received)
        self.assertEqual(received, self.prompt.read_bytes())
        self.assert_outputs_created()
        self.assertEqual(
            pathlib.Path(str(self.prefix) + ".events.jsonl").read_bytes(),
            b'{"type":"event"}\n',
        )
        self.assertEqual(
            pathlib.Path(str(self.prefix) + ".stderr.log").read_bytes(), b"fake stderr\n"
        )
        self.assertEqual(
            pathlib.Path(str(self.prefix) + ".last-message.md").read_text(encoding="utf-8"),
            "last message",
        )

    def run_in_process(self, **environment):
        patched = dict(self.env)
        patched.update(environment)
        with mock.patch.dict(os.environ, patched, clear=True):
            return agent.run_agent(
                str(self.root), str(self.prompt), str(self.prefix), "gpt-test", "high"
            )

    def spawn_kwargs(self, in_thread):
        calls = []
        real_popen = subprocess.Popen

        def recording_popen(*args, **kwargs):
            calls.append(kwargs)
            return real_popen(*args, **kwargs)

        with mock.patch.object(agent.subprocess, "Popen", recording_popen):
            if in_thread:
                results = []
                worker = threading.Thread(target=lambda: results.append(self.run_in_process()))
                worker.start()
                worker.join()
                self.assertEqual(results, [0])
            else:
                self.assertEqual(self.run_in_process(), 0)
        return calls[0]

    def test_main_thread_masks_signals_while_the_agent_registers(self):
        self.assertIn("preexec_fn", self.spawn_kwargs(in_thread=False))

    def test_worker_thread_does_not_use_preexec_fn(self):
        self.assertNotIn("preexec_fn", self.spawn_kwargs(in_thread=True))

    def test_agent_started_in_a_worker_thread_ends_when_the_run_is_stopping(self):
        results = []
        agent.stopping.set()
        try:
            worker = threading.Thread(
                target=lambda: results.append(self.run_in_process(FAKE_SLEEP="30"))
            )
            worker.start()
            worker.join(timeout=10)
        finally:
            agent.stopping.clear()
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [128 + signal.SIGTERM])

    def test_exit_status_is_propagated(self):
        environment = self.env.copy()
        environment["FAKE_EXIT"] = "23"
        result = self.run_agent(env=environment)
        self.assertEqual(result.returncode, 23)

    def test_signal_death_maps_to_shell_status(self):
        environment = self.env.copy()
        environment["KILL_SIGNAL"] = str(signal.SIGTERM)
        result = self.run_agent(env=environment)
        self.assertEqual(result.returncode, 128 + signal.SIGTERM)

    def test_failed_injection_does_not_start_agent(self):
        self.guide.write_text("<!-- inject: missing.md -->\n", encoding="utf-8")
        result = self.run_agent()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"does not exist", result.stderr)
        self.assertFalse(self.arg_log.exists())
        self.assertFalse(self.input_log.exists())

    def test_injection_filesystem_error_exits_one_without_starting_agent(self):
        self.prompt.unlink()
        result = self.run_agent()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"No such file", result.stderr)
        self.assertFalse(self.arg_log.exists())
        self.assertFalse(self.input_log.exists())

    def test_unknown_backend_exits_two_without_starting_agent(self):
        result = self.run_agent(backend="claude")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"backend not implemented: claude", result.stderr)
        self.assertFalse(self.arg_log.exists())

    def test_backend_quota_text_matches_bash_extraction(self):
        backend = agent.CodexBackend()
        events = self.root / "quota.events.jsonl"
        cases = (
            ('{"message":"You\'ve hit your usage limit. try again at 2026-10-23 10:00 UTC"}\n',
             "2026-10-23 10:00 UTC"),
            ('{"message":"You’ve hit your usage limit. try again at tomorrow \\"later\\""}\n',
             'tomorrow \\"later\\"'),
            ('{"message":"You’ve hit your usage limit. Please wait"}\n',
             "You’ve hit your usage limit. Please wait"),
        )
        for content, expected in cases:
            with self.subTest(content=content):
                events.write_text(content, encoding="utf-8")
                self.assertEqual(backend.quota_text(str(events)), expected)

    def test_backend_quota_text_uses_first_matching_line_and_returns_none_without_match(self):
        backend = agent.CodexBackend()
        events = self.root / "quota.events.jsonl"
        events.write_text(
            '{"message":"hit your usage limit; try again at first"}\n'
            '{"message":"hit your usage limit; try again at second"}\n',
            encoding="utf-8",
        )
        self.assertEqual(backend.quota_text(str(events)), "first")
        events.write_text('{"message":"other event"}\n', encoding="utf-8")
        self.assertIsNone(backend.quota_text(str(events)))

    def test_get_backend_returns_registered_class_or_none(self):
        self.assertIs(agent.get_backend("codex"), agent.CodexBackend)
        self.assertIsNone(agent.get_backend("unknown"))

if __name__ == "__main__":
    unittest.main()

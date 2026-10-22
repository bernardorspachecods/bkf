import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import unittest


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

if __name__ == "__main__":
    unittest.main()

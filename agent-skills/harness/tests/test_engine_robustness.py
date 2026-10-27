import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

import test_engine_pipeline


class EngineRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_engine_pipeline.PipelineTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.repo = self.fixture.repo
        self.runs = self.fixture.runs
        self.definition = self.fixture.definition
        self.env = os.environ.copy()
        self.env.update(self.fixture.env)
        harness_dir = Path(__file__).resolve().parents[1]
        self.env["PYTHONPATH"] = str(harness_dir) + os.pathsep + self.env.get("PYTHONPATH", "")
        self.pid_file = self.root / "agent.pid"
        self.env["FAKE_AGENT_PID"] = str(self.pid_file)
        codex = self.fixture.bin_dir / "codex"
        codex.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys, time\n"
            "pathlib.Path(os.environ['FAKE_AGENT_PID']).write_text(str(os.getpid()))\n"
            "if os.environ.get('SLEEP_AGENT'):\n"
            "    time.sleep(60)\n"
            "out = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
            "out.write_text('agent completed\\n')\n",
            encoding="utf-8",
        )
        codex.chmod(0o755)

    def tearDown(self):
        self.fixture.tearDown()

    def start(self, command, *args, sleep_agent=False):
        env = self.env.copy()
        if sleep_agent:
            env["SLEEP_AGENT"] = "1"
        script = (
            "import sys; from harness.engine.pipeline import main; "
            "sys.exit(main({0!r}, {1!r}))"
        ).format(str(self.definition), [command] + list(args))
        return subprocess.Popen(
            [sys.executable, "-c", script], cwd=str(self.repo), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )

    def start_with_spawn_race(self, command):
        script = (
            "import os, signal, subprocess, sys, time\n"
            "original = subprocess.Popen\n"
            "def racing_popen(*args, **kwargs):\n"
            "    process = original(*args, **kwargs)\n"
            "    command = args[0] if args else kwargs.get('args')\n"
            "    if command and 'codex' in command[0]:\n"
            "        deadline = time.monotonic() + 5\n"
            "        while not os.path.exists(os.environ['FAKE_AGENT_PID']) and time.monotonic() < deadline:\n"
            "            time.sleep(0.01)\n"
            "        os.kill(os.getpid(), signal.SIGTERM)\n"
            "    return process\n"
            "subprocess.Popen = racing_popen\n"
            "from harness.engine.pipeline import main\n"
            "sys.exit(main({0!r}, ['start', {1!r}]))\n"
        ).format(str(self.definition), command)
        env = self.env.copy()
        env["SLEEP_AGENT"] = "1"
        return subprocess.Popen(
            [sys.executable, "-c", script], cwd=str(self.repo), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )

    def wait_for_agent(self, process):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.pid_file.exists():
                return int(self.pid_file.read_text(encoding="utf-8"))
            if process.poll() is not None:
                break
            time.sleep(0.02)
        stdout, stderr = process.communicate()
        self.fail("fake agent did not start: {0}{1}".format(
            stdout.decode("utf-8"), stderr.decode("utf-8")
        ))

    def assert_process_gone(self, pid):
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_sigterm_interrupts_step_and_reaps_agent(self):
        process = self.start("start", "term", sleep_agent=True)
        agent_pid = self.wait_for_agent(process)
        os.kill(process.pid, signal.SIGTERM)
        stdout, _ = process.communicate(timeout=5)
        run = self.runs / "term"
        status = (run / "status.log").read_text(encoding="utf-8")
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        self.assertIn("INTERRUPTED by signal SIGTERM during step 1", status)
        self.assertFalse((run / ".lock").exists())
        self.assertFalse((run / ".done-S1").exists())
        self.assert_process_gone(agent_pid)
        self.assertIn("Run folder:", stdout.decode("utf-8"))

    def test_signal_between_spawn_and_registration_reaps_agent(self):
        process = self.start_with_spawn_race("spawn-race")
        agent_pid = self.wait_for_agent(process)
        process.communicate(timeout=5)
        try:
            self.assertEqual(process.returncode, 128 + signal.SIGTERM)
            self.assert_process_gone(agent_pid)
        finally:
            try:
                os.kill(agent_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_sigint_interrupts_step(self):
        process = self.start("start", "interrupt", sleep_agent=True)
        agent_pid = self.wait_for_agent(process)
        os.kill(process.pid, signal.SIGINT)
        process.communicate(timeout=5)
        status = (self.runs / "interrupt" / "status.log").read_text(encoding="utf-8")
        self.assertEqual(process.returncode, 128 + signal.SIGINT)
        self.assertIn("INTERRUPTED by signal SIGINT during step 1", status)
        self.assertFalse((self.runs / "interrupt" / ".lock").exists())
        self.assert_process_gone(agent_pid)

    def test_sighup_interrupts_step_and_reaps_agent(self):
        process = self.start("start", "hangup", sleep_agent=True)
        agent_pid = self.wait_for_agent(process)
        os.kill(process.pid, signal.SIGHUP)
        process.communicate(timeout=5)
        status = (self.runs / "hangup" / "status.log").read_text(encoding="utf-8")
        self.assertEqual(process.returncode, 128 + signal.SIGHUP)
        self.assertIn("INTERRUPTED by signal SIGHUP during step 1", status)
        self.assertFalse((self.runs / "hangup" / ".lock").exists())
        self.assert_process_gone(agent_pid)

    def test_sigkill_is_reported_on_resume_and_work_finishes(self):
        process = self.start("start", "killed", sleep_agent=True)
        self.wait_for_agent(process)
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)
        run = self.runs / "killed"
        self.assertFalse((run / ".done-S1").exists())
        result = subprocess.run(
            [sys.executable, "-c", "import sys; from harness.engine.pipeline import main; "
             "sys.exit(main({0!r}, ['resume', 'killed']))".format(str(self.definition))],
            cwd=str(self.repo), env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        status = (run / "status.log").read_text(encoding="utf-8")
        self.assertIn(
            "resume: the previous attempt ended without a STOPPED, PAUSED, READY, "
            "INTERRUPTED or CRASHED line: it was killed or crashed. Steps not marked "
            "done run again.",
            status,
        )
        self.assertTrue((run / ".done-S1").exists())
        self.assertTrue((run / ".done-S2").exists())
        self.assertTrue((run / ".done-report").exists())
        self.assertFalse((run / ".lock").exists())

    def test_step_crash_is_logged_and_reported(self):
        process = self.start("start", "crash", "crash")
        stdout, _ = process.communicate(timeout=5)
        run = self.runs / "crash"
        self.assertTrue((run / "crash-step").exists(), stdout.decode("utf-8"))
        status = (run / "status.log").read_text(encoding="utf-8")
        self.assertEqual(process.returncode, 1, stdout.decode("utf-8"))
        self.assertIn("CRASHED: RuntimeError: workflow broke", status)
        self.assertIn("CRASHED at step 2: workflow broke", stdout.decode("utf-8"))
        self.assertIn("See {0}/status.log".format(run), stdout.decode("utf-8"))
        self.assertIn("RuntimeError: workflow broke", (run / "crash.log").read_text(encoding="utf-8"))
        self.assertFalse((run / ".lock").exists())
        self.assertFalse((run / ".done-S2").exists())

    def test_clean_stop_resume_does_not_report_kill(self):
        process = self.start("start", "clean-stop", "stop")
        process.communicate(timeout=5)
        run = self.runs / "clean-stop"
        self.assertEqual(process.returncode, 1)
        (run / "stop").unlink()
        result = subprocess.run(
            [sys.executable, "-c", "import sys; from harness.engine.pipeline import main; "
             "sys.exit(main({0!r}, ['resume', 'clean-stop']))".format(str(self.definition))],
            cwd=str(self.repo), env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        status = (run / "status.log").read_text(encoding="utf-8")
        self.assertNotIn("the previous attempt ended without", status)


if __name__ == "__main__":
    unittest.main()

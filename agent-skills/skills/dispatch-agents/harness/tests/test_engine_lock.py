import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.engine.lock import Lock, acquire, is_active
from harness.engine.run import RunError


class LockTests(unittest.TestCase):
    marker = "bkf-lock-marker"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.run_path = Path(self.temp_dir.name) / "run"
        self.run_path.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def start_sleep_with_marker(self, marker):
        return subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", marker],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def test_live_process_with_marker_is_active_and_refuses_acquire(self):
        process = self.start_sleep_with_marker(self.marker)
        try:
            lock_path = self.run_path / ".lock"
            lock_path.write_text("{0}\n".format(process.pid))
            ps_result = subprocess.CompletedProcess(
                ["ps"], 0, stdout="{0} {1}\n".format(process.pid, self.marker)
            )
            with patch("harness.engine.lock.subprocess.run", return_value=ps_result) as ps:
                self.assertTrue(is_active(self.run_path, self.marker))
                with self.assertRaisesRegex(
                    RunError,
                    "^run run is already being worked on by pid {0}$".format(process.pid),
                ):
                    acquire(self.run_path, self.marker)
            self.assertEqual(
                ps.call_args[0][0], ["ps", "-p", str(process.pid), "-o", "command="]
            )
        finally:
            process.terminate()
            process.wait()

    def test_live_process_without_marker_is_stale(self):
        process = self.start_sleep_with_marker("other-marker")
        try:
            (self.run_path / ".lock").write_text("{0}\n".format(process.pid))
            ps_result = subprocess.CompletedProcess(
                ["ps"], 0, stdout="{0} other-marker\n".format(process.pid)
            )
            with patch("harness.engine.lock.subprocess.run", return_value=ps_result):
                self.assertFalse(is_active(self.run_path, self.marker))
                lock = acquire(self.run_path, self.marker)
            self.assertEqual((self.run_path / ".lock").read_text(), "{0}\n".format(os.getpid()))
            lock.release()
        finally:
            process.terminate()
            process.wait()

    def test_dead_pid_is_stale(self):
        (self.run_path / ".lock").write_text("99999999\n")
        lock = acquire(self.run_path, self.marker)
        self.assertEqual((self.run_path / ".lock").read_text(), "{0}\n".format(os.getpid()))
        lock.release()

    def test_lock_creation_is_exclusive(self):
        ps_result = subprocess.CompletedProcess(["ps"], 0, stdout="python process\n")
        with patch("harness.engine.lock.subprocess.run", return_value=ps_result):
            lock = acquire(self.run_path, "python")
            self.assertIsInstance(lock, Lock)
            with self.assertRaisesRegex(RunError, "^run run is already being worked on by pid "):
                acquire(self.run_path, "python")
        lock.release()

    def test_release_does_not_remove_another_pids_lock(self):
        lock = acquire(self.run_path, self.marker)
        lock_path = self.run_path / ".lock"
        lock_path.write_text("12345\n")
        lock.release()
        self.assertEqual(lock_path.read_text(), "12345\n")

    def test_context_manager_releases_lock(self):
        with acquire(self.run_path, self.marker):
            self.assertTrue((self.run_path / ".lock").exists())
        self.assertFalse((self.run_path / ".lock").exists())


if __name__ == "__main__":
    unittest.main()

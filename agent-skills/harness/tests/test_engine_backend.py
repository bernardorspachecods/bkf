"""The start-up check for the agent backend follows the backend the run will use."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness.engine.backend import require_backend
from harness.engine.run import RunError


class RequireBackendTests(unittest.TestCase):
    def _bin_with(self, *names):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name in names:
            path = Path(temp.name) / name
            path.write_text("#!/bin/sh\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return temp.name

    def _env(self, bin_dir, backend=None):
        env = {"PATH": bin_dir}
        if backend:
            env["HARNESS_BACKEND"] = backend
        return mock.patch.dict(os.environ, env, clear=True)

    def test_codex_is_the_default_and_must_be_installed(self):
        with self._env(self._bin_with()):
            with self.assertRaises(RunError) as error:
                require_backend()
        self.assertEqual(str(error.exception), "codex not found")

    def test_codex_present_passes(self):
        with self._env(self._bin_with("codex")):
            require_backend()

    def test_claude_backend_does_not_need_codex(self):
        with self._env(self._bin_with("claude"), backend="claude"):
            require_backend()

    def test_claude_backend_without_claude_is_refused(self):
        with self._env(self._bin_with("codex"), backend="claude"):
            with self.assertRaises(RunError) as error:
                require_backend()
        self.assertEqual(str(error.exception), "claude not found")

    def test_unknown_backend_is_refused(self):
        with self._env(self._bin_with("codex"), backend="nothing"):
            with self.assertRaises(RunError) as error:
                require_backend()
        self.assertIn("backend not implemented: nothing", str(error.exception))


if __name__ == "__main__":
    unittest.main()

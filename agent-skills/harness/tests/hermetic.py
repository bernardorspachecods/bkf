"""Shared test helper: fix the agent backend for one test case.

The harness reads HARNESS_BACKEND when no backend is named, so a test that fakes a
backend executable must pin the backend or it runs whichever one the shell names.
"""
import atexit
import os
import shutil
import tempfile
from unittest import mock

# Every test process keeps its task cards in a temporary store, so no test can write to the user's store,
# even when a real `bkf` is installed and a plan run calls it.
_TASKS_DIR = tempfile.mkdtemp(prefix="bkf-tasks-test-")
atexit.register(shutil.rmtree, _TASKS_DIR, ignore_errors=True)
os.environ["BKF_TASKS_DIR"] = _TASKS_DIR


def pin_backend(test_case, backend="codex"):
    """Set HARNESS_BACKEND to backend for this test case, restored after it."""
    patcher = mock.patch.dict(os.environ, {"HARNESS_BACKEND": backend})
    patcher.start()
    test_case.addCleanup(patcher.stop)

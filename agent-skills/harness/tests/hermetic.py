"""Shared test helper: fix the agent backend for one test case.

The harness reads HARNESS_BACKEND when no backend is named, so a test that fakes a
backend executable must pin the backend or it runs whichever one the shell names.
"""
import os
from unittest import mock


def pin_backend(test_case, backend="codex"):
    """Set HARNESS_BACKEND to backend for this test case, restored after it."""
    patcher = mock.patch.dict(os.environ, {"HARNESS_BACKEND": backend})
    patcher.start()
    test_case.addCleanup(patcher.stop)

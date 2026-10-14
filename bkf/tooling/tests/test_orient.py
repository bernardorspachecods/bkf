from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLING = Path(__file__).resolve().parents[1]
CLI = TOOLING / "bkf_cli.py"
sys.path.insert(0, str(TOOLING))
import orient


def map_text(*, root: bool = False, description: str = "An area map.") -> str:
    front = (
        f'bkf_version: "0.1"\ndescription: {description}\n'
        if root
        else f"description: {description}\n"
    )
    return (
        f"---\n{front}---\n\n# Map\n\n## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
    )


def document(name: str, description: str) -> str:
    return f"---\nbkf: document\ndescription: {description}\ntags: [test]\n---\n\n# {name}\n"


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "orient", *map(str, args)],
        cwd=TOOLING,
        check=False,
        capture_output=True,
        text=True,
    )


class OrientTests(unittest.TestCase):
    def test_root_cwd_prints_root_map_and_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (root / "guide.md").write_text(document("Guide", "A guide."), encoding="utf-8")

            result = run("--cwd", root)
            without_validation = run("--cwd", root, "--no-validate")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("orientation (from .)", result.stdout)
        self.assertIn("/MAP.md\n  /guide.md  A guide.", result.stdout)
        self.assertRegex(result.stdout, r"bkf validate: (ok|\d+ errors \(run bkf validate\))")
        self.assertEqual(without_validation.returncode, 0, without_validation.stderr)
        self.assertNotIn("bkf validate:", without_validation.stdout)

    def test_nested_area_cwd_prints_map_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            area = root / "area"
            area.mkdir()
            (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (area / "MAP.md").write_text(map_text(description="Area guides."), encoding="utf-8")
            (area / "guide.md").write_text(document("Guide", "A local guide."), encoding="utf-8")

            result = run("--cwd", area, "--no-validate")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/MAP.md\n", result.stdout)
        self.assertIn("/area/MAP.md\n  /area/guide.md  A local guide.", result.stdout)

    def test_nested_bundle_cwd_includes_outer_and_inner_maps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inner = root / "bundle"
            inner.mkdir()
            (root / "MAP.md").write_text(map_text(root=True, description="Outer bundle."), encoding="utf-8")
            (inner / "MAP.md").write_text(map_text(root=True, description="Inner bundle."), encoding="utf-8")
            (inner / "guide.md").write_text(document("Guide", "Inner guide."), encoding="utf-8")

            result = run("--cwd", inner, "--no-validate")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("orientation (from bundle)", result.stdout)
        self.assertIn(
            "/MAP.md\n  /bundle/MAP.md  Inner bundle.\n/bundle/MAP.md\n  /bundle/guide.md  Inner guide.",
            result.stdout,
        )

    def test_cwd_outside_bundle_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            result = run("--cwd", outside)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_output_stays_under_size_cap_and_reports_omitted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            for index in range(100):
                (root / f"guide-{index:03}.md").write_text(
                    document(f"Guide {index}", f"Description {index} " + "word " * 30),
                    encoding="utf-8",
                )

            result = run("--cwd", root, "--no-validate")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(len(result.stdout), 6000)
        self.assertRegex(result.stdout, r"  \.\.\. \d+ more rows, read /MAP\.md")

    def test_orient_is_listed_as_a_py_module(self) -> None:
        pyproject = (TOOLING / "pyproject.toml").read_text(encoding="utf-8")
        module_list = pyproject.split("py-modules = [", 1)[1].split("]", 1)[0]
        self.assertIn('"orient"', module_list)

    def test_validation_timeout_returns_promptly(self) -> None:
        class SlowValidator:
            findings: list[object] = []

            def __init__(self, bundle: Path) -> None:
                pass

            def validate(self) -> None:
                time.sleep(0.2)

        started = time.monotonic()
        with patch.object(orient, "VALIDATION_TIMEOUT", 0.01):
            result = orient._validate(Path("."), lambda root: [root], SlowValidator)
        elapsed = time.monotonic() - started

        self.assertEqual(result, "bkf validate: skipped (timeout)")
        self.assertLess(elapsed, 0.15)

    def test_orient_does_not_import_signal(self) -> None:
        source = (TOOLING / "orient.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^\s*(?:import\s+signal|from\s+signal\s+import)")

    def test_stdout_without_reconfigure_is_supported(self) -> None:
        class PlainStream:
            def __init__(self) -> None:
                self.output = ""

            def write(self, value: str) -> int:
                self.output += value
                return len(value)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            stream = PlainStream()
            with patch.object(sys, "stdout", stream):
                result = orient.main(["--cwd", str(root), "--no-validate"])

        self.assertEqual(result, 0)
        self.assertIn("/MAP.md", stream.output)

    def test_broken_map_reports_failure_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (root / "broken.md").write_text("---\nbkf: [bad\n---\n", encoding="utf-8")

            result = run("--cwd", root, "--no-validate")

        self.assertEqual(result.returncode, 0)
        self.assertIn('"systemMessage"', result.stdout)
        self.assertIn("bkf hook orient failed", result.stdout)
        self.assertIn("bkf hook orient failed", result.stderr)

    def test_debug_failure_keeps_stderr_and_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (root / "broken.md").write_text("---\nbkf: [bad\n---\n", encoding="utf-8")

            result = run("--cwd", root, "--no-validate", "--debug")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("bkf orient:", result.stderr)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from bkf_cli import COMMANDS
import updates
from validate_bundle import Validator


def make_bundle(root: Path, version: str, *, nested: bool = False) -> Path:
    bundle = root / "nested" if nested else root
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "MAP.md").write_text(
        f'---\nbkf_version: "{version}"\n---\n\n# Bundle\n',
        encoding="utf-8",
    )
    return bundle


def run_updates(*paths: Path, updates_dir: Path) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        status = updates.main([*(str(path) for path in paths)], updates_dir=updates_dir)
    return status, stdout.getvalue(), stderr.getvalue()


class UpdatesTests(unittest.TestCase):
    def test_every_cli_command_module_is_packaged(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        self.assert_command_modules_are_packaged(pyproject)

    def assert_command_modules_are_packaged(self, pyproject: Path) -> None:
        with pyproject.open("rb") as file:
            package_modules = set(tomllib.load(file)["tool"]["setuptools"]["py-modules"])
        command_modules = {module for module, _, _ in COMMANDS.values()}
        self.assertEqual(command_modules - package_modules, set())

    def test_all_bundles_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            make_bundle(root, "0.1")

            status, output, error = run_updates(root, updates_dir=Path(directory) / "updates")

            self.assertEqual(status, 0)
            self.assertIn("Status: current", output)
            self.assertIn("bundle is up to date", output)
            self.assertEqual(error, "")

    def test_behind_prints_update_files_in_numeric_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "bundle"
            make_bundle(root, "0.8")
            updates_dir = base / "updates"
            updates_dir.mkdir()
            (updates_dir / "0-9.md").write_text("Update nine\n", encoding="utf-8")
            (updates_dir / "0-10.md").write_text("Update ten\n", encoding="utf-8")

            with patch.object(updates, "SUPPORTED_VERSION", (0, 10)):
                status, output, error = run_updates(root, updates_dir=updates_dir)

            self.assertEqual(status, 1)
            self.assertLess(output.index("BKF 0.9"), output.index("BKF 0.10"))
            self.assertLess(output.index("Update nine"), output.index("Update ten"))
            self.assertEqual(error, "")

    def test_ahead_bundle_reports_checkout_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            make_bundle(root, "0.2")

            status, output, error = run_updates(root, updates_dir=Path(directory) / "updates")

            self.assertEqual(status, 1)
            self.assertIn("Status: ahead", output)
            self.assertIn("update this checkout", output)
            self.assertEqual(error, "")

    def test_reports_root_and_nested_bundles_with_mixed_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            make_bundle(root, "0.1")
            behind = make_bundle(root, "0.0", nested=True)
            ahead_root = base / "ahead"
            make_bundle(ahead_root, "0.2")
            updates_dir = base / "updates"
            updates_dir.mkdir()
            (updates_dir / "0-1.md").write_text("Update one\n", encoding="utf-8")

            status, output, error = run_updates(root, ahead_root, updates_dir=updates_dir)

            self.assertEqual(status, 1)
            self.assertIn(f"Bundle: {root.resolve()}", output)
            self.assertIn(f"Bundle: {behind.resolve()}", output)
            self.assertIn(f"Bundle: {ahead_root.resolve()}", output)
            self.assertEqual(output.count("Status: "), 3)
            self.assertIn("Status: current", output)
            self.assertIn("Status: behind", output)
            self.assertIn("Status: ahead", output)
            self.assertEqual(error, "")

    def test_missing_supported_update_document_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "bundle"
            make_bundle(root, "0.0")
            updates_dir = base / "updates"
            updates_dir.mkdir()
            (updates_dir / "0-0.md").write_text("Old version\n", encoding="utf-8")

            status, output, error = run_updates(root, updates_dir=updates_dir)

            self.assertEqual(status, 1)
            self.assertIn("Status: behind", output)
            self.assertIn("installed bkf update document for 0.1 is missing", error)

    def test_absent_updates_folder_is_error_for_behind_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "bundle"
            make_bundle(root, "0.0")

            status, _, error = run_updates(root, updates_dir=base / "absent")

            self.assertEqual(status, 1)
            self.assertIn("updates directory", error)

    def test_no_bundles_found_reports_searched_paths_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty"
            empty.mkdir()

            status, output, error = run_updates(empty, updates_dir=Path(directory) / "updates")

            self.assertEqual(status, 1)
            self.assertEqual(output, "")
            self.assertIn(f"no BKF bundles found under {empty.resolve()}", error)

    def test_exit_statuses_for_current_behind_and_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            current = base / "current"
            make_bundle(current, "0.1")
            behind = base / "behind"
            make_bundle(behind, "0.0")
            updates_dir = base / "updates"
            updates_dir.mkdir()
            (updates_dir / "0-1.md").write_text("Update\n", encoding="utf-8")

            self.assertEqual(run_updates(current, updates_dir=updates_dir)[0], 0)
            self.assertEqual(run_updates(behind, updates_dir=updates_dir)[0], 1)
            code, _, error = run_updates(base / "missing", updates_dir=updates_dir)
            self.assertEqual(code, 2)
            self.assertIn("path is not a directory", error)

    def test_validator_older_version_finding_points_to_updates_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = make_bundle(Path(directory) / "bundle", "0.0")
            validator = Validator(bundle)

            with patch("validate_bundle.SUPPORTED_VERSION", (1, 1)):
                validator._check_version("0.9", bundle / "MAP.md")

            migration = next(
                finding
                for finding in validator.findings
                if finding.code == "MIGRATION_RECOMMENDED"
            )
            self.assertIn("run `bkf updates <bundle-root>`", migration.message)
            self.assertIn("on this bundle", migration.message)

    def test_validator_older_minor_version_points_to_updates_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = make_bundle(Path(directory) / "bundle", "0.1")
            validator = Validator(bundle)

            with patch("validate_bundle.SUPPORTED_VERSION", (0, 2)):
                validator.validate()

            migration = next(
                finding
                for finding in validator.findings
                if finding.code == "MINOR_MIGRATION_RECOMMENDED"
            )
            self.assertIn("run `bkf updates <bundle-root>`", migration.message)
            self.assertNotIn(
                "MIGRATION_RECOMMENDED",
                {finding.code for finding in validator.findings},
            )
            self.assertIn("supported version 0.2", migration.message)


if __name__ == "__main__":
    unittest.main()

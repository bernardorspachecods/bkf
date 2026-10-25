import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.engine.diffbase import make_patch, snapshot_base, snapshot_tree
from harness.engine.run import RunError


class DiffBaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.git_env = os.environ.copy()
        self.git_env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.git_env["GIT_CONFIG_GLOBAL"] = os.devnull
        self.environment_patch = patch.dict(os.environ, self.git_env)
        self.environment_patch.start()
        self.git("init", "-q")
        self.git("config", "user.name", "Harness Test")
        self.git("config", "user.email", "harness@example.invalid")
        (self.checkout / ".gitignore").write_text("ignored.txt\n")
        (self.checkout / "tracked.txt").write_text("base\n")
        (self.checkout / "deleted.txt").write_text("delete me\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def tearDown(self):
        self.environment_patch.stop()
        self.temp_dir.cleanup()

    def git(self, *args, env=None):
        return subprocess.run(
            ["git", "-C", str(self.checkout)] + list(args),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env or self.git_env,
        ).stdout.strip()

    def test_snapshot_includes_changes_and_omits_ignored_files_without_changing_index(self):
        (self.checkout / "tracked.txt").write_text("changed\n")
        (self.checkout / "new.txt").write_text("new\n")
        (self.checkout / "deleted.txt").unlink()
        (self.checkout / "ignored.txt").write_text("ignored\n")
        before_status = self.git("status", "--porcelain")
        before_cached = self.git("diff", "--cached")
        tree = snapshot_tree(self.checkout)
        self.assertEqual(self.git("diff", "--cached"), before_cached)
        self.assertEqual(self.git("status", "--porcelain"), before_status)
        names = self.git("ls-tree", "-r", "--name-only", tree).splitlines()
        self.assertEqual(names, [".gitignore", "new.txt", "tracked.txt"])

    def test_patch_includes_modified_added_and_deleted_files_but_not_ignored(self):
        directory = self.root / "round"
        directory.mkdir()
        snapshot_base(directory, self.checkout)
        self.assertEqual((directory / "base-format").read_text(), "tree\n")
        self.assertTrue((directory / "base").read_text().endswith("\n"))
        (self.checkout / "tracked.txt").write_text("changed\n")
        (self.checkout / "new.txt").write_text("new\n")
        (self.checkout / "deleted.txt").unlink()
        (self.checkout / "ignored.txt").write_text("ignored\n")
        output = self.root / "diff.patch"
        make_patch(directory, output, self.checkout)
        patch = output.read_text()
        self.assertIn("diff --git a/tracked.txt b/tracked.txt", patch)
        self.assertIn("diff --git a/new.txt b/new.txt", patch)
        self.assertIn("diff --git a/deleted.txt b/deleted.txt", patch)
        self.assertNotIn("ignored.txt", patch)

    def test_commit_after_base_snapshot_does_not_change_patch(self):
        directory = self.root / "round"
        directory.mkdir()
        snapshot_base(directory, self.checkout)
        (self.checkout / "tracked.txt").write_text("work in progress\n")
        expected = self.git(
            "diff", (directory / "base").read_text().strip(), snapshot_tree(self.checkout)
        ) + "\n"
        self.git("add", "tracked.txt")
        self.git("commit", "-qm", "commit during round")
        output = self.root / "diff.patch"
        make_patch(directory, output, self.checkout)
        self.assertEqual(output.read_text(), expected)

    def test_empty_diff_writes_empty_output_file(self):
        directory = self.root / "round"
        directory.mkdir()
        snapshot_base(directory, self.checkout)
        output = self.root / "diff.patch"
        make_patch(directory, output, self.checkout)
        self.assertTrue(output.exists())
        self.assertEqual(output.read_text(), "")

    def test_snapshot_index_is_removed(self):
        before = set(Path(tempfile.gettempdir()).glob("harness-run-index.*"))
        snapshot_tree(self.checkout)
        after = set(Path(tempfile.gettempdir()).glob("harness-run-index.*"))
        self.assertEqual(after, before)

    def test_snapshot_index_is_removed_when_snapshot_fails(self):
        before = set(Path(tempfile.gettempdir()).glob("harness-run-index.*"))
        with self.assertRaises(RunError):
            snapshot_tree(self.root / "missing")
        after = set(Path(tempfile.gettempdir()).glob("harness-run-index.*"))
        self.assertEqual(after, before)

    def test_snapshot_base_reports_checkout_on_snapshot_failure(self):
        directory = self.root / "round"
        directory.mkdir()
        missing = self.root / "missing"
        with self.assertRaisesRegex(RunError, "^cannot snapshot the checkout {0}$".format(missing)):
            snapshot_base(directory, missing)


if __name__ == "__main__":
    unittest.main()

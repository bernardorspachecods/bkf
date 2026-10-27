import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from harness.engine.run import RunError
import plan_integration
from plan_integration import _normalize_paths, _patch_files, _tree_entries, accept_integration, rebase_integration


class PlanIntegrationCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        (self.repo / "unit.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "initial")
        self.runs = self.root / "runs"
        self.env = os.environ.copy()
        self.env["PLAN_RUNS_DIR"] = str(self.runs)
        self.run = self.runs / "sample"
        self.run.mkdir(parents=True)
        (self.run / "repo").write_text(str(self.repo.resolve()) + "\n", encoding="utf-8")
        (self.run / "00-input").mkdir()
        (self.run / "00-input/order").write_text("01-one 02-two\n", encoding="utf-8")
        self.integration = self.run / "S1-integration"
        self.integration.mkdir()
        self.base = self.git("write-tree")
        (self.integration / "base").write_text(self.base + "\n", encoding="utf-8")
        (self.integration / "base-format").write_text("tree\n", encoding="utf-8")
        self.unit_one = self.run / "01-one"
        self.unit_one.mkdir()
        (self.unit_one / "status").write_text("passed\n", encoding="utf-8")
        (self.run / ".done-01-one").touch()
        unit_two = self.run / "02-two"
        unit_two.mkdir()
        self.checkout_file = self.repo / "unit.txt"
        self.checkout_file.write_text("unit\n", encoding="utf-8")
        self.patch = subprocess.run(
            ["git", "diff", "--", "unit.txt"], cwd=str(self.repo),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        ).stdout
        (self.unit_one / "final.patch").write_text(self.patch, encoding="utf-8")
        (self.integration / ".applied-01-one").touch()
        self.tree_before = self.git("write-tree")
        self.index_before = (self.repo / ".git/index").read_bytes()
        self.checkout_before = {"unit.txt": self.checkout_file.read_bytes()}

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo)] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        ).stdout.strip()

    def call(self, command, *args, **kwargs):
        working_directory = kwargs.pop("working_directory", self.repo)
        output = io.StringIO()
        previous = os.getcwd()
        try:
            os.chdir(working_directory)
            with contextlib.redirect_stdout(output):
                code = command(list(args), environ=self.env)
        finally:
            os.chdir(previous)
        return code, output.getvalue()

    def assert_refusal_preserves_checkout(self):
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.index_before)
        for path, contents in self.checkout_before.items():
            self.assertEqual((self.repo / path).read_bytes(), contents)

    def test_path_normalisation_matches_shell_rules(self):
        self.assertEqual(_normalize_paths(["./plans/", "tests//"]), ["plans", "tests/"])
        for path in ("/etc", "plans/../tests", "././plans", "plans/./one"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(RunError, "bad path"):
                    _normalize_paths([path])

    def test_patch_paths_include_old_and_new_names(self):
        patch = "diff --git a/old.txt b/new.txt\nindex 1..2 100644\n"
        self.assertEqual(_patch_files(patch), ["new.txt", "old.txt"])

    def test_tree_paths_use_literal_pathspecs(self):
        with mock.patch("plan_integration._git", return_value=mock.Mock(returncode=0, stdout=b"")) as git:
            self.assertEqual(_tree_entries(self.repo, "tree", "owner*.txt"), [])
        self.assertIn("--literal-pathspecs", git.call_args.args[1])

    def test_rebase_refuses_after_integrator_ran_without_paths(self):
        (self.integration / "rounds" / "1").mkdir(parents=True)
        (self.integration / "rounds" / "1" / "integrate.last-message.md").write_text(
            "handoff\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RunError, "the integrator already changed the checkout"):
            self.call(rebase_integration, "sample", "1")
        self.assert_refusal_preserves_checkout()

    def test_rebase_refuses_a_path_covering_a_unit_diff(self):
        with self.assertRaisesRegex(RunError, "01-one: unit.txt"):
            self.call(rebase_integration, "sample", "1", "--paths", "unit.txt")
        self.assertEqual((self.integration / "base").read_text(encoding="utf-8"), self.base + "\n")
        self.assert_refusal_preserves_checkout()

    def test_rebase_without_paths_removes_applied_unit_patch_from_new_base(self):
        owner_file = self.repo / "owner.txt"
        owner_file.write_text("owner\n", encoding="utf-8")
        self.call(rebase_integration, "sample", "1")
        new_base = (self.integration / "base").read_text(encoding="utf-8").strip()
        names = self.git("ls-tree", "-r", "--name-only", new_base).splitlines()
        self.assertIn("owner.txt", names)
        self.assertEqual(self.git("show", new_base + ":unit.txt"), "base")
        self.assertTrue(list(self.integration.glob(".base.before-rebase-*")))
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.index_before)

    def test_rebase_paths_moves_current_file_into_new_base(self):
        owner_file = self.repo / "owner.txt"
        owner_file.write_text("owner\n", encoding="utf-8")
        code, output = self.call(rebase_integration, "sample", "1", "--paths", "owner.txt")
        new_base = (self.integration / "base").read_text(encoding="utf-8").strip()
        names = self.git("ls-tree", "-r", "--name-only", new_base).splitlines()
        self.assertEqual(code, 0)
        self.assertIn("owner.txt", names)
        self.assertIn("owner.txt", output)
        self.assertIn("S1-integration: base moved under owner.txt; 1 file(s) no longer in the diff: owner.txt", (self.run / "status.log").read_text())
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.index_before)

    def test_rebase_paths_treats_wildcards_literally(self):
        (self.repo / "owner-one.txt").write_text("one\n", encoding="utf-8")
        (self.repo / "owner-two.txt").write_text("two\n", encoding="utf-8")
        with self.assertRaisesRegex(RunError, r"nothing under owner\*\.txt differs from the base"):
            self.call(rebase_integration, "sample", "1", "--paths", "owner*.txt")
        self.assertEqual((self.integration / "base").read_text(encoding="utf-8"), self.base + "\n")
        self.assert_refusal_preserves_checkout()

    def test_rebase_paths_removes_wildcard_named_file_literally(self):
        selected = self.repo / "owner[1].txt"
        peer = self.repo / "owner1.txt"
        selected.write_text("selected base\n", encoding="utf-8")
        peer.write_text("peer base\n", encoding="utf-8")
        self.git("add", "owner[1].txt", "owner1.txt")
        self.git("commit", "-qm", "add wildcard names")
        self.base = self.git("write-tree")
        (self.integration / "base").write_text(self.base + "\n", encoding="utf-8")

        selected.write_text("selected checkout\n", encoding="utf-8")
        self.checkout_before["owner[1].txt"] = selected.read_bytes()
        self.checkout_before["owner1.txt"] = peer.read_bytes()
        self.index_before = (self.repo / ".git/index").read_bytes()

        with mock.patch("plan_integration._git", wraps=plan_integration._git) as git:
            self.call(rebase_integration, "sample", "1", "--paths", "owner[1].txt")

        removal = next(
            call.args[1] for call in git.call_args_list
            if "update-index" in call.args[1] and "--force-remove" in call.args[1]
        )
        self.assertIn("--literal-pathspecs", removal)

        new_base = (self.integration / "base").read_text(encoding="utf-8").strip()
        self.assertEqual(self.git("show", new_base + ":owner[1].txt"), "selected checkout")
        self.assertEqual(self.git("show", new_base + ":owner1.txt"), "peer base")
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.index_before)

    def test_accept_closes_passed_applied_group(self):
        (self.run / "02-two" / "status").write_text("passed\n", encoding="utf-8")
        (self.run / ".done-02-two").touch()
        (self.integration / ".applied-02-two").touch()
        worktree = self.run / "worktrees" / "01-one"
        worktree.mkdir(parents=True)
        code, output = self.call(accept_integration, "sample", "1", "--why", "reviewed")
        self.assertEqual(code, 0)
        self.assertEqual((self.integration / "status").read_text(encoding="utf-8"), "passed\n")
        self.assertTrue((self.run / ".done-S1-integration").exists())
        self.assertFalse((self.run / "worktrees").exists())
        self.assertIn("S1-integration is closed", output)

    def test_accept_refuses_a_unit_that_did_not_pass(self):
        (self.run / "02-two" / "status").write_text("passed\n", encoding="utf-8")
        (self.run / ".done-02-two").touch()
        (self.integration / ".applied-02-two").touch()
        (self.unit_one / "status").write_text("escalated\n", encoding="utf-8")
        with self.assertRaisesRegex(RunError, "unit 01-one has not passed"):
            self.call(accept_integration, "sample", "1", "--why", "reviewed")
        self.assertFalse((self.run / ".done-S1-integration").exists())
        self.assertFalse((self.integration / "status").exists())
        self.assert_refusal_preserves_checkout()

    def test_accept_requires_the_plan_repository(self):
        other = self.root / "other"
        other.mkdir()
        self.git("worktree", "add", "--detach", str(other), "HEAD")
        with self.assertRaisesRegex(RunError, "run accept-integration inside the plan's repository"):
            self.call(
                accept_integration, "sample", "1", "--why", "reviewed",
                working_directory=other,
            )
        self.assertFalse((self.run / ".done-S1-integration").exists())
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.index_before)


if __name__ == "__main__":
    unittest.main()

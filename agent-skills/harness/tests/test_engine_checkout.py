"""A run's worktree: created on a branch, set up as declared, committed, and taken away."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness.engine.checkout import commit_all, create_tree, prepare_tree, remove_tree, uncommitted
from harness.engine.run import RunError


def git(directory, *args):
    return subprocess.run(["git", "-C", str(directory)] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        self.run_path = self.root / "run"
        self.run_path.mkdir()

    def declare(self, section):
        (self.repo / ".plan-run.json").write_text(json.dumps({"worktree": section}), encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "declare")

    def test_uncommitted_lists_changed_and_untracked_files_but_not_ignored_ones(self):
        self.assertEqual(uncommitted(self.repo), [])
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("x\n", encoding="utf-8")
        listed = " ".join(uncommitted(self.repo))
        self.assertIn("a.txt", listed)
        self.assertIn("new.txt", listed)
        self.assertNotIn("ignored.txt", listed)

    def test_a_tree_on_a_branch_is_created_and_removed_with_its_branch(self):
        tree = create_tree(self.run_path, self.repo, "plan/x")
        self.assertEqual(git(tree, "branch", "--show-current").strip(), "plan/x")
        self.assertEqual((self.run_path / "branch").read_text(), "plan/x\n")
        self.assertEqual(remove_tree(self.run_path, self.repo), "plan/x")
        self.assertFalse(tree.exists())
        self.assertIn("plan/x", git(self.repo, "branch", "--list", "--format=%(refname:short)"))
        create_tree(self.run_path, self.repo, "plan/y")
        remove_tree(self.run_path, self.repo, delete_branch=True)
        self.assertNotIn("plan/y", git(self.repo, "branch", "--list", "--format=%(refname:short)"))

    def test_a_detached_tree_is_cut_at_the_commit_given(self):
        head = git(self.repo, "rev-parse", "HEAD").strip()
        tree = create_tree(self.run_path, self.repo, commit=head)
        self.assertEqual(git(tree, "rev-parse", "HEAD").strip(), head)
        self.assertEqual(git(tree, "branch", "--show-current").strip(), "")
        self.assertFalse((self.run_path / "branch").exists())

    def test_a_branch_that_exists_is_refused(self):
        git(self.repo, "branch", "plan/x")
        with self.assertRaises(RunError) as error:
            create_tree(self.run_path, self.repo, "plan/x")
        self.assertIn("cannot create the worktree", str(error.exception))

    def test_removing_a_run_without_a_tree_does_nothing(self):
        self.assertEqual(remove_tree(self.run_path, self.repo, delete_branch=True), "")

    def test_prepare_copies_what_exists_runs_the_commands_and_reports_both(self):
        (self.repo / "secret.env").write_text("S=1\n", encoding="utf-8")
        (self.repo / "data").mkdir()
        (self.repo / "data" / "f.txt").write_text("d\n", encoding="utf-8")
        self.declare({"copy": ["secret.env", "data", "gone.env"], "prepare": ["echo built > built.txt"]})
        tree = create_tree(self.run_path, self.repo, "plan/p")
        notes = prepare_tree(self.run_path, self.repo, tree, 30)
        self.assertEqual((tree / "secret.env").read_text(), "S=1\n")
        self.assertEqual((tree / "data" / "f.txt").read_text(), "d\n")
        self.assertEqual((tree / "built.txt").read_text(), "built\n")
        self.assertEqual(notes, [
            "worktree.copy: secret.env", "worktree.copy: data",
            "worktree.copy: gone.env does not exist in the checkout, skipped",
            "worktree.prepare: 1 command(s) passed"])

    def test_prepare_with_nothing_declared_does_nothing(self):
        tree = create_tree(self.run_path, self.repo, "plan/p")
        self.assertEqual(prepare_tree(self.run_path, self.repo, tree, 30), [])

    def test_prepare_refuses_paths_outside_the_repository(self):
        for bad in ("../x", "/etc/passwd", "a/../../x"):
            with self.subTest(bad=bad):
                self.declare({"copy": [bad]})
                tree = create_tree(self.run_path, self.repo, "plan/q")
                with self.assertRaises(RunError):
                    prepare_tree(self.run_path, self.repo, tree, 30)
                remove_tree(self.run_path, self.repo, delete_branch=True)

    def test_a_failing_prepare_command_raises_and_keeps_its_log(self):
        self.declare({"prepare": ["echo before", "exit 4"]})
        tree = create_tree(self.run_path, self.repo, "plan/p")
        with self.assertRaises(RunError) as error:
            prepare_tree(self.run_path, self.repo, tree, 30)
        self.assertIn("preparing the worktree failed", str(error.exception))
        self.assertTrue((self.run_path / "prepare" / "gate.md").is_file())

    def test_a_malformed_declaration_is_refused(self):
        self.declare({"copy": "secret.env"})
        tree = create_tree(self.run_path, self.repo, "plan/p")
        with self.assertRaises(RunError):
            prepare_tree(self.run_path, self.repo, tree, 30)

    def test_commit_all_commits_changes_once_and_does_nothing_when_there_are_none(self):
        tree = create_tree(self.run_path, self.repo, "plan/c")
        self.assertFalse(commit_all(tree, "nothing"))
        (tree / "b.txt").write_text("b\n", encoding="utf-8")
        self.assertTrue(commit_all(tree, "plan c: unit"))
        self.assertFalse(commit_all(tree, "again"))
        self.assertEqual(git(tree, "log", "-1", "--format=%s").strip(), "plan c: unit")
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "init")


if __name__ == "__main__":
    unittest.main()

"""A review reads the code under review in a worktree of its own, at the right revision."""
import os
import subprocess
import unittest

import test_review


class ReviewIsolationTests(test_review.ReviewWorkflowTests):
    def setUp(self):
        super().setUp()
        self.env.pop("REVIEW_IN_PLACE")

    def head(self, directory):
        return self._git("-C", str(directory), "rev-parse", "HEAD").stdout.decode().strip()

    def test_a_working_tree_review_reads_and_gates_a_worktree_holding_the_changes(self):
        result = self.start("iso", "-s", str(self.spec), "-g", "pwd > cwd.txt; cat change.txt > seen.txt")
        run = self.runs / "iso"
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = run / "tree"
        self.assertEqual((tree / "change.txt").read_text(), "base\nchange\n")
        self.assertEqual((tree / "seen.txt").read_text(), "base\nchange\n")
        self.assertEqual((tree / "cwd.txt").read_text().strip(), str(tree.resolve()))
        self.assertEqual((self.repo / "change.txt").read_text(), "base\nchange\n")
        self.assertFalse((self.repo / "seen.txt").exists())
        brief = (run / "01-review" / "spec" / "brief.md").read_text()
        self.assertIn("It is at {0}.".format(tree), brief)
        report = (run / "report.md").read_text()
        self.assertIn("in a worktree of the run", report)

    def test_a_range_review_reads_the_end_of_the_range_not_the_current_branch(self):
        base = self.head(self.repo)
        self._git("-C", str(self.repo), "checkout", "-q", "-b", "feature")
        (self.repo / "change.txt").write_text("feature\n", encoding="utf-8")
        self._git("-C", str(self.repo), "commit", "-qam", "feature work")
        feature = self.head(self.repo)
        self._git("-C", str(self.repo), "checkout", "-q", "-")
        self._git("-C", str(self.repo), "checkout", "--", ".")
        result = self.call("start", "-s", str(self.spec), "-g", "cat change.txt > seen.txt", "rng", "{0}...{1}".format(base, feature))
        run = self.runs / "rng"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(run / "tree"), feature)
        self.assertEqual((run / "tree" / "seen.txt").read_text(), "feature\n")
        self.assertNotEqual((self.repo / "change.txt").read_text(), "feature\n")

    def test_finish_removes_the_worktree(self):
        self.assertEqual(self.start("done", "-s", str(self.spec)).returncode, 0)
        result = self.call("finish", "done")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("done", self._git("-C", str(self.repo), "worktree", "list").stdout.decode())
        self.assertFalse((self.runs / "done").exists())
        kept = self.repo / "records" / "reviews" / "done"
        self.assertTrue((kept / "report.md").is_file())
        self.assertFalse((kept / "tree").exists())

    def test_the_flag_keeps_the_old_behaviour(self):
        result = self.start("flag", "-s", str(self.spec), "--in-place")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.runs / "flag" / "tree").exists())


# The tests of the parent class check the in-place texts; only the ones above belong here.
for _name in dir(test_review.ReviewWorkflowTests):
    if _name.startswith("test_") and _name not in ReviewIsolationTests.__dict__:
        setattr(ReviewIsolationTests, _name, None)


if __name__ == "__main__":
    unittest.main()

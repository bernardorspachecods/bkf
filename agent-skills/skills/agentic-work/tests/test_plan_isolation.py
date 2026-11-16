"""A plan run works in a worktree of its own, on its own branch, and leaves the checkout untouched."""
import contextlib
import io
import json
import subprocess
import unittest

from plan_test_support import PlanRunFixture


class PlanIsolationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PlanRunFixture(self)
        self.repo = self.fixture.repo

    def tearDown(self):
        self.fixture.close()

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = self.fixture.call(*args)
        return code, output.getvalue(), errors.getvalue()

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", str(cwd or self.repo)] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout

    def branch(self, name):
        return self.git("branch", "--list", "--format=%(refname:short)", name).strip()

    def start(self, name="iso", *flags):
        self.fixture.add_brief("one")
        self.fixture.add_brief("two")
        plan = self.fixture.write_plan("one.md", "two.md")
        return self.call("start", *flags, name, str(self.fixture.goal), str(plan))

    def test_the_work_lands_on_a_branch_and_the_checkout_stays_untouched(self):
        head = self.git("rev-parse", "HEAD").strip()
        code, out, err = self.start()
        run = self.fixture.runs / "iso"
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), head)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual((self.repo / "seed.txt").read_text(), "seed\n")
        tree = run / "tree"
        self.assertEqual((tree / "seed.txt").read_text(), "seed\nchange\nchange\n")
        self.assertEqual((run / "branch").read_text(), "plan/iso\n")
        subjects = self.git("log", "--format=%s", "plan/iso").splitlines()
        self.assertEqual(subjects[:2], ["plan iso: 02-two", "plan iso: 01-one"])
        self.assertEqual(self.branch("plan/iso"), "plan/iso")

    def test_a_checkout_with_uncommitted_changes_is_refused_and_leaves_nothing_behind(self):
        (self.repo / "seed.txt").write_text("edited\n", encoding="utf-8")
        code, out, err = self.start()
        self.assertEqual(code, 1)
        self.assertIn("1 uncommitted change(s)", err)
        self.assertIn("--in-place", err)
        self.assertFalse((self.fixture.runs / "iso").exists())
        self.assertEqual(self.branch("plan/iso"), "")

    def test_in_place_works_in_the_checkout_as_before(self):
        (self.repo / "seed.txt").write_text("edited\n", encoding="utf-8")
        code, out, err = self.start("inplace", "--in-place")
        self.assertEqual(code, 0, err)
        self.assertFalse((self.fixture.runs / "inplace" / "tree").exists())
        self.assertEqual((self.repo / "seed.txt").read_text(), "edited\nchange\nchange\n")
        self.assertEqual(self.branch("plan/inplace"), "")

    def test_the_worktree_is_set_up_as_the_repository_declares(self):
        (self.repo / "local.env").write_text("SECRET=1\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("local.env\nsetup-ran\n", encoding="utf-8")
        (self.repo / ".plan-run.json").write_text(json.dumps({"worktree": {
            "copy": ["local.env", "missing.env"], "prepare": ["echo ok > setup-ran"]}}), encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "declare")
        code, out, err = self.start()
        run = self.fixture.runs / "iso"
        self.assertEqual(code, 0, err)
        self.assertEqual((run / "tree" / "local.env").read_text(), "SECRET=1\n")
        self.assertEqual((run / "tree" / "setup-ran").read_text(), "ok\n")
        log = (run / "status.log").read_text()
        self.assertIn("worktree.copy: local.env", log)
        self.assertIn("worktree.copy: missing.env does not exist in the checkout, skipped", log)
        self.assertIn("worktree.prepare: 1 command(s) passed", log)

    def test_a_failing_prepare_command_leaves_nothing_behind(self):
        (self.repo / ".plan-run.json").write_text(json.dumps({"worktree": {"prepare": ["exit 3"]}}), encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "declare")
        code, out, err = self.start()
        self.assertEqual(code, 1)
        self.assertIn("preparing the worktree failed", err)
        self.assertFalse((self.fixture.runs / "iso").exists())
        self.assertEqual(self.branch("plan/iso"), "")
        self.assertNotIn("iso", self.git("worktree", "list"))

    def test_a_copy_outside_the_repository_is_refused(self):
        (self.repo / ".plan-run.json").write_text(json.dumps({"worktree": {"copy": ["../x"]}}), encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "declare")
        code, out, err = self.start()
        self.assertEqual(code, 1)
        self.assertIn("needs paths inside the repository", err)

    def test_finish_keeps_the_branch_and_removes_the_worktree(self):
        self.start()
        code, out, err = self.call("finish", "iso")
        self.assertEqual(code, 0, err)
        self.assertIn("The work is on branch plan/iso", out)
        self.assertFalse((self.fixture.runs / "iso").exists())
        self.assertNotIn("iso", self.git("worktree", "list"))
        self.assertEqual(self.branch("plan/iso"), "plan/iso")
        record = self.repo / "records" / "plans" / "iso"
        self.assertTrue((record / "report.md").is_file())
        self.assertFalse((record / "tree").exists())

    def test_discard_removes_the_worktree_and_the_branch(self):
        self.start()
        code, out, err = self.call("finish", "--discard", "iso")
        self.assertEqual(code, 0, err)
        self.assertIn("Deleted branch plan/iso", out)
        self.assertEqual(self.branch("plan/iso"), "")
        self.assertNotIn("iso", self.git("worktree", "list"))

    def test_a_group_runs_inside_the_runs_worktree(self):
        self.fixture.add_brief("a")
        self.fixture.add_brief("b")
        plan = self.fixture.write_plan("a.md b.md")
        code, out, err = self.call("start", "grp", str(self.fixture.goal), str(plan))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("status", "--porcelain"), "")
        subjects = self.git("log", "--format=%s", "plan/grp").splitlines()
        self.assertIn("plan grp: S1 integration", subjects)


if __name__ == "__main__":
    unittest.main()

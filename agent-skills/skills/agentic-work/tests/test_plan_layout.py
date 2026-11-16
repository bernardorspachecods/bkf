"""Where plan runs and pending plans live: a folder per repository, and an old flat run still found."""
import contextlib
import io
import shutil
import unittest

from plan_test_support import PlanRunFixture


class PlanLayoutTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PlanRunFixture(self)
        self.home = self.fixture.root / "home"
        self.home.mkdir()
        self.fixture.env.pop("PLAN_RUNS_DIR")
        self.fixture.env["HOME"] = str(self.home)
        self.slug = self.fixture.repo.name

    def tearDown(self):
        self.fixture.close()

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = self.fixture.call(*args)
        return code, output.getvalue(), errors.getvalue()

    def _pending(self, name):
        folder = self.home / ".plan-runs-pending" / self.slug / name
        folder.mkdir(parents=True)
        (folder / "goal.md").write_text("Goal\n", encoding="utf-8")
        (folder / "unit.md").write_text("## Result\nImplement it.\n", encoding="utf-8")
        (folder / "plan.txt").write_text("unit.md\n", encoding="utf-8")
        return folder

    def test_a_run_is_created_under_its_repository(self):
        self.fixture.add_brief("unit")
        code, out, err = self.call("start", "sample", str(self.fixture.goal), str(self.fixture.write_plan("unit.md")))
        run = self.home / ".plan-runs" / self.slug / "sample"
        self.assertEqual(code, 0, err)
        self.assertTrue((run / "report.md").is_file())
        self.assertFalse((self.home / ".plan-runs" / "sample").exists())
        code, out, _ = self.call("status", "sample")
        self.assertEqual(code, 0)
        self.assertIn("READY", out)

    def test_a_run_made_in_the_old_flat_folder_is_still_found(self):
        self.fixture.add_brief("unit")
        self.call("start", "sample", str(self.fixture.goal), str(self.fixture.write_plan("unit.md")))
        new = self.home / ".plan-runs" / self.slug / "sample"
        old = self.home / ".plan-runs" / "sample"
        shutil.move(str(new), str(old))
        code, out, err = self.call("status", "sample")
        self.assertEqual(code, 0, err)
        self.assertIn("READY", out)

    def test_start_by_name_uses_the_pending_plan_and_moves_it_into_the_run(self):
        folder = self._pending("later")
        code, out, err = self.call("pending")
        self.assertEqual((code, out), (0, "later\n"))
        code, out, err = self.call("start", "later")
        run = self.home / ".plan-runs" / self.slug / "later"
        self.assertEqual(code, 0, err)
        self.assertFalse(folder.exists())
        self.assertTrue((run / "00-input" / "source" / "plan.txt").is_file())
        self.assertTrue((run / "report.md").is_file())
        self.assertEqual(self.call("pending")[1], "")

    def test_start_by_name_without_a_pending_plan_says_where_it_looked(self):
        code, out, err = self.call("start", "nothing")
        self.assertEqual(code, 1)
        self.assertIn("no pending plan nothing for this repository", err)
        self.assertIn(".plan-runs-pending", err)


if __name__ == "__main__":
    unittest.main()

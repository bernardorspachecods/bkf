"""Where runs and pending plans live, and how an old flat run is still found."""
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from harness.engine.layout import find_run, list_pending, new_run_parent, pending_dir, repo_slug
from harness.engine.run import RunError


class LayoutTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.environ = {}
        patcher = unittest.mock.patch("pathlib.Path.home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, folder, repo):
        folder.mkdir(parents=True)
        (folder / "repo").write_text(repo + "\n", encoding="utf-8")
        return folder

    def test_the_slug_is_the_folder_name_of_the_repository(self):
        self.assertEqual(repo_slug("/work/desmor-hub"), "desmor-hub")

    def test_a_new_run_goes_under_its_repository(self):
        self.assertEqual(new_run_parent("plan", "/work/hub", self.environ), self.home / ".plan-runs" / "hub")

    def test_an_explicit_folder_holds_the_runs_themselves(self):
        self.assertEqual(new_run_parent("plan", "/work/hub", {"PLAN_RUNS_DIR": "/x"}), Path("/x"))
        self.assertEqual(new_run_parent("plan", "/work/hub", {"HARNESS_RUNS_DIR": "/y", "PLAN_RUNS_DIR": "/x"}), Path("/y"))
        self.assertEqual(find_run("plan", "r", "/work/hub", {"PLAN_RUNS_DIR": "/x"}), Path("/x/r"))

    def test_a_run_is_found_in_its_repository_folder(self):
        own = self._run(self.home / ".plan-runs" / "hub" / "r", "/work/hub")
        self.assertEqual(find_run("plan", "r", "/work/hub", self.environ), own)

    def test_an_old_flat_run_of_the_same_repository_is_still_found(self):
        old = self._run(self.home / ".plan-runs" / "r", "/work/hub")
        self.assertEqual(find_run("plan", "r", "/work/hub", self.environ), old)

    def test_an_old_flat_run_of_another_repository_is_not_taken(self):
        self._run(self.home / ".plan-runs" / "r", "/work/other")
        self.assertEqual(find_run("plan", "r", "/work/hub", self.environ), self.home / ".plan-runs" / "hub" / "r")

    def test_without_a_repository_the_only_run_with_that_name_is_found(self):
        own = self._run(self.home / ".plan-runs" / "hub" / "r", "/work/hub")
        self.assertEqual(find_run("plan", "r", None, self.environ), own)

    def test_without_a_repository_two_runs_with_one_name_are_refused(self):
        self._run(self.home / ".plan-runs" / "hub" / "r", "/work/hub")
        self._run(self.home / ".plan-runs" / "other" / "r", "/work/other")
        with self.assertRaises(RunError) as error:
            find_run("plan", "r", None, self.environ)
        self.assertIn("more than one run is called r", str(error.exception))

    def test_a_missing_run_is_reported_where_it_would_be(self):
        self.assertEqual(find_run("plan", "gone", "/work/hub", self.environ), self.home / ".plan-runs" / "hub" / "gone")

    def test_a_bad_name_is_refused(self):
        with self.assertRaises(RunError):
            find_run("plan", "../x", "/work/hub", self.environ)

    def test_pending_plans_are_listed_per_repository(self):
        for repo, name in (("hub", "b"), ("hub", "a"), ("other", "c")):
            pending_dir("plan", "/work/" + repo, name, self.environ).mkdir(parents=True)
        self.assertEqual(list_pending("plan", "/work/hub", self.environ), ["a", "b"])
        self.assertEqual(list_pending("plan", "/work/none", self.environ), [])
        self.assertEqual(pending_dir("plan", "/work/hub", "a", {"PLAN_PENDING_DIR": "/p"}), Path("/p/hub/a"))


if __name__ == "__main__":
    unittest.main()

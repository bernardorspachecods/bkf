import pathlib
import tempfile
import unittest
from unittest import mock

from harness.engine.record import RecordError, keep_record


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.repo = self.root / "repo"
        self.run = self.root / "runs" / "sample"
        self.repo.mkdir()
        self.run.mkdir(parents=True)
        (self.run / "report.md").write_text("report\n", encoding="utf-8")
        (self.run / "events.jsonl").write_text("raw\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_copy_verifies_and_removes_source(self):
        message = keep_record(self.run, self.repo, "reviews", "sample", ["*.jsonl"])
        destination = self.repo / "records/reviews/sample"
        self.assertEqual("report\n", (destination / "report.md").read_text())
        self.assertFalse((destination / "events.jsonl").exists())
        self.assertFalse(self.run.exists())
        self.assertEqual("Kept in {0}; removed {1}".format(destination, self.run), message)

    def test_exclusion_can_remove_a_directory_tree(self):
        (self.run / "review").mkdir()
        (self.run / "review/private.md").write_text("private", encoding="utf-8")
        keep_record(self.run, self.repo, "reviews", "sample", ["review"])
        self.assertFalse((self.repo / "records/reviews/sample/review").exists())

    def test_mismatch_refuses_to_delete_source(self):
        real_copy = __import__("harness.engine.record", fromlist=["_copy"])._copy

        def broken_copy(source, destination, exclusions):
            real_copy(source, destination, exclusions)
            (destination / "report.md").write_text("corrupt\n", encoding="utf-8")

        with mock.patch("harness.engine.record._copy", side_effect=broken_copy):
            with self.assertRaisesRegex(RecordError, "does not match"):
                keep_record(self.run, self.repo, "reviews", "sample")
        self.assertTrue(self.run.exists())

    def test_destination_exists_refuses(self):
        destination = self.repo / "records/reviews/sample"
        destination.mkdir(parents=True)
        with self.assertRaisesRegex(RecordError, "already exists"):
            keep_record(self.run, self.repo, "reviews", "sample")
        self.assertTrue(self.run.exists())

    def test_name_cannot_escape_records_directory(self):
        with self.assertRaisesRegex(RecordError, "simple path components"):
            keep_record(self.run, self.repo, "reviews", "../outside")
        self.assertTrue(self.run.exists())


if __name__ == "__main__":
    unittest.main()

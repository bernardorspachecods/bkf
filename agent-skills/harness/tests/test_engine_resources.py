"""The shared-memory check: it reports only when too few segments are free, and never removes any."""
import unittest
from unittest.mock import patch

from harness.engine import resources


class ShmTests(unittest.TestCase):
    def check(self, segments, limit=32, min_free=4, system="Darwin"):
        with patch.object(resources.platform, "system", return_value=system), \
                patch.object(resources, "_limit", return_value=limit), \
                patch.object(resources, "_segments", return_value=segments):
            return resources.shm_problem(min_free)

    def test_enough_free_segments_report_nothing(self):
        self.assertIsNone(self.check([("1", 0)] * 10))

    def test_too_few_free_names_the_orphans_and_the_command(self):
        text = self.check([("11", 0), ("12", 3)] + [("9", 1)] * 27)
        self.assertIn("only 3 of 32", text)
        self.assertIn("not the disk", text)
        self.assertIn("ipcrm -m 11 .", text)
        self.assertNotIn("-m 12", text)

    def test_all_attached_says_to_stop_the_databases(self):
        self.assertIn("stop the databases", self.check([("1", 2)] * 30))

    def test_off_when_zero_other_system_or_unreadable(self):
        self.assertIsNone(self.check([("1", 0)] * 32, min_free=0))
        self.assertIsNone(self.check([("1", 0)] * 32, system="Linux"))
        self.assertIsNone(self.check(None))
        self.assertIsNone(self.check([("1", 0)] * 32, limit=None))


if __name__ == "__main__":
    unittest.main()

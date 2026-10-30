import io
import os
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from harness import cli
from harness.quota import parse_reset, wait_for_reset

LOCAL = timezone(timedelta(hours=1))
NOW = datetime(2026, 10, 29, 19, 50, tzinfo=LOCAL)


def at(*parts, tz=LOCAL):
    return datetime(*parts, tzinfo=tz)


class ParseResetTests(unittest.TestCase):
    def parse(self, text, now=NOW):
        return parse_reset(text, now)

    def test_clock_time_today(self):
        self.assertEqual(self.parse("8:26 PM"), at(2026, 10, 29, 20, 26))
        self.assertEqual(self.parse("8:26 PM."), at(2026, 10, 29, 20, 26))

    def test_midday_and_midnight(self):
        self.assertEqual(self.parse("12:05 PM", at(2026, 10, 29, 11, 0)), at(2026, 10, 29, 12, 5))
        self.assertEqual(self.parse("12:05 AM", at(2026, 10, 29, 23, 50)), at(2026, 10, 30, 0, 5))

    def test_clock_time_just_passed_is_reached_not_tomorrow(self):
        self.assertEqual(self.parse("7:44 PM"), at(2026, 10, 29, 19, 44))

    def test_clock_time_long_passed_is_tomorrow(self):
        self.assertEqual(self.parse("8:26 AM"), at(2026, 10, 30, 8, 26))

    def test_date_forms(self):
        self.assertEqual(self.parse("2026-10-29 20:26"), at(2026, 10, 29, 20, 26))
        self.assertEqual(self.parse("resets at 2026-10-29 20:26"), at(2026, 10, 29, 20, 26))
        self.assertEqual(self.parse("2026-10-23 10:00 UTC"), at(2026, 10, 23, 10, 0, tz=timezone.utc))
        self.assertEqual(self.parse("8:26 PM UTC", at(2026, 10, 29, 20, 0, tz=timezone.utc)),
                         at(2026, 10, 29, 20, 26, tz=timezone.utc))

    def test_unreadable_text_is_none(self):
        for text in ("tomorrow", "later", "", "13:00 PM", "0:30 AM", "2026-13-40 10:00", "tomorrow at 5 PM"):
            self.assertIsNone(self.parse(text), text)


class WaitTests(unittest.TestCase):
    def test_sleeps_until_the_reset_plus_margin(self):
        clock = [NOW.timestamp()]
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            clock[0] += seconds

        with redirect_stderr(io.StringIO()):
            status = wait_for_reset("8:26 PM", 120, now=NOW, sleep=sleep, clock=lambda: clock[0])
        self.assertEqual(status, 0)
        self.assertEqual(clock[0], at(2026, 10, 29, 20, 28).timestamp())
        self.assertTrue(all(0 < s <= 30 for s in slept))

    def wait_from_now(self, text):
        clock = [NOW.timestamp()]
        with redirect_stderr(io.StringIO()):
            wait_for_reset(text, 120, now=NOW, sleep=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0])
        return clock[0]

    def test_reached_time_waits_only_what_is_left_of_the_margin(self):
        self.assertEqual(self.wait_from_now("7:49 PM"), at(2026, 10, 29, 19, 51).timestamp())

    def test_reached_time_past_the_margin_does_not_wait(self):
        self.assertEqual(self.wait_from_now("7:44 PM"), NOW.timestamp())

    def test_unreadable_text_fails_without_sleeping(self):
        err = io.StringIO()
        with redirect_stderr(err):
            status = wait_for_reset("tomorrow", 120, now=NOW, sleep=self.fail, clock=lambda: 0)
        self.assertEqual(status, 2)
        self.assertIn("cannot read a time", err.getvalue())

    def test_cli_passes_text_and_margin(self):
        with patch("harness.cli.wait_for_reset", return_value=0) as wait:
            self.assertEqual(cli.main(["quota-wait", "--margin", "60", "8:26 PM"]), 0)
        wait.assert_called_once_with("8:26 PM", 60, announce=None)

    def test_cli_passes_announce_file(self):
        with patch("harness.cli.wait_for_reset", return_value=0) as wait:
            cli.main(["quota-wait", "--announce", "/w/crew-a", "8:26 PM"])
        wait.assert_called_once_with("8:26 PM", 120, announce="/w/crew-a")

    def test_announce_holds_the_wake_time_while_waiting_and_is_removed_after(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "sub", "crew-a")
        clock = [NOW.timestamp()]
        seen = []

        def sleep(seconds):
            seen.append(open(path).read().strip())
            clock[0] += seconds

        with redirect_stderr(io.StringIO()):
            wait_for_reset("7:49 PM", 120, now=NOW, sleep=sleep, clock=lambda: clock[0], announce=path)
        self.assertEqual(seen[0], str(int(at(2026, 10, 29, 19, 51).timestamp())))
        self.assertFalse(os.path.exists(path))

    def test_unreadable_text_announces_nothing(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "crew-a")
        with redirect_stderr(io.StringIO()):
            wait_for_reset("tomorrow", 120, now=NOW, sleep=self.fail, clock=lambda: 0, announce=path)
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()

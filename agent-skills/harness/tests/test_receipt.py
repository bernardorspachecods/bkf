import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.receipt import (
    forget_receipt,
    receipt_gate_file,
    receipt_passes,
    receipt_path,
    write_receipt,
)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        # The unit directory sits outside the checkout, so writing a receipt does not change the tree.
        self.unit = self.root / "unit"
        self.unit.mkdir()
        git_env = os.environ.copy()
        git_env["GIT_CONFIG_NOSYSTEM"] = "1"
        git_env["GIT_CONFIG_GLOBAL"] = os.devnull
        environment = patch.dict(os.environ, git_env)
        environment.start()
        self.addCleanup(environment.stop)
        self.git("init", "-q")
        self.git("config", "user.name", "Harness Test")
        self.git("config", "user.email", "harness@example.invalid")
        (self.checkout / "tracked.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.checkout)] + list(args),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def record_green(self, commands=("true",)):
        data = write_receipt(self.unit, str(self.checkout), list(commands), 5)
        self.assertEqual(data["red"], 0)
        return data

    def test_paths_are_inside_the_unit_receipt_folder(self):
        self.assertEqual(receipt_path(self.unit), self.unit / "receipt" / "receipt.json")
        self.assertEqual(receipt_gate_file(self.unit), self.unit / "receipt" / "gate" / "gate.md")

    def test_write_receipt_writes_gate_logs_where_receipt_gate_file_points(self):
        self.record_green()
        self.assertTrue(receipt_gate_file(self.unit).is_file())
        self.assertIn("Result: all green (1 commands).", receipt_gate_file(self.unit).read_text())

    def test_green_receipt_passes(self):
        self.record_green(("true", "true"))
        self.assertTrue(receipt_passes(self.unit, str(self.checkout), ["true", "true"]))

    def test_receipt_tree_is_taken_after_the_gate(self):
        # The gate writes a file; the receipt must match the tree as it is after the gate, so it still passes.
        self.record_green(("echo made > generated.txt",))
        self.assertTrue((self.checkout / "generated.txt").is_file())
        self.assertTrue(receipt_passes(self.unit, str(self.checkout), ["echo made > generated.txt"]))

    def test_edited_tree_fails(self):
        self.record_green()
        (self.checkout / "tracked.txt").write_text("edited\n")
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true"]))

    def test_new_untracked_file_fails(self):
        self.record_green()
        (self.checkout / "new.txt").write_text("new\n")
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true"]))

    def test_different_commands_fail(self):
        self.record_green(("true", "true"))
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true", "echo other"]))
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true"]))

    def test_red_receipt_fails(self):
        data = write_receipt(self.unit, str(self.checkout), ["false"], 5)
        self.assertEqual(data["red"], 1)
        self.assertEqual(json.loads(receipt_path(self.unit).read_text())["red"], 1)
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["false"]))

    def test_missing_receipt_fails(self):
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true"]))

    def test_unreadable_json_fails(self):
        self.record_green()
        for content in ("{not json", "[]", '"green"'):
            with self.subTest(content=content):
                receipt_path(self.unit).write_text(content, encoding="utf-8")
                self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true"]))

    def test_receipt_without_integer_red_fails(self):
        self.record_green()
        receipt = json.loads(receipt_path(self.unit).read_text())
        for red in (None, 0.0, False):
            with self.subTest(red=red):
                receipt["red"] = red
                receipt_path(self.unit).write_text(json.dumps(receipt), encoding="utf-8")
                self.assertFalse(receipt_passes(self.unit, str(self.checkout), ["true"]))

    def test_forget_receipt_removes_it_and_tolerates_none(self):
        self.record_green()
        forget_receipt(self.unit)
        self.assertFalse(receipt_path(self.unit).exists())
        forget_receipt(self.unit)

    def test_write_receipt_removes_old_receipt_before_running_and_leaves_a_red_one(self):
        self.record_green()
        self.assertTrue(receipt_path(self.unit).is_file())
        # The first command passes only when the old receipt is already gone; the second always fails.
        gone = "test ! -e {0}".format(shlex.quote(str(receipt_path(self.unit))))
        data = write_receipt(self.unit, str(self.checkout), [gone, "false"], 5)
        self.assertEqual(data["red"], 1)
        receipt = json.loads(receipt_path(self.unit).read_text())
        self.assertEqual(receipt["red"], 1)
        self.assertEqual(receipt["commands"], [gone, "false"])
        self.assertFalse(receipt_passes(self.unit, str(self.checkout), [gone, "false"]))


if __name__ == "__main__":
    unittest.main()

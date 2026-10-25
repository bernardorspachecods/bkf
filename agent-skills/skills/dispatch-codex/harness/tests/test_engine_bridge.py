import errno
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from harness.engine import bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.write_package({"db:test": "printf base", "db:prod": "printf prod"})
        self.write_config({"bridge": {"pnpmScripts": ["^db:test$"]}})
        self.base = self.tree()
        self.base_file = self.root / "base"
        self.base_file.write_text(self.base + "\n", encoding="utf-8")
        self.log = self.root / "porteiro.log"

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.checkout)] + list(args),
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.decode("utf-8").strip()

    def write_package(self, scripts):
        (self.checkout / "package.json").write_text(
            json.dumps({"scripts": scripts}), encoding="utf-8"
        )

    def write_config(self, value):
        (self.checkout / ".plan-run.json").write_text(
            value if isinstance(value, str) else json.dumps(value),
            encoding="utf-8",
        )

    def tree(self):
        self.git("add", "-A")
        return self.git("write-tree")

    def allowed(self, argv, commands=()):
        return bridge.porteiro_allowed(
            self.checkout, self.base_file, list(commands), argv
        )

    def test_gate_command_is_the_only_shell_request_and_keeps_exit_code(self):
        self.assertEqual(
            self.allowed(["bash", "-c", "exit 7"], ["bash -c exit 7"]),
            ("shell", ""),
        )
        self.assertEqual(self.allowed(["echo", "gate-ok"], ["echo gate-ok"]), ("shell", ""))
        self.assertNotEqual(self.allowed(["echo", "gate-no"], ["echo gate-ok"])[0], "shell")

    def test_pnpm_pattern_is_anchored(self):
        self.write_config({"bridge": {"pnpmScripts": ["db:test"]}})
        self.base_file.write_text(self.tree() + "\n", encoding="utf-8")
        self.assertEqual(self.allowed(["pnpm", "db:test"]), ("argv", ""))
        self.assertEqual(
            self.allowed(["pnpm", "db:test:child"]),
            (None, "db:test:child is not in the pnpm scripts that .plan-run.json allows"),
        )

    def test_charset_guard_precedes_pattern_and_script_lookup(self):
        self.write_config({"bridge": {"pnpmScripts": [".*"]}})
        self.base_file.write_text(self.tree() + "\n", encoding="utf-8")
        self.assertEqual(
            self.allowed(["pnpm", "db:test;touch pwned"]),
            (None, "db:test;touch pwned has characters that are not allowed"),
        )

    def test_pattern_must_compile_alone(self):
        self.write_config({"bridge": {"pnpmScripts": ["^db:test$", "x)|(.*"]}})
        self.base_file.write_text(self.tree() + "\n", encoding="utf-8")
        self.assertEqual(
            self.allowed(["pnpm", "db:test"]),
            (None, "the .plan-run.json at the unit's base is not usable: only gate commands run"),
        )

    def test_unparseable_or_wrong_shape_config_is_unusable(self):
        for config in ("{not json", {"bridge": {"pnpmScripts": "db:test"}}):
            with self.subTest(config=config):
                self.write_config(config)
                self.base_file.write_text(self.tree() + "\n", encoding="utf-8")
                self.assertEqual(
                    self.allowed(["pnpm", "db:test"]),
                    (None, "the .plan-run.json at the unit's base is not usable: only gate commands run"),
                )

    def test_checkout_only_config_is_ignored(self):
        self.git("rm", "--cached", ".plan-run.json")
        self.base_file.write_text(self.git("write-tree") + "\n", encoding="utf-8")
        self.assertEqual(
            self.allowed(["pnpm", "db:test"]),
            (None, "no .plan-run.json at the unit's base: only gate commands run"),
        )

    def test_base_tree_can_contain_config_not_in_checkout_index(self):
        base_tree = self.tree()
        self.git("rm", "--cached", ".plan-run.json")
        self.base_file.write_text(base_tree + "\n", encoding="utf-8")
        self.assertEqual(self.allowed(["pnpm", "db:test"]), ("argv", ""))

    def test_changed_checkout_script_is_refused(self):
        self.write_package({"db:test": "printf changed", "db:prod": "printf prod"})
        self.assertEqual(
            self.allowed(["pnpm", "db:test"]),
            (None, "db:test was changed in this unit"),
        )

    def test_refusal_reasons_match_the_bridge(self):
        self.assertEqual(self.allowed([]), (None, "empty request"))
        self.assertEqual(
            self.allowed(["pnpm"]),
            (None, "not allowed: only the pnpm scripts listed in .plan-run.json at the unit's base and the gate commands of the brief"),
        )
        self.assertEqual(
            self.allowed(["pnpm", "db:prod"]),
            (None, "db:prod is not in the pnpm scripts that .plan-run.json allows"),
        )
        self.assertEqual(
            self.allowed(["pnpm", "missing"]),
            (None, "missing is not in the pnpm scripts that .plan-run.json allows"),
        )
        self.write_config({"bridge": {"pnpmScripts": ["^db:ghost$"]}})
        self.base_file.write_text(self.tree() + "\n", encoding="utf-8")
        self.assertEqual(
            self.allowed(["pnpm", "db:ghost"]),
            (None, "db:ghost is not a script of the unit's base"),
        )
        self.assertEqual(
            self.allowed(["rm", "-rf", "."])[1],
            "not allowed: only the pnpm scripts listed in .plan-run.json at the unit's base and the gate commands of the brief",
        )

    def test_timeout_returns_142_and_kills_the_process_group(self):
        self.write_config({"bridge": {"pnpmScripts": []}})
        self.base_file.write_text(self.tree() + "\n", encoding="utf-8")
        marker = self.root / "child.pid"
        command = "sleep 1; touch {0}".format(marker)
        gate = "bash -c '{0}'".format(command)
        with mock.patch.dict(os.environ, {"PLAN_PORTEIRO_TIMEOUT": "0.2"}), bridge.porteiro(
            self.checkout, "01-unit", self.base_file, [gate], self.log
        ):
            script = self.checkout / ".plan-porteiro" / "ponte"
            result = subprocess.run(
                [str(script), "bash", "-c", "'{0}'".format(command)],
                capture_output=True,
            )
        self.assertEqual(result.returncode, 142)
        self.assertTrue(result.stdout.endswith(b"ponte: timed out after 0.2s\n"))
        time.sleep(1.1)
        self.assertFalse(marker.exists())

    def test_missing_executable_publishes_failure_response_and_log(self):
        request_dir = self.checkout / ".plan-porteiro" / "req"
        response_dir = self.checkout / ".plan-porteiro" / "res"
        request_dir.mkdir(parents=True)
        response_dir.mkdir()
        request = request_dir / "missing-command"
        request.write_bytes(b"pnpm\0db:test\0")
        with mock.patch.object(bridge, "porteiro_allowed", return_value=("argv", "")):
            with mock.patch.object(
                bridge.subprocess, "Popen",
                side_effect=FileNotFoundError(errno.ENOENT, "No such file or directory", "pnpm"),
            ):
                bridge.porteiro_handle(
                    self.checkout, "01-unit", self.base_file, [], request, self.log
                )
        self.assertEqual((response_dir / "missing-command.done").read_text(), "127\n")
        self.assertIn(b"pnpm", (response_dir / "missing-command.out").read_bytes())
        line = self.log.read_text(encoding="utf-8").splitlines()[0]
        self.assertRegex(line, r"\t01-unit\tALLOWED exit=127 \d+s\tpnpm db:test$")

    def test_real_ponte_protocol_setup_exclusion_log_and_cleanup(self):
        command = "printf protocol-ok"
        expected_script = bridge.porteiro_ponte_script().encode("utf-8")
        gate_failure = "bash -c 'exit 7'"
        with bridge.porteiro(
            self.checkout, "01-unit", self.base_file, [command, gate_failure], self.log
        ):
            folder = self.checkout / ".plan-porteiro"
            script = folder / "ponte"
            self.assertEqual(script.read_bytes(), expected_script)
            self.assertTrue(os.access(str(script), os.X_OK))
            exclude = pathlib.Path(self.git("rev-parse", "--git-path", "info/exclude"))
            if not exclude.is_absolute():
                exclude = self.checkout / exclude
            self.assertEqual(exclude.read_text().splitlines().count(".plan-porteiro/"), 1)
            result = subprocess.run([str(script), "printf", "protocol-ok"], capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"protocol-ok")
            failed = subprocess.run(
                [str(script), "bash", "-c", "'exit 7'"], capture_output=True
            )
            self.assertEqual(failed.returncode, 7)
            self.assertEqual(failed.stdout, b"")
        self.assertFalse((self.checkout / ".plan-porteiro").exists())
        self.assertEqual(exclude.read_text().splitlines().count(".plan-porteiro/"), 1)
        line = self.log.read_text(encoding="utf-8").splitlines()[0]
        self.assertRegex(line, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\t01-unit\tALLOWED exit=0 \d+s\tprintf protocol-ok$")

    def test_output_is_limited_to_last_200000_bytes(self):
        command = "python3 -c 'import sys; sys.stdout.write(\"x\" * 210000)'"
        with bridge.porteiro(self.checkout, "01-unit", self.base_file, [command], self.log):
            result = subprocess.run(
                [str(self.checkout / ".plan-porteiro" / "ponte"), "python3", "-c", "'import sys; sys.stdout.write(\"x\" * 210000)'"],
                capture_output=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout), 200000)


if __name__ == "__main__":
    unittest.main()

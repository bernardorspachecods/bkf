from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import bkf_hooks


def run(*args: object) -> tuple[int, str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = bkf_hooks.main([str(arg) for arg in args])
    return code, output.getvalue()


class HooksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir()
        self.stub = self.home / "bkf"
        self.stub.write_text(
            "#!" + sys.executable + "\n"
            "import os, sys, time\n"
            "args = sys.argv[1:]\n"
            "mode = os.environ.get('BKF_STUB_MODE', 'ok')\n"
            "if args[:2] == ['hooks', 'run']:\n"
            "    if args[2:3] == ['rules']: raise SystemExit(0)\n"
            "    if mode == 'sleep': time.sleep(1)\n"
            "    if mode == 'traceback': print('Traceback (most recent call last):')\n"
            "    elif mode == 'none': pass\n"
            "    elif mode == 'nonzero': raise SystemExit(7)\n"
            "    else: print('{\"probe\":\"ok\"}')\n",
            encoding="utf-8",
        )
        self.stub.chmod(0o755)
        self.command = str(self.stub)
        patcher = patch("bkf_hooks.shutil.which", return_value=self.command)
        patcher.start()
        self.addCleanup(patcher.stop)

    def config(self, directory: str, name: str) -> dict:
        return json.loads((self.home / directory / name).read_text())

    def test_run_accepts_snapshot_event(self) -> None:
        self.assertEqual(bkf_hooks.build_parser().parse_args(["run", "snapshot"]).event, "snapshot")

    def test_run_rules_prints_file_content(self) -> None:
        path = self.home / ".agent-hooks" / "rules.md"
        path.parent.mkdir()
        path.write_text("Keep changes scoped.\n", encoding="utf-8")
        code, output = run("run", "rules", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertEqual(output, "Keep changes scoped.\n")

    def test_run_rules_missing_or_empty_file_is_silent(self) -> None:
        code, output = run("run", "rules", "--home", self.home)
        self.assertEqual((code, output), (0, ""))
        path = self.home / ".agent-hooks" / "rules.md"
        path.parent.mkdir()
        path.write_text("", encoding="utf-8")
        self.assertEqual(run("run", "rules", "--home", self.home), (0, ""))

    def test_run_rules_invalid_utf8_is_reported(self) -> None:
        path = self.home / ".agent-hooks" / "rules.md"
        path.parent.mkdir()
        path.write_bytes(b"\xff")
        code, output = run("run", "rules", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertIn("rules failed", json.loads(output)["systemMessage"])

    def test_run_rules_truncates_at_line_boundary(self) -> None:
        path = self.home / ".agent-hooks" / "rules.md"
        path.parent.mkdir()
        path.write_text("a" * 3999 + "\n" + "b" * 100, encoding="utf-8")
        code, output = run("run", "rules", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertEqual(output, "a" * 3999 + "\n... rules.md truncated\n")

    def test_preview_changes_nothing(self) -> None:
        code, output = run("install", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertIn("preview only", output)
        self.assertFalse((self.home / ".agent-hooks").exists())
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

    def test_install_registers_both_tools_and_copies_script(self) -> None:
        code, _ = run("install", "--write", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertEqual(
            (self.home / ".agent-hooks" / "mode.py").read_bytes(),
            (TOOLING / "agent_modes.py").read_bytes(),
        )
        for directory, name in ((".claude", "settings.json"), (".codex", "hooks.json")):
            hooks = self.config(directory, name)["hooks"]
            self.assertEqual(set(hooks), {"UserPromptSubmit", "PreToolUse", "SessionStart", "PostToolUse", "Stop"})
            self.assertEqual(len(hooks["UserPromptSubmit"]), 3)
            self.assertEqual(hooks["UserPromptSubmit"][0]["hooks"][0]["command"], "python3 " + str((self.home / ".agent-hooks" / "mode.py").resolve()))
            self.assertEqual(hooks["UserPromptSubmit"][1]["hooks"][0]["command"], f"{self.command} hooks run log")
            self.assertEqual(hooks["UserPromptSubmit"][2]["hooks"][0]["command"], f"{self.command} hooks run audit")
            self.assertEqual(hooks["PreToolUse"][0]["matcher"], "*")
            self.assertEqual(hooks["PreToolUse"][1]["matcher"], "Read|Bash")
            self.assertEqual(hooks["PreToolUse"][1]["hooks"][0]["command"], f"{self.command} hooks run guard")
            self.assertEqual(hooks["SessionStart"][0]["hooks"][0]["command"], f"{self.command} orient")
            self.assertEqual(len(hooks["SessionStart"]), 3)
            self.assertEqual(hooks["SessionStart"][1]["hooks"][0]["command"], f"{self.command} hooks run rules")
            self.assertEqual(hooks["SessionStart"][2]["hooks"][0]["command"], f"{self.command} hooks run snapshot")
            self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Edit|Write|NotebookEdit|MultiEdit|apply_patch")
            self.assertEqual(hooks["PostToolUse"][0]["hooks"][0]["command"], f"{self.command} hooks run record")
            self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], f"{self.command} hooks run stop")
            self.assertEqual(hooks["Stop"][0]["hooks"][0]["timeout"], 60)
            self.assertEqual(hooks["Stop"][1]["hooks"][0]["command"], f"{self.command} hooks run last")
        self.assertEqual(run("status", "--home", self.home)[0], 0)

    def test_install_rules_registers_only_for_both_tools(self) -> None:
        code, _ = run("install", "--write", "--only", "rules", "--home", self.home)
        self.assertEqual(code, 0)
        for directory, name in ((".claude", "settings.json"), (".codex", "hooks.json")):
            hooks = self.config(directory, name)["hooks"]
            self.assertEqual(set(hooks), {"SessionStart"})
            self.assertEqual(hooks["SessionStart"][0]["hooks"][0]["command"], f"{self.command} hooks run rules")
            self.assertNotIn("matcher", hooks["SessionStart"][0])
        self.assertEqual(
            (self.home / ".agent-hooks" / "rules.md").read_bytes(),
            (TOOLING / "default_rules.txt").read_bytes(),
        )
        self.assertEqual(run("status", "--only", "rules", "--home", self.home)[0], 0)

    def test_install_never_overwrites_existing_rules(self) -> None:
        path = self.home / ".agent-hooks" / "rules.md"
        path.parent.mkdir(parents=True)
        path.write_text("mine\n", encoding="utf-8")
        run("install", "--write", "--only", "rules", "--home", self.home)
        self.assertEqual(path.read_text(encoding="utf-8"), "mine\n")

    def test_install_preview_does_not_create_rules(self) -> None:
        run("install", "--only", "rules", "--home", self.home)
        self.assertFalse((self.home / ".agent-hooks" / "rules.md").exists())

    def test_status_reports_rules_registration_and_file_size(self) -> None:
        run("install", "--write", "--only", "rules", "--home", self.home)
        path = self.home / ".agent-hooks" / "rules.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("one\ntwo\n", encoding="utf-8")
        code, output = run("status", "--only", "rules", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertIn("ok       claude  SessionStart", output)
        self.assertIn("ok       codex   SessionStart", output)
        self.assertIn(f"exists   rules   file              {path.resolve()} (8 characters)", output)

    def test_install_keeps_existing_settings_and_hooks_and_is_idempotent(self) -> None:
        settings = self.home / ".claude" / "settings.json"
        other = {"type": "command", "command": "echo mine"}
        settings.write_text(json.dumps({"theme": "dark", "hooks": {"SessionStart": [{"hooks": [other]}]}}))
        run("install", "--write", "--home", self.home)
        once = settings.read_text()
        config = json.loads(once)
        self.assertEqual(config["theme"], "dark")
        self.assertIn(other, config["hooks"]["SessionStart"][0]["hooks"])
        self.assertEqual(len(config["hooks"]["SessionStart"]), 4)
        code, output = run("install", "--write", "--home", self.home)
        self.assertIn("nothing to do", output)
        self.assertEqual(settings.read_text(), once)

    def test_only_installs_one_hook(self) -> None:
        run("install", "--write", "--only", "orient", "--home", self.home)
        self.assertEqual(set(self.config(".claude", "settings.json")["hooks"]), {"SessionStart"})
        self.assertFalse((self.home / ".agent-hooks").exists())

    def test_only_guard_registers_read_and_bash_pre_tool_use(self) -> None:
        run("install", "--write", "--only", "guard", "--home", self.home)
        hooks = self.config(".claude", "settings.json")["hooks"]
        self.assertEqual(set(hooks), {"PreToolUse"})
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "Read|Bash")
        self.assertEqual(hooks["PreToolUse"][0]["hooks"][0]["command"], f"{self.command} hooks run guard")
        self.assertEqual(run("status", "--only", "guard", "--home", self.home)[0], 0)

    def test_only_audit_registers_the_prompt_hook(self) -> None:
        run("install", "--write", "--only", "audit", "--home", self.home)
        hooks = self.config(".claude", "settings.json")["hooks"]
        self.assertEqual(set(hooks), {"UserPromptSubmit"})
        self.assertEqual(hooks["UserPromptSubmit"][0]["hooks"][0]["command"], f"{self.command} hooks run audit")
        self.assertEqual(hooks["UserPromptSubmit"][0]["hooks"][0]["timeout"], 60)
        self.assertEqual(run("status", "--only", "audit", "--home", self.home)[0], 0)

    def test_only_check_installs_the_recorder_snapshot_and_stop_check(self) -> None:
        run("install", "--write", "--only", "check", "--home", self.home)
        hooks = self.config(".claude", "settings.json")["hooks"]
        self.assertEqual(set(hooks), {"PostToolUse", "Stop", "SessionStart"})
        self.assertEqual(hooks["SessionStart"][0]["hooks"][0]["command"], f"{self.command} hooks run snapshot")
        self.assertEqual(hooks["PostToolUse"][0]["hooks"][0]["command"], f"{self.command} hooks run record")
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], f"{self.command} hooks run stop")
        self.assertFalse((self.home / ".agent-hooks").exists())

    def test_only_log_adds_both_registrations_beside_existing_entries(self) -> None:
        settings = self.home / ".claude" / "settings.json"
        existing_prompt = {"type": "command", "command": "echo prompt"}
        existing_stop = {"type": "command", "command": "echo stop"}
        settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [existing_prompt]}], "Stop": [{"hooks": [existing_stop]}]}}))
        run("install", "--write", "--only", "log", "--home", self.home)
        config = json.loads(settings.read_text())
        hooks = config["hooks"]
        self.assertEqual(hooks["UserPromptSubmit"][0]["hooks"], [existing_prompt])
        self.assertEqual(hooks["UserPromptSubmit"][1]["hooks"][0]["command"], f"{self.command} hooks run log")
        self.assertEqual(hooks["Stop"][0]["hooks"], [existing_stop])
        self.assertEqual(hooks["Stop"][1]["hooks"][0]["command"], f"{self.command} hooks run last")
        once = settings.read_text()
        code, output = run("install", "--write", "--only", "log", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", output)
        self.assertEqual(settings.read_text(), once)
        code, status = run("status", "--only", "log", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertIn("UserPromptSubmit", status)
        self.assertIn("Stop", status)

    def test_status_reports_stale_script_and_changed_command(self) -> None:
        run("install", "--write", "--home", self.home)
        (self.home / ".agent-hooks" / "mode.py").write_text("old")
        path = self.home / ".claude" / "settings.json"
        config = json.loads(path.read_text())
        config["hooks"]["SessionStart"][0]["hooks"][0]["command"] = "/old/bkf orient"
        path.write_text(json.dumps(config))
        code, output = run("status", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("differs  script", output)
        self.assertIn("broken   claude  SessionStart", output)
        run("install", "--write", "--home", self.home)
        self.assertEqual(run("status", "--home", self.home)[0], 0)

    def test_status_probes_registered_commands(self) -> None:
        run("install", "--write", "--only", "log", "--home", self.home)
        self.assertEqual(run("status", "--only", "log", "--home", self.home)[0], 0)
        with patch.dict(os.environ, {"BKF_STUB_MODE": "nonzero"}):
            code, output = run("status", "--only", "log", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("broken", output)
        self.assertIn("exit code 7", output)

    def test_probe_reports_traceback_no_answer_and_timeout(self) -> None:
        run("install", "--write", "--only", "log", "--home", self.home)
        for mode, reason in (("traceback", "traceback"), ("none", "no probe answer")):
            with self.subTest(mode=mode), patch.dict(os.environ, {"BKF_STUB_MODE": mode}):
                code, output = run("status", "--only", "log", "--home", self.home)
                self.assertEqual(code, 1)
                self.assertIn(reason, output)
        with patch.dict(os.environ, {"BKF_STUB_MODE": "sleep"}), patch.object(bkf_hooks, "TIMEOUT", 0.05):
            code, output = run("status", "--only", "log", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("timed out", output)

    def test_write_install_prints_broken_probe_results(self) -> None:
        with patch.dict(os.environ, {"BKF_STUB_MODE": "nonzero"}):
            code, output = run("install", "--write", "--only", "log", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("applied", output)
        self.assertIn("broken", output)

    def test_only_limits_which_commands_are_probed(self) -> None:
        run("install", "--write", "--home", self.home)
        seen = []
        original = bkf_hooks._probe_command

        def record(command, registration, home):
            seen.append(registration.hook)
            return original(command, registration, home)

        with patch.object(bkf_hooks, "_probe_command", side_effect=record):
            run("status", "--only", "log", "--home", self.home)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {"log"})

    def test_cli_reports_hooks_run_import_failure_as_json(self) -> None:
        import bkf_cli

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(bkf_cli.importlib, "import_module", side_effect=ImportError("missing module")):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = bkf_cli.main(["hooks", "run", "log"])
        self.assertEqual(code, 0)
        self.assertIn("log", json.loads(stdout.getvalue())["systemMessage"])
        self.assertIn("log", stderr.getvalue())

    def test_run_reports_hook_events_import_failure(self) -> None:
        import builtins

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "hook_events":
                raise ImportError("missing hook module")
            return original_import(name, *args, **kwargs)

        stdout = io.StringIO()
        with patch("builtins.__import__", side_effect=failing_import):
            with contextlib.redirect_stdout(stdout):
                code = bkf_hooks.main(["run", "log"])
        self.assertEqual(code, 0)
        self.assertIn("log", json.loads(stdout.getvalue())["systemMessage"])

    def test_missing_tool_is_skipped(self) -> None:
        (self.home / ".codex").rmdir()
        code, output = run("install", "--write", "--home", self.home)
        self.assertEqual(code, 0)
        self.assertIn("skipped  codex", output)
        self.assertFalse((self.home / ".codex").exists())

    def test_invalid_json_fails_without_writing(self) -> None:
        settings = self.home / ".claude" / "settings.json"
        settings.write_text("{not json")
        code, _ = run("install", "--write", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertEqual(settings.read_text(), "{not json")
        self.assertFalse((self.home / ".agent-hooks").exists())


if __name__ == "__main__":
    unittest.main()

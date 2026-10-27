import os
import pathlib
import tempfile
import unittest
from unittest import mock

from harness.engine import agentstep


class AgentStepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_tier_from_environment_distinguishes_unset_empty_and_value(self):
        self.assertEqual(agentstep.tier_from_environment({}), "fast")
        self.assertIsNone(agentstep.tier_from_environment({"HARNESS_CODEX_TIER": ""}))
        self.assertEqual(agentstep.tier_from_environment({"HARNESS_CODEX_TIER": "priority"}), "priority")

    def test_run_agent_step_reports_quota_and_records_note(self):
        events = self.root / "run.events.jsonl"
        events.write_text("quota event\n", encoding="utf-8")
        run = mock.Mock()
        with mock.patch("harness.engine.agentstep.agent.run_agent", return_value=42), mock.patch(
            "harness.agent.CodexBackend.quota_text", return_value="retry tomorrow\r\n"
        ) as quota_text:
            result = agentstep.run_agent_step(
                run, "review", str(self.root), "brief.md", str(self.root / "run"),
                "model", "high", "workspace-write", "fast", "ordinary failure",
            )
        self.assertEqual(
            result,
            agentstep.StepResult(
                False,
                "review: usage limit reached. QUOTA: retry tomorrow (see {0})".format(events),
                "retry tomorrow",
            ),
        )
        quota_text.assert_called_once_with(str(events))
        run.note.assert_called_once_with("QUOTA: retry tomorrow")

    def test_run_agent_step_replaces_exit_placeholder(self):
        run = mock.Mock()
        with mock.patch("harness.engine.agentstep.agent.run_agent", return_value=7), mock.patch(
            "harness.agent.CodexBackend.quota_text", return_value=None
        ):
            result = agentstep.run_agent_step(
                run, "review", str(self.root), "brief.md", str(self.root / "run"),
                "model", "high", "read-only", "fast",
                "review exit=<exit> (see review.stderr.log)",
            )
        self.assertEqual(
            result,
            agentstep.StepResult(False, "review exit=7 (see review.stderr.log)", None),
        )
        run.note.assert_not_called()

    def test_run_agent_step_keeps_non_quota_reason_and_success(self):
        run = mock.Mock()
        with mock.patch("harness.engine.agentstep.agent.run_agent", return_value=9), mock.patch(
            "harness.agent.CodexBackend.quota_text", return_value=None
        ):
            result = agentstep.run_agent_step(
                run, "implement", str(self.root), "brief.md", str(self.root / "run"),
                "model", "high", "workspace-write", "fast", "given reason",
            )
        self.assertEqual(result, agentstep.StepResult(False, "given reason", None))
        run.note.assert_not_called()
        with mock.patch("harness.engine.agentstep.agent.run_agent", return_value=0):
            result = agentstep.run_agent_step(
                run, "implement", str(self.root), "brief.md", str(self.root / "run"),
                "model", "high", "workspace-write", "fast", "given reason",
            )
        self.assertEqual(result, agentstep.StepResult(True, "", None))

    def make_fake_codex(self, code="0", overlap=False):
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        executable = bin_dir / "codex"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys, time\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "if os.environ.get('OVERLAP') == '1':\n"
            "    marker = pathlib.Path(os.environ['MARKERS']) / (cwd.name + '.started')\n"
            "    marker.touch()\n"
            "    other = pathlib.Path(os.environ['MARKERS']) / (('one' if cwd.name == 'two' else 'two') + '.started')\n"
            "    deadline = time.time() + 8\n"
            "    while not other.exists() and time.time() < deadline: time.sleep(0.02)\n"
            "    if not other.exists(): sys.exit(99)\n"
            "code = int(os.environ.get('FAKE_CODE', '" + code + "'))\n"
            "if code == 0: (cwd / os.environ.get('OUTPUT_FILE', 'output.md')).write_text('done')\n"
            "sys.exit(code)\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return bin_dir

    def prepare_folder(self, phase_dir, name):
        folder = phase_dir / name
        folder.mkdir(parents=True)
        (folder / "brief.md").write_text("brief", encoding="utf-8")
        return folder

    def test_run_agents_overlaps_and_skips_existing_output(self):
        phase = self.root / "phase"
        phase.mkdir()
        one = self.prepare_folder(phase, "one")
        two = self.prepare_folder(phase, "two")
        bin_dir = self.make_fake_codex(overlap=True)
        with mock.patch.dict(os.environ, {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "OVERLAP": "1", "MARKERS": str(self.root), "OUTPUT_FILE": "output.md",
        }):
            result = agentstep.run_agents(str(phase), "output.md", ["one", "two"], "model", "high", "fast")
        self.assertTrue(result.ok, result.reason)
        self.assertTrue((self.root / "one.started").exists())
        self.assertTrue((self.root / "two.started").exists())
        (one / "output.md").write_text("already done", encoding="utf-8")
        one_events = one / "run.events.jsonl"
        one_events.write_text("must stay untouched", encoding="utf-8")
        (two / "output.md").unlink()
        with mock.patch.dict(os.environ, {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "OUTPUT_FILE": "output.md",
        }, clear=False):
            os.environ.pop("OVERLAP", None)
            result = agentstep.run_agents(str(phase), "output.md", ["one", "two"], "model", "high", "fast")
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(one_events.read_text(), "must stay untouched")
        self.assertEqual((two / "output.md").read_text(), "done")

    def test_run_agents_failure_reason_contains_failed_file_text_and_removes_marker(self):
        phase = self.root / "phase"
        phase.mkdir()
        folder = self.prepare_folder(phase, "broken")
        bin_dir = self.make_fake_codex(code="7")
        with mock.patch.dict(os.environ, {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_CODE": "7", "OUTPUT_FILE": "output.md",
        }):
            result = agentstep.run_agents(str(phase), "output.md", ["broken"], "model", "high", None)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "broken: exit=7 (see {0}/run.stderr.log); ".format(folder))
        self.assertFalse((folder / "failed").exists())


if __name__ == "__main__":
    unittest.main()

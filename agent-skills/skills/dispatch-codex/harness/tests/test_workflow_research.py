"""Research workflow tests with a fake Codex command."""
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from harness.engine.pipeline import main

_WORKFLOW = Path(__file__).parents[2] / "workflows" / "research.py"
_SCRIPT = Path(__file__).parents[2] / "scripts" / "research-run.sh"

_FAKE_CODEX = '''#!/usr/bin/env python3
import os
import pathlib
import sys
args = sys.argv[1:]
directory = pathlib.Path(args[args.index("-C") + 1])
output = pathlib.Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
if os.environ.get("FAKE_FAIL") == "collection" and prompt.startswith("# Brief: collection (collector "):
    collector = prompt.split("# Brief: collection (collector ", 1)[1].split(")", 1)[0]
    if not os.environ.get("FAKE_FAIL_COLLECTOR") or collector == os.environ["FAKE_FAIL_COLLECTOR"]:
        raise SystemExit(1)
if prompt.startswith("# Brief: complete the source map"):
    (directory / "additions.md").write_text("2. **Independent sources.** Examples; counterweight. (agent)\\n")
elif prompt.startswith("# Brief: collection (collector "):
    name = prompt.split("# Brief: collection (collector ", 1)[1].split(")", 1)[0]
    (directory / "sources.md").write_text("# Sources\\n\\nCollected by " + name + ".\\n")
elif prompt.startswith("# Brief: review of the collection"):
    verdict = os.environ.get("FAKE_COLLECTOR_VERDICT", "pass")
    if verdict == "back":
        if pathlib.Path(os.environ["FAKE_BACK_ONCE"]).exists():
            verdict = "pass"
        else:
            pathlib.Path(os.environ["FAKE_BACK_ONCE"]).touch()
    (directory / "problems.md").write_text("## What I checked\\n\\n- objective\\n- sources\\n- scope\\n\\n## Problems\\n\\nNone.\\n\\nVERDICT: " + verdict + "\\n")
elif prompt.startswith("# Brief: digest"):
    (directory / "digest.md").write_text("# Digest\\n\\nSummary.\\n")
elif prompt.startswith("# Brief: review of the digest"):
    (directory / "problems.md").write_text("## What I checked\\n\\n- objective\\n- sources\\n- digest\\n\\n## Problems\\n\\nNone.\\n\\nVERDICT: pass\\n")
elif prompt.startswith("# Brief: review of the delivery"):
    verdict = os.environ.get("FAKE_DELIVERY_VERDICT", "pass")
    (directory / "problems.md").write_text("## What I checked\\n\\n- digest in delivery\\n- objective\\n- coverage\\n\\n## Problems\\n\\nNone.\\n\\nVERDICT: " + verdict + "\\n")
else:
    raise SystemExit("unexpected prompt: " + prompt[:100])
if prompt.startswith("# Brief: review of the collection") or prompt.startswith("# Brief: review of the digest") or prompt.startswith("# Brief: review of the delivery"):
    output.write_text((directory / "problems.md").read_text())
else:
    output.write_text("fake response\\n")
print('{"type":"turn.completed"}')
'''


class ResearchWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.guides = self.root / "guides"
        self.guides.mkdir()
        self.runs = self.root / "runs"
        self.plan = self.root / "inputs"
        self.plan.mkdir()
        self.objective = self.plan / "objective.md"
        self.objective.write_text("# Objective\n\nFind useful evidence.\n", encoding="utf-8")
        self.sourcemap = self.plan / "sourcemap.md"
        self.sourcemap.write_text("1. **Primary sources.** Example sites.\n", encoding="utf-8")
        self.collectors = self.plan / "collectors.txt"
        self.collectors.write_text("alpha: 1\nbeta: 1\n", encoding="utf-8")
        self.delivery = self.plan / "delivery.md"
        self.delivery.write_text("Delivery\n", encoding="utf-8")
        binary = self.root / "bin"
        binary.mkdir()
        codex = binary / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({"PATH": str(binary) + os.pathsep + self.env.get("PATH", ""),
                         "RESEARCH_RUNS_DIR": str(self.runs), "RESEARCH_GUIDES": str(self.guides),
                         "FAKE_BACK_ONCE": str(self.root / "back-once")})

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, **extra):
        previous = os.getcwd()
        try:
            os.chdir(self.repo)
            old = os.environ.copy()
            os.environ.clear()
            os.environ.update(self.env)
            os.environ.update(extra)
            try:
                self.stderr = StringIO()
                with redirect_stderr(self.stderr):
                    return main(str(_WORKFLOW), list(args))
            finally:
                os.environ.clear()
                os.environ.update(old)
        finally:
            os.chdir(previous)

    def run_path(self, name="study"):
        return self.runs / name

    def start(self, name="study", **extra):
        return self.call("start", name, str(self.objective), str(self.sourcemap), str(self.collectors), **extra)

    def run_script(self, *args):
        return subprocess.run([str(_SCRIPT)] + list(args), cwd=str(self.repo), env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_full_run_to_ready_and_agent_added_niche(self):
        self.assertEqual(self.start(), 0)
        run = self.run_path()
        self.assertTrue((run / "03-digest" / "digest.md").is_file())
        self.assertIn("2. **Independent sources.", (run / "01-map" / "sourcemap.md").read_text())
        self.assertIn("nicho 2 · concluído", self.stderr.getvalue())
        self.assertIn("alpha", (run / "00-input" / "collectors.txt").read_text())

    def test_start_uses_repository_default_guide_directory(self):
        self.env.pop("RESEARCH_GUIDES")
        self.assertEqual(self.start(), 0)

    def test_niche_assigned_to_no_collector_is_refused(self):
        self.collectors.write_text("alpha: 99\n", encoding="utf-8")
        self.assertEqual(self.start(), 1)
        self.assertIn("niche 1 is not assigned", (self.run_path() / "status.log").read_text())

    def test_collector_back_then_passes(self):
        self.collectors.write_text("alpha: 1\n", encoding="utf-8")
        self.assertEqual(self.start(FAKE_COLLECTOR_VERDICT="back"), 0, msg="collection rounds should retry a back verdict")
        phase = self.run_path() / "02-collection" / "alpha"
        self.assertEqual((phase / "status").read_text().strip(), "passed")
        self.assertEqual(len(list((phase / "rounds").iterdir())), 2)

    def test_failed_collector_resume_archives_old_stage(self):
        self.collectors.write_text("alpha: 1\n", encoding="utf-8")
        self.assertEqual(self.start(FAKE_FAIL="collection"), 1)
        run = self.run_path()
        old = run / "02-collection"
        self.assertTrue(old.is_dir())
        self.assertEqual(self.call("resume", "study"), 0)
        self.assertTrue(old.is_dir())
        self.assertTrue(list(run.glob("02-collection.attempt-*")))

    def test_collection_progress_is_emitted_when_other_collector_fails(self):
        result = self.start(FAKE_FAIL="collection", FAKE_FAIL_COLLECTOR="beta")
        self.assertEqual(result, 1)
        output = self.stderr.getvalue()
        self.assertNotIn("nicho 1 · concluído", output)
        self.assertIn("nicho 2 · concluído", output)

    def test_deliver_verdict_exit_codes(self):
        self.assertEqual(self.start(), 0)
        self.assertEqual(self.call("deliver", "study", str(self.delivery)), 0)
        self.assertEqual(self.call("deliver", "study", str(self.delivery), FAKE_DELIVERY_VERDICT="back"), 1)
        self.assertEqual(self.call("deliver", "study", str(self.delivery), FAKE_DELIVERY_VERDICT="escalate"), 2)

    def test_deliver_uses_saved_model_and_effort(self):
        self.assertEqual(self.call("start", "-m", "saved-model", "-e", "low", "study",
                                   str(self.objective), str(self.sourcemap), str(self.collectors)), 0)
        self.assertEqual(self.call("deliver", "study", str(self.delivery)), 0)
        log = (self.run_path() / "status.log").read_text(encoding="utf-8")
        self.assertIn("delivery review round 1 (saved-model low): pass", log)

    def test_finish_full_delivery_only_and_keep_attempts(self):
        self.assertEqual(self.start(), 0)
        run = self.run_path()
        (run / "02-collection.attempt-123").mkdir()
        self.delivery.write_text("Delivery full\n", encoding="utf-8")
        (run / "delivery.md").write_text("Delivery full\n", encoding="utf-8")
        self.assertEqual(self.call("finish", "study"), 0)
        record = self.repo / "records" / "research" / "study"
        self.assertTrue((record / "status.md").is_file())
        self.assertFalse((record / ".research-board").exists())
        self.assertFalse(list(record.glob("*.attempt-*")))
        self.assertFalse(run.exists())

        self.assertEqual(self.start("delivery-only"), 0)
        only = self.run_path("delivery-only")
        (only / "delivery.md").write_text("Only delivery\n", encoding="utf-8")
        self.delivery.write_text("Only delivery\n", encoding="utf-8")
        (only / "02-collection").mkdir(exist_ok=True)
        result = self.run_script("finish", "--delivery-only", "delivery-only")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        only_record = self.repo / "records" / "research" / "delivery-only"
        self.assertEqual(sorted(p.name for p in only_record.iterdir()), ["delivery.md"])

        self.assertEqual(self.start("keep"), 0)
        keep = self.run_path("keep")
        (keep / "delivery.md").write_text("keep\n", encoding="utf-8")
        (keep / "03-digest.attempt-456").mkdir()
        result = self.run_script("finish", "--keep-attempts", "keep")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue((self.repo / "records" / "research" / "keep" / "03-digest.attempt-456").is_dir())

    def test_summary_table_records_phases(self):
        self.assertEqual(self.start(), 0)
        run = self.run_path()
        (run / "delivery.md").write_text("Delivery\n", encoding="utf-8")
        self.assertEqual(self.call("finish", "study"), 0)
        summary = (self.repo / "records" / "research" / "study" / "status.md").read_text()
        self.assertIn("| Phase | Model and effort | Result | Rounds | Notes |", summary)
        self.assertIn("| 01-map |", summary)
        self.assertIn("| 02-collection |", summary)
        self.assertIn("| 03-digest |", summary)


if __name__ == "__main__":
    unittest.main()

"""A unit's agents keep their conversations: later rounds and a resumed run continue them instead of starting over."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.agent import ClaudeBackend, CodexBackend
from harness.engine.loop import UnitHooks, run_unit_loop
from harness.engine.run import RunDir, Settings


class Limits:
    max_rounds = 3
    max_gate_rounds = 3
    gate_timeout = 10
    min_checked = 1


class Hooks(UnitHooks):
    def implement_prompt(self, brief, round_number, resumed, previous_problems, previous_handoff,
                         last_review_problems=None):
        return "IMPLEMENT FULL round={0}\n".format(round_number)

    def review_prompt(self, brief, patch, previous_problems, attempt, gate_file, last_review_problems=None):
        return "# Review FULL attempt={0}\n".format(attempt)

    def gate_commands(self, brief):
        return ["test -f ready"]

    def progress(self, text):
        pass

    def implement_continuation(self, brief, brief_changed, round_number, resumed, previous_problems,
                               earlier_problems, say):
        if round_number == 1 and not resumed:
            return None
        return "IMPLEMENT CONTINUE round={0} resumed={1} say={2} earlier={3} changed={4}\n".format(
            round_number, resumed, say, bool(earlier_problems), brief_changed)

    def review_continuation(self, brief, brief_changed, patch, previous_problems, attempt, gate_file,
                            last_review_problems):
        return "# Review CONTINUE attempt={0}\n".format(attempt)


FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
argv = sys.argv[1:]
prompt = sys.stdin.read()
resume = argv[argv.index("resume") + 1:] if "resume" in argv else None
out = pathlib.Path(argv[argv.index("-o") + 1])
cwd = pathlib.Path(os.getcwd())
log = pathlib.Path(os.environ["FAKE_LOG"])
role = "review" if prompt.startswith("# Review") else "implement"
resume_id = next((a for a in argv if a.startswith("SESSION-")), None) if resume else None
with log.open("a") as handle:
    handle.write(json.dumps({"role": role, "resume": resume_id, "prompt": prompt.splitlines()[0],
                             "sandbox": next((a for a in argv if a.startswith("sandbox_mode=")), None)}) + "\n")
if resume_id and resume_id == os.environ.get("FAKE_BAD_SESSION"):
    sys.stderr.write("no such session\n")
    sys.exit(1)
counter = pathlib.Path(os.environ["FAKE_LOG"] + ".n")
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))
session = resume_id or "SESSION-%s-%d" % (role, n)
print(json.dumps({"type": "thread.started", "thread_id": session}))
print(json.dumps({"type": "turn.started"}))
if role == "review":
    verdicts = os.environ.get("FAKE_VERDICTS", "pass").split(",")
    reviews = sum(1 for line in log.read_text().splitlines() if json.loads(line)["role"] == "review")
    verdict = verdicts[min(reviews - 1, len(verdicts) - 1)]
    out.write_text("## What I checked\n- diff\n\n## Problems\nsomething.py\n\nVERDICT: %s\n" % verdict)
else:
    out.write_text("BLOCKED: stuck\n" if os.environ.get("FAKE_BLOCKED") else "handoff\n")
    (cwd / "tracked.txt").write_text("changed %d\n" % n)
    if os.environ.get("FAKE_READY_AFTER", "1") and n >= int(os.environ.get("FAKE_READY_AFTER", "1")):
        (cwd / "ready").write_text("ok")
'''


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "T")
        self.git("config", "user.email", "t@t")
        (self.checkout / "tracked.txt").write_text("base\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.run = RunDir.create(self.root / "runs", "sample", str(self.checkout), Settings("m", "high", "r"), "none")
        self.unit = self.run.path / "01-unit"
        self.brief = self.root / "brief.md"
        self.brief.write_text("# Unit\n", encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "codex"
        fake.write_text(FAKE_CODEX, encoding="utf-8")
        fake.chmod(0o755)
        self.log = self.root / "calls.jsonl"
        env = {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_LOG": str(self.log),
               "HARNESS_SHM_MIN_FREE": "0", "FAKE_READY_AFTER": "1", "FAKE_VERDICTS": "pass"}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.checkout)] + list(args), check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def loop(self):
        return run_unit_loop(self.run, "01-unit", self.checkout, source_brief=self.brief, hooks=Hooks(),
                             settings=self.run.settings, tier=None, limits=Limits(), step=1)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_a_returned_unit_continues_the_implementer_and_the_reviewer_conversations(self):
        os.environ["FAKE_VERDICTS"] = "back,pass"
        self.assertTrue(self.loop().ok)
        calls = self.calls()
        self.assertEqual([(c["role"], c["resume"] is not None) for c in calls],
                         [("implement", False), ("review", False), ("implement", True), ("review", True)])
        self.assertEqual(calls[0]["prompt"], "IMPLEMENT FULL round=1")
        self.assertEqual(calls[2]["prompt"], "IMPLEMENT CONTINUE round=2 resumed=0 say= earlier=False changed=False")
        self.assertEqual(calls[3]["prompt"], "# Review CONTINUE attempt=1")
        self.assertEqual(calls[2]["resume"], "SESSION-implement-1")
        self.assertEqual(calls[3]["resume"], "SESSION-review-2")
        self.assertEqual(calls[3]["sandbox"], 'sandbox_mode="read-only"')
        self.assertEqual(calls[2]["sandbox"], 'sandbox_mode="workspace-write"')

    def test_a_resumed_run_continues_the_blocked_implementer_with_what_the_coordinator_said(self):
        os.environ["FAKE_BLOCKED"] = "1"
        self.assertFalse(self.loop().ok)
        os.environ.pop("FAKE_BLOCKED")
        (self.run.path / "say.md").write_text("the column exists now\n", encoding="utf-8")
        self.brief.write_text("# Unit\ncorrected\n", encoding="utf-8")
        self.assertTrue(self.loop().ok)
        resumed = [c for c in self.calls() if c["role"] == "implement"][1]
        self.assertEqual(resumed["resume"], "SESSION-implement-1")
        self.assertEqual(resumed["prompt"], "IMPLEMENT CONTINUE round=1 resumed=True say=the column exists now earlier=False changed=True")

    def test_a_conversation_that_cannot_be_resumed_starts_a_new_one(self):
        os.environ["FAKE_BLOCKED"] = "1"
        self.assertFalse(self.loop().ok)
        os.environ.pop("FAKE_BLOCKED")
        os.environ["FAKE_BAD_SESSION"] = "SESSION-implement-1"
        self.assertTrue(self.loop().ok)
        implements = [c for c in self.calls() if c["role"] == "implement"]
        self.assertEqual([c["resume"] for c in implements], [None, "SESSION-implement-1", None])
        self.assertEqual(implements[2]["prompt"], "IMPLEMENT FULL round=1")
        self.assertTrue(any("could not be resumed" in line for line in (self.run.path / "status.log").read_text().splitlines()))

    def test_backend_arguments_resume_and_session_ids(self):
        codex = CodexBackend().arguments("/w", "m", "high", "workspace-write", "fast", "/last.md", resume_id="ID-1")
        self.assertEqual(codex[:3], ["exec", "-c", 'service_tier="fast"'])
        self.assertIn("resume", codex)
        self.assertEqual(codex[-2:], ["ID-1", "-"])
        self.assertIn('sandbox_mode="workspace-write"', codex)
        self.assertNotIn("-s", codex)
        self.assertNotIn("-C", codex)
        claude = ClaudeBackend().arguments("/w", "m", "high", "workspace-write", None, "/last.md", resume_id="ID-2")
        self.assertEqual(claude[claude.index("--resume") + 1], "ID-2")
        self.assertNotIn("--no-session-persistence", claude)
        self.assertIn("--no-session-persistence", ClaudeBackend().arguments("/w", "m", "high", "read-only", None, "/l"))
        self.assertNotIn("--no-session-persistence",
                         ClaudeBackend().arguments("/w", "m", "high", "read-only", None, "/l", track=True))
        events = self.root / "e.jsonl"
        events.write_text('{"type":"thread.started","thread_id":"T-9"}\n{"type":"turn.started"}\n', encoding="utf-8")
        self.assertEqual(CodexBackend().session_id(str(events)), "T-9")
        self.assertTrue(CodexBackend().started(str(events)))
        events.write_text('{"type":"system","subtype":"init","session_id":"C-3"}\n', encoding="utf-8")
        self.assertEqual(ClaudeBackend().session_id(str(events)), "C-3")
        self.assertTrue(ClaudeBackend().started(str(events)))
        events.write_text("", encoding="utf-8")
        self.assertFalse(ClaudeBackend().started(str(events)))
        self.assertIsNone(CodexBackend().session_id(str(events)))


if __name__ == "__main__":
    unittest.main()

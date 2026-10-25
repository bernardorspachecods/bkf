"""Integration tests for the council workflow using a fake Codex executable."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "council-run.sh"


_FAKE_CODEX = r'''#!/usr/bin/env python3
import os
import pathlib
import sys

args = sys.argv[1:]
directory = pathlib.Path(args[args.index("-C") + 1])
last_message = pathlib.Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
state = pathlib.Path(os.environ["FAKE_STATE"])
counter = state / ("calls-" + directory.parent.name + "-" + directory.name)
count = int(counter.read_text() if counter.exists() else "0") + 1
counter.write_text(str(count), encoding="utf-8")
if prompt.startswith("# Brief: advice"):
    if os.environ.get("FAKE_FAIL_ADVISOR") == directory.name and not (state / "failed-once").exists():
        (state / "failed-once").write_text("yes")
        raise SystemExit(1)
    text = "Advice from " + directory.name
    if os.environ.get("FAKE_NAMES_PERSPECTIVE") and directory.name == "outsider":
        text += " The outsider perspective agrees."
    (directory / "advice.md").write_text(text + "\n", encoding="utf-8")
elif prompt.startswith("# Brief: review of the responses"):
    (directory / "review.md").write_text("Review from " + directory.name + "\n", encoding="utf-8")
elif prompt.startswith("# Brief: completeness check of the report"):
    (state / ("check-prompt-" + directory.parent.name)).write_text(prompt, encoding="utf-8")
    if os.environ.get("FAKE_NO_USABLE"):
        text = "No usable response\n"
    else:
        verdicts = os.environ.get("FAKE_VERDICTS", "pass").split(",")
        round_number = int(directory.parent.name)
        verdict = verdicts[min(round_number - 1, len(verdicts) - 1)]
        text = "## What I checked\n\n- advice one\n- advice two\n- reviews\n\n## Problems\n\nnone\n\nVERDICT: " + verdict + "\n"
    last_message.write_text(text, encoding="utf-8")
else:
    raise SystemExit("unexpected prompt")
last_message.touch(exist_ok=True)
print('{"type":"turn.completed"}')
'''


class CouncilWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.guides = self.root / "guides"
        self.guides.mkdir()
        for name in ("council-advisor.md", "council-reviewer.md", "council-completeness.md"):
            (self.guides / name).write_text("guide\n", encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        codex = self.bin / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        self.state = self.root / "state"
        self.state.mkdir()
        self.runs = self.root / "runs"
        self.brief = self.root / "brief.md"
        self.brief.write_text("# Question\n\nWhat should the council consider?\n", encoding="utf-8")
        self.report = self.root / "report.md"
        self.report.write_text("# Report\n\nSummary.\n", encoding="utf-8")
        self.empty = self.root / "empty.md"
        self.empty.write_text("", encoding="utf-8")
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + self.env.get("PATH", ""),
            "COUNCIL_RUNS_DIR": str(self.runs),
            "COUNCIL_GUIDES": str(self.guides),
            "FAKE_STATE": str(self.state),
        })

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, env=None):
        return subprocess.run(
            [str(SCRIPT)] + list(args), cwd=str(self.repo), env=env or self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
            check=False,
        )

    def start(self, name="run", env=None):
        return self.call("start", name, str(self.brief), env=env)

    def test_full_run_packet_anonymity_and_self_identification_note(self):
        result = self.start("full", dict(self.env, FAKE_NAMES_PERSPECTIVE="1"))
        run = self.runs / "full"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("READY", result.stdout)
        self.assertEqual(len((run / "02-packet" / "key.md").read_text().splitlines()), 5)
        key = (run / "02-packet" / "key.md").read_text()
        self.assertEqual({line.split(": ", 1)[1] for line in key.splitlines()},
                         {"contrarian", "first-principles", "expansionist", "outsider", "executor"})
        packet = (run / "02-packet" / "packet.md").read_text()
        self.assertEqual({line for line in packet.splitlines() if line.startswith("# Response ")},
                         {"# Response A", "# Response B", "# Response C", "# Response D", "# Response E"})
        for folder in (run / "03-review").iterdir():
            self.assertTrue((folder / "packet.md").is_file())
            self.assertFalse((folder / "key.md").exists())
            self.assertFalse(any(folder.glob("review-*.md")))
            self.assertEqual((folder / "review.md").read_text(), "Review from " + folder.name + "\n")
        status = (run / "status.log").read_text()
        self.assertIn("may name its own perspective (outsider)", status)
        for number in range(1, 6):
            self.assertTrue((run / "03-review" / str(number) / "review.md").is_file())

    def test_resume_retries_only_failed_advisor(self):
        env = dict(self.env, FAKE_FAIL_ADVISOR="outsider")
        first = self.start("retry", env)
        self.assertEqual(first.returncode, 1)
        run = self.runs / "retry"
        self.assertTrue((run / "01-advisors" / "contrarian" / "advice.md").exists())
        self.assertFalse((run / "01-advisors" / "outsider" / "advice.md").exists())
        second = self.call("resume", "retry")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.state / "calls-01-advisors-contrarian").read_text(), "1")
        self.assertEqual((self.state / "calls-01-advisors-outsider").read_text(), "2")

    def _ready(self, name):
        result = self.start(name)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.runs / name

    def test_check_pass_back_and_round_cap_escalation_keep_exit_codes(self):
        run = self._ready("checks")
        passing = self.call("check", "checks", str(self.report))
        self.assertEqual(passing.returncode, 0, passing.stderr)
        run2 = self._ready("backs")
        returned = self.call("check", "backs", str(self.report), env=dict(self.env, FAKE_VERDICTS="back"))
        self.assertEqual(returned.returncode, 1, returned.stderr)
        self.assertIn("VERDICT: back", (run2 / "04-check" / "rounds" / "1" / "problems.md").read_text())
        returned = self.call("check", "backs", str(self.report), env=dict(self.env, FAKE_VERDICTS="back"))
        self.assertEqual(returned.returncode, 1, returned.stderr)
        previous = run2 / "04-check" / "rounds" / "2" / "review" / "previous-problems.md"
        self.assertEqual(previous.read_text(), (run2 / "04-check" / "rounds" / "1" / "problems.md").read_text())
        self.assertIn("The cuts you listed in the previous round", (self.state / "check-prompt-2").read_text())
        capped = self.call("check", "backs", str(self.report), env=dict(self.env, FAKE_VERDICTS="back"))
        self.assertEqual(capped.returncode, 2, capped.stderr)
        self.assertEqual((run2 / "04-check" / "rounds" / "3" / "verdict").read_text(), "escalate\n")
        self.assertEqual((run / "04-check" / "rounds" / "1" / "verdict").read_text(), "pass\n")

    def test_check_escalate_and_no_usable_reviewer_file(self):
        self._ready("escalate")
        escalated = self.call("check", "escalate", str(self.report), env=dict(self.env, FAKE_VERDICTS="escalate"))
        self.assertEqual(escalated.returncode, 2, escalated.stderr)
        self._ready("unusable")
        unusable = self.call("check", "unusable", str(self.report), env=dict(self.env, FAKE_NO_USABLE="1"))
        self.assertEqual(unusable.returncode, 1)
        self.assertIn("no usable review after 3 attempts", unusable.stderr)

    def test_finish_and_discard(self):
        run = self._ready("kept")
        (run / "report.md").write_text("# Report\n", encoding="utf-8")
        finished = self.call("finish", "kept")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertTrue((self.repo / "records" / "councils" / "kept" / "report.md").is_file())
        self.assertFalse(run.exists())
        discarded = self._ready("discard")
        removed = self.call("finish", "--discard", "discard")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(discarded.exists())

    def test_start_finds_the_default_role_guides(self):
        env = {key: value for key, value in self.env.items() if key != "COUNCIL_GUIDES"}
        result = self.call("start", "default-guides", str(self.brief), env=env)
        self.assertNotIn("no role guides", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_start_refusals(self):
        for args, phrase in (
            (("start", "bad/name", str(self.brief)), "bad run name"),
            (("start", "missing", str(self.root / "missing.md")), "missing or empty brief"),
            (("start", "empty", str(self.empty)), "missing or empty brief"),
        ):
            with self.subTest(phrase=phrase):
                result = self.call(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn(phrase, result.stderr)
        no_codex_bin = self.root / "no-codex"
        no_codex_bin.mkdir()
        for executable in ("bash", "python3", "dirname", "env"):
            (no_codex_bin / executable).symlink_to(shutil.which(executable))
        no_codex = dict(self.env, PATH=str(no_codex_bin))
        missing = self.call("start", "no-codex", str(self.brief), env=no_codex)
        self.assertIn("codex not found", missing.stderr)


if __name__ == "__main__":
    unittest.main()

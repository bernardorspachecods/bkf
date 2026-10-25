import pathlib
import tempfile
import threading
import unittest
from unittest import mock

from harness.engine.agentstep import StepResult
from harness.engine.phase import clean_phase, join_phase, run_phase
from harness.engine.review import ReviewResult


class FakeRun:
    def __init__(self):
        self.notes = []

    def note(self, text):
        self.notes.append(text)


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.run = FakeRun()
        self.phase = self.root / "phase"
        self.agent_brief = self.root / "agent.md"
        self.review_brief = self.root / "review.md"
        self.agent_brief.write_text("agent brief\n", encoding="utf-8")
        self.review_brief.write_text("review brief\n", encoding="utf-8")
        self.verdicts = {}
        self.calls = {}
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.sync_agents = False
        self.barrier = threading.Barrier(2)

    def tearDown(self):
        self.temp.cleanup()

    def fake_agent(self, run, label, directory, prompt_file, out_prefix, model,
                   effort, sandbox, tier, reason, backend):
        name = label
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if self.sync_agents:
            self.barrier.wait(timeout=2)
        prompt = pathlib.Path(prompt_file).read_text(encoding="utf-8")
        call = self.calls.get(name, 0) + 1
        self.calls[name] = call
        if name == "failing":
            result = StepResult(False, "failing: agent exit=7", None)
        elif name == "quota":
            result = StepResult(False, "quota: usage limit reached. QUOTA: reset time (see events)", "reset time")
        else:
            pathlib.Path(directory, "output.md").write_text(
                "work {0} {1}\n".format(name, call), encoding="utf-8"
            )
            result = StepResult(True, "", None)
        with self.lock:
            self.active -= 1
        return result

    def fake_review(self, run, label, directory, round_dir, build_prompt,
                  model, effort, tier, min_checked, previous_problems=None):
        round_number = int(pathlib.Path(round_dir).name)
        queue = self.verdicts.get(label, ["pass"])
        verdict = queue.pop(0) if queue else "pass"
        if verdict is None:
            return ReviewResult(None, "{0}: the reviewer left no usable review after 3 attempts".format(label))
        problems = pathlib.Path(round_dir, "problems.md")
        pathlib.Path(round_dir, "review-prompt.md").write_text(build_prompt(1), encoding="utf-8")
        problems.write_text("## What I checked\n\n- file\n\nVERDICT: {0}\n".format(verdict), encoding="utf-8")
        pathlib.Path(round_dir, "verdict").write_text(verdict + "\n", encoding="utf-8")
        if round_number > 1:
            self.assertIn("Problems from the review", pathlib.Path(round_dir, "agent-prompt.md").read_text(encoding="utf-8"))
        return ReviewResult(verdict, "")

    def call(self, agents=None, **options):
        if agents is None:
            agents = [("one", self.agent_brief, self.review_brief)]
        with mock.patch("harness.engine.phase.run_agent_step", side_effect=self.fake_agent), \
             mock.patch("harness.engine.phase.run_review", side_effect=self.fake_review):
            return run_phase(self.run, self.phase, agents, "model", "high", **options)

    def test_pass_first_round_persists_all_phase_files_and_join(self):
        result = self.call()
        self.assertTrue(result.ok)
        self.assertEqual("passed", (self.phase / "one/status").read_text().strip())
        self.assertEqual("pass\n", (self.phase / "one/rounds/1/verdict").read_text())
        self.assertTrue((self.phase / "one/rounds/1/agent-prompt.md").is_file())
        self.assertTrue((self.phase / "one/rounds/1/review-prompt.md").is_file())
        self.assertEqual("one\n", (self.phase / "names").read_text())
        self.assertEqual("output.md\n", (self.phase / "outfile").read_text())
        joined = pathlib.Path(join_phase(self.phase))
        self.assertEqual("# one\n\nwork one 1\n\n\n", joined.read_text())

    def test_back_then_pass_preserves_prior_problem_in_next_agent_prompt(self):
        self.verdicts["one"] = ["back", "pass"]
        result = self.call()
        self.assertTrue(result.ok)
        prompt = (self.phase / "one/rounds/2/agent-prompt.md").read_text()
        self.assertIn("VERDICT: back", prompt)
        self.assertEqual(2, self.calls["one"])

    def test_back_at_round_cap_escalates(self):
        self.verdicts["one"] = ["back"]
        result = self.call(max_rounds=1)
        self.assertFalse(result.ok)
        self.assertEqual("escalated", (self.phase / "one/status").read_text().strip())
        self.assertIn("round cap 1 reached", (self.phase / "log.tsv").read_text())

    def test_explicit_escalate_ends_agent(self):
        self.verdicts["one"] = ["escalate"]
        result = self.call()
        self.assertFalse(result.ok)
        self.assertEqual("escalated", (self.phase / "one/status").read_text().strip())

    def test_agent_failure_is_persisted(self):
        result = self.call([("failing", self.agent_brief, self.review_brief)])
        self.assertFalse(result.ok)
        self.assertIn("agent exit=7", (self.phase / "failing/status").read_text())

    def test_quota_is_returned_as_engine_quota_result(self):
        result = self.call([("quota", self.agent_brief, self.review_brief)])
        self.assertFalse(result.ok)
        self.assertEqual("reset time", result.quota)
        self.assertIn("QUOTA: reset time", result.reason)

    def test_unusable_review_failure_is_persisted_after_three_attempts(self):
        review_attempts = []

        def unusable_review_step(run, label, directory, prompt_file, out_prefix,
                                 model, effort, sandbox, tier, reason):
            review_attempts.append(prompt_file)
            pathlib.Path(out_prefix + ".last-message.md").write_text(
                "VERDICT: pass\n", encoding="utf-8"
            )
            return StepResult(True, "", None)

        with mock.patch("harness.engine.phase.run_agent_step", side_effect=self.fake_agent), \
             mock.patch("harness.engine.review.run_agent_step", side_effect=unusable_review_step):
            result = run_phase(self.run, self.phase,
                               [("one", self.agent_brief, self.review_brief)], "model", "high",
                               min_checked=1)
        self.assertFalse(result.ok)
        self.assertEqual(3, len(review_attempts))
        self.assertIn("no usable review after 3 attempts", (self.phase / "one/status").read_text())

    def test_resume_skips_agent_that_already_passed(self):
        self.call()
        self.calls.clear()
        result = self.call()
        self.assertTrue(result.ok)
        self.assertEqual({}, self.calls)

    def test_clean_removes_phase_with_names_marker(self):
        self.call()
        result = clean_phase(self.phase)
        self.assertEqual("removed {0}".format(self.phase), result)
        self.assertFalse(self.phase.exists())

    def test_invalid_agent_name_does_not_create_phase_or_escape_it(self):
        with self.assertRaisesRegex(ValueError, "simple names"):
            self.call([("..", self.agent_brief, self.review_brief)])
        self.assertFalse(self.phase.exists())

    def test_two_agents_run_concurrently(self):
        self.sync_agents = True
        agents = [(name, self.agent_brief, self.review_brief) for name in ("one", "two")]
        self.call(agents)
        self.assertEqual(2, self.max_active)


if __name__ == "__main__":
    unittest.main()

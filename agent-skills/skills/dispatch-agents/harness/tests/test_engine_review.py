import os
import pathlib
import tempfile
import unittest
from unittest import mock

from harness.engine.review import run_review
from harness.engine.run import RunDir, Settings


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.run = RunDir.create(
            self.root / "runs", "sample", "/repo", Settings("model", "high", ""), "none"
        )
        self.directory = self.root / "checkout"
        self.directory.mkdir()
        self.round_dir = self.root / "rounds" / "2"
        self.round_dir.mkdir(parents=True)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.codex = self.bin_dir / "codex"
        path_patch = mock.patch.dict(
            os.environ,
            {"PATH": str(self.bin_dir) + os.pathsep + os.environ.get("PATH", "")},
        )
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def tearDown(self):
        self.temp.cleanup()

    def install_codex(self, script):
        self.codex.write_text("#!/usr/bin/env python3\n" + script, encoding="utf-8")
        self.codex.chmod(0o755)

    def call_review(self, builder=None, min_checked=2):
        attempts = []

        def build_prompt(attempt):
            attempts.append(attempt)
            return "review attempt {0}\n".format(attempt)

        result = run_review(
            self.run,
            "unit-a",
            str(self.directory),
            str(self.round_dir),
            builder or build_prompt,
            "model",
            "high",
            "priority",
            min_checked,
        )
        return result, attempts

    def review_text(self, verdict):
        return "## What I checked\nfirst line\nsecond line\n\nVERDICT:{0}\n".format(verdict)

    def test_each_verdict_writes_expected_files_and_success_note(self):
        for verdict in ("pass", "back", "escalate"):
            with self.subTest(verdict=verdict):
                self.round_dir = self.root / "rounds" / verdict
                self.round_dir.mkdir(parents=True)
                self.install_codex(
                    "import pathlib, sys\n"
                    "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
                    "(cwd / sys.argv[sys.argv.index('-o') + 1]).write_text(" + repr(self.review_text(verdict)) + ")\n"
                )
                result, attempts = self.call_review()
                expected = self.review_text(verdict)
                self.assertEqual((result.verdict, result.reason), (verdict, ""))
                self.assertEqual(attempts, [1])
                self.assertEqual((self.round_dir / "review-prompt.md").read_text(), "review attempt 1\n")
                self.assertEqual((self.round_dir / "review.last-message.md").read_text(), expected)
                self.assertEqual((self.round_dir / "problems.md").read_text(), expected)
                self.assertEqual((self.round_dir / "verdict").read_text(), verdict + "\n")
                self.assertEqual(
                    sorted(path.name for path in self.round_dir.iterdir()),
                    [
                        "problems.md",
                        "review-prompt.md",
                        "review.events.jsonl",
                        "review.last-message.md",
                        "review.stderr.log",
                        "verdict",
                    ],
                )
                self.assertEqual(
                    self.run.path.joinpath("status.log").read_text().splitlines()[-1].split("\t", 1)[1],
                    "unit-a: round {0}: verdict {1}".format(verdict, verdict),
                )

    def test_unusable_first_attempt_is_noted_then_usable_attempt_succeeds(self):
        self.install_codex(
            "import pathlib, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "out = cwd / sys.argv[sys.argv.index('-o') + 1]\n"
            "prompt = sys.stdin.read()\n"
            "out.write_text('no verdict\\n' if 'attempt 1' in prompt else " + repr(self.review_text("pass")) + ")\n"
        )
        result, attempts = self.call_review()

        self.assertEqual((result.verdict, result.reason), ("pass", ""))
        self.assertEqual(attempts, [1, 2])
        notes = [line.split("\t", 1)[1] for line in self.run.path.joinpath("status.log").read_text().splitlines()[1:]]
        self.assertEqual(notes, [
            "unit-a: review attempt 1 was not usable",
            "unit-a: round 2: verdict pass",
        ])
        self.assertEqual((self.round_dir / "review-prompt.md").read_text(), "review attempt 2\n")
        self.assertEqual((self.round_dir / "problems.md").read_text(), self.review_text("pass"))

    def test_three_unusable_attempts_stop_with_exact_reason(self):
        self.install_codex(
            "import pathlib, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "(cwd / sys.argv[sys.argv.index('-o') + 1]).write_text('no verdict\\n')\n"
        )
        result, attempts = self.call_review()

        self.assertEqual(result.verdict, None)
        self.assertEqual(attempts, [1, 2, 3])
        self.assertEqual(
            result.reason,
            "unit-a: the reviewer left no usable review after 3 attempts (see {0})".format(
                self.round_dir / "review.last-message.md"
            ),
        )
        self.assertEqual(
            [line.split("\t", 1)[1] for line in self.run.path.joinpath("status.log").read_text().splitlines()[1:]],
            ["unit-a: review attempt 1 was not usable", "unit-a: review attempt 2 was not usable", "unit-a: review attempt 3 was not usable"],
        )
        self.assertFalse((self.round_dir / "problems.md").exists())
        self.assertFalse((self.round_dir / "verdict").exists())

    def test_checked_section_with_too_few_lines_is_unusable(self):
        self.install_codex(
            "import pathlib, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "(cwd / sys.argv[sys.argv.index('-o') + 1]).write_text('## What I checked\\none line\\n## Verdict\\nVERDICT:pass\\n')\n"
        )
        result, attempts = self.call_review(min_checked=2)

        self.assertIsNone(result.verdict)
        self.assertEqual(attempts, [1, 2, 3])

    def test_agent_failure_returns_quota_aware_or_regular_reason(self):
        self.install_codex("import sys\nsys.exit(7)\n")
        result, attempts = self.call_review()
        self.assertIsNone(result.verdict)
        self.assertEqual(result.reason, "unit-a: review exit=7 (see {0}/review.stderr.log)".format(self.round_dir))
        self.assertEqual(attempts, [1])

        self.install_codex(
            "import pathlib, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "(cwd / (sys.argv[sys.argv.index('-o') + 1]).replace('.last-message.md', '.events.jsonl')).write_text('hit your usage limit; try again at tomorrow\\n')\n"
            "sys.exit(7)\n"
        )
        result, attempts = self.call_review()
        self.assertIsNone(result.verdict)
        self.assertEqual(result.reason, "unit-a: usage limit reached. QUOTA: tomorrow (see {0}/review.events.jsonl)".format(self.round_dir))
        self.assertEqual(attempts, [1])

    def test_agent_receives_read_only_sandbox_settings_and_prompt_builder_gets_attempt(self):
        self.install_codex(
            "import pathlib, sys\n"
            "cwd = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "(cwd / 'arguments.txt').write_text(' '.join(sys.argv))\n"
            "(cwd / sys.argv[sys.argv.index('-o') + 1]).write_text(" + repr(self.review_text("pass")) + ")\n"
        )
        result, attempts = self.call_review()

        arguments = (self.directory / "arguments.txt").read_text()
        self.assertEqual(attempts, [1])
        self.assertIn("-m model", arguments)
        self.assertIn('model_reasoning_effort="high"', arguments)
        self.assertIn("-s read-only", arguments)
        self.assertIn('service_tier="priority"', arguments)
        self.assertEqual(result.verdict, "pass")
        self.assertTrue((self.directory / "arguments.txt").exists())


if __name__ == "__main__":
    unittest.main()

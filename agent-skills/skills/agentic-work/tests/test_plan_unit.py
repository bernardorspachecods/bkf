import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "plan-unit.sh"

# A fake `codex` that records how it was called and answers from FAKE_VERDICTS, one verdict per review.
_FAKE_CODEX = '''#!/usr/bin/env python3
import json, os, pathlib, sys

args = sys.argv[1:]
output = pathlib.Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
state = pathlib.Path(os.environ["FAKE_STATE"])
count = len(list(state.glob("prompt-*.md"))) + 1
(state / "prompt-{0}.md".format(count)).write_text(prompt, encoding="utf-8")
(state / "args-{0}.json".format(count)).write_text(json.dumps(args), encoding="utf-8")
thread_id = args[-2] if "resume" in args else "thread-{0}".format(count)
verdicts = json.loads(os.environ["FAKE_VERDICTS"])
verdict = verdicts[min(count, len(verdicts)) - 1]
output.write_text("## What I checked\\n\\n- patch\\n- prompt\\n- result\\n\\n## Problems\\n\\nfix the thing\\n\\n"
                  "VERDICT: " + verdict + "\\n", encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": thread_id}))
print('{"type":"turn.completed","usage":{"input_tokens":1}}')
'''



class PlanUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.repo)] + command, check=True)
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "init"], check=True)
        self.out = root / "units"
        self.state = root / "state"
        self.state.mkdir()
        guides = root / "guides"
        guides.mkdir()
        (guides / "agentic-work-review.md").write_text("guide\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        codex = bin_dir / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(bin_dir) + os.pathsep + self.env["PATH"], "FAKE_STATE": str(self.state),
            "PLAN_GUIDES": str(guides), "FAKE_VERDICTS": json.dumps(["pass"]), "HARNESS_BACKEND": "codex",
        })
        self.brief = root / "unit.md"

    def write_brief(self, gate=None):
        text = "## Result\nChange seed.\n"
        if gate:
            text += "\n```gate\n{0}\n```\n".format(gate)
        self.brief.write_text(text, encoding="utf-8")

    def plan_unit(self, *args, cwd=None):
        return subprocess.run(
            [str(SCRIPT)] + list(args), cwd=cwd or self.repo, env=self.env, capture_output=True, text=True
        )

    def git(self, *args, cwd=None):
        return subprocess.check_output(["git", *args], cwd=cwd or self.repo).decode("utf-8")

    def unit_command(self, command, *extra, cwd=None):
        return self.plan_unit(command, str(self.brief), "--dir", str(self.out), *extra, cwd=cwd)

    def worktree(self, *extra, unit=None):
        options = ("--unit", unit) if unit else ()
        result = self.unit_command("worktree", *options, *extra)
        tree = (self.out / (unit or "unit") / "worktree").resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("worktree: {0}".format(tree), result.stdout.splitlines())
        return tree

    def begin(self, *extra):
        result = self.plan_unit("begin", str(self.brief), "--dir", str(self.out), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)

    def check(self, *extra, unit=None):
        args = ["check", str(self.brief), "--dir", str(self.out)]
        if unit:
            args.extend(["--unit", unit])
        return self.plan_unit(*(args + list(extra)))

    def implement(self, text="changed\n"):
        (self.repo / "seed.txt").write_text(text, encoding="utf-8")

    def gate(self, *extra, unit=None):
        args = ["gate", str(self.brief), "--dir", str(self.out)]
        if unit:
            args.extend(["--unit", unit])
        return self.plan_unit(*(args + list(extra)))

    def reviews(self):
        return sorted(self.state.glob("prompt-*.md"))

    def counted_gate(self, check="grep -q changed seed.txt", log="gate-runs.log"):
        """A gate command that appends a line to a log outside the checkout each time it really runs."""
        return 'echo run >> "{0}"; {1}'.format(self.state / log, check)

    def runs(self, log="gate-runs.log"):
        path = self.state / log
        return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0

    def receipt(self):
        return self.out / "unit" / "receipt" / "receipt.json"

    def test_passing_gate_then_a_separate_reviewer_on_its_own_model_gives_pass(self):
        self.write_brief(gate="grep -q changed seed.txt")
        self.begin()
        self.implement()
        result = self.check("--review-model", "haiku-x", "-r", "low")
        self.assertEqual((result.returncode, "VERDICT: pass" in result.stdout), (0, True), result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        args = json.loads((self.state / "args-1.json").read_text())
        self.assertEqual(args[args.index("-m") + 1], "haiku-x")
        self.assertIn('model_reasoning_effort="low"', args)
        self.assertEqual(args[args.index("-s") + 1], "read-only")
        prompt = self.reviews()[0].read_text()
        self.assertIn("Change seed.", prompt)
        self.assertIn("+changed", (self.out / "unit" / "rounds" / "1" / "diff.patch").read_text())

    def test_a_failing_gate_sends_the_unit_back_without_starting_a_reviewer(self):
        self.write_brief(gate="grep -q never-there seed.txt")
        self.begin()
        self.implement()
        result = self.check("--review-model", "haiku-x")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("VERDICT: back", result.stdout)
        self.assertEqual(self.reviews(), [])
        problems = (self.out / "unit" / "rounds" / "1" / "problems.md").read_text()
        self.assertIn("The gate failed: 1 of 1", problems)

    def test_same_unit_resumes_reviewer_with_continuation_and_previous_problems(self):
        self.env["FAKE_VERDICTS"] = json.dumps(["back", "pass"])
        self.write_brief()
        self.begin()
        self.implement()
        first = self.check("--review-model", "m")
        self.assertEqual(first.returncode, 1, first.stdout)
        self.implement("changed again\n")
        second = self.check("--review-model", "m")
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(len(self.reviews()), 2)
        first_args = json.loads((self.state / "args-1.json").read_text())
        second_args = json.loads((self.state / "args-2.json").read_text())
        self.assertNotIn("resume", first_args)
        self.assertIn("-C", first_args)
        self.assertIn("resume", second_args)
        self.assertNotIn("-C", second_args)
        self.assertEqual(second_args[-2], "thread-1")
        self.assertIn("fix the thing", self.reviews()[1].read_text())
        self.assertNotIn("Change seed.", self.reviews()[1].read_text())
        self.assertNotIn("fix the thing", self.reviews()[0].read_text())

    def test_a_different_unit_starts_a_fresh_reviewer_conversation(self):
        self.write_brief()
        self.begin()
        self.implement()
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        self.begin("--unit", "another")
        self.assertEqual(self.check("--review-model", "m", unit="another").returncode, 0)
        args = json.loads((self.state / "args-2.json").read_text())
        self.assertNotIn("resume", args)
        self.assertIn("-C", args)

    def test_begin_restart_drops_the_reviewer_conversation(self):
        self.write_brief()
        self.begin()
        self.implement()
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        self.implement("changed again\n")
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        self.begin("--restart")
        self.assertEqual(self.check("--review-model", "m").returncode, 0)
        args = json.loads((self.state / "args-3.json").read_text())
        self.assertNotIn("resume", args)
        self.assertIn("-C", args)

    def test_escalate_and_brief_verdicts_stop_with_exit_two(self):
        for verdict in ("escalate", "brief"):
            with self.subTest(verdict=verdict):
                for path in self.state.iterdir():
                    path.unlink()
                self.env["FAKE_VERDICTS"] = json.dumps([verdict])
                self.write_brief()
                self.begin("--restart")
                result = self.check("--review-model", "m")
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_gate_only_runs_the_gate_and_writes_the_diff_without_a_reviewer(self):
        self.write_brief(gate="true")
        self.begin()
        self.implement()
        result = self.check("--gate-only")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("VERDICT", result.stdout)
        self.assertEqual(self.reviews(), [])
        self.assertTrue((self.out / "unit" / "rounds" / "1" / "diff.patch").is_file())

    def test_begin_does_not_overwrite_a_unit_unless_restarted(self):
        self.write_brief()
        self.begin()
        again = self.plan_unit("begin", str(self.brief), "--dir", str(self.out))
        self.assertEqual(again.returncode, 3)
        self.assertIn("already begun", again.stderr)
        restarted = self.plan_unit("begin", str(self.brief), "--dir", str(self.out), "--restart")
        self.assertEqual(restarted.returncode, 0, restarted.stderr)

    def test_errors_exit_three(self):
        self.write_brief()
        no_begin = self.check("--review-model", "m")
        self.assertEqual(no_begin.returncode, 3)
        self.assertIn("run begin first", no_begin.stderr)
        self.begin()
        no_model = self.check()
        self.assertEqual(no_model.returncode, 3)
        self.assertIn("--review-model is required", no_model.stderr)

    def test_missing_review_verdict_is_an_error(self):
        self.env["FAKE_VERDICTS"] = json.dumps(["invalid"])
        self.write_brief()
        self.begin()
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 3, result.stdout)

    def test_green_receipt_makes_check_skip_the_gate(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        receipt = self.gate()
        self.assertEqual((receipt.returncode, receipt.stdout.strip()), (0, "receipt: pass (1 command(s))"), receipt.stderr)
        self.assertEqual(self.runs(), 1)
        data = json.loads(self.receipt().read_text(encoding="utf-8"))
        self.assertEqual((data["commands"], data["red"]), ([self.counted_gate()], 0))
        self.assertRegex(data["tree"], r"^[0-9a-f]+$")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (receipt, 1 command(s))", result.stdout)
        self.assertEqual(self.runs(), 1)
        self.assertIn(str(self.out / "unit" / "receipt" / "gate" / "gate.md"), self.reviews()[0].read_text())

    def test_edit_after_gate_makes_check_run_the_gate_again(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.implement("changed again\n")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        self.assertEqual(self.runs(), 2)

    def test_changed_gate_command_in_the_brief_makes_check_run_the_gate_again(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.write_brief(gate=self.counted_gate(log="other.log"))
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        self.assertEqual((self.runs(), self.runs("other.log")), (1, 1))

    def test_red_receipt_never_makes_check_skip_the_gate(self):
        self.write_brief(gate=self.counted_gate(check="grep -q never-there seed.txt"))
        self.begin()
        self.implement()
        receipt = self.gate()
        self.assertEqual((receipt.returncode, receipt.stdout.strip()), (1, "receipt: FAIL (1 of 1)"), receipt.stderr)
        self.assertEqual(json.loads(self.receipt().read_text(encoding="utf-8"))["red"], 1)
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("VERDICT: back", result.stdout)
        self.assertEqual(self.runs(), 2)
        self.assertEqual(self.reviews(), [])

    def test_failing_gate_in_check_deletes_an_old_receipt(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.implement("other\n")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse(self.receipt().exists())

    def test_gate_needs_begin_first(self):
        self.write_brief(gate="true")
        result = self.gate()
        self.assertEqual(result.returncode, 3)
        self.assertIn("run begin first", result.stderr)

    def test_green_receipt_also_skips_the_gate_with_gate_only(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        result = self.check("--gate-only")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (receipt, 1 command(s))", result.stdout)
        self.assertNotIn("VERDICT", result.stdout)
        self.assertEqual((self.runs(), self.reviews()), (1, []))

    def test_unreadable_receipt_is_ignored_and_the_gate_runs(self):
        self.write_brief(gate=self.counted_gate())
        self.begin()
        self.implement()
        self.assertEqual(self.gate().returncode, 0)
        self.receipt().write_text("{not json", encoding="utf-8")
        result = self.check("--review-model", "m")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gate: pass (1 command(s))", result.stdout)
        self.assertEqual(self.runs(), 2)

    def test_gate_without_gate_commands_writes_no_receipt(self):
        self.write_brief()
        self.begin()
        self.implement()
        result = self.gate()
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "receipt: none (no gate commands)"), result.stderr)
        self.assertFalse(self.receipt().exists())

    def test_worktree_base_includes_uncommitted_and_untracked_files(self):
        self.write_brief()
        self.implement("working seed\n")
        (self.repo / "untracked.txt").write_text("untracked\n")
        (self.repo / ".gitignore").write_text("ignored.txt\n")
        (self.repo / "ignored.txt").write_text("ignored\n")

        tree = self.worktree()
        self.assertEqual(self.git("branch", "--show-current", cwd=tree), "")
        self.assertEqual((tree / "seed.txt").read_text(), "working seed\n")
        self.assertEqual((tree / "untracked.txt").read_text(), "untracked\n")
        self.assertFalse((tree / "ignored.txt").exists())
        base = (tree.parent / "base").read_text().strip()
        self.assertEqual(self.git("rev-parse", "HEAD^{tree}", cwd=tree).strip(), base)
        self.assertEqual(self.git("show", base + ":seed.txt"), "working seed\n")

    def test_worktree_runs_the_committed_setup(self):
        self.write_brief()
        config = self.repo / ".plan-run.json"
        config.write_text(json.dumps({"worktree": {
            "copy": ["local.txt"],
            "prepare": ["test -f local.txt && echo prepared > prepared.txt"],
        }}))
        (self.repo / ".gitignore").write_text("local.txt\nprepared.txt\n")
        self.git("add", ".plan-run.json", ".gitignore")
        self.git("commit", "-qm", "declare setup")
        config.write_text('{}')
        (self.repo / "local.txt").write_text("local\n")

        tree = self.worktree()
        self.assertEqual((tree / "local.txt").read_text(), "local\n")
        self.assertEqual((tree / "prepared.txt").read_text(), "prepared\n")
        self.assertEqual((tree / ".plan-run.json").read_text(), '{}')

    def test_gate_and_check_use_the_worktree_from_outside_the_repo(self):
        self.write_brief(gate=self.counted_gate("grep -q unit-change seed.txt"))
        tree = self.worktree()
        self.implement("main change\n")
        (tree / "seed.txt").write_text("unit-change\n")
        gate = self.unit_command("gate", cwd=self.state)
        self.assertEqual(gate.returncode, 0, gate.stderr)
        checked = self.unit_command("check", "--gate-only", cwd=self.state)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("gate: pass (receipt, 1 command(s))", checked.stdout)
        self.assertEqual(self.runs(), 1)
        patch = (tree.parent / "rounds" / "1" / "diff.patch").read_text()
        self.assertIn("+unit-change", patch)
        self.assertNotIn("main change", patch)

    def test_two_units_merge_different_lines_into_current_main_checkout(self):
        self.write_brief()
        self.implement("first\n2\n3\n4\n5\n6\n7\n8\nlast\n")
        first = self.worktree(unit="first")
        last = self.worktree(unit="last")
        for tree, old, new in ((first, "first", "unit one"), (last, "last", "unit two")):
            path = tree / "seed.txt"
            path.write_text(path.read_text().replace(old, new))
        self.implement((self.repo / "seed.txt").read_text().replace("5\n", "main edit\n"))

        for unit in ("first", "last"):
            result = self.unit_command("integrate", "--unit", unit)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["integrated: 1 file(s)", "seed.txt"])
            self.assertFalse((self.out / unit / "marked").exists())
        self.assertEqual(
            (self.repo / "seed.txt").read_text(), "unit one\n2\n3\n4\nmain edit\n6\n7\n8\nunit two\n"
        )
        before_last = (last.parent / "pre-integration").read_text().strip()
        self.assertEqual(self.git("show", before_last + ":seed.txt").splitlines()[0], "unit one")

    def test_two_units_append_functions_with_the_files_blank_line_spacing(self):
        self.write_brief()
        original = "def original():\n    pass\n\n\n"
        first_function = "def first():\n    pass\n"
        second_function = "def second():\n    pass\n"
        (self.repo / "text.py").write_text(original)
        first = self.worktree(unit="first")
        second = self.worktree(unit="second")
        (first / "text.py").write_text(original + first_function)
        (second / "text.py").write_text(original + second_function)

        result = self.unit_command("integrate", "--unit", "first")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.unit_command("integrate", "--unit", "second")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["integrated: 1 file(s)", "text.py", "joined:", "text.py"])
        self.assertEqual((self.repo / "text.py").read_text(), original + first_function + "\n\n" + second_function)
        self.assertEqual((second.parent / "joined.txt").read_text(), "text.py\n")
        self.assertFalse((second.parent / "conflicts.txt").exists())

    def test_conflict_preserves_index_and_keeps_the_pre_integration_tree_readable(self):
        self.write_brief()
        tree = self.worktree(unit="change-seed")
        (tree / "seed.txt").write_text("from unit\n")
        (tree / "other.txt").write_text("also from unit\n")
        self.implement("staged seed\n")
        self.git("add", "seed.txt")
        self.implement("from main\n")
        index = self.repo / ".git" / "index"
        index_before = index.read_bytes()
        head_before = self.git("rev-parse", "HEAD")

        result = self.unit_command("integrate", "--unit", "change-seed")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["conflicts:", "seed.txt"])
        self.assertEqual((tree.parent / "conflicts.txt").read_text(), "seed.txt\n")
        conflicted = (self.repo / "seed.txt").read_text()
        self.assertRegex(conflicted, r"\A<<<<<<< main checkout\nfrom main\n\|{7} .*\nseed\n"
                         r"=======\nfrom unit\n>>>>>>> change-seed\n\Z")
        self.assertEqual((self.repo / "other.txt").read_text(), "also from unit\n")
        self.assertEqual(index.read_bytes(), index_before)
        self.assertEqual(self.git("rev-parse", "HEAD"), head_before)
        self.assertEqual(self.git("show", ":seed.txt"), "staged seed\n")

        marked = (tree.parent / "marked").read_text().strip()
        self.assertNotEqual(marked, (tree.parent / "pre-integration").read_text().strip())
        self.git("cat-file", "-e", marked + "^{tree}")
        self.implement("resolved seed\n")
        conflicts = (tree.parent / "conflicts.txt").read_text().splitlines()
        patch = self.git("diff", marked, "--", *conflicts)
        changed = [line for line in patch.splitlines()
                   if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
        self.assertEqual(changed, ["-" + line for line in conflicted.splitlines()] + ["+resolved seed"])

    def test_third_unit_is_refused_while_a_file_it_would_write_has_markers(self):
        self.write_brief()
        for unit in ("first", "second", "third"):
            tree = self.worktree(unit=unit)
            (tree / "seed.txt").write_text(unit + "\n")
        (tree / "also.txt").write_text("new file\n")
        self.assertEqual(self.unit_command("integrate", "--unit", "first").returncode, 0)
        self.assertEqual(self.unit_command("integrate", "--unit", "second").returncode, 1)
        seed = self.repo / "seed.txt"
        conflicted = seed.read_bytes()
        index = self.repo / ".git" / "index"
        index_before = index.read_bytes()
        head_before = self.git("rev-parse", "HEAD")
        unit_files = set(tree.parent.iterdir())

        result = self.unit_command("integrate", "--unit", "third")
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertIn("seed.txt", result.stderr)
        self.assertEqual(seed.read_bytes(), conflicted)
        self.assertFalse((self.repo / "also.txt").exists())
        self.assertEqual(index.read_bytes(), index_before)
        self.assertEqual(self.git("rev-parse", "HEAD"), head_before)
        self.assertEqual(set(tree.parent.iterdir()), unit_files)

    def test_only_files_the_integration_would_write_are_checked_for_markers(self):
        self.write_brief()
        markers = ("<<<<<<< main checkout\n", "||||||| base\n", "=======\n", ">>>>>>> earlier unit\n")
        for number, marker in enumerate(markers):
            with self.subTest(marker=marker):
                unit = "marker-" + str(number)
                nearby = "other-" + str(number) + ".txt"
                (self.repo / nearby).write_text("======= heading\nA line with <<<<<<< inside it\n")
                self.implement(marker)
                tree = self.worktree(unit=unit)
                (tree / "seed.txt").write_text("replacement\n")
                blocked = self.unit_command("integrate", "--unit", unit)
                self.assertEqual(blocked.returncode, 3, blocked.stdout)
                self.assertIn("seed.txt", blocked.stderr)
                self.assertEqual((self.repo / "seed.txt").read_text(), marker)

                (tree / "seed.txt").write_text(marker)
                (tree / nearby).write_text("new content\n")
                integrated = self.unit_command("integrate", "--unit", unit)
                self.assertEqual(integrated.returncode, 0, integrated.stderr)
                self.assertEqual((self.repo / "seed.txt").read_text(), marker)
                self.assertEqual((self.repo / nearby).read_text(), "new content\n")

    def test_joined_insertion_and_real_conflict_in_the_same_file(self):
        self.write_brief()
        unchanged = "line two\nline three\nlast line\n\n"
        self.implement("original\n" + unchanged)
        tree = self.worktree(unit="mixed")
        self.implement("from main\n" + unchanged + "main insertion\n")
        (tree / "seed.txt").write_text("from unit\n" + unchanged + "unit insertion\n")

        result = self.unit_command("integrate", "--unit", "mixed")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["conflicts:", "seed.txt", "joined:", "seed.txt"])
        self.assertEqual((tree.parent / "conflicts.txt").read_text(), "seed.txt\n")
        marked = (tree.parent / "marked").read_text().strip()
        self.git("cat-file", "-e", marked + "^{tree}")
        self.assertEqual((tree.parent / "joined.txt").read_text(), "seed.txt\n")
        self.assertEqual(
            (self.repo / "seed.txt").read_text(),
            "<<<<<<< main checkout\nfrom main\n||||||| base\noriginal\n=======\nfrom unit\n>>>>>>> mixed\n"
            + unchanged + "main insertion\n\nunit insertion\n",
        )

    def test_integrate_adds_and_deletes_files(self):
        self.write_brief()
        tree = self.worktree()
        contents = b"\x00\xff\x03"
        (tree / "new file.bin").write_bytes(contents)
        (tree / "seed.txt").unlink()

        result = self.unit_command("integrate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["integrated: 2 file(s)", "new file.bin", "seed.txt"])
        self.assertEqual((self.repo / "new file.bin").read_bytes(), contents)
        self.assertFalse((self.repo / "seed.txt").exists())
        self.assertEqual(self.git("show", ":seed.txt"), "seed\n")

    def test_integrate_twice_is_refused(self):
        self.write_brief()
        tree = self.worktree()
        (tree / "seed.txt").write_text("first edit\n")
        first = self.unit_command("integrate")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (tree.parent / "pre-integration").read_bytes()
        (tree / "seed.txt").write_text("second edit\n")
        again = self.unit_command("integrate")
        self.assertEqual(again.returncode, 3, again.stdout)
        self.assertIn("already integrated", again.stderr)
        self.assertEqual((self.repo / "seed.txt").read_text(), "first edit\n")
        self.assertEqual((tree.parent / "pre-integration").read_bytes(), before)

    def test_integrate_refuses_a_unit_without_a_worktree(self):
        self.write_brief()
        not_begun = self.unit_command("integrate")
        self.assertEqual(not_begun.returncode, 3)
        self.assertIn("run begin first", not_begun.stderr)
        self.begin()
        in_place = self.unit_command("integrate")
        self.assertEqual(in_place.returncode, 3)
        self.assertIn("no worktree", in_place.stderr)

    def test_apply_write_failure_rolls_back_main_and_allows_retry(self):
        self.write_brief()
        directory = self.repo / "folder"
        directory.mkdir()
        (directory / "nested.txt").write_text("original nested\n")
        tree = self.worktree()
        (tree / "seed.txt").write_text("unit seed\n")
        (tree / "folder" / "nested.txt").write_text("unit nested\n")
        directory.chmod(0o555)
        try:
            if os.access(directory, os.W_OK):
                self.skipTest("test user can write to a read-only directory")
            failed = self.unit_command("integrate")
        finally:
            directory.chmod(0o755)
        self.assertEqual(failed.returncode, 3, failed.stdout)
        self.assertIn("git apply failed", failed.stderr)
        self.assertEqual((self.repo / "seed.txt").read_text(), "seed\n")
        self.assertEqual((directory / "nested.txt").read_text(), "original nested\n")
        self.assertFalse((tree.parent / "pre-integration").exists())
        retried = self.unit_command("integrate")
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual((directory / "nested.txt").read_text(), "unit nested\n")

    def test_discard_removes_a_dirty_worktree_and_keeps_evidence(self):
        self.write_brief()
        tree = self.worktree()
        (tree / "seed.txt").write_text("unit edit\n")
        checked = self.unit_command("check", "--gate-only")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        base = (tree.parent / "base").read_bytes()

        result = self.unit_command("discard", cwd=self.state)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(tree.exists())
        self.assertNotIn("worktree " + str(tree), self.git("worktree", "list", "--porcelain"))
        self.assertEqual((tree.parent / "base").read_bytes(), base)
        self.assertIn("+unit edit", (tree.parent / "rounds" / "1" / "diff.patch").read_text())

    def test_worktree_restart_replaces_the_worktree_and_evidence(self):
        self.write_brief()
        tree = self.worktree()
        (tree / "old edit.txt").write_text("discard me\n")
        old_evidence = tree.parent / "status.log"
        old_evidence.touch()
        refused = self.unit_command("worktree")
        self.assertEqual(refused.returncode, 3)
        self.assertTrue((tree / "old edit.txt").is_file())

        self.implement("fresh main state\n")
        self.assertEqual(self.worktree("--restart"), tree)
        self.assertFalse(old_evidence.exists())
        self.assertFalse((tree / "old edit.txt").exists())
        self.assertEqual((tree / "seed.txt").read_text(), "fresh main state\n")
        self.assertEqual(self.git("worktree", "list", "--porcelain").count("worktree " + str(tree) + "\n"), 1)


if __name__ == "__main__":
    unittest.main()

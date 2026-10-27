import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))

from harness.engine.run import RunError
import plan_inputs
import plan_lint


class PlanLintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "package.json").write_text(
            '{"scripts":{"test":"echo test","build":"echo build"}}',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def brief(self, content):
        path = self.root / "unit.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_handoff_proof_is_an_error_but_prohibition_is_not(self):
        passing = self.brief(
            "## Criteria\n- The handoff must not be used as proof.\n"
        )
        self.assertEqual(plan_lint.lint_brief(passing, self.root), [])

        failing = self.brief("## Criteria\n- The handoff is proof of completion.\n")
        self.assertEqual(
            plan_lint.lint_brief(failing, self.root),
            [("error", "Criteria must not use the handoff as proof")],
        )

        mixed = self.brief(
            "## Criteria\n- The handoff proves completion; there is no automated check for this.\n"
        )
        self.assertEqual(
            plan_lint.lint_brief(mixed, self.root),
            [("error", "Criteria must not use the handoff as proof")],
        )

    def test_gate_file_checks_resolve_paths_from_repository_root(self):
        passing = self.brief(
            "## Gate\n```gate\n"
            "bash scripts/check.sh\n"
            "python3 tools/check.py\n"
            "./scripts/check.sh\n"
            "pnpm test\n"
            "npm run build\n```\n"
        )
        (self.root / "scripts").mkdir()
        (self.root / "tools").mkdir()
        (self.root / "scripts" / "check.sh").touch()
        (self.root / "tools" / "check.py").touch()
        python_options = self.brief(
            "## Gate\n```gate\npython3 -W ignore tools/check.py\n```\n"
        )
        self.assertEqual(plan_lint.lint_brief(passing, self.root), [])
        self.assertEqual(plan_lint.lint_brief(python_options, self.root), [])

        failing = self.brief("## Gate\n```gate\npython3 missing/check.py\n```\n")
        self.assertEqual(
            plan_lint.lint_brief(failing, self.root),
            [("warning", "does not exist now: a unit before this one must create it")],
        )

    def test_unknown_package_script_is_a_warning(self):
        failing = self.brief("## Gate\n```gate\nnpm run deploy\n```\n")
        self.assertEqual(
            plan_lint.lint_brief(failing, self.root),
            [("warning", "does not exist now: a unit before this one must create it")],
        )

    def test_out_of_scope_prefers_exclusion_over_only_allowed_files(self):
        passing = self.brief("## Out of scope\n- Do not touch generated files.\n")
        self.assertEqual(plan_lint.lint_brief(passing, self.root), [])

        failing = self.brief(
            "## Out of scope\n- The diff only touches `src/a.py` and `src/b.py`.\n"
        )
        self.assertEqual(
            plan_lint.lint_brief(failing, self.root),
            [("error", "write the scope by exclusion")],
        )

    def test_gates_prints_lint_after_commands_and_errors_change_status(self):
        brief = self.brief(
            "## Criteria\n- The handoff proves it worked.\n"
            "## Gate\n```gate\necho check\n```\n"
        )
        plan = self.root / "plan.txt"
        plan.write_text("unit.md\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = plan_inputs.gates_command([str(plan)])
        self.assertEqual(status, 1)
        self.assertEqual(
            output.getvalue(),
            "unit\n  $ echo check\n  ! error: Criteria must not use the handoff as proof\n\n",
        )

    def test_gates_warning_does_not_change_status(self):
        brief = self.brief("## Gate\n```gate\nnode missing.js\n```\n")
        plan = self.root / "plan.txt"
        plan.write_text("unit.md\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = plan_inputs.gates_command([str(plan)])
        self.assertEqual(status, 0)
        self.assertEqual(
            output.getvalue(),
            "unit\n  $ node missing.js\n"
            "  ? warning: does not exist now: a unit before this one must create it\n\n",
        )

    def test_gates_no_lint_keeps_legacy_output_exactly(self):
        brief = self.brief("## Gate\n```gate\necho check\n```\n")
        plan = self.root / "plan.txt"
        plan.write_text("unit.md\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = plan_inputs.gates_command([str(plan)])
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), "unit\n  $ echo check\n\n")


if __name__ == "__main__":
    unittest.main()

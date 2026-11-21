import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))

from skill_catalog_common import validate_repository  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
CODES = {"INVOCATION_MARKERS_MISMATCH", "INVOCATION_EXEMPTION_STALE", "DISABLE_MODEL_INVOCATION_INVALID"}
OPEN_CODEX = "policy:\n  allow_implicit_invocation: false\n"


def skill_text(name: str, extra: str = "") -> str:
    return f"---\nname: {name}\ndescription: A skill for the test.\n{extra}---\n\n# Skill\n"


class InvocationMarkerTests(unittest.TestCase):
    def check(self, name: str, extra: str = "", metadata: str | None = None) -> list[str]:
        """Return the invocation-marker codes the catalog reports for one skill in a temporary repository."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            package = root / "agent-skills" / "skills" / name
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text(skill_text(name, extra), encoding="utf-8")
            if metadata is not None:
                (package / "agents").mkdir()
                (package / "agents" / "openai.yaml").write_text(metadata, encoding="utf-8")
            report = validate_repository(root)
        finally:
            temp_dir.cleanup()
        return [issue["code"] for issue in report["issues"] if issue["code"] in CODES]

    def test_both_markers_for_a_user_invoked_skill_pass(self):
        self.assertEqual(self.check("alpha", "disable-model-invocation: true\n", OPEN_CODEX), [])

    def test_no_markers_for_a_model_invoked_skill_pass(self):
        self.assertEqual(self.check("alpha"), [])

    def test_claude_marker_alone_is_a_mismatch(self):
        self.assertEqual(self.check("alpha", "disable-model-invocation: true\n"), ["INVOCATION_MARKERS_MISMATCH"])

    def test_codex_marker_alone_is_a_mismatch(self):
        self.assertEqual(self.check("alpha", "", OPEN_CODEX), ["INVOCATION_MARKERS_MISMATCH"])

    def test_codex_marker_true_with_claude_marker_is_a_mismatch(self):
        self.assertEqual(
            self.check("alpha", "disable-model-invocation: true\n", "policy:\n  allow_implicit_invocation: true\n"),
            ["INVOCATION_MARKERS_MISMATCH"],
        )

    def test_exempt_agent_invoked_skill_keeps_the_codex_marker_alone(self):
        self.assertEqual(self.check("git-merge-queue", "", OPEN_CODEX), [])

    def test_exempt_skill_with_the_claude_marker_is_stale(self):
        self.assertEqual(
            self.check("git-merge-queue", "disable-model-invocation: true\n", OPEN_CODEX),
            ["INVOCATION_EXEMPTION_STALE"],
        )

    def test_exempt_skill_without_the_codex_marker_is_stale(self):
        self.assertEqual(self.check("git-merge-queue"), ["INVOCATION_EXEMPTION_STALE"])

    def test_non_boolean_claude_marker_is_invalid(self):
        self.assertEqual(
            self.check("alpha", "disable-model-invocation: yes-please\n", OPEN_CODEX),
            ["DISABLE_MODEL_INVOCATION_INVALID"],
        )

    def test_claude_marker_is_a_supported_frontmatter_field(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            package = root / "agent-skills" / "skills" / "alpha"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text(skill_text("alpha", "disable-model-invocation: true\n"), encoding="utf-8")
            (package / "agents").mkdir()
            (package / "agents" / "openai.yaml").write_text(OPEN_CODEX, encoding="utf-8")
            report = validate_repository(root)
        finally:
            temp_dir.cleanup()
        self.assertFalse(
            any(issue["code"] == "FRONTMATTER_FIELD_UNKNOWN" for issue in report["issues"]), report["issues"]
        )

    def test_repository_skills_keep_their_markers_paired(self):
        report = validate_repository(REPO_ROOT)
        found = [issue for issue in report["issues"] if issue["code"] in CODES]
        self.assertEqual(found, [], found)


if __name__ == "__main__":
    unittest.main()

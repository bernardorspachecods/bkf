import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from catalog_common import generate_catalog, validate_repository  # noqa: E402


class SkillCatalogTests(unittest.TestCase):
    def make_repo(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        skills = root / "agent-skills" / "skills"
        skills.mkdir(parents=True)
        return temp_dir, root, skills

    def add_skill(self, skills, name, body=None, metadata=None):
        package = skills / name
        package.mkdir()
        if body is not None:
            (package / "SKILL.md").write_text(body, encoding="utf-8")
        if metadata is not None:
            agents = package / "agents"
            agents.mkdir()
            (agents / "openai.yaml").write_text(metadata, encoding="utf-8")
        return package

    def test_validator_discovers_valid_missing_and_empty_packages(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "alpha-skill",
            "---\nname: alpha-skill\ndescription: Alpha behavior\n---\n\n# Alpha\n",
        )
        missing = self.add_skill(skills, "missing-skill")
        (missing / "notes.txt").write_text("package content", encoding="utf-8")
        (skills / "empty-skill").mkdir()

        try:
            report = validate_repository(root)
        finally:
            temp_dir.cleanup()

        statuses = {
            package["path"]: package["status"] for package in report["packages"]
        }
        self.assertEqual(statuses["agent-skills/skills/alpha-skill"], "valid")
        self.assertEqual(statuses["agent-skills/skills/missing-skill"], "missing")
        self.assertEqual(statuses["agent-skills/skills/empty-skill"], "empty")
        self.assertTrue(any(issue["code"] == "SKILL_MISSING" for issue in report["issues"]))
        self.assertTrue(any(issue["code"] == "SKILL_EMPTY" for issue in report["issues"]))

    def test_app_managed_synced_folder_is_not_a_package(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "alpha-skill",
            "---\nname: alpha-skill\ndescription: Alpha behavior\n---\n",
        )
        synced = skills / "synced"
        synced.mkdir()
        (synced / "manifest.json").write_text("{}", encoding="utf-8")

        try:
            report = validate_repository(root)
            catalog = generate_catalog(root)
        finally:
            temp_dir.cleanup()

        self.assertEqual(report["status"], "valid", report["issues"])
        self.assertEqual([package["path"] for package in report["packages"]], ["agent-skills/skills/alpha-skill"])
        self.assertNotIn("synced", catalog)

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_git_ignored_skill_is_left_out_only_inside_a_git_repository(self):
        skill = "---\nname: {0}\ndescription: A skill\n---\n"
        for use_git in (True, False):
            temp_dir, root, skills = self.make_repo()
            self.add_skill(skills, "alpha-skill", skill.format("alpha-skill"))
            self.add_skill(skills, "local-skill", skill.format("local-skill"))
            (root / ".gitignore").write_text("/agent-skills/skills/local-skill/\n", encoding="utf-8")
            if use_git:
                subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            try:
                paths = [package["path"] for package in validate_repository(root)["packages"]]
                catalog = generate_catalog(root)
            finally:
                temp_dir.cleanup()

            self.assertIn("alpha-skill", catalog)
            if use_git:
                self.assertEqual(paths, ["agent-skills/skills/alpha-skill"])
                self.assertNotIn("local-skill", catalog)
            else:
                self.assertEqual(len(paths), 2)
                self.assertIn("local-skill", catalog)

    def test_validator_reports_broken_links_and_mismatched_name(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "actual-name",
            "---\nname: declared-name\ndescription: A skill\n---\n\n[Missing](references/nope.md)\n",
        )

        try:
            report = validate_repository(root)
        finally:
            temp_dir.cleanup()

        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("SKILL_NAME_MISMATCH", codes)
        self.assertIn("REFERENCE_MISSING", codes)
        self.assertEqual(report["status"], "invalid")

    def test_generator_is_deterministic_and_check_detects_drift(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "zeta-skill",
            "---\nname: zeta-skill\ndescription: Zeta behavior\n---\n",
            "interface:\n  display_name: Zeta\n  short_description: Zeta UI\n",
        )
        self.add_skill(
            skills,
            "alpha-skill",
            "---\nname: alpha-skill\ndescription: Alpha behavior\n---\n\nUse $zeta-skill when needed.\n",
        )
        output = root / "agent-skills" / "SKILL-ARCHITECTURE.md"

        try:
            first = generate_catalog(root)
            second = generate_catalog(root)
            output.write_text(first, encoding="utf-8")
            clean = validate_repository(root, check_catalog=True)
            output.write_text(first.replace("Alpha behavior", "Changed"), encoding="utf-8")
            drifted = validate_repository(root, check_catalog=True)
        finally:
            temp_dir.cleanup()

        self.assertEqual(first, second)
        self.assertEqual(clean["catalog"]["status"], "valid")
        self.assertEqual(drifted["catalog"]["status"], "drifted")
        self.assertIn("CATALOG_DRIFT", {issue["code"] for issue in drifted["issues"]})
        self.assertLess(first.index("alpha-skill"), first.index("zeta-skill"))
        self.assertIn("](skills/alpha-skill/SKILL.md)", first)
        self.assertIn("`display_name`: Zeta", first)

    def test_cli_json_output_is_machine_readable(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "alpha-skill",
            "---\nname: alpha-skill\ndescription: Alpha behavior\n---\n",
        )
        script = SCRIPTS / "validate_skill_catalog.py"

        try:
            result = subprocess.run(
                [sys.executable, str(script), str(root), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )
        finally:
            temp_dir.cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "valid")
        self.assertIn("issues", payload)

    def test_generator_cli_writes_and_checks_both_catalog_formats(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "alpha-skill",
            "---\nname: alpha-skill\ndescription: Alpha behavior\n---\n",
        )
        script = SCRIPTS / "generate_skill_catalog.py"

        try:
            written = subprocess.run(
                [sys.executable, str(script), str(root), "--write"],
                check=False,
                capture_output=True,
                text=True,
            )
            checked = subprocess.run(
                [sys.executable, str(script), str(root), "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            markdown_exists = (root / "agent-skills" / "SKILL-ARCHITECTURE.md").is_file()
        finally:
            temp_dir.cleanup()

        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertTrue(markdown_exists)

    def test_validator_checks_runtime_yaml_and_machine_specific_paths(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "runtime-skill",
            "---\nname: runtime-skill\ndescription: Runtime behavior\n---\n\nSee /Users/example/file.md\n",
            "interface:\n  - display_name\n",
        )

        try:
            report = validate_repository(root)
        finally:
            temp_dir.cleanup()

        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("RUNTIME_METADATA_INVALID", codes)
        self.assertIn("MACHINE_SPECIFIC_PATH", codes)

    def test_generator_excludes_empty_packages_and_write_boundary_is_explicit(self):
        temp_dir, root, skills = self.make_repo()
        self.add_skill(
            skills,
            "real-skill",
            "---\nname: real-skill\ndescription: Real behavior\n---\n",
        )
        (skills / "empty-skill").mkdir()

        try:
            generated = generate_catalog(root)
            self.assertIn("## real-skill", generated)
            self.assertNotIn("## empty-skill", generated)
            with self.assertRaises(ValueError):
                from catalog_common import write_catalog

                write_catalog(root, root / "other.md")
        finally:
            temp_dir.cleanup()

    def test_validator_distinguishes_unavailable_and_indeterminate(self):
        unavailable_dir = tempfile.TemporaryDirectory()
        unavailable_root = Path(unavailable_dir.name)
        try:
            unavailable = validate_repository(unavailable_root)
            self.assertEqual(unavailable["status"], "unavailable")
            self.assertIn("SKILL_ROOT_UNAVAILABLE", {item["code"] for item in unavailable["issues"]})
        finally:
            unavailable_dir.cleanup()

        temp_dir, root, skills = self.make_repo()
        package = self.add_skill(skills, "undecidable-skill")
        (package / "SKILL.md").write_bytes(b"---\nname: undecidable-skill\ndescription: \xff\n---\n")
        try:
            report = validate_repository(root)
        finally:
            temp_dir.cleanup()

        self.assertEqual(report["packages"][0]["status"], "indeterminate")
        self.assertEqual(report["status"], "indeterminate")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLING = Path(__file__).resolve().parents[1]
CLI = TOOLING / "bkf_cli.py"
sys.path.insert(0, str(TOOLING))
import search


def map_text(*, root: bool = False) -> str:
    front = 'bkf_version: "0.1"\n' if root else ""
    return f"---\n{front}description: Bundle map.\n---\n\n# Map\n"


def document(name: str, body: str, *, description: str = "A tracked guide.", profile: str = "document") -> str:
    return (
        f"---\nbkf: {profile}\ndescription: {description}\ntags: [test]\n---\n\n"
        f"# {name}\n\n{body}"
    )


def make_bundle(root: Path) -> None:
    (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")


def run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "search", *arguments, "--cwd", str(root)],
        cwd=TOOLING,
        check=False,
        capture_output=True,
        text=True,
    )


class SearchTests(unittest.TestCase):
    def test_heading_match_ranks_above_body_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "body.md").write_text(document("Overview", "The description rules are discussed here."), encoding="utf-8")
            (root / "heading.md").write_text(document("Descriptions", "Short content."), encoding="utf-8")

            result = run(root, "description")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1  /heading.md § Descriptions", result.stdout)

    def test_heading_splitting_and_fenced_code_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(
                document("Guide", """Intro text.

## Parent
Parent content.

```md
## Fake heading
```

### Child
Child content.

## Last
Last content.
"""),
                encoding="utf-8",
            )

            result = run(root, "child")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("§ Guide > Parent > Child", result.stdout)
        self.assertNotIn("Fake heading", result.stdout)

    def test_excluded_files_do_not_appear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "MAP.md").write_text(map_text(root=True) + "needle hiddenmap\n", encoding="utf-8")
            (root / "feedback.md").write_text(document("Needle feedback", "needle", profile="feedback"), encoding="utf-8")
            (root / "ideas.md").write_text(document("Needle ideas", "needle", profile="ideas"), encoding="utf-8")
            (root / "untracked.md").write_text("# Needle untracked\nneedle\n", encoding="utf-8")
            hidden = root / ".private"
            hidden.mkdir()
            (hidden / "hidden.md").write_text(document("Needle hidden", "needle"), encoding="utf-8")
            hidden_bundle = hidden / "bundle"
            hidden_bundle.mkdir()
            (hidden_bundle / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (hidden_bundle / "hidden-bundle.md").write_text(document("Needle hidden bundle", "needle"), encoding="utf-8")
            (root / "visible.md").write_text(document("Visible", "needle content."), encoding="utf-8")

            result = run(root, "needle", "--limit", "20")

        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("feedback.md", "ideas.md", "untracked.md", "hidden.md", "hidden-bundle.md", "MAP.md"):
            self.assertNotIn(name, result.stdout)
        self.assertIn("/visible.md", result.stdout)

    def test_agents_file_is_indexed_without_minimum_body_length(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "AGENTS.md").write_text(
                "# Agent instructions\n\nRecord what went wrong after an unexpected command failure.\n",
                encoding="utf-8",
            )

            result = run(root, "where do agents record what went wrong")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/AGENTS.md", result.stdout)

    def test_nested_bundle_paths_are_relative_to_outer_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            nested = root / "nested"
            nested.mkdir()
            (nested / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (nested / "guide.md").write_text(document("Nested", "needle in nested bundle."), encoding="utf-8")

            result = run(nested, "needle")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/nested/guide.md", result.stdout)

    def test_limit_and_output_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            for index in range(40):
                (root / f"doc-{index:02}.md").write_text(
                    document(f"Needle {index}", "needle " + "x " * 195), encoding="utf-8"
                )

            limited = run(root, "needle", "--limit", "2")
            capped = run(root, "needle", "--limit", "40")

        self.assertEqual(limited.returncode, 0, limited.stderr)
        self.assertEqual(limited.stdout.count(" § "), 2)
        self.assertEqual(capped.returncode, 0, capped.stderr)
        self.assertLessEqual(len(capped.stdout), search.OUTPUT_LIMIT)

    def test_fts_syntax_characters_are_quoted_as_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(document("Syntax", "NEAR search syntax."), encoding="utf-8")

            result = run(root, '" * - NEAR :')

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_query_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)

            result = run(root, "the and of")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "query has no searchable words")

    def test_no_hit_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)

            result = run(root, "unmatched")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "no sections match\n")

    def test_search_is_listed_as_a_py_module(self) -> None:
        pyproject = (TOOLING / "pyproject.toml").read_text(encoding="utf-8")
        module_list = pyproject.split("py-modules = [", 1)[1].split("]", 1)[0]
        self.assertIn('"search"', module_list)

    def test_failure_prints_to_stderr_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            with patch.object(search, "_collect_sections", side_effect=RuntimeError("failed to read")):
                with patch("sys.stderr", new_callable=lambda: _TextStream()) as stderr:
                    result = search.main(["topic", "--cwd", str(root)])

        self.assertEqual(result, 1)
        self.assertIn("bkf search: failed to read", stderr.output)


class _TextStream:
    def __init__(self) -> None:
        self.output = ""

    def write(self, value: str) -> int:
        self.output += value
        return len(value)

    def flush(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()

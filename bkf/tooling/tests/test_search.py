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


def document(
    name: str, body: str, *, description: str = "A tracked guide.", profile: str = "document", tags: str = "test"
) -> str:
    return (
        f"---\nbkf: {profile}\ndescription: {description}\ntags: [{tags}]\n---\n\n"
        f"# {name}\n\n{body}"
    )


def make_bundle(root: Path) -> None:
    (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")


def run(root: Path, *arguments: str, cwd: Path = TOOLING) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "search", *arguments, "--cwd", str(root)],
        cwd=cwd,
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


VOCABULARY = """\
ai: [artificial intelligence, inteligência artificial]
thesis: []
"""


def paths(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.split()[1] for line in result.stdout.splitlines() if " § " in line]


class TagSearchTests(unittest.TestCase):
    def test_tag_is_indexed_for_every_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tagged.md").write_text(
                document("Notes", "Intro.\n\n## Other\n\nMore words.", tags="zebra"), encoding="utf-8"
            )
            (root / "plain.md").write_text(document("Other notes", "Plain words."), encoding="utf-8")

            result = run(root, "zebra")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(paths(result), ["/tagged.md", "/tagged.md"])
        self.assertIn("§ Notes > Other", result.stdout)

    def test_tag_column_does_not_change_ranking_of_other_queries(self) -> None:
        sections = [
            search.Section("/a.md", "Alpha", "", "needle " + "x " * 5, "Alpha", ("a", "b", "c", "d")),
            search.Section("/b.md", "Beta", "", "needle " + "x " * 5, "Beta", ()),
            search.Section("/c.md", "Gamma", "", "needle", "Gamma", ("long tag list here", "more")),
        ]
        stripped = [search.Section(s.path, s.heading, s.description, s.body, s.title) for s in sections]

        ranked = [(hit.path, rank) for hit, rank in search._search(sections, ["needle"], 5)]
        self.assertEqual(ranked, [(hit.path, rank) for hit, rank in search._search(stripped, ["needle"], 5)])

    def test_single_word_synonym_expands_to_canonical_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text("ai: [robotics]\n", encoding="utf-8")
            (root / "tagged.md").write_text(document("Notes", "Unrelated text.", tags="ai"), encoding="utf-8")
            (root / "other.md").write_text(document("Other", "Nothing here."), encoding="utf-8")

            with_vocabulary = run(root, "robotics")
            (root / "tag-vocabulary.yaml").unlink()
            without = run(root, "robotics")

        self.assertEqual(paths(with_vocabulary), ["/tagged.md"])
        self.assertEqual(without.stdout, "no sections match\n")

    def test_multi_word_synonym_matches_contiguous_words_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text(VOCABULARY, encoding="utf-8")
            (root / "tagged.md").write_text(document("Notes", "Unrelated text.", tags="ai"), encoding="utf-8")

            together = run(root, "what is artificial intelligence?")
            canonical = run(root, "tell me about ai")
            apart = run(root, "intelligence of an artificial lake")

        self.assertEqual(paths(together), ["/tagged.md"])
        self.assertEqual(paths(canonical), ["/tagged.md"])
        self.assertEqual(apart.stdout, "no sections match\n")

    def test_canonical_tag_adds_its_synonyms_to_the_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text(VOCABULARY, encoding="utf-8")
            (root / "pt.md").write_text(document("Portugues", "Texto sobre inteligência artificial."), encoding="utf-8")

            result = run(root, "ai")

        self.assertEqual(paths(result), ["/pt.md"])

    def test_invalid_vocabulary_fails_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text("ai: not-a-list\n", encoding="utf-8")

            result = run(root, "needle")

        self.assertEqual(result.returncode, 1)
        self.assertIn("tag-vocabulary.yaml", result.stderr)


class FilterTests(unittest.TestCase):
    def make(self, root: Path) -> None:
        make_bundle(root)
        (root / "sub").mkdir()
        (root / "sub" / "inner.md").write_text(
            document("Inner", "Intro needle.\n\n## Rules\n\nneedle rule.", tags="alpha, beta"), encoding="utf-8"
        )
        (root / "outer.md").write_text(
            document("Outer", "Intro needle.\n\n## Rules\n\nneedle rule.\n\n### Deep\n\nneedle deep.", tags="alpha"),
            encoding="utf-8",
        )
        (root / "sub2.md").write_text(document("Sub two", "needle again.", tags="beta"), encoding="utf-8")

    def test_path_directory_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            directory_result = run(root, "needle", "--path", "sub", "--limit", "20")
            file_result = run(root, "needle", "--path", "outer.md", "--limit", "20")
            from_subdirectory = subprocess.run(
                [sys.executable, str(CLI), "search", "needle", "--path", ".", "--cwd", str(root / "sub"), "--limit", "20"],
                check=False, capture_output=True, text=True,
            )

        self.assertEqual(set(paths(directory_result)), {"/sub/inner.md"})
        self.assertEqual(set(paths(file_result)), {"/outer.md"})
        self.assertEqual(set(paths(from_subdirectory)), {"/sub/inner.md"})

    def test_path_outside_the_bundle_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            root.mkdir()
            self.make(root)

            result = run(root, "needle", "--path", "..")

        self.assertEqual(result.returncode, 2)
        self.assertIn("outside the bundle", result.stderr)

    def test_heading_matches_own_heading_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            rules = run(root, "needle", "--heading", "rules", "--limit", "20")
            deep = run(root, "needle", "--heading", "DEEP", "--limit", "20")
            trail = run(root, "needle", "--heading", "Outer > Rules", "--limit", "20")

        self.assertEqual(sorted(paths(rules)), ["/outer.md", "/sub/inner.md"])
        self.assertNotIn("Deep", rules.stdout)
        self.assertEqual(paths(deep), ["/outer.md"])
        self.assertIn("§ Outer > Rules > Deep", deep.stdout)
        self.assertEqual(trail.stdout, "no sections match\n")

    def test_tag_filter_requires_all_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            alpha = run(root, "needle", "--tag", "alpha", "--limit", "20")
            both = run(root, "needle", "--tag", "alpha", "--tag", "BETA", "--limit", "20")

        self.assertEqual(set(paths(alpha)), {"/outer.md", "/sub/inner.md"})
        self.assertEqual(set(paths(both)), {"/sub/inner.md"})

    def test_tag_filter_resolves_synonyms_with_a_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)
            (root / "tag-vocabulary.yaml").write_text("alpha: [first letter]\nbeta: []\n", encoding="utf-8")

            with_vocabulary = run(root, "needle", "--tag", "first letter", "--limit", "20")
            (root / "tag-vocabulary.yaml").unlink()
            without = run(root, "needle", "--tag", "first letter", "--limit", "20")

        self.assertEqual(set(paths(with_vocabulary)), {"/outer.md", "/sub/inner.md"})
        self.assertEqual(without.stdout, "no sections match\n")

    def test_filters_combine_with_and(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            result = run(root, "needle", "--path", "sub", "--heading", "Rules", "--tag", "beta", "--limit", "20")
            empty = run(root, "needle", "--path", "outer.md", "--tag", "beta", "--limit", "20")

        self.assertEqual(paths(result), ["/sub/inner.md"])
        self.assertIn("§ Inner > Rules", result.stdout)
        self.assertEqual(empty.stdout, "no sections match\n")


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

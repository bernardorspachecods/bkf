from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"

VOCABULARY = """\
ai: [artificial intelligence, inteligência artificial]
thesis: []
"""


def make_bundle(root: Path, vocabulary: str | None = VOCABULARY, *, nested: bool = False) -> None:
    (root / "MAP.md").write_text(
        "---\nbkf_version: \"0.1\"\n"
        + ("description: A nested bundle.\n" if nested else "")
        + "---\n\n# Bundle\n\n## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
        encoding="utf-8",
    )
    if vocabulary is not None:
        (root / "tag-vocabulary.yaml").write_text(vocabulary, encoding="utf-8")


def write_document(root: Path, tags: str, name: str = "topic.md") -> None:
    (root / name).write_text(
        f"---\nbkf: document\ndescription: A topic.\ntags: [{tags}]\n---\n\n# Topic\n",
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(INVENTORY), "--write", str(root)], check=True, capture_output=True, text=True)


def validate(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root), *arguments], check=False, capture_output=True, text=True
    )
    return f"{result.returncode}\n{result.stdout}{result.stderr}"


class TagVocabularyTests(unittest.TestCase):
    def test_known_tags_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, "ai, thesis")

            output = validate(root)

        self.assertTrue(output.startswith("0\n"), output)
        self.assertNotIn("TAG_", output)

    def test_unknown_tag_without_a_close_match_lists_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, "zzzzzz")

            output = validate(root)

        self.assertTrue(output.startswith("1\n"), output)
        self.assertIn("ERROR TAG_UNKNOWN topic.md: tag `zzzzzz` is not in tag-vocabulary.yaml\n", output)

    def test_unknown_tag_lists_the_closest_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, "thesis: []\nthesaurus: []\nthesis-choice: []\nthesis-plan: []\nzoo: []\n")
            write_document(root, "thesi")

            output = validate(root)

        line = next(line for line in output.splitlines() if "TAG_UNKNOWN" in line)
        self.assertIn("closest tags: `thesis`", line)
        self.assertLessEqual(line.count("`") // 2, 4)  # the tag itself plus at most three suggestions
        self.assertNotIn("`zoo`", line)

    def test_synonym_names_its_canonical_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, "Artificial Intelligence")

            output = validate(root)

        self.assertIn("ERROR TAG_UNKNOWN topic.md: tag `Artificial Intelligence` is a synonym; use `ai`", output)

    def test_absent_file_leaves_tags_unchecked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, None)
            write_document(root, "anything-goes")

            output = validate(root)

        self.assertTrue(output.startswith("0\n"), output)

    def test_nested_bundle_uses_its_own_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            write_document(root, "ai")
            nested = root / "nested"
            nested.mkdir()
            make_bundle(nested, "other: []\n", nested=True)
            write_document(nested, "other")
            write_document(nested, "ai", "wrong.md")

            output = validate(root)

        self.assertIn("ERROR TAG_UNKNOWN wrong.md", output)
        self.assertNotIn("ERROR TAG_UNKNOWN topic.md", output)

    def test_invalid_vocabularies_report_the_problem_on_the_file(self) -> None:
        cases = {
            "not a mapping": ("- ai\n- thesis\n", "must be a mapping"),
            "synonyms not a list": ("ai: artificial\n", "synonyms of `ai` must be a list"),
            "empty key": ('"": []\n', "non-empty string"),
            "empty synonym": ("ai: ['  ']\n", "must be non-empty strings"),
            "non-string synonym": ("ai: [3]\n", "must be non-empty strings"),
            "duplicate synonym": ("ai: [x]\nthesis: [X]\n", "already a synonym of `ai`"),
            "synonym equals key": ("ai: [Thesis]\nthesis: []\n", "equals a tag"),
            "invalid yaml": ("ai: [unclosed\n", "cannot use tag-vocabulary.yaml"),
            "duplicate key": ("ai: []\nai: []\n", "cannot use tag-vocabulary.yaml"),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bundle(root, text)
                write_document(root, "ai")

                output = validate(root)

                self.assertTrue(output.startswith("1\n"), output)
                line = next(line for line in output.splitlines() if "TAG_VOCABULARY_INVALID" in line)
                self.assertIn("ERROR TAG_VOCABULARY_INVALID tag-vocabulary.yaml:", line)
                self.assertIn(expected, line)
                self.assertNotIn("TAG_UNKNOWN", output)

    def test_empty_synonym_list_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, "thesis: []\n")
            write_document(root, "thesis")

            output = validate(root)

        self.assertTrue(output.startswith("0\n"), output)


if __name__ == "__main__":
    unittest.main()

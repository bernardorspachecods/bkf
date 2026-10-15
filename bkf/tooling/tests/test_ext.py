from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"

SCHEMA = """\
$schema: https://json-schema.org/draft/2020-12/schema
type: object
properties:
  ext:
    type: object
    required: [type, id]
    unevaluatedProperties: false
    properties:
      type: {enum: [thematic_knowledge, course_supplement]}
      id: {type: string, minLength: 1}
      connections:
        type: array
        items:
          type: object
          additionalProperties: false
          required: [id, relation]
          properties:
            id: {type: string, minLength: 1}
            relation: {enum: [prerequisite, application, related, contrast]}
    allOf:
      - if: {properties: {type: {const: thematic_knowledge}}}
        then: {required: [connections]}
      - if: {properties: {type: {const: course_supplement}}}
        then: {not: {required: [connections]}}
"""

TOPIC_EXT = """\
ext:
  type: thematic_knowledge
  id: topic-a
  connections:
    - id: topic-b
      relation: prerequisite
"""


def make_bundle(root: Path, *, schema: str | None = SCHEMA) -> None:
    (root / "MAP.md").write_text(
        "---\nbkf_version: \"0.1\"\n---\n\n# Bundle\n\n"
        "## Member inventory\n\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
        "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n",
        encoding="utf-8",
    )
    if schema is not None:
        (root / "ext-schema.yaml").write_text(schema, encoding="utf-8")


def write_document(root: Path, ext: str, name: str = "topic.md") -> None:
    (root / name).write_text(
        f"---\nbkf: document\ndescription: A topic.\ntags: [topic]\n{ext}---\n\n# Topic\n",
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(INVENTORY), "--write", str(root)], check=True, capture_output=True, text=True)


def validate(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)], check=False, capture_output=True, text=True
    )
    return f"{result.returncode}\n{result.stdout}{result.stderr}"


class ExtTests(unittest.TestCase):
    def check(self, ext: str, *, schema: str | None = SCHEMA) -> str:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root, schema=schema)
            write_document(root, ext)
            return validate(root)

    def test_conforming_ext_is_accepted(self) -> None:
        self.assertTrue(self.check(TOPIC_EXT).startswith("0\n"))

    def test_document_without_ext_is_unaffected(self) -> None:
        self.assertTrue(self.check("", schema=None).startswith("0\n"))

    def test_ext_without_schema_is_an_error(self) -> None:
        output = self.check(TOPIC_EXT, schema=None)
        self.assertNotIn("0\n", output[:2])
        self.assertIn("EXT_SCHEMA_MISSING", output)

    def test_invalid_schema_is_an_error(self) -> None:
        output = self.check(TOPIC_EXT, schema="type: 12\n")
        self.assertIn("EXT_SCHEMA_INVALID", output)

    def test_unknown_ext_field_is_rejected(self) -> None:
        output = self.check(TOPIC_EXT + "  invented: true\n")
        self.assertIn("EXT_INVALID", output)
        self.assertIn("invented", output)

    def test_relation_outside_enum_is_rejected_with_its_location(self) -> None:
        output = self.check(TOPIC_EXT.replace("prerequisite", "sibling"))
        self.assertIn("EXT_INVALID", output)
        self.assertIn("ext/connections/0/relation", output)

    def test_topic_without_connections_is_rejected(self) -> None:
        output = self.check("ext:\n  type: thematic_knowledge\n  id: topic-a\n")
        self.assertIn("connections", output)

    def test_supplement_shape_differs_from_topic_shape(self) -> None:
        self.assertTrue(self.check("ext:\n  type: course_supplement\n  id: course\n").startswith("0\n"))
        output = self.check("ext:\n  type: course_supplement\n  id: course\n  connections: []\n")
        self.assertIn("EXT_INVALID", output)

    def test_ext_must_be_a_mapping(self) -> None:
        self.assertIn("EXT_INVALID", self.check("ext: [a, b]\n"))

    def test_top_level_fields_stay_closed(self) -> None:
        self.assertIn("METADATA_UNKNOWN_FIELD", self.check(TOPIC_EXT + "type: thematic_knowledge\n"))

    def test_ext_is_not_allowed_on_other_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "ideas.md").write_text(
                f"---\nbkf: ideas\ndescription: Ideas.\n{TOPIC_EXT}---\n\n# Ideas\n", encoding="utf-8"
            )
            subprocess.run([sys.executable, str(INVENTORY), "--write", str(root)], check=True, capture_output=True, text=True)
            output = validate(root)
        self.assertIn("METADATA_UNKNOWN_FIELD", output)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"

ROOT_FRONT = '---\nbkf_version: "0.2"\n---\n\n'
CHILD_FRONT = '---\ndescription: Inner folder map for the test.\n---\n\n'
NESTED_FRONT = '---\ndescription: Nested bundle for the test.\nbkf_version: "0.2"\n---\n\n'
WARNING = "WARNING MAP_TOO_SMALL inner/MAP.md: map covers {size} items (limit 4)."


def map_text(front: str, routes: int = 0, references: int = 0) -> str:
    text = f"{front}# Map\n\n"
    if routes:
        text += "## Task routes\n\n| Task | Start here |\n| --- | --- |\n"
        text += "".join(f"| Task {index} | [Start](/inner/doc1.md) |\n" for index in range(routes))
        text += "\n"
    text += "## Member inventory\n\n<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    text += "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
    if references:
        text += "\n## Artifact references\n\n"
        text += "".join(f"- [tool{index}.py](/inner/tool{index}.py) — A script.\n" for index in range(references))
    return text


def build(root: Path, *, inner_front: str = CHILD_FRONT, documents: int = 0,
          references: int = 0, routes: int = 0, inner_map: str | None = None) -> None:
    (root / "MAP.md").write_text(map_text(ROOT_FRONT), encoding="utf-8")
    inner = root / "inner"
    inner.mkdir()
    inner.joinpath("MAP.md").write_text(
        inner_map if inner_map is not None else map_text(inner_front, routes, references),
        encoding="utf-8",
    )
    for index in range(1, documents + 1):
        (inner / f"doc{index}.md").write_text(
            f"---\nbkf: document\ndescription: Document {index}.\ntags: [test]\n---\n# Doc\n", encoding="utf-8"
        )
    for index in range(references):
        (inner / f"tool{index}.py").write_text("print('tool')\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(INVENTORY), "--write", str(root)],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def validate(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        check=False, capture_output=True, text=True,
    )
    return result.stdout


class MapSizeTests(unittest.TestCase):
    def test_small_map_warns_with_its_size_and_the_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=2)

            output = validate(root)

            self.assertIn(WARNING.format(size=2), output)
            self.assertIn(
                "Folders without a distinct navigation purpose use their nearest ancestor map.",
                output,
            )

    def test_map_at_the_limit_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=4)

            self.assertIn(WARNING.format(size=4), validate(root))

    def test_map_with_five_items_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=5)

            self.assertNotIn("MAP_TOO_SMALL", validate(root))

    def test_artifact_references_count_toward_the_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=2, references=2)

            self.assertIn(WARNING.format(size=4), validate(root))

    def test_artifact_references_can_lift_a_map_above_the_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=2, references=3)

            self.assertNotIn("MAP_TOO_SMALL", validate(root))

    def test_task_route_rows_count_toward_the_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=1, routes=3)

            self.assertIn(WARNING.format(size=4), validate(root))

    def test_child_maps_count_toward_the_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=1)
            deep = root / "inner" / "deep"
            deep.mkdir()
            (deep / "MAP.md").write_text(map_text(CHILD_FRONT), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(INVENTORY), "--write", str(root)],
                check=True, capture_output=True, text=True,
            )

            output = validate(root)

            self.assertIn(WARNING.format(size=2), output)

    def test_root_map_does_not_warn_however_small(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, documents=5)
            (root / "outer.md").write_text(
                "---\nbkf: document\ndescription: Outer document.\ntags: [test]\n---\n# Outer\n", encoding="utf-8"
            )
            subprocess.run(
                [sys.executable, str(INVENTORY), "--write", str(root)],
                check=True, capture_output=True, text=True,
            )

            self.assertNotIn("MAP_TOO_SMALL MAP.md", validate(root))

    def test_nested_bundle_root_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root, inner_front=NESTED_FRONT, documents=1)

            self.assertNotIn("MAP_TOO_SMALL", validate(root))


if __name__ == "__main__":
    unittest.main()

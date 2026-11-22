from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLING / "validate_bundle.py"
INVENTORY = TOOLING / "generate_inventory.py"
sys.path.insert(0, str(TOOLING))

import bkf_upgrade  # noqa: E402

MAP_TEXT = (
    "{front}# Bundle\n\n"
    "## Member inventory\n\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
ROOT_FRONT = '---\ndescription: Outer bundle.\nbkf_version: "0.1"\n---\n\n'
CHILD_FRONT = '---\ndescription: Inner bundle holds its own guides and agent instructions.\nbkf_version: "0.1"\n---\n\n'


def document(description: str, body: str = "# Doc\n") -> str:
    return f"---\nbkf: document\ndescription: {description}\ntags: [test]\n---\n{body}"


def run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *map(str, args)], check=False, capture_output=True, text=True)


def main_upgrade(cwd: Path, *args: str) -> tuple[int, str, str]:
    import contextlib
    import io
    import os

    out, err = io.StringIO(), io.StringIO()
    previous = os.getcwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = bkf_upgrade.main(list(args))
    finally:
        os.chdir(previous)
    return status, out.getvalue(), err.getvalue()


def write_map(path: Path, front: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MAP_TEXT.format(front=front), encoding="utf-8")


def build(root: Path) -> None:
    """Outer bundle at root and a nested 0.1 bundle at root/bkf, cross-linking with own-root links."""
    nested = root / "bkf"
    write_map(root / "MAP.md", ROOT_FRONT)
    write_map(nested / "MAP.md", CHILD_FRONT)
    (root / "outer.md").write_text(
        document("Outer document.", "See [nested](/bkf/guide.md) and [outer](/outer.md).\n"),
        encoding="utf-8",
    )
    (nested / "guide.md").write_text(
        document(
            "Nested guide.",
            "Read [manual](/manual/x.md#top) and [self](/guide.md \"T\"), not [external](https://e.org).\n\n"
            "```\n[code](/manual/x.md)\n```\n",
        ),
        encoding="utf-8",
    )
    (nested / "manual").mkdir()
    (nested / "manual" / "x.md").write_text(document("Manual page.", "# Manual\n"), encoding="utf-8")
    (nested / "AGENTS.md").write_text(document("Nested agent entry.", "See [guide](/guide.md).\n"), encoding="utf-8")
    result = run(INVENTORY, "--write", root)
    assert result.returncode == 0, result.stderr


def version_of(map_path: Path) -> str:
    for line in map_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("bkf_version:"):
            return line
    raise AssertionError("no bkf_version line")


class UpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        build(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_nested_links_get_prefix_and_both_bundles_become_current(self) -> None:
        status, out, err = main_upgrade(self.root, str(self.root))
        self.assertEqual(status, 0, err)
        self.assertIn("upgraded: ", out)
        self.assertEqual(version_of(self.root / "MAP.md"), 'bkf_version: "0.2"')
        self.assertEqual(version_of(self.root / "bkf" / "MAP.md"), 'bkf_version: "0.2"')
        guide = (self.root / "bkf" / "guide.md").read_text(encoding="utf-8")
        self.assertIn("[manual](/bkf/manual/x.md#top)", guide)
        self.assertIn('[self](/bkf/guide.md "T")', guide)
        self.assertIn("[external](https://e.org)", guide)
        self.assertIn("[code](/manual/x.md)", guide)
        agents = (self.root / "bkf" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("[guide](/bkf/guide.md)", agents)
        outer = (self.root / "outer.md").read_text(encoding="utf-8")
        self.assertIn("[nested](/bkf/guide.md)", outer)

    def test_upgraded_bundle_validates_without_link_or_inventory_errors(self) -> None:
        main_upgrade(self.root, str(self.root))
        result = run(VALIDATOR, self.root)
        output = result.stdout + result.stderr
        self.assertNotIn("LINK_TARGET_MISSING", output)
        self.assertNotIn("MAP_INVENTORY_STALE", output)
        self.assertEqual(run(INVENTORY, "--check", self.root).returncode, 0)

    def test_second_run_changes_nothing(self) -> None:
        main_upgrade(self.root, str(self.root))
        before = (self.root / "bkf" / "guide.md").read_bytes()
        status, out, _ = main_upgrade(self.root, str(self.root))
        self.assertEqual(status, 0)
        self.assertEqual(out.strip(), "already current")
        self.assertEqual((self.root / "bkf" / "guide.md").read_bytes(), before)

    def test_check_changes_nothing_and_exits_one_then_zero(self) -> None:
        before = (self.root / "bkf" / "guide.md").read_bytes()
        status, out, _ = main_upgrade(self.root, "--check", str(self.root))
        self.assertEqual(status, 1)
        self.assertIn("would upgrade:", out)
        self.assertIn("would update:", out)
        self.assertEqual((self.root / "bkf" / "guide.md").read_bytes(), before)
        self.assertEqual(version_of(self.root / "MAP.md"), 'bkf_version: "0.1"')
        main_upgrade(self.root, str(self.root))
        status, _, _ = main_upgrade(self.root, "--check", str(self.root))
        self.assertEqual(status, 0)

    def test_nested_bundle_already_current_is_untouched(self) -> None:
        write_map(self.root / "bkf" / "MAP.md", CHILD_FRONT.replace('"0.1"', '"0.2"'))
        before = (self.root / "bkf" / "guide.md").read_bytes()
        main_upgrade(self.root, str(self.root))
        self.assertEqual((self.root / "bkf" / "guide.md").read_bytes(), before)

    def test_plain_outer_links_outside_nested_bundle_stay_plain(self) -> None:
        (self.root / "bkf" / "guide.md").write_text(
            document("Nested guide.", "Relative [up](../outer.md) and [plain](manual/x.md).\n"),
            encoding="utf-8",
        )
        main_upgrade(self.root, str(self.root))
        text = (self.root / "bkf" / "guide.md").read_text(encoding="utf-8")
        self.assertIn("[up](../outer.md)", text)
        self.assertIn("[plain](manual/x.md)", text)

    def test_map_version_line_keeps_other_bytes(self) -> None:
        map_path = self.root / "bkf" / "MAP.md"
        original = map_path.read_text(encoding="utf-8")
        main_upgrade(self.root, str(self.root))
        self.assertEqual(
            map_path.read_text(encoding="utf-8"),
            original.replace('bkf_version: "0.1"', 'bkf_version: "0.2"'),
        )

    def test_invalid_path_exits_two(self) -> None:
        status, _, err = main_upgrade(self.root, str(self.root / "missing"))
        self.assertEqual(status, 2)
        self.assertIn("not a directory", err)

    def test_invalid_version_exits_two_and_changes_nothing(self) -> None:
        write_map(self.root / "bkf" / "MAP.md", CHILD_FRONT.replace('"0.1"', '"zero"'))
        before = (self.root / "MAP.md").read_bytes()
        status, _, err = main_upgrade(self.root, str(self.root))
        self.assertEqual(status, 2)
        self.assertIn("bkf_version", err)
        self.assertEqual((self.root / "MAP.md").read_bytes(), before)

    def test_bundle_without_nested_bundles_only_bumps_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp).resolve()
            write_map(plain / "MAP.md", ROOT_FRONT)
            (plain / "doc.md").write_text(document("Doc.", "[x](/doc.md)\n"), encoding="utf-8")
            before = (plain / "doc.md").read_bytes()
            status, _, err = main_upgrade(plain, str(plain))
            self.assertEqual(status, 0, err)
            self.assertEqual((plain / "doc.md").read_bytes(), before)
            self.assertEqual(version_of(plain / "MAP.md"), 'bkf_version: "0.2"')

    def test_two_nesting_levels_get_full_prefixes(self) -> None:
        deep = self.root / "bkf" / "a" / "b"
        write_map(deep / "MAP.md", CHILD_FRONT)
        (deep / "leaf.md").write_text(document("Leaf.", "[up](/leaf.md) [m](/x.md)\n"), encoding="utf-8")
        (deep / "x.md").write_text(document("X.", "# X\n"), encoding="utf-8")
        main_upgrade(self.root, str(self.root))
        leaf = (deep / "leaf.md").read_text(encoding="utf-8")
        self.assertIn("[up](/bkf/a/b/leaf.md) [m](/bkf/a/b/x.md)", leaf)
        middle = (self.root / "bkf" / "guide.md").read_text(encoding="utf-8")
        self.assertIn("[manual](/bkf/manual/x.md#top)", middle)
        self.assertEqual(version_of(deep / "MAP.md"), 'bkf_version: "0.2"')

    def test_second_pass_does_not_double_prefix(self) -> None:
        main_upgrade(self.root, str(self.root))
        main_upgrade(self.root, str(self.root))
        self.assertNotIn("/bkf/bkf/", (self.root / "bkf" / "guide.md").read_text(encoding="utf-8"))

    def test_command_is_registered_in_install_group(self) -> None:
        import bkf_cli

        self.assertEqual(bkf_cli.COMMANDS["upgrade"][0], "bkf_upgrade")
        self.assertEqual(bkf_cli.COMMANDS["upgrade"][3], "install")


if __name__ == "__main__":
    unittest.main()

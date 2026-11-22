import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bkf_mv import main
from generate_inventory import main as _inventory
from validate_bundle import Validator

ROOT_MAP = (
    '---\nbkf_version: "0.1"\n---\n\n# Bundle\n\n## Member inventory\n\n'
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
INNER_MAP = (
    '---\ndescription: Inner bundle.\nbkf_version: "0.1"\n---\n\n# Inner\n\n## Member inventory\n\n'
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)


def inventory(args: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return _inventory(args)


def document(description: str, body: str) -> str:
    return f"---\nbkf: document\ndescription: {description}\n---\n{body}"


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    )


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def snapshot(root: Path) -> dict[str, object]:
    """Return the working tree content and git status, so a refused move can be shown to change nothing."""
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file() and ".git" not in path.relative_to(root).parts
    }
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout
    return {"files": files, "status": status}


def run(cwd: Path, *args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    previous = Path.cwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
    finally:
        os.chdir(previous)
    return code, out.getvalue(), err.getvalue()


class MvTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name).resolve()
        git(self.root, "init", "-q")
        write(self.root, "MAP.md", ROOT_MAP)
        write(self.root, "guide.md", document("Guide.", "# Guide\n\nSee [a](/notes/a.md#sec) and [c](/notes/sub/c.md).\n"))
        write(self.root, "notes/a.md", document("A.", "# A\n\n[back](/guide.md)\n"))
        write(self.root, "notes/sub/c.md", document("C.", "# C\n\n[a](/notes/a.md)\n"))
        write(self.root, "notes/sub/d.md", document("D.", "# D\n"))
        write(self.root, "page.html", '<a href="notes/a.html">a</a>\n')
        write(self.root, "notes/a.html", '<a href="../guide.md">g</a>\n')
        write(self.root, "inner/MAP.md", INNER_MAP)
        write(self.root, "inner/g.md", document("G.", "[x](/notes/a.md)\n"))
        write(self.root, "inner/notes/a.md", document("Inner A.", "# Inner A\n"))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "fixture")
        self.nested_before = (self.root / "inner/g.md").read_bytes()

    def tearDown(self) -> None:
        self._dir.cleanup()

    def assert_refused(self, *args: str, cwd: Path | None = None) -> None:
        before = snapshot(self.root)
        code, out, err = run(cwd or self.root, *args)
        self.assertEqual(code, 1, out)
        self.assertTrue(err.startswith("error: "), err)
        self.assertEqual(snapshot(self.root), before)

    def test_moved_file_fixes_incoming_markdown_links_and_inventory(self) -> None:
        code, out, err = run(self.root, "notes/a.md", "archive/a.md")

        self.assertEqual(code, 0, err)
        self.assertIn("moved: notes/a.md -> archive/a.md", out.splitlines())
        self.assertIn("updated: guide.md", out.splitlines())
        self.assertIn("[a](/archive/a.md#sec)", (self.root / "guide.md").read_text(encoding="utf-8"))
        self.assertIn("[a](/archive/a.md)", (self.root / "notes/sub/c.md").read_text(encoding="utf-8"))
        self.assertIn("[a.md](/archive/a.md)", (self.root / "MAP.md").read_text(encoding="utf-8"))
        self.assertNotIn("/notes/a.md", (self.root / "MAP.md").read_text(encoding="utf-8"))
        ls = subprocess.run(["git", "-C", str(self.root), "ls-files"], capture_output=True, text=True).stdout
        self.assertIn("archive/a.md", ls.splitlines())

    def test_moved_file_recomputes_its_own_html_links_and_fixes_incoming(self) -> None:
        code, out, err = run(self.root, "notes/a.html", "deep/x/a.html")

        self.assertEqual(code, 0, err)
        self.assertEqual((self.root / "deep/x/a.html").read_text(encoding="utf-8"), '<a href="../../guide.md">g</a>\n')
        self.assertEqual((self.root / "page.html").read_text(encoding="utf-8"), '<a href="deep/x/a.html">a</a>\n')

    def test_directory_move_fixes_links_to_files_below_it(self) -> None:
        code, out, err = run(self.root, "notes/sub", "archive")

        self.assertEqual(code, 0, err)
        self.assertIn("moved: notes/sub/c.md -> archive/c.md", out.splitlines())
        self.assertIn("moved: notes/sub/d.md -> archive/d.md", out.splitlines())
        self.assertIn("[c](/archive/c.md)", (self.root / "guide.md").read_text(encoding="utf-8"))

    def test_nested_bundle_is_not_touched(self) -> None:
        code, out, err = run(self.root, "notes/a.md", "archive/a.md")

        self.assertEqual(code, 0, err)
        self.assertNotIn("inner/g.md", out)
        self.assertEqual((self.root / "inner/g.md").read_bytes(), self.nested_before)

    def link_errors(self) -> list[str]:
        validator = Validator(self.root)
        validator.validate()
        return [finding.path for finding in validator.findings if finding.code == "LINK_TARGET_MISSING"]

    def nested_move_fixture(self) -> None:
        write(self.root, "peek.md", document("Peek.", "[i](/inner/notes/a.md)\n"))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "peek")

    def test_nested_move_from_outer_root_fixes_both_links(self) -> None:
        self.nested_move_fixture()

        code, out, err = run(self.root, "inner/notes/a.md", "inner/notes/b.md")

        self.assertEqual(code, 0, err)
        self.assertIn("moved: inner/notes/a.md -> inner/notes/b.md", out.splitlines())
        self.assertIn("[x](/notes/b.md)", (self.root / "inner/g.md").read_text(encoding="utf-8"))
        self.assertIn("[i](/inner/notes/b.md)", (self.root / "peek.md").read_text(encoding="utf-8"))
        self.assertEqual(self.link_errors(), [])

    def test_nested_move_leaves_every_inventory_fresh(self) -> None:
        self.assertEqual(inventory([str(self.root), "--write"]), 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "fresh inventories")

        code, out, err = run(self.root, "inner/notes/a.md", "inner/notes/zzz.md")

        self.assertEqual(code, 0, err)
        self.assertEqual(inventory([str(self.root), "--check"]), 0)
        validator = Validator(self.root)
        validator.validate()
        self.assertNotIn("MAP_INVENTORY_STALE", [finding.code for finding in validator.findings])

    def test_nested_move_from_inside_nested_folder_fixes_both_links(self) -> None:
        self.nested_move_fixture()

        code, out, err = run(self.root / "inner", "notes/a.md", "notes/b.md")

        self.assertEqual(code, 0, err)
        self.assertIn("[x](/notes/b.md)", (self.root / "inner/g.md").read_text(encoding="utf-8"))
        self.assertIn("[i](/inner/notes/b.md)", (self.root / "peek.md").read_text(encoding="utf-8"))
        self.assertEqual(self.link_errors(), [])

    def test_untracked_source_is_refused(self) -> None:
        write(self.root, "loose.md", document("Loose.", "# Loose\n"))

        self.assert_refused("loose.md", "archive/loose.md")

    def test_existing_target_is_refused(self) -> None:
        self.assert_refused("notes/a.md", "guide.md")

    def test_target_outside_root_is_refused(self) -> None:
        write(self.root, "notes/MAP.md", ROOT_MAP)
        self.assert_refused("--root", str(self.root / "notes"), "a.md", "../outside.md", cwd=self.root / "notes")

    def test_source_outside_root_is_refused(self) -> None:
        write(self.root, "notes/MAP.md", ROOT_MAP)
        self.assert_refused("--root", str(self.root / "notes"), "../guide.md", "archive.md", cwd=self.root / "notes")

    def test_move_out_of_nested_bundle_is_refused(self) -> None:
        self.assert_refused("inner/g.md", "notes/g.md")

    def test_move_into_nested_bundle_is_refused(self) -> None:
        self.assert_refused("notes/a.md", "inner/a.md")

    def test_map_file_is_refused(self) -> None:
        self.assert_refused("MAP.md", "archive/MAP.md")

    def test_target_inside_source_is_refused(self) -> None:
        self.assert_refused("notes", "notes/sub/inner")

    def test_check_changes_nothing_and_lists_the_work(self) -> None:
        before = snapshot(self.root)

        code, out, err = run(self.root, "--check", "notes/a.md", "archive/a.md")

        self.assertEqual(code, 0, err)
        self.assertIn("would move: notes/a.md -> archive/a.md", out.splitlines())
        self.assertIn("would update: guide.md", out.splitlines())
        self.assertEqual(snapshot(self.root), before)

    def test_runs_from_subdirectory_with_relative_arguments(self) -> None:
        code, out, err = run(self.root / "notes", "--root", str(self.root), "sub/d.md", "../archive/d.md")

        self.assertEqual(code, 0, err)
        self.assertIn("moved: notes/sub/d.md -> archive/d.md", out.splitlines())
        self.assertTrue((self.root / "archive/d.md").is_file())

    def test_root_is_found_from_subdirectory_without_flag(self) -> None:
        code, out, err = run(self.root / "notes" / "sub", "d.md", "../../archive/d.md")

        self.assertEqual(code, 0, err)
        self.assertIn("moved: notes/sub/d.md -> archive/d.md", out.splitlines())


if __name__ == "__main__":
    unittest.main()

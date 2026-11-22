import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bkf_relink import main
from generate_inventory import main as _inventory
from validate_bundle import Validator

ROOT_MAP = (
    '---\nbkf_version: "0.2"\n---\n\n# Bundle\n\n## Member inventory\n\n'
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
INNER_MAP = (
    '---\ndescription: Inner bundle.\nbkf_version: "0.2"\n---\n\n# Inner\n\n## Member inventory\n\n'
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->\n"
    "<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->\n"
)
LONG_A = "# A\n\n" + "".join(f"Paragraph {n} keeps this note long enough to stay similar.\n\n" for n in range(12))


def inventory(args: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return _inventory(args)


def document(description: str, body: str) -> str:
    return f"---\nbkf: document\ndescription: {description}\n---\n{body}"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def move(root: Path, old: str, new: str) -> None:
    (root / new).parent.mkdir(parents=True, exist_ok=True)
    os.rename(root / old, root / new)


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


class RelinkTests(unittest.TestCase):
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
        self.commit("fixture")

    def tearDown(self) -> None:
        self._dir.cleanup()

    def commit(self, message: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", message)

    def index_bytes(self) -> bytes:
        return (self.root / ".git" / "index").read_bytes()

    def staged(self) -> str:
        return git(self.root, "diff", "--cached", "--name-status")

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def test_moved_file_links_fixed_and_real_index_untouched(self) -> None:
        move(self.root, "notes/a.md", "archive/a.md")
        index_before, staged_before = self.index_bytes(), self.staged()

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertIn("relinked: notes/a.md -> archive/a.md", lines)
        self.assertIn("updated: guide.md", lines)
        self.assertIn("[a](/archive/a.md#sec)", self.read("guide.md"))
        self.assertIn("[a](/archive/a.md)", self.read("notes/sub/c.md"))
        self.assertEqual(self.index_bytes(), index_before)
        self.assertEqual(self.staged(), staged_before)
        self.assertIn("notes/a.md", git(self.root, "ls-files").splitlines())

    def test_moved_directory_fixes_links_to_files_below_it(self) -> None:
        move(self.root, "notes/sub", "archive")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("relinked: notes/sub/c.md -> archive/c.md", out.splitlines())
        self.assertIn("relinked: notes/sub/d.md -> archive/d.md", out.splitlines())
        self.assertIn("[c](/archive/c.md)", self.read("guide.md"))

    def test_moved_and_slightly_edited_file_is_found(self) -> None:
        write(self.root, "notes/a.md", document("A.", LONG_A + "[back](/guide.md)\n"))
        self.commit("long a")
        write(self.root, "notes/a.md", document("A.", LONG_A + "[back](/guide.md)\nOne new line.\n"))
        move(self.root, "notes/a.md", "archive/a.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("relinked: notes/a.md -> archive/a.md", out.splitlines())
        self.assertIn("[a](/archive/a.md#sec)", self.read("guide.md"))

    def test_moved_html_artifact_recomputes_its_relative_links(self) -> None:
        move(self.root, "notes/a.html", "deep/x/a.html")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertEqual(self.read("deep/x/a.html"), '<a href="../../guide.md">g</a>\n')
        self.assertEqual(self.read("page.html"), '<a href="deep/x/a.html">a</a>\n')

    def test_same_basename_in_two_places_is_reported_and_no_link_changes(self) -> None:
        os.remove(self.root / "notes/a.md")
        write(self.root, "x/a.md", document("X.", "# Unrelated X\n"))
        write(self.root, "y/a.md", document("Y.", "# Unrelated Y\n"))
        guide_before = self.read("guide.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 1, err)
        lines = out.splitlines()
        self.assertIn("unresolved: notes/a.md", lines)
        self.assertIn("  candidates: x/a.md, y/a.md", lines)
        self.assertEqual(self.read("guide.md"), guide_before)

    def test_moved_and_heavily_rewritten_file_is_unresolved(self) -> None:
        os.remove(self.root / "notes/a.md")
        write(self.root, "archive/a.md", document("New.", "completely different words here\n"))
        guide_before = self.read("guide.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 1, err)
        lines = out.splitlines()
        self.assertIn("unresolved: notes/a.md", lines)
        self.assertIn("  candidates: archive/a.md", lines)
        self.assertEqual(self.read("guide.md"), guide_before)

    def test_map_resolves_an_ambiguous_case(self) -> None:
        os.remove(self.root / "notes/a.md")
        write(self.root, "x/a.md", document("X.", "# Unrelated X\n"))

        code, out, err = run(self.root, "--map", "notes/a.md=x/a.md")

        self.assertEqual(code, 0, err)
        self.assertIn("relinked: notes/a.md -> x/a.md", out.splitlines())
        self.assertIn("[a](/x/a.md#sec)", self.read("guide.md"))

    def test_map_rejects_an_old_path_that_still_exists(self) -> None:
        write(self.root, "x/a.md", document("X.", "# X\n"))

        code, out, err = run(self.root, "--map", "notes/a.md=x/a.md")

        self.assertEqual(code, 2)
        self.assertIn("still exists", err)

    def test_since_finds_a_move_that_was_already_committed(self) -> None:
        move(self.root, "notes/a.md", "archive/a.md")
        self.commit("move a")

        code, out, err = run(self.root, "--since", "HEAD~1")

        self.assertEqual(code, 0, err)
        self.assertIn("relinked: notes/a.md -> archive/a.md", out.splitlines())
        self.assertIn("[a](/archive/a.md#sec)", self.read("guide.md"))

    def test_check_changes_nothing(self) -> None:
        move(self.root, "notes/a.md", "archive/a.md")
        guide_before, map_before = self.read("guide.md"), self.read("MAP.md")
        index_before = self.index_bytes()

        code, out, err = run(self.root, "--check")

        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertIn("would relink: notes/a.md -> archive/a.md", lines)
        self.assertIn("would update: guide.md", lines)
        self.assertEqual(self.read("guide.md"), guide_before)
        self.assertEqual(self.read("MAP.md"), map_before)
        self.assertEqual(self.index_bytes(), index_before)

    def test_nothing_to_do_exits_zero(self) -> None:
        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines(), ["nothing to relink"])

    def test_outside_a_git_repository_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as plain:
            root = Path(plain).resolve()
            write(root, "MAP.md", ROOT_MAP)

            code, out, err = run(root)

        self.assertEqual(code, 2)
        self.assertIn("not inside a git repository", err)

    def findings(self):
        validator = Validator(self.root)
        validator.validate()
        return validator.findings

    def link_errors(self) -> list[str]:
        return [finding.path for finding in self.findings() if finding.code == "LINK_TARGET_MISSING"]

    def test_nested_bundle_move_is_relinked_from_the_root(self) -> None:
        move(self.root, "inner/g.md", "inner/h.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("relinked: inner/g.md -> inner/h.md", out.splitlines())
        self.assertEqual(self.read("inner/h.md"), document("G.", "[x](/notes/a.md)\n"))

    def nested_fixture(self) -> None:
        write(self.root, "inner/dir/doc.md", document("Doc.", "# Doc\n"))
        write(self.root, "inner/g.md", document("G.", "[d](/inner/dir/doc.md)\n"))
        write(self.root, "guide.md", document("Guide.", "# Guide\n\n[d](/inner/dir/doc.md)\n"))
        self.commit("nested links")
        move(self.root, "inner/dir/doc.md", "inner/dir/new.md")

    def test_nested_move_fixes_nested_and_outer_links(self) -> None:
        self.nested_fixture()

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("[d](/inner/dir/new.md)", self.read("inner/g.md"))
        self.assertIn("[d](/inner/dir/new.md)", self.read("guide.md"))
        self.assertEqual(self.link_errors(), [])

    def test_run_from_inside_nested_bundle_uses_the_outermost_root(self) -> None:
        self.nested_fixture()

        code, out, err = run(self.root / "inner")

        self.assertEqual(code, 0, err)
        self.assertIn("[d](/inner/dir/new.md)", self.read("inner/g.md"))
        self.assertIn("[d](/inner/dir/new.md)", self.read("guide.md"))
        self.assertEqual(self.link_errors(), [])

    def test_explicit_root_is_the_same_coordinate_base(self) -> None:
        self.nested_fixture()

        code, out, err = run(self.root / "inner", "--root", str(self.root))

        self.assertEqual(code, 0, err)
        self.assertIn("[d](/inner/dir/new.md)", self.read("inner/g.md"))
        self.assertEqual(self.link_errors(), [])

    def test_move_across_a_bundle_boundary_is_relinked(self) -> None:
        move(self.root, "inner/g.md", "g.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("relinked: inner/g.md -> g.md", out.splitlines())
        self.assertNotIn("skipped", out)
        self.assertEqual(self.link_errors(), [])

    def test_file_moved_by_hand_into_nested_bundle_is_relinked(self) -> None:
        move(self.root, "notes/a.md", "inner/a.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("[a](/inner/a.md#sec)", self.read("guide.md"))
        self.assertIn("[x](/inner/a.md)", self.read("inner/g.md"))
        self.assertEqual(self.link_errors(), [])

    def test_whole_nested_bundle_folder_moved_by_hand_keeps_both_bundles_conformant(self) -> None:
        write(self.root, "peek.md", document("Peek.", "[g](/inner/g.md)\n"))
        self.commit("peek")
        move(self.root, "inner", "moved")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("[g](/moved/g.md)", self.read("peek.md"))
        self.assertEqual(self.link_errors(), [])
        for bundle in (self.root, self.root / "moved"):
            validator = Validator(bundle)
            validator.validate()
            self.assertEqual(
                [f.code for f in validator.findings if f.code in ("LINK_TARGET_MISSING", "MAP_INVENTORY_STALE")], [],
            )

    def test_linked_worktree_inside_the_root_is_never_rewritten(self) -> None:
        write(self.root, ".claude/worktrees/w/.git", "gitdir: elsewhere\n")
        write(self.root, ".claude/worktrees/w/guide.md", document("Copy.", "[a](/notes/a.md)\n"))
        move(self.root, "notes/a.md", "archive/a.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertIn("[a](/archive/a.md#sec)", self.read("guide.md"))
        self.assertEqual(self.read(".claude/worktrees/w/guide.md"), document("Copy.", "[a](/notes/a.md)\n"))

    def test_nested_move_leaves_every_inventory_fresh(self) -> None:
        write(self.root, "inner/dir/zed.md", document("Zed.", "# Zed\n"))
        write(self.root, "inner/g.md", document("G.", "[d](/inner/dir/zed.md)\n"))
        self.assertEqual(inventory([str(self.root), "--write"]), 0)
        self.commit("fresh inventories")
        move(self.root, "inner/dir/zed.md", "inner/dir/alpha.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertEqual(inventory([str(self.root), "--check"]), 0)
        self.assertNotIn("MAP_INVENTORY_STALE", [finding.code for finding in self.findings()])

    def test_move_across_boundary_relinks_only_links_to_the_moved_file(self) -> None:
        write(self.root, "inner/b.md", document("B.", "# B\n"))
        write(self.root, "inner/c.md", document("C.", "[b](/inner/b.md)\n[x](/inner/x.md)\n"))
        write(self.root, "inner/x.md", document("X.", "[b](/inner/b.md)\n[c](/inner/c.md)\n"))
        self.commit("linked nested documents")
        move(self.root, "inner/x.md", "y.md")

        code, out, err = run(self.root)

        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines(), ["relinked: inner/x.md -> y.md", "updated: inner/c.md"])
        self.assertIn("[x](/y.md)", self.read("inner/c.md"))

    def test_unresolved_link_in_nested_bundle_is_reported_in_top_coordinates(self) -> None:
        write(self.root, "inner/g.md", document("G.", "[gone](/gone.md)\n"))
        self.commit("broken")

        code, out, err = run(self.root)

        self.assertEqual(code, 1, err)
        self.assertIn("unresolved: gone.md", out.splitlines())

if __name__ == "__main__":
    unittest.main()

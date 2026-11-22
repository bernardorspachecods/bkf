import os
import tempfile
import unittest
from pathlib import Path

from relink import apply_chain, apply_moves

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


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def move(root: Path, old: str, new: str) -> None:
    (root / new).parent.mkdir(parents=True, exist_ok=True)
    os.rename(root / old, root / new)


class ApplyMovesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        write(self.root, "MAP.md", ROOT_MAP)
        write(self.root, "guide.md", "# Guide\n\nSee [a](/notes/a.md#sec) and [c](/notes/sub/c.md \"t\").\r\n")
        write(self.root, "notes/a.md", "# A\n")
        write(self.root, "notes/sub/c.md", "# C\n\n[back](/notes/a.md)\n")
        write(self.root, "notes/sub/d.md", "# D\n")
        write(self.root, "page.html", '<a href="notes/a.html">a</a>\n')
        write(self.root, "notes/a.html", '<a href="../guide.md">g</a><img src="sub/c.png">\n')
        write(self.root, "inner/MAP.md", INNER_MAP)
        write(self.root, "inner/g.md", "[x](/notes/a.md)\n")

    def tearDown(self) -> None:
        self._dir.cleanup()

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8", newline="")

    def test_moved_file_incoming_markdown_links_fixed_with_fragment(self) -> None:
        move(self.root, "notes/a.md", "archive/a.md")

        changed = apply_moves(self.root, {"notes/a.md": "archive/a.md"}, True)

        self.assertEqual(changed, ["guide.md", "notes/sub/c.md"])
        self.assertEqual(self.read("guide.md"), '# Guide\n\nSee [a](/archive/a.md#sec) and [c](/notes/sub/c.md "t").\r\n')
        self.assertIn("[back](/archive/a.md)", self.read("notes/sub/c.md"))

    def test_directory_move_fixes_links_to_files_below_it(self) -> None:
        moves = {}
        for rel in ("notes/a.md", "notes/sub/c.md", "notes/sub/d.md"):
            moves[rel] = "archive/" + rel[len("notes/"):]
        for old, new in moves.items():
            move(self.root, old, new)
        os.rmdir(self.root / "notes/sub")

        changed = apply_moves(self.root, moves, True)

        self.assertIn("guide.md", changed)
        self.assertIn("[c](/archive/sub/c.md", self.read("guide.md"))
        self.assertIn("[a](/archive/a.md#sec)", self.read("guide.md"))

    def test_html_relative_links_to_and_from_moved_file(self) -> None:
        moves = {"notes/a.html": "deep/x/a.html"}
        move(self.root, "notes/a.html", "deep/x/a.html")

        changed = apply_moves(self.root, moves, True)

        self.assertEqual(changed, ["deep/x/a.html", "page.html"])
        self.assertEqual(self.read("page.html"), '<a href="deep/x/a.html">a</a>\n')
        self.assertEqual(self.read("deep/x/a.html"), '<a href="../../guide.md">g</a><img src="../../notes/sub/c.png">\n')

    def test_nested_bundle_files_are_not_touched(self) -> None:
        move(self.root, "notes/a.md", "archive/a.md")

        changed = apply_moves(self.root, {"notes/a.md": "archive/a.md"}, True)

        self.assertNotIn("inner/g.md", changed)
        self.assertEqual(self.read("inner/g.md"), "[x](/notes/a.md)\n")

    def test_apply_chain_fixes_links_in_the_nested_bundle_in_its_own_coordinates(self) -> None:
        write(self.root, "inner/x.md", "# X\n")
        write(self.root, "inner/g.md", "[x](/x.md)\n")
        move(self.root, "inner/x.md", "inner/y.md")

        changed = apply_chain(self.root, {"inner/x.md": "inner/y.md"}, True)

        self.assertEqual(changed, ["inner/g.md"])
        self.assertEqual(self.read("inner/g.md"), "[x](/y.md)\n")

    def test_apply_chain_does_not_apply_a_move_across_a_boundary(self) -> None:
        move(self.root, "notes/a.md", "inner/a.md")
        before = self.read("guide.md")

        changed = apply_chain(self.root, {"notes/a.md": "inner/a.md"}, True)

        self.assertEqual(changed, [])
        self.assertEqual(self.read("guide.md"), before)

    def test_write_false_reports_without_writing(self) -> None:
        move(self.root, "notes/a.md", "archive/a.md")
        before = self.read("guide.md")

        changed = apply_moves(self.root, {"notes/a.md": "archive/a.md"}, False)

        self.assertEqual(changed, ["guide.md", "notes/sub/c.md"])
        self.assertEqual(self.read("guide.md"), before)

    def test_unrelated_files_are_not_listed(self) -> None:
        move(self.root, "notes/sub/d.md", "archive/d.md")

        changed = apply_moves(self.root, {"notes/sub/d.md": "archive/d.md"}, True)

        self.assertEqual(changed, [])



class OutermostBundleRootStopsAtGitTests(unittest.TestCase):
    def test_worktree_inside_another_checkout_does_not_climb_into_it(self) -> None:
        import tempfile
        from pathlib import Path

        import relink

        map_text = '---\nbkf_version: "0.1"\n---\n\n# M\n'
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp).resolve()
            (main / ".git").mkdir()
            (main / "MAP.md").write_text(map_text, encoding="utf-8")
            worktree = main / ".claude" / "worktrees" / "w"
            worktree.mkdir(parents=True)
            (worktree / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
            (worktree / "MAP.md").write_text(map_text, encoding="utf-8")
            nested = worktree / "inner"
            nested.mkdir()
            (nested / "MAP.md").write_text(map_text, encoding="utf-8")

            self.assertEqual(relink.find_outermost_bundle_root(worktree), worktree)
            self.assertEqual(relink.find_outermost_bundle_root(nested), worktree)
            self.assertEqual(relink.find_outermost_bundle_root(main), main)


if __name__ == "__main__":
    unittest.main()

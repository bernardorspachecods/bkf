import unittest

from relink import rewrite_html

MOVES = {"tooling/commands.md": "tools/commands.md"}


class RewriteHtmlTests(unittest.TestCase):
    def test_target_moved_source_fixed(self):
        text = '<a href="../tooling/commands.md">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "docs/p.html", MOVES),
            '<a href="../tools/commands.md">x</a>',
        )

    def test_source_moved_outgoing_links_recomputed(self):
        text = '<a href="../tooling/c.md">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "site/q/p.html", {}),
            '<a href="../../tooling/c.md">x</a>',
        )

    def test_both_moved(self):
        moves = {"docs/c.md": "site/c.md", "docs/p.html": "site/p.html"}
        text = '<a href="c.md">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "site/p.html", moves),
            '<a href="c.md">x</a>',
        )

    def test_both_moved_into_other_directory(self):
        moves = {"docs/c.md": "other/c.md"}
        text = '<img src="img/a.png"><a href="c.md">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "site/p.html", moves),
            '<img src="../docs/img/a.png"><a href="../other/c.md">x</a>',
        )

    def test_fragment_and_query_are_kept(self):
        text = '<a href="../tooling/commands.md?v=2&amp;x=1#sec-3">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "docs/p.html", MOVES),
            '<a href="../tools/commands.md?v=2&amp;x=1#sec-3">x</a>',
        )

    def test_external_anchor_absolute_and_empty_values_are_left_alone(self):
        text = (
            '<a href="https://example.com/tooling/commands.md">a</a>'
            '<a href="mailto:tooling/commands.md">b</a>'
            '<a href="data:text/plain,x">c</a>'
            '<a href="javascript:void(0)">d</a>'
            '<a href="#tooling/commands.md">e</a>'
            '<a href="/tooling/commands.md">f</a>'
            '<a href="//host/tooling/commands.md">g</a>'
            '<a href="">h</a>'
        )
        self.assertEqual(rewrite_html(text, "docs/p.html", "docs/p.html", MOVES), text)

    def test_script_style_and_comment_content_are_left_alone(self):
        text = (
            '<script>var s = "../tooling/commands.md";</script>'
            "<style>a { background: url(../tooling/commands.md); }</style>"
            '<!-- <a href="../tooling/commands.md">x</a> -->'
        )
        self.assertEqual(rewrite_html(text, "docs/p.html", "docs/p.html", MOVES), text)

    def test_script_src_attribute_is_rewritten(self):
        text = '<script src="../tooling/commands.md"></script>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "docs/p.html", MOVES),
            '<script src="../tools/commands.md"></script>',
        )

    def test_single_quoted_attribute_keeps_quote_style(self):
        moves = {"tooling/c.png": "img/c.png"}
        text = "<img src='../tooling/c.png'>"
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "docs/p.html", moves),
            "<img src='../img/c.png'>",
        )

    def test_percent_encoded_path_is_resolved_and_encoded(self):
        moves = {"tooling/a b.md": "tools/a b.md"}
        text = '<a href="../tooling/a%20b.md">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "docs/p.html", moves),
            '<a href="../tools/a%20b.md">x</a>',
        )

    def test_link_outside_bundle_is_left_alone(self):
        text = '<a href="../../x.md">x</a>'
        self.assertEqual(
            rewrite_html(text, "docs/p.html", "site/p.html", {"x.md": "y.md"}), text
        )

    def test_unchanged_input_returns_identical_string(self):
        text = '<!doctype html><p>No links.</p><a href="docs/p.html">self</a>\n'
        self.assertEqual(rewrite_html(text, "docs/p.html", "docs/p.html", MOVES), text)


if __name__ == "__main__":
    unittest.main()

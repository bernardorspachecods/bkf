import unittest

from relink import rewrite_markdown

MOVES = {"a/b.md": "x/y.md"}


class RewriteMarkdownTests(unittest.TestCase):
    def test_inline_link_is_rewritten(self):
        self.assertEqual(rewrite_markdown("[t](/a/b.md)", MOVES), "[t](/x/y.md)")

    def test_image_is_rewritten(self):
        self.assertEqual(rewrite_markdown("![t](/a/b.md)", MOVES), "![t](/x/y.md)")

    def test_fragment_is_kept(self):
        self.assertEqual(rewrite_markdown("[t](/a/b.md#sec-1)", MOVES), "[t](/x/y.md#sec-1)")

    def test_title_is_kept(self):
        self.assertEqual(
            rewrite_markdown('[t](/a/b.md "A title")', MOVES), '[t](/x/y.md "A title")'
        )

    def test_title_and_fragment_are_kept(self):
        self.assertEqual(
            rewrite_markdown("[t](/a/b.md#f 'T')", MOVES), "[t](/x/y.md#f 'T')"
        )

    def test_reference_definition_is_rewritten(self):
        self.assertEqual(
            rewrite_markdown('[ref]: /a/b.md "T"\n', MOVES), '[ref]: /x/y.md "T"\n'
        )

    def test_reference_definition_with_indent_and_fragment(self):
        self.assertEqual(rewrite_markdown("  [ref]: /a/b.md#s\n", MOVES), "  [ref]: /x/y.md#s\n")

    def test_space_in_new_and_old_names_is_percent_encoded(self):
        moves = {"a/b c.md": "a/d e.md"}
        self.assertEqual(rewrite_markdown("[t](/a/b%20c.md)", moves), "[t](/a/d%20e.md)")

    def test_non_ascii_new_name_is_percent_encoded(self):
        moves = {"a/b.md": "a/café.md"}
        self.assertEqual(
            rewrite_markdown("[t](/a/b.md)", moves), "[t](/a/caf%C3%A9.md)"
        )

    def test_encoded_non_ascii_old_name_matches(self):
        moves = {"a/café.md": "a/c.md"}
        self.assertEqual(rewrite_markdown("[t](/a/caf%C3%A9.md)", moves), "[t](/a/c.md)")

    def test_angle_bracket_destination_is_rewritten(self):
        moves = {"a/b c.md": "a/d.md"}
        self.assertEqual(rewrite_markdown("[t](</a/b c.md>)", moves), "[t](</a/d.md>)")

    def test_two_links_on_one_line(self):
        text = "[one](/a/b.md) and ![two](/a/b.md#x)"
        self.assertEqual(
            rewrite_markdown(text, MOVES), "[one](/x/y.md) and ![two](/x/y.md#x)"
        )

    def test_link_inside_fenced_backtick_block_is_left_alone(self):
        text = "```\n[t](/a/b.md)\n```\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_link_inside_fenced_tilde_block_is_left_alone(self):
        text = "~~~\n[t](/a/b.md)\n~~~\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_fence_closes_only_with_same_marker_and_length(self):
        text = "````\n```\n[t](/a/b.md)\n~~~~\n````\n[t](/a/b.md)\n"
        expected = "````\n```\n[t](/a/b.md)\n~~~~\n````\n[t](/x/y.md)\n"
        self.assertEqual(rewrite_markdown(text, MOVES), expected)

    def test_link_inside_fence_in_list_item_is_left_alone(self):
        text = "- ```\n  [t](/a/b.md)\n  ```\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_link_inside_fence_in_nested_list_is_left_alone(self):
        text = "- item\n  - ```\n    [t](/a/b.md)\n    ```\n[after](/a/b.md)\n"
        expected = "- item\n  - ```\n    [t](/a/b.md)\n    ```\n[after](/x/y.md)\n"
        self.assertEqual(rewrite_markdown(text, MOVES), expected)

    def test_link_inside_numbered_list_fence_is_left_alone(self):
        text = "1. ~~~\n   [t](/a/b.md)\n   ~~~\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_link_inside_fence_in_blockquote_is_left_alone(self):
        text = "> ```\n> [t](/a/b.md)\n> ```\n[after](/a/b.md)\n"
        expected = "> ```\n> [t](/a/b.md)\n> ```\n[after](/x/y.md)\n"
        self.assertEqual(rewrite_markdown(text, MOVES), expected)

    def test_link_inside_fence_in_blockquote_list_item_is_left_alone(self):
        text = "> - ```\n>   [t](/a/b.md)\n>   ```\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_list_fence_closes_only_with_same_marker(self):
        text = "- ```\n  ~~~\n  [t](/a/b.md)\n  ```\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_link_inside_inline_code_is_left_alone(self):
        text = "see `[t](/a/b.md)` and [t](/a/b.md)"
        self.assertEqual(
            rewrite_markdown(text, MOVES), "see `[t](/a/b.md)` and [t](/x/y.md)"
        )

    def test_link_inside_double_backtick_code_is_left_alone(self):
        text = "``a `[t](/a/b.md)` b``"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_destination_in_inline_code_is_not_a_link(self):
        text = "[t](`/a/b.md`)"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_path_that_starts_with_moved_path_is_left_alone(self):
        text = "[a](/a/b.md.bak) [b](/a/b.mdx) [c](/a/b.md)"
        self.assertEqual(
            rewrite_markdown(text, MOVES), "[a](/a/b.md.bak) [b](/a/b.mdx) [c](/x/y.md)"
        )

    def test_link_text_containing_old_path_is_left_alone(self):
        text = "[/a/b.md](/other.md) [/a/b.md](/a/b.md)"
        self.assertEqual(
            rewrite_markdown(text, MOVES), "[/a/b.md](/other.md) [/a/b.md](/x/y.md)"
        )

    def test_external_urls_and_anchors_are_left_alone(self):
        text = (
            "[h](https://example.com/a/b.md) [m](mailto:a/b.md) "
            "[s](#a/b.md) [r](a/b.md) [p](//host/a/b.md)"
        )
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_unmoved_link_is_left_alone(self):
        text = "[t](/other/c.md)"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_unchanged_text_is_returned_identically(self):
        text = "# Title\n\nNo links here.\n"
        self.assertEqual(rewrite_markdown(text, MOVES), text)

    def test_line_endings_are_preserved(self):
        text = "[t](/a/b.md)\r\nnext\r\n[r]: /a/b.md\r\n"
        self.assertEqual(
            rewrite_markdown(text, MOVES), "[t](/x/y.md)\r\nnext\r\n[r]: /x/y.md\r\n"
        )

    def test_no_trailing_newline_is_preserved(self):
        self.assertEqual(rewrite_markdown("[t](/a/b.md)", MOVES), "[t](/x/y.md)")


if __name__ == "__main__":
    unittest.main()

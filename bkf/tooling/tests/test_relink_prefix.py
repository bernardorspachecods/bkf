import unittest

from relink import prefix_markdown_links

EXISTS_NONE = lambda path: False  # noqa: E731
EXISTS_ALL = lambda path: True  # noqa: E731


def prefixed(text: str, exists=EXISTS_NONE, prefix: str = "bkf") -> str:
    return prefix_markdown_links(text, prefix, exists)


class PrefixMarkdownLinksTests(unittest.TestCase):
    def test_inline_link_gets_prefix(self):
        self.assertEqual(prefixed("[t](/manual/x.md)"), "[t](/bkf/manual/x.md)")

    def test_image_gets_prefix(self):
        self.assertEqual(prefixed("![t](/img/a.png)"), "![t](/bkf/img/a.png)")

    def test_fragment_is_kept(self):
        self.assertEqual(prefixed("[t](/manual/x.md#sec-1)"), "[t](/bkf/manual/x.md#sec-1)")

    def test_title_is_kept(self):
        self.assertEqual(prefixed('[t](/manual/x.md "A title")'), '[t](/bkf/manual/x.md "A title")')

    def test_reference_definition_gets_prefix(self):
        self.assertEqual(prefixed('[ref]: /manual/x.md "T"\n'), '[ref]: /bkf/manual/x.md "T"\n')

    def test_angle_bracket_form_is_supported(self):
        self.assertEqual(prefixed("[t](</manual/my x.md>)"), "[t](</bkf/manual/my x.md>)")

    def test_multi_segment_prefix(self):
        self.assertEqual(prefixed("[t](/x.md)", prefix="a/b"), "[t](/a/b/x.md)")

    def test_percent_encoding_is_kept(self):
        self.assertEqual(prefixed("[t](/my%20docs/a.md)"), "[t](/bkf/my%20docs/a.md)")

    def test_external_and_fragment_links_are_untouched(self):
        text = "[a](https://example.com/x) [b](http://e.org) [c](mailto:a@b.c) [d](#top) [e](relative/x.md)"
        self.assertEqual(prefixed(text), text)

    def test_protocol_relative_link_is_untouched(self):
        self.assertEqual(prefixed("[t](//cdn.example/x.js)"), "[t](//cdn.example/x.js)")

    def test_code_span_and_fence_are_untouched(self):
        text = "`[t](/manual/x.md)`\n\n```\n[t](/manual/x.md)\n```\n\n[t](/manual/x.md)\n"
        self.assertEqual(
            prefixed(text),
            "`[t](/manual/x.md)`\n\n```\n[t](/manual/x.md)\n```\n\n[t](/bkf/manual/x.md)\n",
        )

    def test_already_prefixed_is_skipped_when_own_root_target_is_missing(self):
        self.assertEqual(prefixed("[t](/bkf/manual/x.md)"), "[t](/bkf/manual/x.md)")

    def test_already_prefixed_is_prefixed_when_own_root_target_exists(self):
        self.assertEqual(prefixed("[t](/bkf/manual/x.md)", exists=EXISTS_ALL), "[t](/bkf/bkf/manual/x.md)")

    def test_exists_receives_decoded_path_after_prefix(self):
        seen = []

        def exists(path):
            seen.append(path)
            return False

        prefixed("[t](/bkf/my%20docs/a.md)", exists=exists)
        self.assertEqual(seen, ["my docs/a.md"])

    def test_root_relative_link_without_prefix_match_is_prefixed(self):
        self.assertEqual(prefixed("[t](/bkfx/a.md)"), "[t](/bkf/bkfx/a.md)")

    def test_text_outside_links_is_byte_identical(self):
        text = "Intro\r\n\r\n[t](/a.md)\r\nTail without newline [u](/b.md)"
        self.assertEqual(
            prefixed(text),
            "Intro\r\n\r\n[t](/bkf/a.md)\r\nTail without newline [u](/bkf/b.md)",
        )


if __name__ == "__main__":
    unittest.main()

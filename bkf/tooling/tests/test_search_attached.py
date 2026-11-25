from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bkf_common import BKFInputError
from search_attached import (
    AttachedTextEntry,
    EmbeddingsConfig,
    SearchConfig,
    TextPassage,
    attached_text_for,
    load_search_config,
    read_attached_text,
    text_passages,
)


CONFIG = """\
attached_text:
  - documents: "library/records/*/*.md"
    text: "{stem}.txt"
    locator:
      pattern: '^=== pdf (?P<pdf>\\d+) \\| printed (?P<printed>\\S+) ===$'
      labels:
        - when: {printed: '^([1-9]\\d*|[ivxlc]+)$'}
          label: "p. {printed}"
        - label: "pdf {pdf}"
    chunk: {words: 220, stride: 160}
"""


def write_config(root: Path, text: str) -> None:
    (root / "search.yaml").write_text(text, encoding="utf-8")


def collapse(value: str) -> str:
    return " ".join(value.split())


class SearchAttachedTests(unittest.TestCase):
    def test_absent_config_and_basic_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(load_search_config(root))
            write_config(root, CONFIG + "embeddings: {model: test-model}\n")
            config = load_search_config(root)

        assert config is not None
        self.assertEqual(config.attached_text[0].words, 220)
        self.assertEqual(config.attached_text[0].stride, 160)
        self.assertEqual(config.embeddings, EmbeddingsConfig("test-model", "lexical"))
        self.assertEqual(config.attached_text[0].locator.pattern.groupindex, {"pdf": 1, "printed": 2})

    def test_yaml_uses_yaml_12_and_rejects_duplicate_keys(self) -> None:
        for text, expected in (("attached_text: []\nattached_text: []\n", "cannot use search.yaml"),
                               ("attached_text: on\n", "must be a list"),
                               ("attached_text: [yes]\n", "must be a mapping")):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_config(root, text)
                with self.assertRaisesRegex(BKFInputError, expected):
                    load_search_config(root)

    def test_embeddings_configuration_is_validated(self) -> None:
        for value, expected in (
            ("true", "embeddings` must be a mapping"),
            ("{model: '  '}\n", "embeddings.model"),
            ("{model: 7}\n", "embeddings.model"),
            ("{mode: [hybrid]}\n", "embeddings.mode"),
            ("{mode: dense}\n", "embeddings.mode"),
            ("{fusion: mixed}\n", "embeddings.fusion"),
            ("{provider: future}\n", "embeddings.provider"),
        ):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_config(root, f"embeddings: {value}")
                with self.assertRaisesRegex(BKFInputError, expected):
                    load_search_config(root)

    def test_embeddings_fusion_defaults_and_accepts_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_config(root, "embeddings: {mode: hybrid}\n")
            self.assertEqual(load_search_config(root).embeddings.fusion, "passage")
            write_config(root, "embeddings: {mode: hybrid, fusion: document}\n")
            self.assertEqual(load_search_config(root).embeddings.fusion, "document")

    def test_optional_locator_defaults_and_chunk_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_config(root, 'attached_text: [{documents: "**/*.md", text: "{stem}.txt"}]\n')
            entry = load_search_config(root).attached_text[0]
        self.assertIsNone(entry.locator)
        self.assertEqual((entry.words, entry.stride), (220, 160))

    def test_attached_sidecar_matching_and_segment_aware_globs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = SearchConfig((AttachedTextEntry("library/records/*/*.md", "{stem}.txt", None),), None)
            good = root / "library/records/a/a.md"
            good.parent.mkdir(parents=True)
            good.touch()
            (good.parent / "a.txt").touch()
            self.assertIsNotNone(attached_text_for(config, root, good))
            self.assertIsNone(attached_text_for(config, root, root / "x/library/records/a/a.md"))
            self.assertIsNone(attached_text_for(config, root, root / "library/records/a/b/a.md"))

            recursive = SearchConfig((AttachedTextEntry("**/*.md", "{stem}.txt", None),), None)
            self.assertIsNotNone(attached_text_for(recursive, root, good))
            deep = root / "one/two/three/deep.md"
            deep.parent.mkdir(parents=True)
            deep.touch()
            (deep.parent / "deep.txt").touch()
            self.assertIsNotNone(attached_text_for(recursive, root, deep))
            root_doc = root / "root.md"
            root_doc.touch()
            (root / "root.txt").touch()
            self.assertIsNotNone(attached_text_for(recursive, root, root_doc))

    def test_first_matching_entry_wins_and_missing_sidecar_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / "x.md"
            doc.touch()
            first = AttachedTextEntry("*.md", "missing.txt", None)
            second = AttachedTextEntry("*.md", "{stem}.txt", None)
            config = SearchConfig((first, second), None)
            (root / "x.txt").touch()
            self.assertIsNone(attached_text_for(config, root, doc))
            found = attached_text_for(SearchConfig((second, first), None), root, doc)
        self.assertEqual(found, (root / "x.txt", second))

    def test_read_preserves_newlines_and_replaces_bad_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sidecar.txt"
            path.write_bytes(b"a\r\nb\rc\xff")
            self.assertEqual(read_attached_text(path), "a\r\nb\rc\ufffd")

    def test_locator_labels_integer_roman_and_fallback_values(self) -> None:
        config = load_search_config_from_text(CONFIG)
        entry = config.attached_text[0]
        source = "\n".join(
            [f"=== pdf {number} | printed {printed} ===\n" + "word " * 25
             for number, printed in ((1, "12"), (2, "iv"), (3, "cover"), (4, "-1"))]
        )
        passages = text_passages(source, entry)
        self.assertTrue(all(isinstance(passage, TextPassage) for passage in passages))
        self.assertEqual([passage.locator["label"] for passage in passages], ["p. 12", "p. iv", "pdf 3", "pdf 4"])
        self.assertEqual(passages[1].locator, {"label": "p. iv", "pdf": "2", "printed": "iv"})

    def test_offsets_are_exact_after_markers_and_at_eof(self) -> None:
        config = load_search_config_from_text(CONFIG)
        entry = config.attached_text[0]
        text = "intro " + "i " * 24 + "\n=== pdf 8 | printed 3 ===\n" + "m " * 25 + "m"
        passages = text_passages(text, entry)
        self.assertEqual(len(passages), 2)
        for passage in passages:
            self.assertEqual(collapse(text[passage.start:passage.end]), passage.text)
        self.assertEqual(text[passages[-1].start:passages[-1].end].split()[0], "m")
        self.assertEqual(passages[-1].locator["label"], "p. 3")
        self.assertEqual(passages[-1].end, len(text))

    def test_crlf_markers_are_recognized_and_offsets_preserved(self) -> None:
        entry = load_search_config_from_text(CONFIG).attached_text[0]
        text = "=== pdf 2 | printed ii ===\r\n" + "token " * 25
        passage, = text_passages(text, entry)
        self.assertEqual(collapse(text[passage.start:passage.end]), passage.text)
        self.assertEqual(passage.locator["label"], "p. ii")
        self.assertEqual(text[passage.start:passage.end].split()[0], "token")

    def test_no_locator_makes_one_unlocated_segment(self) -> None:
        entry = AttachedTextEntry("**/*.md", "{stem}.txt", None, words=40, stride=30)
        passages = text_passages(" ".join(f"w{i}" for i in range(55)), entry)
        self.assertEqual([p.start for p in passages], [0, len(" ".join(f"w{i}" for i in range(30))) + 1])
        self.assertTrue(all(p.locator is None for p in passages))

    def test_window_start_stop_rule(self) -> None:
        entry = AttachedTextEntry("*.md", "{stem}.txt", None)
        expected = {200: [0], 220: [0], 221: [0, 160], 380: [0, 160], 381: [0, 160, 320]}
        for count, starts in expected.items():
            with self.subTest(words=count):
                source = " ".join(f"w{i}" for i in range(count))
                passages = text_passages(source, entry)
                self.assertEqual([p.start for p in passages], [source.index(f"w{i}") for i in starts])
                self.assertTrue(all(collapse(source[p.start:p.end]) == p.text for p in passages))

    def test_short_noninitial_window_is_dropped_but_segment_first_is_kept(self) -> None:
        entry = AttachedTextEntry("*.md", "{stem}.txt", None, words=220, stride=200)
        source = " ".join(f"w{i}" for i in range(221))
        self.assertEqual(len(text_passages(source, entry)), 1)
        short = text_passages(" ".join(f"w{i}" for i in range(12)), entry)
        self.assertEqual(len(short), 1)

    def test_invalid_configs_name_the_offending_key(self) -> None:
        cases = [
            ("unknown top key", "oops: true\nattached_text: []\n", "oops"),
            ("attached list", "attached_text: {}\n", "attached_text"),
            ("entry mapping", "attached_text: [bad]\n", "attached_text[0]"),
            ("unknown entry key", 'attached_text: [{documents: "*.md", text: x, typo: 1}]\n', "typo"),
            ("documents missing", 'attached_text: [{text: x}]\n', "documents"),
            ("documents type", 'attached_text: [{documents: 3, text: x}]\n', "documents"),
            ("documents blank", 'attached_text: [{documents: "  ", text: x}]\n', "documents"),
            ("text missing", 'attached_text: [{documents: "*.md"}]\n', "text"),
            ("text type", 'attached_text: [{documents: "*.md", text: 3}]\n', "text"),
            ("text blank", 'attached_text: [{documents: "*.md", text: "  "}]\n', "text"),
            ("text absolute", 'attached_text: [{documents: "*.md", text: "/x"}]\n', "text"),
            ("text parent", 'attached_text: [{documents: "*.md", text: "../x"}]\n', "text"),
            ("text placeholder", 'attached_text: [{documents: "*.md", text: "{name}.txt"}]\n', "text"),
            ("locator mapping", 'attached_text: [{documents: "*.md", text: x, locator: []}]\n', "locator"),
            ("unknown locator key", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{label: a}], typo: x}}]\n', "locator.typo"),
            ("invalid regex", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "[", labels: [{label: x}]}}]\n', "pattern"),
            ("unnamed pattern", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "x", labels: [{label: x}]}}]\n', "pattern"),
            ("reserved group", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<label>x)", labels: [{label: x}]}}]\n', "pattern"),
            ("labels list", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: []}}]\n', "labels"),
            ("rule mapping", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [x]}}]\n', "labels[0]"),
            ("label missing", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{}]}}]\n', "label"),
            ("bad label field", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{label: "{b}"}]}}]\n', "label"),
            ("when mapping", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{when: x, label: x}]}}]\n', "when"),
            ("unknown when group", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{when: {b: x}, label: x}]}}]\n', "when.b"),
            ("invalid when regex", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{when: {a: "["}, label: x}]}}]\n', "when.a"),
            ("non-final fallback", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{label: x}, {label: x}]}}]\n', "when"),
            ("last conditional", 'attached_text: [{documents: "*.md", text: x, locator: {pattern: "(?P<a>x)", labels: [{when: {a: x}, label: x}]}}]\n', "labels"),
            ("chunk mapping", 'attached_text: [{documents: "*.md", text: x, chunk: []}]\n', "chunk"),
            ("unknown chunk key", 'attached_text: [{documents: "*.md", text: x, chunk: {widht: 2}}]\n', "widht"),
            ("words type", 'attached_text: [{documents: "*.md", text: x, chunk: {words: true}}]\n', "words"),
            ("words positive", 'attached_text: [{documents: "*.md", text: x, chunk: {words: 0}}]\n', "words"),
            ("stride type", 'attached_text: [{documents: "*.md", text: x, chunk: {stride: 1.5}}]\n', "stride"),
            ("stride range", 'attached_text: [{documents: "*.md", text: x, chunk: {words: 3, stride: 4}}]\n', "stride"),
            ("embeddings mapping", "embeddings: []\n", "embeddings"),
        ]
        for name, text, key in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_config(root, text)
                with self.assertRaises(BKFInputError) as caught:
                    load_search_config(root)
                self.assertIn(key, str(caught.exception))


def load_search_config_from_text(text: str) -> SearchConfig:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_config(root, text)
        config = load_search_config(root)
        assert config is not None
        return config


if __name__ == "__main__":
    unittest.main()

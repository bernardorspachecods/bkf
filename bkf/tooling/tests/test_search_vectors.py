from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import builtins
import io
from contextlib import redirect_stdout
from unittest.mock import patch

import search
from bkf_common import BKFInputError
from search_attached import EmbeddingsConfig, embeddings_config, load_search_config


def make_bundle(root: Path) -> None:
    (root / "MAP.md").write_text('---\nbkf_version: "0.2"\n---\n\n# Bundle\n', encoding="utf-8")


def document(title: str, body: str, tags: str = "topic") -> str:
    return f"---\nbkf: document\ndescription: Guide.\ntags: [{tags}]\n---\n\n# {title}\n\n{body}\n"


class FakeEmbedder:
    def __init__(self) -> None:
        self.embedded: list[str] = []

    def _vector(self, text: str) -> list[float]:
        lowered = text.casefold()
        return [1.0, 0.0] if "orchard" in lowered else [0.0, 1.0]

    def embed(self, texts):
        texts = list(texts)
        self.embedded.extend(texts)
        return [self._vector(text) for text in texts]

    def query_embed(self, texts):
        return [self._vector(text) for text in texts]


class VectorSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "bundle"
        self.root.mkdir()
        make_bundle(self.root)
        self.cache = Path(self.temp.name) / "cache"
        self.env_patch = patch.object(search, "_cache_directory", return_value=self.cache)
        self.env_patch.start()
        self.embedder = FakeEmbedder()
        self.embed_patch = patch.object(search, "_embedder", return_value=self.embedder)
        self.embed_patch.start()

    def tearDown(self) -> None:
        self.embed_patch.stop()
        self.env_patch.stop()
        self.temp.cleanup()

    def test_similarity_cache_reuses_unchanged_and_only_embeds_changed_sections(self) -> None:
        path = self.root / "guide.md"
        path.write_text(document("Guide", "## Orchard\n\norchard fruit details.\n\n## Other\n\nstone details."), encoding="utf-8")
        ranked = search.vector_rank(self.root, "orchard fruit")
        self.assertEqual(ranked[0].section.title, "Orchard")
        self.assertEqual(len(self.embedder.embedded), 3)

        search.vector_rank(self.root, "orchard fruit")
        self.assertEqual(len(self.embedder.embedded), 3)

        (self.root / "search.yaml").write_text(
            'attached_text:\n  - documents: "guide.md"\n    text: "guide.txt"\n', encoding="utf-8"
        )
        (self.root / "guide.txt").write_text("one sidecar passage with orchard detail.", encoding="utf-8")
        search.vector_rank(self.root, "orchard fruit")
        self.assertEqual(len(self.embedder.embedded), 4)

        path.write_text(document("Guide", "## Orchard\n\norchard fruit changed.\n\n## Other\n\nstone details."), encoding="utf-8")
        search.vector_rank(self.root, "orchard fruit")
        self.assertEqual(len(self.embedder.embedded), 5)

        (self.root / "search.yaml").write_text("embeddings: {model: second-model}\n", encoding="utf-8")
        search.vector_rank(self.root, "orchard fruit")
        self.assertEqual(len(self.embedder.embedded), 8)

    def test_filters_and_config_defaults(self) -> None:
        (self.root / "a.md").write_text(document("Alpha", "orchard details.", "red"), encoding="utf-8")
        (self.root / "b.md").write_text(document("Beta", "orchard details.", "blue"), encoding="utf-8")
        (self.root / "search.yaml").write_text("embeddings: {mode: hybrid}\n", encoding="utf-8")
        self.assertEqual(embeddings_config(self.root), EmbeddingsConfig(mode="hybrid"))
        result = search.vector_rank(self.root, "orchard", heading="Alpha", tags=["red"])
        self.assertEqual([hit.section.title for hit in result], ["Alpha"])
        self.assertEqual(load_search_config(self.root).embeddings.mode, "hybrid")

    def test_config_accepts_vector_mode(self) -> None:
        (self.root / "search.yaml").write_text("embeddings: {mode: vector}\n", encoding="utf-8")
        self.assertEqual(embeddings_config(self.root).mode, "vector")

    def test_rrf_exact_scores_order_and_lexical_ties(self) -> None:
        def hit(name: str) -> search.RankedPassage:
            section = search.Section(f"/{name}.md", name, "", f"body {name}", name)
            return search.RankedPassage(section, 0.0)

        lexical = [hit("a"), hit("b")]
        vector = [hit("b"), hit("c")]

        fused = search._reciprocal_rank_fusion(lexical, vector)

        self.assertEqual([row.section.title for row in fused], ["b", "a", "c"])
        self.assertEqual([row.score for row in fused], [1 / 61 + 1 / 60, 1 / 60, 1 / 61])
        # Equal RRF scores use lexical rank first; a precedes vector-only c.
        tied = search._reciprocal_rank_fusion([hit("a"), hit("b")], [hit("c")])
        self.assertEqual([row.section.title for row in tied], ["a", "c", "b"])

    def test_cli_uses_config_default_and_explicit_mode_override(self) -> None:
        (self.root / "search.yaml").write_text("embeddings: {mode: hybrid}\n", encoding="utf-8")
        output = io.StringIO()
        with patch.object(search, "rank_passages", return_value=[]) as rank, redirect_stdout(output):
            self.assertEqual(search.main(["question", "--cwd", str(self.root)]), 0)
        self.assertEqual(rank.call_args.kwargs["mode"], "hybrid")

        output = io.StringIO()
        with patch.object(search, "rank_passages", return_value=[]) as rank, redirect_stdout(output):
            self.assertEqual(search.main(["question", "--cwd", str(self.root), "--mode", "lexical"]), 0)
        self.assertEqual(rank.call_args.kwargs["mode"], "lexical")

    def test_cli_missing_fastembed_is_one_line_and_lexical_does_not_embed(self) -> None:
        from contextlib import redirect_stderr

        (self.root / "search.yaml").write_text("embeddings: {mode: hybrid}\n", encoding="utf-8")
        stderr = io.StringIO()
        failure = BKFInputError("vector search requires fastembed; install it with: install-command")
        with patch.object(search, "_embedder", side_effect=failure), redirect_stderr(stderr):
            self.assertEqual(search.main(["question", "--cwd", str(self.root)]), 1)
        self.assertEqual(stderr.getvalue(), "bkf search: vector search requires fastembed; install it with: install-command\n")

        stderr = io.StringIO()
        with patch.object(search, "_embedder", side_effect=AssertionError("must not embed")), \
                redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            self.assertEqual(search.main(["question", "--cwd", str(self.root), "--mode", "lexical"]), 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_missing_fastembed_has_install_message(self) -> None:
        self.embed_patch.stop()
        original_import = builtins.__import__
        def without_fastembed(name, *args, **kwargs):
            if name == "fastembed":
                raise ImportError("no fastembed")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=without_fastembed):
            with self.assertRaisesRegex(BKFInputError, "uv tool install --editable"):
                search.vector_rank(self.root, "question")

    def test_similarity_math_fallback_and_numpy_agree(self) -> None:
        vectors = [[1.0, 0.0], [0.0, 1.0], [0.70710678, 0.70710678]]
        query = [0.8, 0.6]
        with patch.dict("sys.modules", {"numpy": None}):
            pure = search._vector_similarity(query, vectors)
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is not installed")
        accelerated = search._vector_similarity(query, vectors)
        self.assertEqual(sorted(range(3), key=lambda i: -pure[i]), sorted(range(3), key=lambda i: -accelerated[i]))


if __name__ == "__main__":
    unittest.main()

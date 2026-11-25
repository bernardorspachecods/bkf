from __future__ import annotations

import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import search
import search_eval


def make_bundle(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "MAP.md").write_text('---\nbkf_version: "0.2"\n---\n\n# Bundle\n', encoding="utf-8")
    for name in ("a", "b", "zero"):
        (root / f"{name}.md").write_text(
            f"---\nbkf: document\ndescription: Test document.\ntags: [test]\n---\n\n# {name}\n\nBody.\n",
            encoding="utf-8",
        )


class SearchEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "bundle"
        make_bundle(self.root)
        self.questions = self.base / "questions.tsv"
        self.qrels = self.base / "qrels.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_inputs(self, questions: str, qrels: object) -> None:
        self.questions.write_text(questions, encoding="utf-8")
        self.qrels.write_text(json.dumps(qrels), encoding="utf-8")

    @staticmethod
    def hits(*paths: str) -> list[search.RankedPassage]:
        return [search.RankedPassage(search.Section(path, "", "", "body", ""), float(-index))
                for index, path in enumerate(paths)]

    def test_ndcg_matches_perfect_permuted_and_zero_ideal_values(self) -> None:
        relevance = {"/a.md": 2, "/b.md": 1}
        self.assertEqual(search_eval.ndcg(["/a.md", "/b.md"], relevance), 1.0)
        expected = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
        self.assertAlmostEqual(search_eval.ndcg(["/b.md", "/a.md"], relevance), expected)
        self.assertEqual(search_eval.ndcg(["/missing.md"], {"/zero.md": 0}), 1.0)

    def test_metrics_use_document_ranking_and_accept_both_grade_forms(self) -> None:
        self.write_inputs("id\tquestion\nq1\tfirst question\nq2\tsecond question\n",
                          {"q1": {"/a.md": 2, "/b.md": {"grade": 1, "locators": ["section"]}},
                           "q2": {"/a.md": 2, "/b.md": 2}})

        def ranked(_root, question, **kwargs):
            self.assertEqual(kwargs["mode"], "lexical")
            return self.hits("/a.md", "/b.md") if question.startswith("first") else self.hits("/b.md", "/a.md")

        with patch.object(search_eval.search, "rank_passages", side_effect=ranked), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = search_eval.main([str(self.questions), str(self.qrels), "--cwd", str(self.root), "--json"])
        self.assertEqual(result, 0)
        with patch.object(search_eval.search, "rank_passages", side_effect=ranked):
            methods = search_eval._run(self.root,
                {"q1": "first question", "q2": "second question"},
                {"q1": {"/a.md": 2, "/b.md": 1}, "q2": {"/a.md": 2, "/b.md": 2}},
                modes=["lexical"], weights=[20.0], k=8, recall_grade=2, scope=None, passages="all")
        self.assertEqual(methods["lexical"]["per_question_ndcg@5"]["q1"], 1.0)
        self.assertAlmostEqual(methods["lexical"]["per_question_ndcg@5"]["q2"],
                               search_eval.ndcg(["/b.md", "/a.md"], {"/a.md": 2, "/b.md": 2}))
        self.assertEqual(methods["lexical"]["recall@k"], 1.0)

    def test_question_without_qrels_warns_and_qrels_without_question_is_input_error(self) -> None:
        self.write_inputs("id\tquestion\nq1\tquestion\nq2\tskipped\n", {"q1": {}})
        error = io.StringIO()
        with patch.object(search_eval, "_available_modes", return_value=["lexical"]), \
                patch.object(search_eval.search, "rank_passages", return_value=[]), \
                redirect_stdout(io.StringIO()), redirect_stderr(error):
            self.assertEqual(search_eval.main([str(self.questions), str(self.qrels), "--cwd", str(self.root)]), 0)
        self.assertIn("question 'q2' has no qrels", error.getvalue())

        self.qrels.write_text(json.dumps({"unknown": {}}), encoding="utf-8")
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(search_eval.main([str(self.questions), str(self.qrels)]), 2)
        self.assertIn(str(self.qrels), error.getvalue())
        self.assertIn("unknown", error.getvalue())

    def test_malformed_tsv_and_qrels_report_file_and_location(self) -> None:
        self.questions.write_text("question\nmissing id\n", encoding="utf-8")
        self.qrels.write_text("{}", encoding="utf-8")
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(search_eval.main([str(self.questions), str(self.qrels)]), 2)
        self.assertIn(f"{self.questions}: line 1", error.getvalue())

        self.write_inputs("id\tquestion\nq1\tquestion\n", {"q1": {"/a.md": {"grade": -1}}})
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(search_eval.main([str(self.questions), str(self.qrels)]), 2)
        self.assertIn(f"{self.qrels}: key q1.'/a.md'", error.getvalue())

        self.qrels.write_text('{\n  "q1": {\n', encoding="utf-8")
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(search_eval.main([str(self.questions), str(self.qrels)]), 2)
        self.assertIn(f"{self.qrels}: line", error.getvalue())

    def test_vector_is_called_once_when_heading_weights_repeat(self) -> None:
        self.write_inputs("id\tquestion\nq1\tquestion\n", {"q1": {}})
        with patch.object(search_eval, "_available_modes", return_value=["lexical", "vector", "hybrid"]), \
                patch.object(search_eval.search, "rank_passages", return_value=[]) as rank, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(search_eval.main([str(self.questions), str(self.qrels), "--cwd", str(self.root),
                                               "--mode", "vector", "--heading-weight", "10",
                                               "--heading-weight", "30"]), 0)
        self.assertEqual(rank.call_count, 1)


if __name__ == "__main__":
    unittest.main()

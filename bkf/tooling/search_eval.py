"""Evaluate BKF document search rankings against TSV questions and JSON qrels."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import search
from bkf_common import BKFInputError, find_outermost_bundle_root
from search_attached import load_search_config


class InputError(Exception):
    """Malformed question or qrels input."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf search-eval", description=__doc__)
    parser.add_argument("questions", type=Path, help="TSV file with id and question columns")
    parser.add_argument("qrels", type=Path, help="JSON relevance judgments keyed by question id")
    parser.add_argument("--cwd", type=Path, help="directory in the bundle (defaults to current directory)")
    parser.add_argument("--mode", action="append", choices=("lexical", "vector", "hybrid"),
                        help="search mode to evaluate; repeat to compare modes")
    parser.add_argument("--fusion", action="append", choices=("passage", "document"), default=None,
                        help="hybrid fusion method to evaluate; repeat to compare methods (default: passage)")
    parser.add_argument("--k", type=int, default=8, help="recall cutoff (default: 8)")
    parser.add_argument("--recall-grade", type=int, default=2, help="minimum grade counted for recall (default: 2)")
    parser.add_argument("--path", type=Path, help="only search documents under this directory or file")
    parser.add_argument("--passages", choices=("all", "sections", "text"), default="all",
                        help="passage kinds to search (default: all)")
    parser.add_argument("--heading-weight", type=float, action="append", default=None,
                        help="heading weight for lexical and hybrid ranking; repeat to compare weights (default: 20)")
    parser.add_argument("--depth", type=int, default=150,
                        help="passages per mode before hybrid fusion (default: 150)")
    parser.add_argument("--rrf-k", type=float, default=60.0,
                        help="RRF constant (default: 60)")
    parser.add_argument("--json", action="store_true", help="print metrics as JSON")
    return parser


def _read_questions(path: Path) -> dict[str, str]:
    try:
        stream = path.open(encoding="utf-8", newline="")
    except OSError as exc:
        raise InputError(f"{path}: {exc}") from exc
    try:
        with stream:
            reader = csv.reader(stream, delimiter="\t", strict=True)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise InputError(f"{path}: line 1: missing header row") from exc
            except csv.Error as exc:
                raise InputError(f"{path}: line {reader.line_num}: {exc}") from exc
            if len(header) != len(set(header)):
                raise InputError(f"{path}: line 1: duplicate header column")
            missing = {"id", "question"} - set(header)
            if missing:
                raise InputError(f"{path}: line 1: missing required column(s): {', '.join(sorted(missing))}")
            id_column, question_column = header.index("id"), header.index("question")
            questions: dict[str, str] = {}
            try:
                for row in reader:
                    line = reader.line_num
                    if len(row) != len(header):
                        raise InputError(f"{path}: line {line}: expected {len(header)} columns, found {len(row)}")
                    qid, question = row[id_column].strip(), row[question_column].strip()
                    if not qid:
                        raise InputError(f"{path}: line {line}: empty id")
                    if not question:
                        raise InputError(f"{path}: line {line}: empty question for id {qid!r}")
                    if qid in questions:
                        raise InputError(f"{path}: line {line}: duplicate id {qid!r}")
                    questions[qid] = question
            except csv.Error as exc:
                raise InputError(f"{path}: line {reader.line_num}: {exc}") from exc
    except UnicodeError as exc:
        raise InputError(f"{path}: line 1: input is not valid UTF-8") from exc
    return questions


def _read_qrels(path: Path) -> dict[str, dict[str, int]]:
    try:
        with path.open(encoding="utf-8") as stream:
            raw = json.load(stream)
    except OSError as exc:
        raise InputError(f"{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except UnicodeError as exc:
        raise InputError(f"{path}: line 1: input is not valid UTF-8") from exc
    if not isinstance(raw, dict):
        raise InputError(f"{path}: key <root>: expected an object keyed by question id")
    result: dict[str, dict[str, int]] = {}
    for qid, judgments in raw.items():
        if not isinstance(qid, str) or not qid:
            raise InputError(f"{path}: key {qid!r}: question id must be a non-empty string")
        if not isinstance(judgments, dict):
            raise InputError(f"{path}: key {qid!r}: expected an object mapping document paths to grades")
        result[qid] = {}
        for docpath, value in judgments.items():
            key = f"{qid}.{docpath!r}"
            if not isinstance(docpath, str) or not docpath.startswith("/"):
                raise InputError(f"{path}: key {key}: document path must start with '/'")
            if isinstance(value, dict):
                if set(value) - {"grade", "locators"} or "grade" not in value:
                    raise InputError(f"{path}: key {key}: expected grade and optional locators")
                grade = value["grade"]
                locators = value.get("locators", [])
                if not isinstance(locators, list) or any(not isinstance(item, str) for item in locators):
                    raise InputError(f"{path}: key {key}: locators must be an array of strings")
            else:
                grade = value
            if isinstance(grade, bool) or not isinstance(grade, int) or grade < 0:
                raise InputError(f"{path}: key {key}: grade must be a non-negative integer")
            result[qid][docpath] = grade
    return result


def ndcg(docs: list[str], relevance: dict[str, int], cutoff: int = 5) -> float:
    """Compute graded nDCG using exponential gain and log2 discount."""
    def dcg(grades: list[int]) -> float:
        return sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades[:cutoff]))

    actual = [relevance.get(path, 0) for path in docs]
    ideal = sorted(relevance.values(), reverse=True)
    ideal_dcg = dcg(ideal)
    return dcg(actual) / ideal_dcg if ideal_dcg else 1.0


def recall(docs: list[str], relevance: dict[str, int], *, k: int, minimum_grade: int) -> float | None:
    relevant = [path for path, grade in relevance.items() if grade >= minimum_grade]
    if not relevant:
        return None
    return sum(path in docs[:k] for path in relevant) / len(relevant)


def _fastembed_available() -> bool:
    try:
        from fastembed import TextEmbedding  # noqa: F401
    except ImportError:
        return False
    return True


def _available_modes(root: Path) -> list[str]:
    config = load_search_config(root)
    modes = ["lexical"]
    if _fastembed_available() and config is not None and config.embeddings is not None:
        modes.extend(("vector", "hybrid"))
    return modes


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _run(root: Path, questions: dict[str, str], qrels: dict[str, dict[str, int]], *,
         modes: list[str], weights: list[float], k: int, recall_grade: int,
         scope: Path | None, passages: str, fusions: list[str] | None = None,
         depth: int = 150, rrf_k: float = 60.0) -> dict[str, dict[str, Any]]:
    multiple_weights = len(weights) > 1
    fusions = fusions or ["passage"]
    multiple_fusions = len(fusions) > 1
    methods: dict[str, dict[str, Any]] = {}
    for mode in modes:
        method_weights = [weights[0]] if mode == "vector" else weights
        for weight in method_weights:
            method_fusions = fusions if mode == "hybrid" else ["passage"]
            for fusion in method_fusions:
                name = mode
                if mode == "hybrid" and multiple_fusions:
                    name += f"/{fusion}"
                if multiple_weights and mode != "vector":
                    name += f"@{weight:g}"
                per_question: dict[str, float] = {}
                recalls: list[float] = []
                for qid, question in questions.items():
                    relevance = qrels.get(qid)
                    if relevance is None:
                        continue
                    hits = search.rank_documents(
                        root, question, limit=max(5, k), mode=mode, fusion=fusion,
                        scope=scope, passages=passages, heading_weight=weight,
                        depth=depth, rrf_k=rrf_k,
                    )
                    docs = [hit.path for hit in hits]
                    per_question[qid] = ndcg(docs, relevance)
                    question_recall = recall(docs, relevance, k=k, minimum_grade=recall_grade)
                    if question_recall is not None:
                        recalls.append(question_recall)
                methods[name] = {
                    "ndcg@5": _mean(list(per_question.values())),
                    "recall@k": _mean(recalls),
                    "questions": len(per_question),
                    "per_question_ndcg@5": per_question,
                }
    return methods


def _render_text(methods: dict[str, dict[str, Any]], k: int) -> str:
    lines = [f"method          nDCG@5  recall@{k}  questions"]
    for name, values in methods.items():
        nd = "—" if values["ndcg@5"] is None else f"{values['ndcg@5']:.2f}"
        rec = "—" if values["recall@k"] is None else f"{values['recall@k']:.2f}"
        lines.append(f"{name:<15} {nd:>6}  {rec:>9}  {values['questions']}")
    lines.append("")
    for name, values in methods.items():
        scores = "  ".join(f"{qid}={value:.2f}" for qid, value in values["per_question_ndcg@5"].items())
        lines.append(f"{name} per-question nDCG@5: {scores}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.k < 1:
        print("bkf search-eval: --k must be at least 1", file=sys.stderr)
        return 2
    if args.recall_grade < 0:
        print("bkf search-eval: --recall-grade must be non-negative", file=sys.stderr)
        return 2
    if args.depth < 1:
        print("bkf search-eval: --depth must be at least 1", file=sys.stderr)
        return 2
    if not math.isfinite(args.rrf_k) or args.rrf_k <= 0:
        print("bkf search-eval: --rrf-k must be finite and greater than 0", file=sys.stderr)
        return 2
    weights = args.heading_weight or [20.0]
    if any(not math.isfinite(weight) for weight in weights):
        print("bkf search-eval: --heading-weight must be finite", file=sys.stderr)
        return 2
    try:
        questions = _read_questions(args.questions)
        qrels = _read_qrels(args.qrels)
        missing = set(qrels) - set(questions)
        if missing:
            key = sorted(missing)[0]
            raise InputError(f"{args.qrels}: key {key!r}: qrels id has no matching question")
        for qid in questions:
            if qid not in qrels:
                print(f"bkf search-eval: warning: question {qid!r} has no qrels; skipped", file=sys.stderr)

        cwd = (args.cwd or Path.cwd()).resolve()
        root = find_outermost_bundle_root(cwd)
        if root is None:
            raise BKFInputError(f"no BKF bundle contains {cwd}")
        scope = None
        if args.path is not None:
            scope = (args.path if args.path.is_absolute() else cwd / args.path).resolve()
            if not scope.is_relative_to(root):
                print(f"bkf search-eval: --path is outside the bundle: {args.path}", file=sys.stderr)
                return 2
        modes = list(dict.fromkeys(args.mode)) if args.mode else _available_modes(root)
        requested_embedding_mode = next((mode for mode in modes if mode in ("vector", "hybrid")), None)
        if requested_embedding_mode is not None and not _fastembed_available():
            message = (
                "vector and hybrid search require fastembed; install with: "
                "uv tool install --editable ./bkf/tooling --with fastembed --reinstall"
            )
            raise RuntimeError(f"mode {requested_embedding_mode!r} cannot run: {message}")
        methods = _run(root, questions, qrels, modes=modes, weights=weights, k=args.k,
                       recall_grade=args.recall_grade, scope=scope, passages=args.passages,
                       fusions=args.fusion or ["passage"], depth=args.depth, rrf_k=args.rrf_k)
    except InputError as exc:
        print(f"bkf search-eval: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"bkf search-eval: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(methods, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(_render_text(methods, args.k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLING = Path(__file__).resolve().parents[1]
CLI = TOOLING / "bkf_cli.py"
sys.path.insert(0, str(TOOLING))
import search

_SEARCH_CACHE = tempfile.TemporaryDirectory()
os.environ["BKF_SEARCH_CACHE"] = _SEARCH_CACHE.name


def map_text(*, root: bool = False) -> str:
    front = 'bkf_version: "0.2"\n' if root else ""
    return f"---\n{front}description: Bundle map.\n---\n\n# Map\n"


def document(
    name: str, body: str, *, description: str = "A tracked guide.", profile: str = "document", tags: str = "test"
) -> str:
    return (
        f"---\nbkf: {profile}\ndescription: {description}\ntags: [{tags}]\n---\n\n"
        f"# {name}\n\n{body}"
    )


def make_bundle(root: Path) -> None:
    (root / "MAP.md").write_text(map_text(root=True), encoding="utf-8")


def run(root: Path, *arguments: str, cwd: Path = TOOLING) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "search", *arguments, "--cwd", str(root)],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "BKF_SEARCH_CACHE": _SEARCH_CACHE.name},
    )


class PreviewTests(unittest.TestCase):
    def preview_of(self, result: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()[1].strip().split("  ", 1)[-1]

    def test_match_deep_in_long_body_appears_in_preview(self) -> None:
        claims = "\n".join(f"- Claim {n}: finding number {n} about topic{n}." for n in range(1, 16))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "a.md").write_text(document("Paper", f"## Key claims\n\n{claims}\n"), encoding="utf-8")

            result = run(root, "topic13", "--heading", "Key claims")

        preview = self.preview_of(result)
        self.assertIn("topic13", preview)
        self.assertLessEqual(len(preview), search.PREVIEW_LENGTH)
        self.assertNotIn("\x02", preview)
        self.assertTrue(preview.startswith("…"))

    def test_heading_description_or_tag_match_gives_start_of_body(self) -> None:
        body = "Opening words here. " + "filler " * 80
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "a.md").write_text(
                document("Quokka", body, description="About wombats."), encoding="utf-8"
            )
            (root / "b.md").write_text(document("Plain", body, tags="zebra"), encoding="utf-8")
            for query, name in (("quokka", "/a.md"), ("wombats", "/a.md"), ("zebra", "/b.md")):
                result = run(root, query)
                lines = result.stdout.splitlines()
                self.assertIn(name, lines[0])
                self.assertTrue(lines[1].strip().startswith("§ Quokka  Opening words here. filler") or
                                lines[1].strip().startswith("§ Plain  Opening words here. filler"), (query, lines[1]))
                self.assertEqual(len(lines[1].split("  ", 2)[-1].strip()), search.PREVIEW_LENGTH + 1)

    def test_multi_word_synonym_phrase_match_appears_in_preview(self) -> None:
        body = "Preamble. " * 60 + "Notes on artificial intelligence in practice. " + "Tail. " * 60
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text(VOCABULARY, encoding="utf-8")
            (root / "a.md").write_text(document("Notes", body, tags="ai"), encoding="utf-8")

            result = run(root, "tell me about ai")

        preview = self.preview_of(result)
        self.assertIn("artificial intelligence", preview)
        self.assertLessEqual(len(preview), search.PREVIEW_LENGTH)

    def test_preview_never_exceeds_limit_and_order_is_unchanged(self) -> None:
        sections = [
            search.Section(f"/{n}.md", f"H{n}", "", ("word " * (n * 30)) + "needle " + "tail " * 100, f"H{n}")
            for n in range(1, 6)
        ]
        hits = search._search(sections, ["needle"], 5)
        # bm25 ranks shorter bodies first; the fixture's order is fixed by length.
        self.assertEqual([hit.path for hit, _ in hits], ["/1.md", "/2.md", "/3.md", "/4.md", "/5.md"])
        for hit, _ in hits:
            self.assertLessEqual(len(hit.preview), search.PREVIEW_LENGTH)
            self.assertIn("needle", hit.preview)
        ranks = [rank for _, rank in hits]
        self.assertEqual(ranks, sorted(ranks))


class SearchTests(unittest.TestCase):
    def test_per_document_limit_and_renderer_boundary(self) -> None:
        ranked = [search.RankedPassage(
            search.Section("/many.md", f"H{index}", "", f"body {index}", f"H{index}", document_title="Many"),
            float(index),
        ) for index in range(5)]
        hit = search.group_documents(ranked, limit=1, per_document=4)[0]
        self.assertEqual(len(hit.passages), 4)
        first = search.DocumentHit("/a.md", "A", 1, (ranked[0],))
        second = search.DocumentHit("/b.md", "B", 1, (ranked[1],))
        rendered_one = search._render([first], max_chars=200)
        rendered_both = search._render([first, second], max_chars=len(rendered_one) + 1)
        self.assertEqual(rendered_both, rendered_one)

    def test_cli_per_document_option_applies_to_single_and_multi_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            sections = "\n\n".join(
                f"## Section {index}\n\nalpha beta passage {index}." for index in range(6)
            )
            (root / "many.md").write_text(document("Many", sections), encoding="utf-8")
            single = run(root, "alpha", "--per-document", "4", "--json")
            multi = run(root, "--query", "alpha", "--query", "beta", "--per-document", "4", "--json")
        self.assertEqual(single.returncode, 0, single.stderr)
        self.assertEqual(multi.returncode, 0, multi.stderr)
        self.assertEqual(len(__import__("json").loads(single.stdout)[0]["passages"]), 4)
        self.assertLessEqual(len(__import__("json").loads(multi.stdout)[0]["passages"]), 4)

    def test_search_numeric_options_reject_invalid_values_with_status_two(self) -> None:
        from contextlib import redirect_stderr
        cases = [("--per-document", "0"), ("--max-chars", "199"), ("--depth", "0"),
                 ("--heading-weight", "-1"), ("--rrf-k", "0")]
        for option, value in cases:
            error = io.StringIO()
            with self.subTest(option=option), redirect_stderr(error):
                self.assertEqual(search.main(["query", option, value]), 2)
            self.assertIn(option, error.getvalue())

    def test_multi_query_document_rrf_and_passage_query_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)

            def passage(path: str, title: str, body: str, score: float) -> search.RankedPassage:
                return search.RankedPassage(
                    search.Section(path, title, "", body, title, document_title=title), score
                )

            rankings = {
                "alpha": [passage("/a.md", "A", "alpha passage", 3),
                          passage("/c.md", "C", "shared alpha passage", 2)],
                "beta": [passage("/b.md", "B", "beta passage", 3),
                         passage("/c.md", "C", "shared beta passage", 2)],
            }
            with patch.object(search, "rank_passages", side_effect=lambda _root, query, **_kwargs: rankings[query]):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = search.main(["--query", "alpha", "--query", "beta", "--json", "--cwd", str(root)])

        self.assertEqual(result, 0)
        payload = __import__("json").loads(output.getvalue())
        self.assertEqual(payload[0]["path"], "/c.md")
        self.assertAlmostEqual(payload[0]["score"], 1 / 61 + 1 / 61)
        self.assertEqual([row["query"] for row in payload[0]["passages"]], ["alpha", "beta"])
        self.assertEqual([row["preview"] for row in payload[0]["passages"]],
                         ["shared alpha passage", "shared beta passage"])

    def test_multi_query_uses_positional_query_first_and_ignores_empty_subqueries(self) -> None:
        args = search.build_parser().parse_args(["first", "words", "--query", "the and of", "--query", "last"])
        questions = ([" ".join(args.query)] if args.query else []) + (args.queries or [])
        self.assertEqual([question for question in questions if search._query_terms(question)],
                         ["first words", "last"])

    def test_group_documents_skips_overlapping_text_passages(self) -> None:
        ranked = [
            search.RankedPassage(search.Section("/guide.md", "Page 1", "", "first", "Page 1",
                                                kind="text", start=0, end=220, document_title="Guide"), 1.0),
            search.RankedPassage(search.Section("/guide.md", "Page 2", "", "overlap", "Page 2",
                                                kind="text", start=160, end=380, document_title="Guide"), 2.0),
            search.RankedPassage(search.Section("/guide.md", "Page 3", "", "next", "Page 3",
                                                kind="text", start=320, end=540, document_title="Guide"), 3.0),
        ]

        hits = search.group_documents(ranked, limit=1)

        self.assertEqual([hit.section.start for hit in hits[0].passages], [0, 320])
        section = search.RankedPassage(
            search.Section("/guide.md", "Content", "", "section", "Content", document_title="Guide"), 1.5
        )
        with_section = search.group_documents([ranked[0], section, ranked[1]], limit=1)
        self.assertEqual([hit.section.kind for hit in with_section[0].passages], ["text", "section"])

    def test_navigation_map_sections_are_excluded_in_both_search_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(
                document("Guide", "## Navigation map\n\nmaponlyword\n\n"
                         "### nAvIgAtIoN MaP\n\nmapsectiononlyword\n\n"
                         "#### Child\n\nchildword\n\n## Content\n\nrealword."),
                encoding="utf-8",
            )

            for memory_only in (False, True):
                with self.subTest(memory_only=memory_only):
                    fallback = patch.object(search, "_persistent_search", return_value=None)
                    if memory_only:
                        fallback.start()
                    try:
                        self.assertEqual(search.rank_passages(root, "maponlyword"), [])
                        self.assertEqual(search.rank_passages(root, "mapsectiononlyword"), [])
                        hits = search.rank_passages(root, "childword realword")
                    finally:
                        if memory_only:
                            fallback.stop()

                    self.assertEqual({hit.section.title for hit in hits}, {"Child", "Content"})

    def test_heading_weight_changes_heading_only_match_order_in_both_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(
                document("Guide", "## needle\n\n"
                         "## Body match\n\nneedle " + "filler " * 120), encoding="utf-8"
            )

            for memory_only in (False, True):
                with self.subTest(memory_only=memory_only):
                    fallback = patch.object(search, "_persistent_search", return_value=None)
                    if memory_only:
                        fallback.start()
                    try:
                        default = search.rank_passages(root, "needle")
                        without_heading_weight = search.rank_passages(root, "needle", heading_weight=0)
                    finally:
                        if memory_only:
                            fallback.stop()

                    self.assertEqual(default[0].section.title, "needle")
                    self.assertEqual(without_heading_weight[0].section.title, "Body match")

    def test_broad_query_only_previews_selected_document_passages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            for document_number in range(8):
                sections = "\n\n".join(
                    f"## Match {passage_number}\n\nneedle matching passage {passage_number}."
                    for passage_number in range(40)
                )
                (root / f"doc-{document_number}.md").write_text(
                    document(f"Document {document_number}", sections), encoding="utf-8"
                )

            output = io.StringIO()
            with patch.object(search, "_preview", wraps=search._preview) as preview:
                with redirect_stdout(output):
                    result = search.main(["needle", "--cwd", str(root), "--limit", "3"])

        self.assertEqual(result, 0)
        self.assertLessEqual(preview.call_count, 2 * 3)
        self.assertEqual(sum(line[:1].isdigit() for line in output.getvalue().splitlines()), 3)

    def test_limit_counts_documents_and_keeps_two_passages_per_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            ten = "\n\n".join(f"## Section {n}\n\nneedle passage number {n}." for n in range(10))
            (root / "many.md").write_text(document("Many", ten), encoding="utf-8")
            for n in range(1, 4):
                (root / f"single{n}.md").write_text(
                    document(f"Single {n}", "needle once. " + "filler " * 400), encoding="utf-8"
                )

            result = run(root, "needle", "--limit", "3")

        self.assertEqual(result.returncode, 0, result.stderr)
        document_lines = [line for line in result.stdout.splitlines() if line[:1].isdigit()]
        self.assertEqual(len(document_lines), 3)
        self.assertEqual(len({line.split()[1] for line in document_lines}), 3)
        current_path = None
        many_passages = 0
        for line in result.stdout.splitlines():
            if line[:1].isdigit():
                current_path = line.split()[1]
            elif line.strip().startswith("§ ") and current_path == "/many.md":
                many_passages += 1
        self.assertEqual(many_passages, 2)

    def test_json_has_document_and_passage_shape_and_full_located_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "*.md"\n    text: "{stem}.txt"\n'
                '    locator:\n      pattern: "^PAGE (?P<page>[0-9]+)$"\n'
                '      labels:\n        - label: "Page {page}"\n', encoding="utf-8"
            )
            (root / "guide.md").write_text(document("Guide", "sectionjsonword"), encoding="utf-8")
            sidecar = "before\nPAGE 9\nlocatedjsonword full passage text\nafter"
            (root / "guide.txt").write_text(sidecar, encoding="utf-8")

            section_result = run(root, "sectionjsonword", "--json")
            text_result = run(root, "locatedjsonword", "--json", "--full")

        section = __import__("json").loads(section_result.stdout)
        self.assertEqual(set(section[0]), {"path", "title", "score", "passages"})
        self.assertEqual(section[0]["title"], "Guide")
        passage = section[0]["passages"][0]
        self.assertEqual(set(passage), {"kind", "heading", "locator", "start", "end", "preview", "score"})
        self.assertEqual(passage["kind"], "section")
        self.assertIsNone(passage["locator"])
        text_hit = __import__("json").loads(text_result.stdout)[0]["passages"][0]
        self.assertEqual(text_hit["kind"], "text")
        self.assertEqual(text_hit["heading"], None)
        self.assertEqual(text_hit["locator"]["label"], "Page 9")
        self.assertEqual(" ".join(sidecar[text_hit["start"]:text_hit["end"]].split()), text_hit["preview"])

    def test_passages_option_filters_kinds_before_document_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "*.md"\n    text: "{stem}.txt"\n', encoding="utf-8"
            )
            (root / "guide.md").write_text(document("Guide", "sectiononlyword"), encoding="utf-8")
            (root / "guide.txt").write_text("textonlyword sidecar passage", encoding="utf-8")

            text_only = run(root, "sectiononlyword", "--passages", "text")
            sections_only = run(root, "textonlyword", "--passages", "sections")
            located = run(root, "textonlyword", "--passages", "text")

        self.assertEqual(text_only.stdout, "no sections match\n")
        self.assertEqual(sections_only.stdout, "no sections match\n")
        self.assertIn("1  /guide.md", located.stdout)
        self.assertIn("textonlyword", located.stdout)

    def test_linked_worktree_uses_its_bundle_and_finds_uncommitted_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            (checkout / ".git").mkdir(parents=True)
            make_bundle(checkout)
            (checkout / "outer.md").write_text(document("Outer", "worktreeword"), encoding="utf-8")
            worktree = checkout / ".claude" / "worktrees" / "feature"
            library = worktree / "library"
            library.mkdir(parents=True)
            (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/feature\n", encoding="utf-8")
            make_bundle(worktree)
            (library / "tracked.md").write_text(document("Inner", "worktreeword"), encoding="utf-8")
            (library / "uncommitted.md").write_text(document("Draft", "draftworktreeword"), encoding="utf-8")

            result = run(worktree, "worktreeword")
            scoped = run(worktree, "draftworktreeword", "--path", "library")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/library/tracked.md", result.stdout)
        self.assertNotIn("outer.md", result.stdout)
        self.assertEqual(scoped.returncode, 0, scoped.stderr)
        self.assertIn("/library/uncommitted.md", scoped.stdout)

    def test_heading_match_ranks_above_body_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "body.md").write_text(document("Overview", "The description rules are discussed here."), encoding="utf-8")
            (root / "heading.md").write_text(document("Descriptions", "Short content."), encoding="utf-8")

            result = run(root, "description")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1  /heading.md  Descriptions", result.stdout)
        self.assertIn("§ Descriptions", result.stdout)

    def test_heading_splitting_and_fenced_code_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(
                document("Guide", """Intro text.

## Parent
Parent content.

```md
## Fake heading
```

### Child
Child content.

## Last
Last content.
"""),
                encoding="utf-8",
            )

            result = run(root, "child")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("§ Guide > Parent > Child", result.stdout)
        self.assertNotIn("Fake heading", result.stdout)

    def test_excluded_files_do_not_appear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "MAP.md").write_text(map_text(root=True) + "needle hiddenmap\n", encoding="utf-8")
            (root / "feedback.md").write_text(document("Needle feedback", "needle", profile="feedback"), encoding="utf-8")
            (root / "ideas.md").write_text(document("Needle ideas", "needle", profile="ideas"), encoding="utf-8")
            (root / "untracked.md").write_text("# Needle untracked\nneedle\n", encoding="utf-8")
            hidden = root / ".private"
            hidden.mkdir()
            (hidden / "hidden.md").write_text(document("Needle hidden", "needle"), encoding="utf-8")
            hidden_bundle = hidden / "bundle"
            hidden_bundle.mkdir()
            (hidden_bundle / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (hidden_bundle / "hidden-bundle.md").write_text(document("Needle hidden bundle", "needle"), encoding="utf-8")
            (root / "visible.md").write_text(document("Visible", "needle content."), encoding="utf-8")

            result = run(root, "needle", "--limit", "20")

        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("feedback.md", "ideas.md", "untracked.md", "hidden.md", "hidden-bundle.md", "MAP.md"):
            self.assertNotIn(name, result.stdout)
        self.assertIn("/visible.md", result.stdout)

    def test_agents_file_is_indexed_without_minimum_body_length(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "AGENTS.md").write_text(
                "# Agent instructions\n\nRecord what went wrong after an unexpected command failure.\n",
                encoding="utf-8",
            )

            result = run(root, "where do agents record what went wrong")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/AGENTS.md", result.stdout)

    def test_nested_bundle_paths_are_relative_to_outer_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            nested = root / "nested"
            nested.mkdir()
            (nested / "MAP.md").write_text(map_text(root=True), encoding="utf-8")
            (nested / "guide.md").write_text(document("Nested", "needle in nested bundle."), encoding="utf-8")

            result = run(nested, "needle")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/nested/guide.md", result.stdout)

    def test_limit_and_output_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            for index in range(40):
                (root / f"doc-{index:02}.md").write_text(
                    document(f"Needle {index}", "needle " + "x " * 195), encoding="utf-8"
                )

            limited = run(root, "needle", "--limit", "2")
            capped = run(root, "needle", "--limit", "40")

        self.assertEqual(limited.returncode, 0, limited.stderr)
        self.assertEqual(sum(line.startswith("1  ") or line.startswith("2  ") for line in limited.stdout.splitlines()), 2)
        self.assertEqual(capped.returncode, 0, capped.stderr)
        self.assertLessEqual(len(capped.stdout), search.OUTPUT_LIMIT)

    def test_fts_syntax_characters_are_quoted_as_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(document("Syntax", "NEAR search syntax."), encoding="utf-8")

            result = run(root, '" * - NEAR :')

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_query_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)

            result = run(root, "the and of")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "query has no searchable words")

    def test_no_hit_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)

            result = run(root, "unmatched")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "no sections match\n")

    def test_search_is_listed_as_a_py_module(self) -> None:
        pyproject = (TOOLING / "pyproject.toml").read_text(encoding="utf-8")
        module_list = pyproject.split("py-modules = [", 1)[1].split("]", 1)[0]
        self.assertIn('"search"', module_list)

    def test_failure_prints_to_stderr_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            with patch.object(search, "_persistent_search", side_effect=RuntimeError("failed to read")):
                with patch("sys.stderr", new_callable=lambda: _TextStream()) as stderr:
                    result = search.main(["topic", "--cwd", str(root)])

        self.assertEqual(result, 1)
        self.assertIn("bkf search: failed to read", stderr.output)


class PersistentIndexTests(unittest.TestCase):
    def make_root(self, root: Path) -> Path:
        make_bundle(root)
        (root / "guide.md").write_text(document("Guide", "oldneedle"), encoding="utf-8")
        return root

    def test_document_edit_and_removal_refresh_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            self.assertIn("/guide.md", run(root, "oldneedle").stdout)
            (root / "guide.md").write_text(document("Guide", "newneedle and longer"), encoding="utf-8")
            self.assertIn("/guide.md", run(root, "newneedle").stdout)
            self.assertEqual(run(root, "oldneedle").stdout, "no sections match\n")
            (root / "guide.md").unlink()
            self.assertEqual(run(root, "newneedle").stdout, "no sections match\n")

    def test_sidecar_add_edit_remove_and_config_edit_refresh_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            (root / "search.yaml").write_text(
                "attached_text:\n  - documents: '*.md'\n    text: '{stem}.txt'\n", encoding="utf-8"
            )
            self.assertEqual(run(root, "sidecarfirst").stdout, "no sections match\n")
            (root / "guide.txt").write_text("sidecarfirst", encoding="utf-8")
            self.assertIn("/guide.md", run(root, "sidecarfirst").stdout)
            (root / "guide.txt").write_text("sidecarsecond", encoding="utf-8")
            self.assertIn("/guide.md", run(root, "sidecarsecond").stdout)
            self.assertEqual(run(root, "sidecarfirst").stdout, "no sections match\n")
            (root / "search.yaml").write_text(
                "attached_text:\n  - documents: '*.md'\n    text: 'alternate.txt'\n", encoding="utf-8"
            )
            (root / "alternate.txt").write_text("configchanged", encoding="utf-8")
            self.assertIn("/guide.md", run(root, "configchanged").stdout)
            (root / "alternate.txt").unlink()
            self.assertEqual(run(root, "configchanged").stdout, "no sections match\n")

    def test_unchanged_call_parses_no_member_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            (root / "untracked.md").write_text("plain text", encoding="utf-8")
            (root / "feedback.md").write_text(document("Feedback", "plain", profile="feedback"), encoding="utf-8")
            self.assertTrue(any(hit.path == "/guide.md" for hit, _ in search.search_bundle(root, "oldneedle", limit=5)))
            from bkf_common import parse_markdown
            parsed_paths = []

            def record_parse(path):
                parsed_paths.append(Path(path))
                return parse_markdown(path)

            with patch("bkf_common.parse_markdown", side_effect=record_parse):
                self.assertTrue(any(hit.path == "/guide.md" for hit, _ in search.search_bundle(root, "oldneedle", limit=5)))
            self.assertTrue(all(path.name == "MAP.md" for path in parsed_paths), parsed_paths)

    def test_changed_documents_are_indexed_after_one_membership_walk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            search.search_bundle(root, "oldneedle", limit=5)
            (root / "guide.md").write_text(document("Guide", "changedneedle"), encoding="utf-8")
            with patch.object(search, "_candidate_documents", wraps=search._candidate_documents) as candidates:
                hits = search.search_bundle(root, "changedneedle", limit=5)
            self.assertEqual(candidates.call_count, 1)
            self.assertTrue(any(hit.path == "/guide.md" for hit, _ in hits))

    def test_corrupt_cache_is_rebuilt_and_unavailable_cache_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            cache_root = Path(_SEARCH_CACHE.name)
            cache_path = cache_root / (search.hashlib.sha256(str(root.resolve()).encode()).hexdigest() + ".sqlite3")
            cache_path.write_bytes(b"not a sqlite database")
            self.assertIn("/guide.md", run(root, "oldneedle").stdout)
            self.assertIn(b"SQLite", cache_path.read_bytes()[:200])
            with tempfile.NamedTemporaryFile() as occupied:
                result = subprocess.run(
                    [sys.executable, str(CLI), "search", "oldneedle", "--cwd", str(root)],
                    check=False, capture_output=True, text=True,
                    env={**os.environ, "BKF_SEARCH_CACHE": occupied.name},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("/guide.md", result.stdout)
                self.assertEqual(result.stderr, "")
                result = subprocess.run(
                    [sys.executable, str(CLI), "search", "oldneedle", "--cwd", str(root), "--debug"],
                    check=False, capture_output=True, text=True,
                    env={**os.environ, "BKF_SEARCH_CACHE": occupied.name},
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/guide.md", result.stdout)
            self.assertIn("using memory", result.stderr)
            self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_broken_frontmatter_is_reported_again_on_second_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            (root / "guide.md").write_text("---\n: [ broken\n---\nneedle\n", encoding="utf-8")
            for _ in range(2):
                result = run(root, "needle")
                self.assertEqual(result.returncode, 1)
                self.assertIn("guide.md", result.stderr)

    def test_two_processes_can_build_the_same_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(Path(directory))
            def invoke() -> subprocess.CompletedProcess[str]:
                return run(root, "oldneedle")
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: invoke(), range(2)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/guide.md", result.stdout)


VOCABULARY = """\
ai: [artificial intelligence, inteligência artificial]
thesis: []
"""


def paths(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.split()[1] for line in result.stdout.splitlines() if line[:1].isdigit()]


class TagSearchTests(unittest.TestCase):
    def test_tag_is_indexed_for_every_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tagged.md").write_text(
                document("Notes", "Intro.\n\n## Other\n\nMore words.", tags="zebra"), encoding="utf-8"
            )
            (root / "plain.md").write_text(document("Other notes", "Plain words."), encoding="utf-8")

            result = run(root, "zebra")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(paths(result), ["/tagged.md"])
        self.assertEqual(sum(line.strip().startswith("§ ") for line in result.stdout.splitlines()), 2)
        self.assertIn("§ Notes > Other", result.stdout)

    def test_tag_column_does_not_change_ranking_of_other_queries(self) -> None:
        sections = [
            search.Section("/a.md", "Alpha", "", "needle " + "x " * 5, "Alpha", ("a", "b", "c", "d")),
            search.Section("/b.md", "Beta", "", "needle " + "x " * 5, "Beta", ()),
            search.Section("/c.md", "Gamma", "", "needle", "Gamma", ("long tag list here", "more")),
        ]
        stripped = [search.Section(s.path, s.heading, s.description, s.body, s.title) for s in sections]

        ranked = [(hit.path, rank) for hit, rank in search._search(sections, ["needle"], 5)]
        self.assertEqual(ranked, [(hit.path, rank) for hit, rank in search._search(stripped, ["needle"], 5)])

    def test_single_word_synonym_expands_to_canonical_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text("ai: [robotics]\n", encoding="utf-8")
            (root / "tagged.md").write_text(document("Notes", "Unrelated text.", tags="ai"), encoding="utf-8")
            (root / "other.md").write_text(document("Other", "Nothing here."), encoding="utf-8")

            with_vocabulary = run(root, "robotics")
            (root / "tag-vocabulary.yaml").unlink()
            without = run(root, "robotics")

        self.assertEqual(paths(with_vocabulary), ["/tagged.md"])
        self.assertEqual(without.stdout, "no sections match\n")

    def test_multi_word_synonym_matches_contiguous_words_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text(VOCABULARY, encoding="utf-8")
            (root / "tagged.md").write_text(document("Notes", "Unrelated text.", tags="ai"), encoding="utf-8")

            together = run(root, "what is artificial intelligence?")
            canonical = run(root, "tell me about ai")
            apart = run(root, "intelligence of an artificial lake")

        self.assertEqual(paths(together), ["/tagged.md"])
        self.assertEqual(paths(canonical), ["/tagged.md"])
        self.assertEqual(apart.stdout, "no sections match\n")

    def test_canonical_tag_adds_its_synonyms_to_the_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text(VOCABULARY, encoding="utf-8")
            (root / "pt.md").write_text(document("Portugues", "Texto sobre inteligência artificial."), encoding="utf-8")

            result = run(root, "ai")

        self.assertEqual(paths(result), ["/pt.md"])

    def test_invalid_vocabulary_fails_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "tag-vocabulary.yaml").write_text("ai: not-a-list\n", encoding="utf-8")

            result = run(root, "needle")

        self.assertEqual(result.returncode, 1)
        self.assertIn("tag-vocabulary.yaml", result.stderr)

    def test_attached_text_is_indexed_as_located_passages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "*.md"\n    text: "{stem}.txt"\n'
                '    locator:\n      pattern: "^PAGE (?P<page>[0-9]+)$"\n'
                '      labels:\n        - label: "Page {page}"\n', encoding="utf-8"
            )
            (root / "guide.md").write_text(document("Guide", "Section searchablewords."), encoding="utf-8")
            prefix = " ".join(f"opening{n}" for n in range(25))
            located = " ".join(f"located{n}" for n in range(25)) + " passageonlyword"
            (root / "guide.txt").write_text(f"{prefix}\nPAGE 7\n{located}\n", encoding="utf-8")

            located_result = run(root, "passageonlyword")
            prefix_result = run(root, "opening3")
            section_result = run(root, "searchablewords")

        self.assertIn("Page 7  ", located_result.stdout)
        self.assertIn("passageonlyword", located_result.stdout)
        self.assertIn("(text)  ", prefix_result.stdout)
        self.assertIn("/guide.md", section_result.stdout)

    def test_attached_passage_filters_and_heading_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "**/*.md"\n    text: "{stem}.txt"\n', encoding="utf-8"
            )
            (root / "sub").mkdir()
            (root / "sub" / "guide.md").write_text(
                document("Guide", "Section text.", tags="alpha"), encoding="utf-8"
            )
            (root / "sub" / "guide.txt").write_text(" ".join(f"sidecar{n}" for n in range(25)) + " filterword", encoding="utf-8")

            unfiltered = run(root, "filterword")
            path_filtered = run(root, "filterword", "--path", "sub")
            tag_filtered = run(root, "filterword", "--tag", "alpha")
            tag_excluded = run(root, "filterword", "--tag", "beta")
            heading_filtered = run(root, "filterword", "--heading", "Guide")

        self.assertIn("1  /sub/guide.md", unfiltered.stdout)
        self.assertIn("1  /sub/guide.md", path_filtered.stdout)
        self.assertIn("1  /sub/guide.md", tag_filtered.stdout)
        self.assertEqual(tag_excluded.stdout, "no sections match\n")
        self.assertEqual(heading_filtered.stdout, "no sections match\n")

    def test_attached_text_tag_query_only_boosts_document_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "*.md"\n    text: "{stem}.txt"\n', encoding="utf-8"
            )
            (root / "guide.md").write_text(document("Guide", "ordinary section words.", tags="zebra"), encoding="utf-8")
            (root / "guide.txt").write_text(" ".join(f"passage{n}" for n in range(25)), encoding="utf-8")

            result = run(root, "zebra", "--limit", "10")

        self.assertIn("1  /guide.md", result.stdout.splitlines()[0])
        self.assertNotIn("(text)  ", result.stdout)

    def test_missing_sidecar_keeps_document_sections_searchable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "*.md"\n    text: "{stem}.txt"\n', encoding="utf-8"
            )
            (root / "guide.md").write_text(document("Guide", "sectiononlyword"), encoding="utf-8")

            result = run(root, "sectiononlyword")

        self.assertIn("/guide.md", result.stdout)
        self.assertNotIn("(text)  ", result.stdout)

    def test_gitignored_attached_sidecar_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            make_bundle(root)
            (root / ".gitignore").write_text("*.txt\n", encoding="utf-8")
            (root / "search.yaml").write_text(
                'attached_text:\n  - documents: "*.md"\n    text: "{stem}.txt"\n', encoding="utf-8"
            )
            (root / "guide.md").write_text(document("Guide", "nothing relevant."), encoding="utf-8")
            (root / "guide.txt").write_text(
                " ".join(f"ignored{n}" for n in range(25)) + " ignoredsidecarword", encoding="utf-8"
            )

            result = run(root, "ignoredsidecarword")

        self.assertIn("(text)  ", result.stdout)

    def test_invalid_search_config_fails_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "search.yaml").write_text("attached_text: nope\n", encoding="utf-8")
            (root / "guide.md").write_text(document("Guide", "searchable."), encoding="utf-8")

            result = run(root, "searchable")

        self.assertEqual(result.returncode, 1)
        self.assertIn("search.yaml", result.stderr)


class FilterTests(unittest.TestCase):
    def make(self, root: Path) -> None:
        make_bundle(root)
        (root / "sub").mkdir()
        (root / "sub" / "inner.md").write_text(
            document("Inner", "Intro needle.\n\n## Rules\n\nneedle rule.", tags="alpha, beta"), encoding="utf-8"
        )
        (root / "outer.md").write_text(
            document("Outer", "Intro needle.\n\n## Rules\n\nneedle rule.\n\n### Deep\n\nneedle deep.", tags="alpha"),
            encoding="utf-8",
        )
        (root / "sub2.md").write_text(document("Sub two", "needle again.", tags="beta"), encoding="utf-8")

    def test_path_directory_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            directory_result = run(root, "needle", "--path", "sub", "--limit", "20")
            file_result = run(root, "needle", "--path", "outer.md", "--limit", "20")
            from_subdirectory = subprocess.run(
                [sys.executable, str(CLI), "search", "needle", "--path", ".", "--cwd", str(root / "sub"), "--limit", "20"],
                check=False, capture_output=True, text=True,
                env={**os.environ, "BKF_SEARCH_CACHE": _SEARCH_CACHE.name},
            )

        self.assertEqual(set(paths(directory_result)), {"/sub/inner.md"})
        self.assertEqual(set(paths(file_result)), {"/outer.md"})
        self.assertEqual(set(paths(from_subdirectory)), {"/sub/inner.md"})

    def test_path_dot_at_bundle_root_keeps_all_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)
            result = run(root, "needle", "--path", ".", "--limit", "20")
        self.assertEqual(set(paths(result)), {"/outer.md", "/sub/inner.md", "/sub2.md"})

    def test_path_outside_the_bundle_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            root.mkdir()
            self.make(root)

            result = run(root, "needle", "--path", "..")

        self.assertEqual(result.returncode, 2)
        self.assertIn("outside the bundle", result.stderr)

    def test_heading_matches_own_heading_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            rules = run(root, "needle", "--heading", "rules", "--limit", "20")
            deep = run(root, "needle", "--heading", "DEEP", "--limit", "20")
            trail = run(root, "needle", "--heading", "Outer > Rules", "--limit", "20")

        self.assertEqual(sorted(paths(rules)), ["/outer.md", "/sub/inner.md"])
        self.assertNotIn("Deep", rules.stdout)
        self.assertEqual(paths(deep), ["/outer.md"])
        self.assertIn("§ Outer > Rules > Deep", deep.stdout)
        self.assertEqual(trail.stdout, "no sections match\n")

    def test_heading_filter_casefolds_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            (root / "guide.md").write_text(document("Überblick", "needle"), encoding="utf-8")
            result = run(root, "needle", "--heading", "überblick")
        self.assertEqual(paths(result), ["/guide.md"])

    def test_tag_filter_requires_all_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            alpha = run(root, "needle", "--tag", "alpha", "--limit", "20")
            both = run(root, "needle", "--tag", "alpha", "--tag", "BETA", "--limit", "20")

        self.assertEqual(set(paths(alpha)), {"/outer.md", "/sub/inner.md"})
        self.assertEqual(set(paths(both)), {"/sub/inner.md"})

    def test_tag_filter_resolves_synonyms_with_a_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)
            (root / "tag-vocabulary.yaml").write_text("alpha: [first letter]\nbeta: []\n", encoding="utf-8")

            with_vocabulary = run(root, "needle", "--tag", "first letter", "--limit", "20")
            (root / "tag-vocabulary.yaml").unlink()
            without = run(root, "needle", "--tag", "first letter", "--limit", "20")

        self.assertEqual(set(paths(with_vocabulary)), {"/outer.md", "/sub/inner.md"})
        self.assertEqual(without.stdout, "no sections match\n")

    def test_filters_combine_with_and(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make(root)

            result = run(root, "needle", "--path", "sub", "--heading", "Rules", "--tag", "beta", "--limit", "20")
            empty = run(root, "needle", "--path", "outer.md", "--tag", "beta", "--limit", "20")

        self.assertEqual(paths(result), ["/sub/inner.md"])
        self.assertIn("§ Inner > Rules", result.stdout)
        self.assertEqual(empty.stdout, "no sections match\n")


class _TextStream:
    def __init__(self) -> None:
        self.output = ""

    def write(self, value: str) -> int:
        self.output += value
        return len(value)

    def flush(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()

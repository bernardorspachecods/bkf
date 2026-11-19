from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import source_store
from bkf_cli import main
from bkf_common import parse_markdown
from source_page import SNAPSHOT_HEADER, FetchedPage, extract_page, fetch_page
from source_record import SOURCE_SCHEMA, render_record
from source_store import add, lookup_url, normalize_url, resolve_store_path


ARTICLE = """\
<html><head>
<link rel="canonical" href="https://example.com/news/ratchets">
<meta property="og:title" content="Lower priority title">
<meta name="author" content="Lower priority author">
<meta property="article:modified_time" content="2025-02-03T04:00:00Z">
<title>Fallback title</title>
<script type="application/ld+json">
{"@graph":[{"@type":"WebSite","name":"Site Name"},
{"@type":"NewsArticle","headline":"A Ratchet for the Future of Great Testing Tools",
"author":[{"@type":"Person","name":"Mária Garcìa"}],"datePublished":"2024-05-02T12:34:00Z"}]}
</script></head><body>
<nav>Hidden navigation<h2>Wrong heading</h2></nav><style>Hidden style</style>
<main><h1>Ratchets</h1><p>Ratchets keep <em>the bar</em> high.</p>
<h2>Incremental <code>checks</code></h2><p>It’s a “small step”<br>at a time.</p></main>
<script>Hidden script</script></body></html>
"""


def dns_answer(address: str, port: int) -> list[tuple]:
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    endpoint = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", endpoint)]


def response_socket(response: bytes) -> Mock:
    connection = Mock()
    connection.makefile.return_value = io.BytesIO(response)
    return connection


def html_response(body: bytes, content_type: bytes = b"text/html") -> bytes:
    return b"HTTP/1.1 200 OK\r\nContent-Type: " + content_type + b"\r\n\r\n" + body


class SourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "store"
        environment = patch.dict(os.environ, {"BKF_SOURCES_DIR": str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)
        self.assert_cli(0, "init")

    def assert_cli(self, expected: int, *args: str) -> tuple[str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                status = main(["sources", *args])
            except SystemExit as exc:
                status = exc.code
        self.assertEqual(status, expected, stdout.getvalue() + stderr.getvalue())
        return stdout.getvalue().strip(), stderr.getvalue().strip()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True,
        ).stdout.strip()

    def path(self, source_id: str) -> Path:
        return self.root / "records" / source_id / f"{source_id}.md"

    def ext(self, source_id: str) -> dict:
        return parse_markdown(self.path(source_id)).frontmatter["ext"]

    def validate(self, expected: int = 0) -> str:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = main(["validate", str(self.root)])
        self.assertEqual(status, expected, stdout.getvalue())
        return stdout.getvalue()

    def test_init_creates_bundle_once_and_refuses_other_directories(self) -> None:
        self.validate()
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assert_cli(0, "init", "--dir", str(self.root))
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        other = self.root.parent / "other"
        other.mkdir()
        (other / "keep").write_text("data")
        self.assert_cli(1, "init", "--dir", str(other))
        self.assertEqual(list(other.iterdir()), [other / "keep"])
        self.assertEqual(resolve_store_path(), self.root)

    def test_init_upgrades_an_existing_schema_and_check_names_the_fix(self) -> None:
        requested = "https://example.com/old"
        final = "https://example.org/new"
        with contextlib.redirect_stderr(io.StringIO()):
            source_id = add(requested, fetch=lambda _: FetchedPage(final, "<p>Moved.</p>"))
        schema_path = self.root / "ext-schema.yaml"
        schema = json.loads(schema_path.read_text())
        ext_fields = schema["properties"]["ext"]["properties"]
        ext_fields["custom"] = {"type": "string"}
        legacy = ext_fields.pop("redirected_to")
        schema_path.write_text(json.dumps(schema))
        source_store._commit(self.root, "Save legacy store schema", Path("ext-schema.yaml"))
        head = self.git("rev-parse", "HEAD")
        original = schema_path.read_bytes()
        self.assertIn("redirected_to", self.validate(1))

        for ids in ((), (source_id,)):
            output, _ = self.assert_cli(1, "check", *ids)
            self.assertIn("ext-schema.yaml", output)
            self.assertIn("bkf sources init", output)
        self.assertEqual(schema_path.read_bytes(), original)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

        with patch("source_store._commit", side_effect=source_store.StoreError("commit failed")):
            _, error = self.assert_cli(1, "init")
        self.assertIn("commit failed", error)
        self.assertEqual(schema_path.read_bytes(), original)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

        self.assert_cli(0, "init", "--dir", str(self.root))
        self.assertEqual(self.git("diff", "--name-only", head, "HEAD"), "ext-schema.yaml")
        ext_fields["redirected_to"] = legacy
        self.assertEqual(json.loads(self.git("show", "HEAD:ext-schema.yaml")), schema)
        self.validate()
        self.assert_cli(0, "check", source_id)
        head = self.git("rev-parse", "HEAD")
        self.assert_cli(0, "init")
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

    def test_init_replaces_outdated_definitions_for_existing_fields(self) -> None:
        schema_path = self.root / "ext-schema.yaml"
        schema = json.loads(schema_path.read_text())
        fields = schema["properties"]["ext"]["properties"]
        for name in ("url", "aliases", "published", "updated", "consulted", "completions"):
            fields[name] = {}
        fields["custom"] = {"type": "string"}
        schema_path.write_text(json.dumps(schema))

        self.assertIn("source schema is out of date", self.assert_cli(1, "check")[0])
        self.assert_cli(0, "init")
        upgraded = json.loads(schema_path.read_text())["properties"]["ext"]["properties"]
        self.assertEqual(upgraded, SOURCE_SCHEMA["properties"]["ext"]["properties"] | {"custom": {"type": "string"}})
        self.assert_cli(0, "check")

    def test_normalize_url(self) -> None:
        self.assertEqual(
            normalize_url("HTTP://WWW.Example.COM:80/Path/?z=2&utm_source=1&fbclid=x"
                          "&gclid=y&REF=z&mc_cid=w&a=3&a=1&blank=#section"),
            "https://example.com/Path?REF=z&a=1&a=3&blank=&z=2",
        )
        self.assertEqual(normalize_url("https://Example.com"), "https://example.com/")

    def test_content_selecting_urls_have_distinct_records(self) -> None:
        base = "https://github.com/example/tools"
        urls = [base + suffix for suffix in ("?ref=v1", "?ref=v2", "#/docs", "#!/docs")]
        html = f'<link rel="canonical" href="{base}"><p>Text</p>'
        ids = [add(url, fetch=lambda url: FetchedPage(url, html)) for url in urls]
        self.assertEqual(len(set(ids)), len(urls))
        self.assertEqual([lookup_url(url).id for url in urls], ids)
        self.assertIsNone(lookup_url(base))

    def test_add_extracts_graph_keeps_snapshot_and_deduplicates_both_aliases(self) -> None:
        requested = "http://example.com/go/ratchets"
        redirected = "https://www.example.com/go/ratchets"
        canonical = "https://example.com/news/ratchets"
        with patch("source_store.fetch_page", return_value=FetchedPage(redirected, ARTICLE)) as fetch:
            source_id, error = self.assert_cli(0, "add", requested, "--via", "lint ratchets")
            self.assertEqual(error, "")
            self.assertEqual(source_id, "garcia-ratchet-future-great-testing")
            head = self.git("rev-parse", "HEAD")
            before = self.path(source_id).read_bytes()
            for url in (requested + "?utm_campaign=ignore", redirected, canonical + "/#heading"):
                self.assertEqual(self.assert_cli(3, "add", url), (source_id, ""))
                match = lookup_url(url)
                self.assertEqual((match.id, match.path, match.has_snapshot), (source_id, self.path(source_id), True))
            fetch.assert_called_once()
            self.assertEqual(fetch.call_args.args, (requested,))
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.path(source_id).read_bytes(), before)
        ext = self.ext(source_id)
        self.assertEqual(ext["url"], canonical)
        self.assertEqual(ext["aliases"], [requested, redirected])
        self.assertNotIn("redirected_to", ext)
        self.assertEqual(ext["published"], "2024-05-02")
        self.assertEqual(ext["updated"], "2025-02-03")
        self.assertEqual(ext["author"], "Mária Garcìa")
        self.assertEqual(ext["consulted"], [date.today().isoformat()])
        self.assertEqual(ext["via"], "lint ratchets")
        self.assertEqual(ext["snapshot"], "web")
        snapshot = self.path(source_id).with_suffix(".txt")
        self.assertEqual(snapshot.read_text(), "## Ratchets\nRatchets keep the bar high.\n"
                         "## Incremental checks\nIt’s a “small step”\nat a time.\n")
        self.assertNotIn(snapshot.name, self.git("ls-files"))
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.validate()

    def test_http_redirect_elsewhere_keeps_cited_url_and_upgrades_existing_schema(self) -> None:
        requested = "https://polaris.shopify.com/tools/stylelint-polaris"
        final = "https://shopify.dev/docs/api/polaris"
        html = "<title>Polaris</title><main>Build with Polaris.</main>"
        schema_path = self.root / "ext-schema.yaml"
        schema = json.loads(schema_path.read_text())
        schema["properties"]["ext"]["properties"].pop("redirected_to", None)
        schema_path.write_text(json.dumps(schema))

        with patch("source_store.fetch_page", return_value=FetchedPage(final, html)) as fetch:
            source_id, warning = self.assert_cli(0, "add", requested)
            self.assertEqual(self.assert_cli(3, "add", requested), (source_id, ""))
            self.assertIsNone(lookup_url(final))
            destination_id, destination_warning = self.assert_cli(0, "add", final)
            self.assertNotEqual(destination_id, source_id)
            self.assertEqual(destination_warning, "")
            self.assertEqual(lookup_url(final).id, destination_id)
            self.assertEqual([call.args[0] for call in fetch.call_args_list], [requested, final])
        self.assertIn(f"{requested} redirected to {final}", warning)
        self.assertIn("--status discarded --reason dead", warning)
        ext = self.ext(source_id)
        self.assertEqual((ext["url"], ext["redirected_to"], ext["aliases"]), (requested, final, []))
        self.assertEqual((ext["title"], ext["author"], ext["kind"], ext["status"]),
                         ("Polaris", "shopify", "docs", "pending"))
        self.assertEqual(self.path(source_id).with_suffix(".txt").read_text(), "Build with Polaris.\n")
        self.assertEqual(json.loads(self.git("show", "HEAD:ext-schema.yaml")),
                         json.loads(schema_path.read_text()))
        self.validate()

    def test_http_redirect_with_canonical_matching_request_is_the_same_page(self) -> None:
        requested = "http://www.example.com/news/ratchets/"
        final = "https://example.com/news/edition"
        canonical = "https://example.com/news/ratchets"
        with patch("source_store.fetch_page", return_value=FetchedPage(final, ARTICLE)):
            source_id, warning = self.assert_cli(0, "add", requested)
        self.assertEqual(warning, "")
        ext = self.ext(source_id)
        self.assertEqual((ext["url"], ext["aliases"]), (canonical, [requested, final]))
        self.assertNotIn("redirected_to", ext)

    def test_script_redirect_fetches_atlassian_usage_page(self) -> None:
        requested = "https://atlassian.design/components/eslint-plugin-design-system/ensure-design-token-usage"
        final = requested + "/usage"
        redirect = "<script>location.replace('ensure-design-token-usage/usage');</script>"
        usage = "<title>Ensure design token usage</title><main><h1>Usage</h1><p>Use design tokens.</p></main>"
        pages = {requested: FetchedPage(requested, redirect), final: FetchedPage(final, usage)}
        with patch("source_store.fetch_page", side_effect=lambda url, **_: pages[url]) as fetch:
            source_id, warning = self.assert_cli(0, "add", requested)
            self.assertIsNone(lookup_url(final))
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [requested, final])
        self.assertEqual(source_id, "atlassian-ensure-design-token-usage")
        self.assertIn(f"{requested} redirected to {final}", warning)
        ext = self.ext(source_id)
        self.assertEqual((ext["url"], ext["redirected_to"], ext["title"], ext["author"]),
                         (requested, final, "Ensure design token usage", "atlassian"))
        self.assertEqual(self.path(source_id).with_suffix(".txt").read_text(), "## Usage\nUse design tokens.\n")

    def test_meta_refresh_resolves_against_http_destination_without_adding_aliases(self) -> None:
        requested = "https://example.com/old"
        intermediate = "https://example.com/moved/index"
        final = "https://example.com/moved/next?x=1&y=2"
        canonical = "https://example.com/current"
        refresh = """<meta http-equiv="Refresh" content="0; URL='next?x=1&amp;y=2'">"""
        target = f'<link rel="canonical" href="{canonical}"><title>Current</title><p>Current page.</p>'
        pages = {requested: FetchedPage(intermediate, refresh), final: FetchedPage(final, target)}
        with patch("source_store.fetch_page", side_effect=lambda url, **_: pages[url]) as fetch:
            source_id, warning = self.assert_cli(0, "add", requested)
            self.assertIsNone(lookup_url(final))
            self.assertIsNone(lookup_url(canonical))
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [requested, final])
        self.assertIn(f"{requested} redirected to {final}", warning)
        ext = self.ext(source_id)
        self.assertEqual((ext["url"], ext["redirected_to"], ext["aliases"]),
                         (requested, final, []))

    def test_script_redirect_follows_only_one_hop_in_a_loop(self) -> None:
        for index, script in enumerate(('location.href = "next";', "window.location = 'next'")):
            with self.subTest(script=script):
                requested = f"https://example.com/{index}/start"
                final = f"https://example.com/{index}/next"
                pages = {
                    requested: FetchedPage(requested, f"<script>{script}</script>"),
                    final: FetchedPage(final, "<script>location.replace('start')</script>"),
                }
                with patch("source_store.fetch_page", side_effect=lambda url, **_: pages[url]) as fetch:
                    source_id, warning = self.assert_cli(0, "add", requested)
                self.assertEqual([call.args[0] for call in fetch.call_args_list], [requested, final])
                self.assertIn("page contained no readable text", warning)
                ext = self.ext(source_id)
                self.assertEqual((ext["url"], ext["redirected_to"], ext["snapshot"]),
                                 (requested, final, "none"))

    def test_non_literal_or_inert_redirects_do_not_trigger_a_fetch(self) -> None:
        url = "https://example.com/start"
        html = """<script>if (false) location.replace('next');</script>
        <script type='application/json'>location.href = 'next'</script>
        <script src='external.js'>window.location = 'next'</script>
        <meta http-equiv='refresh' content='0; url=javascript:void(0)'>
        <main>Original page.</main>"""
        with patch("source_store.fetch_page", return_value=FetchedPage(url, html)) as fetch:
            source_id, warning = self.assert_cli(0, "add", url)
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args, (url,))
        self.assertEqual(warning, "")
        self.assertNotIn("redirected_to", self.ext(source_id))

    def test_two_cited_pages_redirect_to_an_already_registered_destination(self) -> None:
        destination = "https://example.com/known"
        destination_id = add(destination, manual=True, title="Known")
        before = self.path(destination_id).read_bytes()
        ids = {destination_id}
        with patch("source_store.fetch_page", return_value=FetchedPage(destination, "<p>Landing page</p>")):
            for requested in ("https://example.com/old", "https://example.com/other"):
                source_id, warning = self.assert_cli(0, "add", requested)
                self.assertNotIn(source_id, ids)
                ids.add(source_id)
                self.assertIn(f"{requested} redirected to {destination}", warning)
                ext = self.ext(source_id)
                self.assertEqual((ext["url"], ext["redirected_to"], ext["aliases"]), (requested, destination, []))
                self.assertEqual(lookup_url(requested).id, source_id)
        self.assertEqual(self.path(destination_id).read_bytes(), before)
        self.assertEqual(lookup_url(destination).id, destination_id)

    def test_legacy_other_page_redirect_aliases_do_not_claim_the_landing_page(self) -> None:
        requested = "https://example.com/old"
        destination = "https://example.com/current"
        canonical = destination + "/canonical"
        source_id = add(requested, manual=True, title="Old")
        path = self.path(source_id)
        parsed = parse_markdown(path)
        parsed.frontmatter["ext"].update(redirected_to=destination, aliases=[destination, canonical])
        path.write_text(render_record(parsed.frontmatter, parsed.body), encoding="utf-8")

        self.assertEqual(lookup_url(requested).id, source_id)
        for url in (destination, canonical):
            self.assertIsNone(lookup_url(url))

        new_destination = "https://example.org/new"
        with contextlib.redirect_stderr(io.StringIO()):
            source_store.refresh(self.root, source_id, requested,
                                 fetch=lambda _: FetchedPage(new_destination, "<p>Moved again.</p>"))
        self.assertEqual(self.ext(source_id)["redirected_to"], new_destination)
        for url in (destination, canonical, new_destination):
            self.assertIsNone(lookup_url(url))
            self.assertNotEqual(add(url, manual=True, title="Current"), source_id)

    def test_redirecting_refresh_keeps_existing_text_and_a_same_page_refresh_clears_the_redirect(self) -> None:
        url = "https://example.com/news/ratchets"
        landing = "https://example.com/landing"
        source_id = add(url, fetch=lambda _: FetchedPage(url, "<p>Original text.</p>"))
        snapshot = self.path(source_id).with_suffix(".txt")
        original = snapshot.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            source_store.refresh(self.root, source_id, url,
                                 fetch=lambda _: FetchedPage(landing, "<p>Landing page text.</p>"))
            self.assertEqual(self.ext(source_id)["redirected_to"], landing)
            self.assertEqual(snapshot.read_bytes(), original)
            self.assertEqual(self.ext(source_id)["snapshot"], "web")

            # A refresh that lands on the same page clears the redirect, and its text is the page's again.
            changes = source_store.refresh(self.root, source_id, url,
                                           fetch=lambda _: FetchedPage(url, "<p>Same page text.</p>"))
        self.assertIn("redirected_to", changes)
        self.assertNotIn("redirected_to", self.ext(source_id))
        self.assertIn("Same page text.", snapshot.read_text())
        self.validate()

    def test_redirecting_refresh_saves_the_landing_text_only_when_there_was_none(self) -> None:
        url = "https://example.com/old"
        landing = "https://example.com/landing"
        source_id = add(url, manual=True, title="Old")
        self.assertFalse(self.path(source_id).with_suffix(".txt").exists())
        with contextlib.redirect_stderr(io.StringIO()):
            source_store.refresh(self.root, source_id, url,
                                 fetch=lambda _: FetchedPage(landing, "<p>Landing page text.</p>"))
        self.assertIn("Landing page text.", self.path(source_id).with_suffix(".txt").read_text())
        self.assertEqual(self.ext(source_id)["snapshot"], "web")

    def test_a_failed_refresh_keeps_the_recorded_redirect(self) -> None:
        url = "https://example.com/news/ratchets"
        landing = "https://example.com/landing"
        source_id = add(url, fetch=lambda _: FetchedPage(landing, "<p>Landing page text.</p>"))
        self.assertEqual(self.ext(source_id)["redirected_to"], landing)

        def offline(_: str) -> FetchedPage:
            raise OSError("offline")
        with contextlib.redirect_stderr(io.StringIO()):
            source_store.refresh(self.root, source_id, url, fetch=offline)
        self.assertEqual(self.ext(source_id)["redirected_to"], landing)

    def test_urls_with_characters_a_browser_encodes_are_captured_once(self) -> None:
        fonts = "https://fonts.example.org/css?family=Roboto|Open+Sans"
        spaced = "https://example.com/my page?q={a b}#top"
        for url, stored in ((fonts, "family=Roboto%7COpen+Sans"), (spaced, "/my%20page?q=%7Ba%20b%7D")):
            with self.subTest(url=url):
                with patch("source_store.fetch_page", side_effect=lambda link, **_: FetchedPage(link, "<p>Text.</p>")):
                    source_id = self.assert_cli(0, "add", f"  {url}  ")[0]
                    self.assertIn(stored, self.ext(source_id)["url"])
                    self.assertEqual(self.assert_cli(3, "add", url), (source_id, ""))
                    self.assertEqual(self.assert_cli(3, "add", self.ext(source_id)["url"]), (source_id, ""))
                self.assertEqual(lookup_url(url).id, source_id)
                self.assertEqual(lookup_url(f" {url}\n").id, source_id)
        self.assert_cli(0, "check")

    def test_meta_fallbacks_and_cross_site_canonical(self) -> None:
        url = "https://docs.example.co.uk/guide"
        html = """<link rel='canonical' href='https://example.net/guide'>
        <meta property='og:title' content='The Meta Guide'>
        <meta name='citation_author' content='Anne Smith'>
        <meta name='citation_publication_date' content='2025/11/19'>
        <script type='application/ld+json'>{"datePublished":"invalid"}</script>
        <title>Lower priority</title><h1>Guide</h1>"""
        source_id = add(url, fetch=lambda _: FetchedPage(url, html))
        ext = self.ext(source_id)
        self.assertEqual(source_id, "smith-meta-guide")
        self.assertEqual((ext["url"], ext["kind"], ext["author"]), (url, "docs", "Anne Smith"))
        self.assertEqual((ext["published"], ext["updated"]), ("2025-11-19", "unknown"))
        blank_url = "https://example.co.uk/blank"
        source_id = add(blank_url, fetch=lambda _: FetchedPage(blank_url, "<p>Body</p>"))
        ext = self.ext(source_id)
        self.assertEqual((source_id, ext["title"], ext["author"], ext["published"]),
                         ("example-blank", "unknown", "example", "unknown"))

    def test_readable_ids_for_migration_pages(self) -> None:
        cases = (
            ("https://ai.engineer/code/2026/talks/walden-yan",
             "<head><title>AI Engineer</title></head>", "ai-engineer-walden-yan", "ai"),
            ("https://socket.dev/npm/package/eslint-seatbelt",
             None, "socket-eslint-seatbelt", "socket"),
            ("https://github.com/imbue-ai/ratchets",
             '<meta property="og:site_name" content="GitHub"><title>GitHub - imbue-ai/ratchets</title>',
             "imbue-ai-ratchets", "imbue-ai"),
            ("https://ast-grep.github.io/guide/project/lint-rule",
             "<title>Lint Rule | ast-grep</title>", "ast-grep-lint-rule", "ast-grep"),
            ("https://www.w3.org/community/design-tokens/2025/10/28/specification/",
             '<meta property="og:site_name" content="W3C">'
             '<title>Design Tokens Specification Reaches 1.0 | W3C</title>',
             "w3c-design-tokens-specification-reaches", "W3C"),
        )
        for url, html, expected_id, author in cases:
            with self.subTest(url=url), patch("source_store.fetch_page") as fetch:
                if html is None:
                    fetch.side_effect = HTTPError(url, 403, "Forbidden", {}, None)
                else:
                    fetch.return_value = FetchedPage(url, html)
                source_id, _ = self.assert_cli(0, "add", url)
                self.assertEqual(source_id, expected_id)
                self.assertEqual(self.ext(source_id)["author"], author)

    def test_generic_gitlab_title_uses_the_project(self) -> None:
        url = "https://gitlab.com/Builders/linter"
        html = '<meta name="author" content="GitLab"><title>GitLab</title><main>Project</main>'
        source_id = add(url, fetch=lambda _: FetchedPage(url, html))
        self.assertEqual(source_id, "builders-linter")
        self.assertEqual(self.ext(source_id)["author"], "Builders")

    def test_site_only_title_uses_the_url_with_a_named_author(self) -> None:
        url = "https://example.org/sources/consistent-renames/v2/index.html"
        html = """<head>
        <meta property="og:site_name" content="The Example Press">
        <meta name="author" content="Anne Smith">
        <title>The Example Press</title>
        </head><main>Article text</main>"""
        source_id = add(url, fetch=lambda _: FetchedPage(url, html))
        self.assertEqual(source_id, "smith-consistent-renames")
        self.assertEqual(self.ext(source_id)["author"], "Anne Smith")

    def test_ids_use_the_first_author_family_name(self) -> None:
        title = "Custom ESLint Ratcheting at Notion"
        cases = (
            ('<meta name="author" content="Ankit Sardesai, Jake Teton-Landis">',
             "sardesai-custom-eslint-ratcheting-notion", "Ankit Sardesai, Jake Teton-Landis"),
            ('<script type="application/ld+json">'
             '{"author":[{"@type":"Person","name":"Jake Teton-Landis"},'
             '{"@type":"Person","name":"Ankit Sardesai"}]}</script>',
             "teton-landis-custom-eslint-ratcheting-notion", "Jake Teton-Landis, Ankit Sardesai"),
            ('<script type="application/ld+json">{"author":["A","B"]}</script>',
             "a-custom-eslint-ratcheting-notion", "A, B"),
        )
        for index, (markup, expected, author) in enumerate(cases):
            with self.subTest(expected=expected):
                url = f"https://www.notion.com/blog/ratcheting-{index}"
                html = f"<head>{markup}<title>{title}</title></head><p>Article text</p>"
                self.assertEqual(add(url, fetch=lambda _: FetchedPage(url, html)), expected)
                self.assertEqual(self.ext(expected)["author"], author)

        self.assertEqual(add(manual=True, title="Another Source", author="Sardesai, Ankit"),
                         "sardesai-another-source")

    def test_publication_date_fallbacks_and_precedence(self) -> None:
        url = "https://example.com/community/2025/10/28/specification/"
        json_ld = '<script type="application/ld+json">{"datePublished":"2025-10-24"}</script>'
        meta = '<meta property="article:published_time" content="2025-10-25">'
        marked = '<time class="entry-date published" datetime="2025-10-26T17:04:52+00:00"></time>'
        itemprop = '<time itemprop="datePublished" datetime="2025-10-26"></time>'
        outside = '<header><time datetime="2025-01-01"></time></header>'
        inside = ('<main><article><time datetime="invalid"></time></article>'
                  '<time datetime="2025-10-27T17:04:52+00:00"></time>'
                  '<time datetime="2025-10-29"></time></main>')
        article = '<article><time datetime="2025-10-30"></time></article>'
        byline = '<article><div class="article-meta"><span><time datetime="2025-10-31"></time></span></div></article>'
        unpublished = '<time class="unpublished" datetime="2025-10-03"></time>'
        cases = (
            (json_ld + meta + inside + marked, "2025-10-24"),
            (meta + inside + marked, "2025-10-25"),
            (outside + inside + unpublished + marked, "2025-10-26"),
            (outside + inside + itemprop, "2025-10-26"),
            (outside + inside, "2025-10-28"),
            (outside + article, "2025-10-28"),
            (outside + byline, "2025-10-31"),
            (unpublished, "2025-10-28"),
            (byline.replace('<time datetime=', '<time class="unpublished" datetime='), "2025-10-28"),
            ("<main></main>" + outside, "2025-10-28"),
            (outside, "2025-10-28"),
        )
        for html, expected in cases:
            with self.subTest(expected=expected, html=html):
                details = extract_page(FetchedPage(url, html))
                self.assertEqual((details.published, details.updated), (expected, "unknown"))

        bad_date = url.replace("10/28", "02/30") + "?path=/2025/10/28/"
        self.assertEqual(extract_page(FetchedPage(bad_date, outside)).published, "unknown")
        for no_date in ("https://example.com/events", "https://example.com/2025/10/28"):
            self.assertEqual(extract_page(FetchedPage(no_date, article)).published, "unknown")
        schema = self.root / "ext-schema.yaml"
        old_schema = json.loads(schema.read_text())
        old_schema["properties"]["ext"]["properties"].pop("published_from", None)
        schema.write_text(json.dumps(old_schema))
        source_id = add(url, fetch=lambda _: FetchedPage(url, inside + "<p>Article text.</p>"))
        self.assertEqual(self.ext(source_id)["published_from"], "url")
        self.validate()

    def test_unreadable_and_dead_sources(self) -> None:
        url = "https://example.com/missing"
        for code, status in ((404, "discarded"), (410, "discarded"), (500, "pending")):
            link = f"{url}/{code}"
            with patch("source_store.fetch_page", side_effect=HTTPError(link, code, "error", {}, None)):
                source_id, error = self.assert_cli(0, "add", link)
            ext = self.ext(source_id)
            self.assertIn("snapshot", error)
            self.assertEqual((ext["status"], ext["snapshot"], ext["title"], ext["author"]),
                             (status, "none", "unknown", "example"))
            self.assertEqual(ext.get("reason"), "dead" if status == "discarded" else None)
            self.assertFalse(lookup_url(link).has_snapshot)
        for suffix, replacement in (
            ("non-html", {"return_value": FetchedPage(url + "/non-html", None)}),
            ("offline", {"side_effect": URLError("offline")}),
        ):
            with patch("source_store.fetch_page", **replacement):
                source_id, error = self.assert_cli(0, "add", f"{url}/{suffix}")
            self.assertIn("snapshot", error)
            self.assertEqual(self.ext(source_id)["snapshot"], "none")

    def test_refused_destination_creates_a_record_without_a_snapshot(self) -> None:
        url = "https://private.example.com/source"
        with (
            patch("socket.getaddrinfo", return_value=dns_answer("10.2.3.4", 443)),
            patch("socket.socket") as connect,
        ):
            source_id, warning = self.assert_cli(0, "add", url)
        connect.assert_not_called()
        self.assertIn("non-public address", warning)
        self.assertIn("10.2.3.4", warning)
        self.assertEqual((self.ext(source_id)["url"], self.ext(source_id)["snapshot"]), (url, "none"))

    def test_client_redirect_refuses_a_non_public_address(self) -> None:
        url = "http://example.com/start"
        target = "http://127.0.0.1/"
        script = f"<script>location.replace('{target}')</script>"
        connection = response_socket(html_response(script.encode()))
        with (
            patch("socket.getaddrinfo", side_effect=[dns_answer("93.184.216.34", 80), dns_answer("127.0.0.1", 80)]),
            patch("socket.socket", return_value=connection) as sockets,
        ):
            source_id, warning = self.assert_cli(0, "add", url)
        sockets.assert_called_once()
        self.assertIn("non-public address", warning)
        ext = self.ext(source_id)
        self.assertEqual((ext["url"], ext["redirected_to"], ext["snapshot"]), (url, target, "none"))

    def test_replacement_characters_warn_without_losing_the_snapshot(self) -> None:
        url = "http://example.com/source"
        connection = response_socket(html_response(b"<p>Invalid byte: \xff</p>", b"text/html; charset=utf-8"))
        with (
            patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
            patch("socket.socket", return_value=connection),
        ):
            source_id, warning = self.assert_cli(0, "add", url)
        self.assertIn("replacement characters", warning)
        self.assertEqual(self.ext(source_id)["snapshot"], "web")
        self.assertEqual(self.path(source_id).with_suffix(".txt").read_text(), "Invalid byte: �\n")

    def test_http_and_client_redirects_share_the_deadline(self) -> None:
        url = "http://example.com/start"
        clock = Mock(wraps=time)
        clock.monotonic.return_value = 0
        redirect = response_socket(b"HTTP/1.1 302 Found\r\nLocation: /script\r\n\r\n")
        script = Mock()
        landing = Mock()

        def read_script(*_):
            clock.monotonic.return_value = 16
            return io.BytesIO(html_response(b"<script>location.replace('/landing')</script>"))

        def read_landing(*_):
            clock.monotonic.return_value = 21
            return io.BytesIO(html_response(b"<p>Too late</p>"))

        script.makefile.side_effect = read_script
        landing.makefile.side_effect = read_landing
        with (
            patch("source_page.time", clock),
            patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
            patch("socket.socket", side_effect=[redirect, script, landing]),
        ):
            source_id, warning = self.assert_cli(0, "add", url)
        landing.settimeout.assert_called_with(4)
        self.assertIn("deadline", warning)
        self.assertEqual((self.ext(source_id)["url"], self.ext(source_id)["snapshot"]), (url, "none"))

    def test_publisher_reference_and_json_type_with_relative_canonical(self) -> None:
        url = "https://papers.example.com/start"
        html = """<link rel="canonical" href="/edition">
        <script type="application/ld+json">
        {"@graph":[{"@type":"ScholarlyArticle","name":"Testing at Scale","publisher":{"@id":"#pub"}},
        {"@id":"#pub","@type":"Organization","name":"Example Press"}]}
        </script><p>The paper text.</p>"""
        source_id = add(url, fetch=lambda _: FetchedPage(url, html))
        self.assertEqual(source_id, "example-press-testing-scale")
        ext = self.ext(source_id)
        self.assertEqual((ext["url"], ext["author"], ext["kind"]),
                         ("https://papers.example.com/edition", "Example Press", "paper"))

    def test_manual_no_fetch_and_id_collision(self) -> None:
        with patch("source_store.fetch_page") as fetch:
            args = ("add", "--manual", "--title", "The Café & API", "--author", "Jane Doe")
            first, _ = self.assert_cli(0, *args, "--kind", "talk", "--published", "2021-02-03")
            second, _ = self.assert_cli(0, *args, "--url", "unknown")
            third, _ = self.assert_cli(0, *args, "--url", "http://example.com/source")
            self.assertEqual(self.assert_cli(3, *args, "--url", "https://www.example.com/source/"), (third, ""))
            fetch.assert_not_called()
        self.assertEqual((first, second, third), ("doe-cafe-api", "doe-cafe-api-2", "doe-cafe-api-3"))
        self.assertEqual((self.ext(first)["kind"], self.ext(first)["published"]), ("talk", "2021-02-03"))
        self.assertEqual((self.ext(second)["url"], self.ext(second)["published"]), ("unknown", "unknown"))
        self.assertIsNone(lookup_url("unknown"))

    def test_finish_requires_status_evidence_and_check_finds_missing_anchor(self) -> None:
        url = "https://example.com/news/ratchets"
        source_id = add(url, fetch=lambda _: FetchedPage(url, ARTICLE))
        second = add(manual=True, title="Manual source")
        path = self.path(source_id)
        self.assertIn("pending", self.assert_cli(0, "check", second)[0])
        options = ("--description", "How ratchets raise the bar")
        self.assert_cli(1, "finish", source_id, "--status", "used", *options)
        self.assert_cli(1, "finish", second, "--status", "discarded", *options)
        self.assert_cli(1, "finish", second, "--status", "discarded", "--reason", "unknown", *options)
        claims = "- c1 (sec. Incremental checks): Change in steps — \"It's a \"small step\" at a time.\"\n"
        bad_claim = '- c2 (sec. Ratchets): Claim — “small step”\n'
        body = path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claims}")
        path.write_text(body.replace(claims, claims + bad_claim))
        for rename in ((), ("--id", "unverified")):
            error = self.assert_cli(1, "finish", source_id, "--status", "used", *options, *rename)[1]
            self.assertIn("c2 anchor missing", error)
            self.assertEqual(self.ext(source_id)["status"], "pending")
        path.write_text(body)
        self.assert_cli(0, "finish", source_id, "--status", "used", *options, "--kind", "docs")
        self.assert_cli(1, "finish", source_id, "--status", "used", *options)
        self.assertEqual(self.ext(source_id)["kind"], "docs")
        self.assertIn(claims, path.read_text())
        path.write_text(path.read_text().replace(claims, claims + bad_claim))
        output, _ = self.assert_cli(1, "check", source_id)
        self.assertIn("c2", output)
        self.assertNotIn("c1", output)
        self.assert_cli(0, "finish", second, "--status", "discarded", "--reason", f"copy-of:{source_id}", *options)
        self.assertEqual(self.ext(second)["reason"], f"copy-of:{source_id}")
        self.validate()

    def test_fetched_and_legacy_headings_match_visible_locators(self) -> None:
        invisible = "\u200b\u200c\u200d\u2060\ufeff"
        url = "https://example.com/docs/lint"
        source_id = add(url, fetch=lambda _: FetchedPage(
            url, f"<h3>  Lint\t Rule{invisible}</h3><p>Check every line.</p>",
        ))
        path = self.path(source_id)
        snapshot = path.with_suffix(".txt")
        self.assertEqual(snapshot.read_text(), "## Lint Rule\nCheck every line.\n")

        snapshot.write_text(f"## Lint\t Rule{invisible}\nCheck every line.\n")
        claims = ('- c1 (sec. Lint Rule): Rule — "Check every line."\n'
                  f'- c2 (sec. Lint{invisible}   Rule): Rule — "Check every line."\n')
        path.write_text(path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claims}"))
        self.assert_cli(0, "check", source_id)

    def test_manual_readme_sections_preserve_fences_and_locate_the_intro(self) -> None:
        source_id = add(manual=True, title="eslint-seatbelt")
        path = self.path(source_id)
        claims = ('- c1 (sec. eslint-seatbelt): Intro — "Protect lint rules."\n'
                  '- c2 (sec. eslint-seatbelt): Example — "## In the first fence"\n')
        body = path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claims}")
        path.write_text(body)
        intro = "Protect lint rules.\r\n\r\n"
        fences = ("````md\r\n```\r\n## In the first fence\r\n````\r\n\r\n"
                  "~~~md\r\n# In the second fence\r\n~~~\r\n\r\n")
        headings = "\r\n".join(f"{'#' * level} Level {level} ###" for level in range(2, 7))
        readme = self.root.parent / "README.md"
        readme.write_bytes(f"# eslint-seatbelt\r\n{intro}{fences}{headings}".encode())

        self.assert_cli(0, "snapshot", source_id, "--from", str(readme), "--note", "Package README")
        expected_headings = "\r\n".join(f"## Level {level}" for level in range(2, 7))
        legacy = f"## eslint-seatbelt\r\n{intro}{fences}{expected_headings}"
        expected = "<!-- BKF:SNAPSHOT:1 -->\n" + legacy.replace("## In the first fence", "\\## In the first fence")
        snapshot = path.with_suffix(".txt")
        self.assertEqual(snapshot.read_bytes(), expected.encode())
        self.assert_cli(0, "finish", source_id, "--status", "used", "--description", "Lint rule protection")
        self.assert_cli(0, "check", source_id)
        snapshot.write_bytes(legacy.encode())
        self.assert_cli(0, "check", source_id)
        snapshot.write_bytes(expected.encode())

        path.write_text(path.read_text().replace("c2 (sec. eslint-seatbelt)", "c2 (sec. In the first fence)"))
        output, _ = self.assert_cli(1, "check", source_id)
        self.assertIn("c2 anchor missing", output)

    def test_manual_snapshot_matches_literal_heading_lines_as_text(self) -> None:
        source_id = add(manual=True, title="Setup guide")
        path = self.path(source_id)
        claims = (
            '- c1 (sec. Installation): Example — "## Example syntax"\n'
            '- c2 (sec. Installation): Run setup — "Run setup."\n'
            '- c3 (sec. Installation): Escaped example — "\\## Literal backslash"\n'
        )
        path.write_text(path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claims}"))
        manual = "# Installation\n\n<!-- Example\n## Example syntax\n-->\n\\## Literal backslash\nRun setup.\n"
        with patch.object(sys, "stdin", io.StringIO(manual)):
            self.assert_cli(0, "snapshot", source_id, "--from", "-", "--note", "Rendered page")
        self.assert_cli(0, "finish", source_id, "--status", "used", "--description", "Setup guide")
        self.assert_cli(0, "check", source_id)

    def test_a_new_manual_snapshot_without_escapes_carries_the_format_marker(self) -> None:
        source_id = add(manual=True, title="Plain notes")
        source = self.root.parent / "notes.txt"
        source.write_text("Plain notes\nwith nothing to escape.\n")
        self.assert_cli(0, "snapshot", source_id, "--from", str(source), "--note", "Typed by hand")
        self.assertEqual(self.path(source_id).with_suffix(".txt").read_text(),
                         SNAPSHOT_HEADER + "\nPlain notes\nwith nothing to escape.\n")

    def test_snapshot_from_file_and_stdin_preserves_citations_and_commits_metadata(self) -> None:
        source_id = add(manual=True, title="Package docs")
        path = self.path(source_id)
        snapshot = path.with_suffix(".txt")
        claims = '- c1 (sec. Usage): Configure the rule — "use this   option"\n'
        path.write_text(path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claims}"))
        options = ("--status", "used", "--description", "Package configuration")
        for rename in ((), ("--id", "new-package")):
            error = self.assert_cli(1, "finish", source_id, *options, *rename)[1]
            self.assertIn(f"bkf sources snapshot {source_id}", error)
            self.assertEqual(self.ext(source_id)["status"], "pending")

        source = self.root.parent / "readme.txt"
        readme = "## Usage\r\nPlease use this option.\r\n"
        source.write_bytes(readme.encode())
        self.assert_cli(0, "snapshot", source_id, "--from", str(source),
                        "--note", "npm registry README", "--dir", str(self.root))
        self.assertEqual(snapshot.read_bytes(), (SNAPSHOT_HEADER + "\n" + readme).encode())
        ext = self.ext(source_id)
        self.assertEqual((ext["snapshot"], ext["snapshot_note"], ext["status"]),
                         ("manual", "npm registry README", "pending"))
        self.assertIn("snapshot_note: npm registry README", self.git("show", f"HEAD:{path.relative_to(self.root)}"))
        self.assertEqual(self.git("ls-files", "--", str(snapshot)), "")
        self.assert_cli(0, "finish", source_id, *options)
        original = parse_markdown(path)
        with patch.object(sys, "stdin", io.StringIO("## Usage\nPlease use this option carefully.\n")):
            self.assert_cli(0, "snapshot", source_id, "--from", "-", "--note", "Rendered package docs")
        updated = parse_markdown(path)
        original.frontmatter["ext"]["snapshot_note"] = "Rendered package docs"
        self.assertEqual(updated, original)
        self.assertEqual(snapshot.read_text(), SNAPSHOT_HEADER + "\n## Usage\nPlease use this option carefully.\n")
        self.assert_cli(0, "check", source_id)
        head = self.git("rev-parse", "HEAD")
        with patch.object(sys, "stdin", io.StringIO("## Usage\nPlease use this option again.\n")):
            _, error = self.assert_cli(0, "snapshot", source_id, "--from", "-", "--note", "Rendered package docs")
        self.assertEqual(error, "")
        self.assertEqual(snapshot.read_text(), SNAPSHOT_HEADER + "\n## Usage\nPlease use this option again.\n")
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        ext = self.ext(source_id)
        ext["consulted"] = ["2000-01-01"]
        path.write_text(render_record({**updated.frontmatter, "ext": ext}, updated.body))
        with patch.object(sys, "stdin", io.StringIO("## Other\nPlease use this option.\n")):
            _, error = self.assert_cli(1, "snapshot", source_id, "--from", "-", "--note", "Moved text")
        self.assertIn("c1 anchor missing", error)
        self.assertEqual(snapshot.read_text(), SNAPSHOT_HEADER + "\n## Usage\nPlease use this option again.\n")
        self.assertEqual(self.ext(source_id)["snapshot_note"], "Rendered package docs")
        self.assertEqual(self.ext(source_id)["consulted"], ["2000-01-01", date.today().isoformat()])
        snapshot.write_text("Different text")
        self.assertIn("c1 anchor missing", self.assert_cli(1, "check", source_id)[0])
        self.validate()

    def test_snapshot_rejects_blank_input_and_protects_web_text(self) -> None:
        pending = add(manual=True, title="Package docs")
        url = "https://example.com/news/ratchets"
        web = add(url, fetch=lambda _: FetchedPage(url, ARTICLE))
        snapshot = self.path(web).with_suffix(".txt")
        original = snapshot.read_bytes()
        head = self.git("rev-parse", "HEAD")
        for source_id, content, note, message in (
            (pending, "", "README", "non-empty"),
            (pending, " \n\t", "README", "non-empty"),
            (pending, "Text", " \t", "--note"),
            (web, "Replacement text", "README", "web snapshot"),
        ):
            with self.subTest(source_id=source_id, content=content, note=note):
                with patch.object(sys, "stdin", io.StringIO(content)):
                    error = self.assert_cli(1, "snapshot", source_id, "--from", "-", "--note", note)[1]
                self.assertIn(message, error)
        self.assertEqual(self.ext(pending)["snapshot"], "none")
        self.assertFalse(self.path(pending).with_suffix(".txt").exists())
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

    def test_snapshot_write_failure_rolls_back_metadata(self) -> None:
        source_id = add(manual=True, title="Package docs")
        path = self.path(source_id)
        head = self.git("rev-parse", "HEAD")
        original = path.read_bytes()
        path.with_suffix(".txt").mkdir()
        with patch.object(sys, "stdin", io.StringIO("Package text")):
            self.assert_cli(1, "snapshot", source_id, "--from", "-", "--note", "README")
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

    def test_check_reports_one_missing_snapshot_for_a_legacy_used_record(self) -> None:
        source_id = add(manual=True, title="Legacy package docs")
        path = self.path(source_id)
        parsed = parse_markdown(path)
        parsed.frontmatter["ext"]["status"] = "used"
        claims = ('- c1 (sec. Usage): First setting — "first setting"\n'
                  '- c2 (sec. Usage): Second setting — "second setting"\n')
        body = parsed.body.replace("## Key claims\n", f"## Key claims\n\n{claims}")
        path.write_text(render_record(parsed.frontmatter, body))
        output, _ = self.assert_cli(1, "check", source_id)
        self.assertEqual(len(output.splitlines()), 1)
        self.assertIn("claims cannot be verified", output)
        self.assertIn(f"bkf sources snapshot {source_id}", output)
        with patch.object(sys, "stdin", io.StringIO("## Usage\nThe first setting and the second setting.")):
            self.assert_cli(0, "snapshot", source_id, "--from", "-", "--note", "Legacy README")
        self.assertEqual(parse_markdown(path).body, body)
        self.assert_cli(0, "check", source_id)

    def test_snapshot_upgrades_an_existing_store_and_enforces_note_in_schema(self) -> None:
        source_id = add(manual=True, title="Package docs")
        schema_path = self.root / "ext-schema.yaml"
        schema = json.loads(schema_path.read_text())
        ext_schema = schema["properties"]["ext"]
        ext_schema["properties"]["snapshot"]["enum"] = ["web", "none"]
        ext_schema["properties"].pop("snapshot_note", None)
        ext_schema.pop("allOf", None)
        schema_path.write_text(json.dumps(schema))
        with patch.object(sys, "stdin", io.StringIO("Package text")):
            self.assert_cli(0, "snapshot", source_id, "--from", "-", "--note", "README")
        self.assertEqual(json.loads(self.git("show", "HEAD:ext-schema.yaml")),
                         json.loads(schema_path.read_text()))
        self.validate()

        path = self.path(source_id)
        parsed = parse_markdown(path)
        for kind, note in (("manual", None), ("manual", "  "), ("web", "README"), ("none", "README")):
            with self.subTest(kind=kind, note=note):
                ext = parsed.frontmatter["ext"]
                ext["snapshot"] = kind
                if note is None:
                    ext.pop("snapshot_note", None)
                else:
                    ext["snapshot_note"] = note
                path.write_text(render_record(parsed.frontmatter, parsed.body))
                self.assertIn("EXT_INVALID", self.validate(1))
                self.assert_cli(1, "check", source_id)

    def test_finish_renames_a_pending_record_in_one_commit(self) -> None:
        url = "https://example.com/news/ratchets"
        source_id = add(url, fetch=lambda _: FetchedPage(url, ARTICLE))
        path = self.path(source_id)
        snapshot = path.with_suffix(".txt").read_bytes()
        claims = '- c1 (sec. Ratchets): Ratchets raise the bar — "Ratchets keep the bar high."\n'
        path.write_text(path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claims}"))
        self.assert_cli(0, "complete", source_id, "--why", "Check the example")
        (self.root / "elsewhere").write_text("unrelated")
        self.git("add", "elsewhere")
        head = self.git("rev-parse", "HEAD")
        final_id = "example-ratchets"
        self.assertEqual(self.assert_cli(0, "finish", source_id, "--status", "used", "--description",
                                         "How ratchets raise the bar", "--id", final_id), (final_id, ""))
        self.assertFalse(path.parent.exists())
        final_path = self.path(final_id)
        self.assertEqual(final_path.with_suffix(".txt").read_bytes(), snapshot)
        self.assertIn(claims, final_path.read_text())
        self.assertEqual((self.ext(final_id)["id"], self.ext(final_id)["status"]), (final_id, "used"))
        self.assertEqual(lookup_url(url).id, final_id)
        self.assertTrue(source_store._window_path(self.root, final_id).exists())
        self.assertEqual(self.git("rev-parse", "HEAD^"), head)
        self.assertEqual(set(self.git("diff", "--no-renames", "--name-only", head, "HEAD").splitlines()),
                         {"records/MAP.md", path.relative_to(self.root).as_posix(),
                          final_path.relative_to(self.root).as_posix()})
        self.assertEqual(self.git("status", "--porcelain"), "A  elsewhere")
        self.assertEqual(self.assert_cli(0, "check", final_id)[0], f"{final_id}: ok")
        self.validate()

    def test_finish_rename_refusals_and_catalog_failure_leave_record_intact(self) -> None:
        url = "https://example.com/news/ratchets"
        source_id = add(url, fetch=lambda _: FetchedPage(url, ARTICLE))
        taken = add(manual=True, title="Other source")
        options = ("--status", "discarded", "--description", "Discarded", "--reason", "outdated")
        self.assertEqual(self.assert_cli(0, "finish", taken, *options), (taken, ""))
        self.assert_cli(0, "complete", source_id, "--why", "Check the example")
        path = self.path(source_id)
        snapshot = path.with_suffix(".txt")
        catalog = self.root / "records" / "MAP.md"
        before = {file: file.read_bytes() for file in (path, snapshot, catalog)}
        head = self.git("rev-parse", "HEAD")
        for old, new, message in (
            (source_id, "../bad", "invalid source id"),
            (source_id, taken, "already exists"),
            (taken, "free", "finish requires a pending record"),
        ):
            with self.subTest(old=old, new=new):
                self.assertIn(message, self.assert_cli(1, "finish", old, *options, "--id", new)[1])
        with patch("source_store._refresh_map", side_effect=OSError("catalog write failed")):
            self.assertIn("catalog write failed",
                          self.assert_cli(1, "finish", source_id, *options, "--id", "free")[1])
        self.assertEqual({file: file.read_bytes() for file in before}, before)
        self.assertFalse(self.path("free").parent.exists())
        self.assertTrue(source_store._window_path(self.root, source_id).exists())
        self.assertFalse(source_store._window_path(self.root, "free").exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_rename_api_refuses_a_closed_record_without_a_snapshot(self) -> None:
        source_id = add(manual=True, title="Manual source")
        self.assert_cli(0, "finish", source_id, "--status", "discarded",
                        "--description", "Old source", "--reason", "outdated")
        head = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(source_store.StoreError, "pending"):
            source_store.rename(self.root, source_id, "archived-source")
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        ext = self.ext(source_id)
        self.assertEqual((ext["id"], ext["status"], ext["reason"]), (source_id, "discarded", "outdated"))
        self.assertFalse(self.path("archived-source").parent.exists())
        self.validate()

    def test_finish_can_rename_a_record_whose_add_commit_failed(self) -> None:
        head = self.git("rev-parse", "HEAD")
        with patch("source_store._commit", side_effect=source_store.StoreError("index locked")):
            source_id, error = self.assert_cli(0, "add", "--manual", "--title", "Manual source")
        self.assertIn("commit failed", error)
        output, error = self.assert_cli(
            0, "finish", source_id, "--status", "discarded", "--description", "Old source",
            "--reason", "outdated", "--id", "archived-source",
        )
        self.assertEqual((output, error), ("archived-source", ""))
        self.assertEqual(self.git("rev-parse", "HEAD^"), head)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_schema_and_check_reject_invalid_metadata(self) -> None:
        source_id = add(manual=True, title="Manual source")
        path = self.path(source_id)
        parsed = parse_markdown(path)
        self.assertEqual(parsed.frontmatter["tags"], ["source"])
        ext = parsed.frontmatter["ext"]
        ext.update(author="  ", status="discarded", kind="other")
        path.write_text(render_record(parsed.frontmatter, parsed.body))
        self.assertIn("EXT_INVALID", self.validate(1))
        output, _ = self.assert_cli(1, "check", source_id)
        for field in ("author", "reason", "kind"):
            self.assertIn(field, output)

    def test_check_and_finish_validate_calendar_dates_and_urls(self) -> None:
        source_id = add(manual=True, title="Manual source")
        path = self.path(source_id)
        parsed = parse_markdown(path)
        parsed.frontmatter["ext"].update(
            url="https://?", aliases=["https://example.com:invalid"], published="2026-02-31",
            updated="2025-02-29", consulted=["2026-04-31"],
            completions=[{"date": "2026-06-31", "why": "New details"}],
        )
        before = render_record(parsed.frontmatter, parsed.body)
        path.write_text(before)
        output, _ = self.assert_cli(1, "check", source_id)
        for field in ("url", "aliases.0", "published", "updated", "consulted.0", "completions.0.date"):
            self.assertIn(field, output)
        for rename in ((), ("--id", "new-id")):
            _, error = self.assert_cli(1, "finish", source_id, "--status", "discarded",
                                       "--description", "Old source", "--reason", "outdated", *rename)
            self.assertIn("published", error)
            self.assertEqual(path.read_text(), before)
            self.assertFalse(self.path("new-id").parent.exists())

    def test_check_and_store_schema_reject_raw_invalid_url_characters(self) -> None:
        source_id = add(manual=True, title="Guide")
        path = self.path(source_id)
        parsed = parse_markdown(path)
        for char in '<>" {}|\\^`\x00\x1f\x7f\x85\n':
            with self.subTest(char=repr(char)):
                url = f"https://example.org/guide{char}"
                parsed.frontmatter["ext"].update(url=url, aliases=[url], redirected_to=url)
                path.write_text(render_record(parsed.frontmatter, parsed.body))
                checked, _ = self.assert_cli(1, "check", source_id)
                validated = self.validate(1)
                for field in ("ext.url", "ext.aliases.0", "ext.redirected_to"):
                    self.assertIn(field, checked)
                    self.assertIn(f"`{field.replace('.', '/')}`", validated)
        encoded = "https://example.org/guide%3E"
        parsed.frontmatter["ext"].update(url=encoded, aliases=[encoded], redirected_to=encoded)
        path.write_text(render_record(parsed.frontmatter, parsed.body))
        self.assert_cli(0, "check", source_id)
        self.validate()

    def test_title_with_markdown_link_syntax_keeps_bundle_valid(self) -> None:
        title = "[Draft](notes.md)"
        source_id = add(manual=True, title=title)
        self.assertEqual(self.ext(source_id)["title"], title)
        self.validate()

    def test_store_commits_leave_other_paths_staged(self) -> None:
        (self.root / "elsewhere").write_text("unrelated")
        self.git("add", "elsewhere")
        source_id = add(manual=True, title="Manual source")
        self.assertEqual(set(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()),
                         {"records/MAP.md", self.path(source_id).relative_to(self.root).as_posix()})
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "elsewhere")

    def test_git_lock_retry_and_warning_when_retries_exhausted(self) -> None:
        lock = self.root / ".git" / "index.lock"
        lock.touch()
        with patch("source_store.time.sleep", side_effect=lambda _: lock.unlink()) as retry:
            source_id, error = self.assert_cli(0, "add", "--manual", "--title", "Saved after retry")
        retry.assert_called_once()
        self.assertEqual(error, "")
        self.assertIn(self.path(source_id).name, self.git("ls-files"))
        head = self.git("rev-parse", "HEAD")

        lock.touch()
        with patch("source_store.time.sleep") as retry:
            source_id, error = self.assert_cli(0, "add", "--manual", "--title", "Saved without commit")
        self.assertGreater(retry.call_count, 0)
        self.assertIn("commit failed", error)
        self.assertTrue(self.path(source_id).is_file())
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.validate()

    def test_concurrent_adds_only_create_one_record(self) -> None:
        url = "https://example.com/source"
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: add(url, manual=True, title="Concurrent"), range(8)))
        self.assertEqual(set(ids), {"example-concurrent"})
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "2")
        self.validate()

class FetchPageTests(unittest.TestCase):
    def test_http_redirect_pins_the_address_and_keeps_the_original_host_and_tls_name(self) -> None:
        redirect = response_socket(b"HTTP/1.1 302 Found\r\nLocation: https://other.example/final\r\n\r\n")
        response = response_socket(html_response(b"<p>Final page</p>"))
        tls = Mock()
        tls.wrap_socket.return_value = response
        with (
            patch("socket.getaddrinfo", side_effect=[dns_answer("93.184.216.34", 80), dns_answer("8.8.8.8", 443)]) as dns,
            patch("socket.socket", side_effect=[redirect, Mock()]) as sockets,
            patch("ssl.create_default_context", return_value=tls),
        ):
            page = fetch_page("http://example.com/start")
        self.assertEqual(page, FetchedPage("https://other.example/final", "<p>Final page</p>"))
        self.assertEqual([call.args[:2] for call in dns.call_args_list], [("example.com", 80), ("other.example", 443)])
        self.assertEqual(sockets.call_count, 2)
        redirect.connect.assert_called_once_with(("93.184.216.34", 80))
        raw_socket = tls.wrap_socket.call_args.args[0]
        raw_socket.connect.assert_called_once_with(("8.8.8.8", 443))
        self.assertEqual(tls.wrap_socket.call_args.kwargs["server_hostname"], "other.example")
        request = response.sendall.call_args.args[0]
        self.assertIn(b"Host: other.example\r\n", request)
        self.assertIn(b"User-Agent: BKF Sources\r\n", request)

    def test_http_redirect_refuses_non_public_destinations_before_connecting(self) -> None:
        destinations = [
            ("127.0.0.1", "127.0.0.1"),
            ("[::1]", "::1"),
            ("[::ffff:192.168.1.5]", "::ffff:192.168.1.5"),
            ("private.example", "10.2.3.4"),
        ]
        for host, address in destinations:
            with self.subTest(host=host):
                redirect = response_socket(f"HTTP/1.1 302 Found\r\nLocation: http://{host}/\r\n\r\n".encode())
                with (
                    patch("socket.getaddrinfo", side_effect=[dns_answer("93.184.216.34", 80), dns_answer(address, 80)]),
                    patch("socket.socket", return_value=redirect) as sockets,
                ):
                    with self.assertRaisesRegex(OSError, "non-public address"):
                        fetch_page("http://example.com/start")
                sockets.assert_called_once()

    def test_http_redirect_limit(self) -> None:
        redirects = [
            response_socket(f"HTTP/1.1 302 Found\r\nLocation: /{hop}\r\n\r\n".encode())
            for hop in range(1, 7)
        ]
        with (
            patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
            patch("socket.socket", side_effect=redirects) as sockets,
        ):
            with self.assertRaisesRegex(OSError, "5 HTTP redirects"):
                fetch_page("http://example.com/start")
        self.assertEqual(sockets.call_count, 6)

    def test_body_with_no_content_length_is_capped(self) -> None:
        connection = response_socket(html_response(b"x" * 5_000_001))
        with (
            patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
            patch("socket.socket", return_value=connection),
        ):
            with self.assertRaisesRegex(OSError, "5 MB"):
                fetch_page("http://example.com/start")

    def test_deadline_interrupts_a_read_that_does_not_return(self) -> None:
        release = threading.Event()
        connection = Mock()
        stream = connection.makefile.return_value
        stream.readline.side_effect = [b"HTTP/1.1 200 OK\r\n", b"Content-Type: text/html\r\n", b"\r\n"]
        stream.read.side_effect = lambda _: release.wait(3) and b""
        connection.shutdown.side_effect = lambda _: release.set()
        started = time.monotonic()
        try:
            with (
                patch("source_page.FETCH_TIMEOUT", 0.2),
                patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
                patch("socket.socket", return_value=connection),
            ):
                with self.assertRaisesRegex(OSError, "deadline"):
                    fetch_page("http://example.com/start")
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 1)
        stream.read.assert_called()
        connection.shutdown.assert_called_once_with(socket.SHUT_RDWR)

    def test_deadline_includes_dns_resolution(self) -> None:
        release = threading.Event()

        def resolve(*_, **__):
            release.wait(3)
            return dns_answer("93.184.216.34", 80)

        started = time.monotonic()
        with (
            patch("source_page.FETCH_TIMEOUT", 0.2),
            patch("socket.getaddrinfo", side_effect=resolve),
            patch("socket.socket") as sockets,
        ):
            try:
                with self.assertRaisesRegex(OSError, "deadline"):
                    fetch_page("http://example.com/start")
            finally:
                release.set()
        sockets.assert_not_called()
        self.assertLess(time.monotonic() - started, 1)

    def test_html_charset_and_bom_header_precedence(self) -> None:
        for html, encoding, header in (
            ('<meta charset="windows-1252"><p>Café’s menu</p>', "windows-1252", b"text/html"),
            ("<meta content='text/html; charset=windows-1252' http-equiv='Content-Type'><p>Café’s menu</p>",
             "windows-1252", b"text/html"),
            ('<meta charset="utf-8"><p>Café’s menu</p>', "windows-1252", b"text/html; charset=windows-1252"),
            ('<meta charset="windows-1252"><p>Café’s menu</p>', "utf-16", b"text/html; charset=windows-1252"),
        ):
            with self.subTest(encoding=encoding, header=header, html=html):
                connection = response_socket(html_response(html.encode(encoding), header))
                with (
                    patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
                    patch("socket.socket", return_value=connection),
                ):
                    self.assertEqual(fetch_page("http://example.com/"), FetchedPage("http://example.com/", html))

    def test_html_charset_labels_use_web_encodings(self) -> None:
        for label, encoding, text in (
            ("iso-8859-1", "windows-1252", "Café’s “menu”"),
            ("latin1", "windows-1252", "Café’s “menu”"),
            ("ASCII", "windows-1252", "Café’s “menu”"),
            ("iso-8859-9", "windows-1254", "Türkiye’nin"),
            ("ISO-8859-11", "cp874", "เมนู…"),
            ("latin2", "iso8859-2", "Łódź"),
            ("gb2312", "gbk", "喆"),
        ):
            for from_header in (False, True):
                with self.subTest(label=label, from_header=from_header):
                    html = f"<p>{text}</p>"
                    header = b"text/html"
                    if from_header:
                        header += f"; charset={label}".encode("ascii")
                    else:
                        html = f'<meta charset="{label}">' + html
                    connection = response_socket(html_response(html.encode(encoding), header))
                    with (
                        patch("socket.getaddrinfo", return_value=dns_answer("93.184.216.34", 80)),
                        patch("socket.socket", return_value=connection),
                    ):
                        self.assertEqual(fetch_page("http://example.com/"), FetchedPage("http://example.com/", html))

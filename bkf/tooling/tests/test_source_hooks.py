from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from bkf_cli import main
from bkf_common import parse_markdown
from source_page import SNAPSHOT_HEADER, FetchedPage
from source_record import render_record
from source_store import WINDOW_SECONDS, add, finish, init_store, lookup_url


URL = "https://example.com/ratchets"
ALIAS = "https://example.com/redirect"
PAGE = f'<link rel="canonical" href="{URL}"><title>Ratchet testing</title><p>Old text</p>'
NEW_PAGE = (
    '<title>Different title</title><meta name="author" content="New author">'
    '<meta property="article:published_time" content="2024-12-01">'
    '<meta property="article:modified_time" content="2025-01-02"><p>New snapshot</p>'
)


class SourceHooksTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "store"
        environment = patch.dict(os.environ, {"BKF_SOURCES_DIR": str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)
        init_store()
        fetch = patch("source_store.fetch_page", side_effect=lambda url, **_: FetchedPage(url, PAGE))
        self.fetch = fetch.start()
        self.addCleanup(fetch.stop)

    def invoke(self, event: str, **data) -> tuple[dict, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        payload = {"hook_event_name": event, "session_id": "s", **data}
        with (
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(main(["hooks", "run", "sources"]), 0)
        return json.loads(stdout.getvalue() or "{}"), stderr.getvalue()

    def web(self, event: str, tool: str, value: str, **data) -> tuple[dict, str]:
        key = "url" if tool == "WebFetch" else "query"
        return self.invoke(event, tool_name=tool, tool_input={key: value}, **data)

    def context(self, output: dict) -> str:
        return output.get("hookSpecificOutput", {}).get("additionalContext", "")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_fetch_denial_names_the_paths_and_reopen_command(self) -> None:
        self.assertEqual(self.web("PreToolUse", "WebFetch", URL), ({}, ""))
        source_id = add(ALIAS)
        match = lookup_url(ALIAS)
        output, error = self.web("PreToolUse", "WebFetch", URL + "?utm_source=search")
        self.assertEqual(error, "")
        decision = output["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        reason = decision["permissionDecisionReason"]
        for part in (source_id, str(match.path), str(match.path.with_suffix(".txt")),
                     f'bkf sources complete {source_id} --why "<reason>"'):
            self.assertIn(part, reason)
        self.assertEqual(self.fetch.call_count, 1)

    def test_complete_opens_only_the_record_and_aliases_then_expires(self) -> None:
        source_id = add(ALIAS)
        other = "https://other.example.org/page"
        add(other, fetch=lambda url: FetchedPage(url, "<p>Other snapshot</p>"))
        with patch("source_store.time", wraps=time) as clock:
            clock.time.return_value = 1000
            self.assertEqual(main(["sources", "complete", source_id, "--why", "Check new date"]), 0)
            clock.time.return_value = 2799
            output, _ = self.web("PreToolUse", "WebFetch", ALIAS, tool_use_id="first")
            self.assertIn(f"registered as {source_id}", self.context(output))
            for data in ({"session_id": "another"}, {"agent_id": "another"}, {"tool_use_id": "later"}):
                identity = {"tool_use_id": "first", **data}
                output, _ = self.web("PreToolUse", "WebFetch", URL, **identity)
                self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertEqual(self.web("PostToolUse", "WebFetch", URL, **identity), ({}, ""))
            output, _ = self.web("PreToolUse", "WebFetch", other)
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("Refreshed", self.context(self.web("PostToolUse", "WebFetch", URL, tool_use_id="first")[0]))
            self.assertEqual(self.web("PostToolUse", "WebFetch", URL, tool_use_id="first"), ({}, ""))
            output, _ = self.web("PreToolUse", "WebFetch", URL, tool_use_id="later")
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
            clock.time.return_value = 2800
            output, _ = self.web("PreToolUse", "WebFetch", ALIAS, tool_use_id="after-expiry")
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        match = lookup_url(URL)
        ext = parse_markdown(match.path).frontmatter["ext"]
        self.assertEqual(ext["completions"], [{"date": date.today().isoformat(), "why": "Check new date"}])
        self.assertEqual(self.git("ls-files", "--others", "--exclude-standard"), "")
        self.assertEqual(self.git("log", "-1", "--format=%s"), f"Complete source {source_id}")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["sources", "check", source_id]), 0)

    def test_grant_releases_only_the_call_that_explicitly_failed(self) -> None:
        source_id = add(ALIAS)
        with patch("source_store.time", wraps=time) as clock:
            clock.time.return_value = 1000
            self.assertEqual(main(["sources", "complete", source_id, "--why", "Retry consultation"]), 0)
            self.web("PreToolUse", "WebFetch", URL, tool_use_id="failed")
            self.assertEqual(self.web("PostToolUseFailure", "WebFetch", URL, tool_use_id="failed"), ({}, ""))
            retry, _ = self.web("PreToolUse", "WebFetch", URL, tool_use_id="slow")
            self.assertIn("refresh", self.context(retry))
            clock.time.return_value = 1301
            self.assertEqual(self.web("PostToolUseFailure", "WebFetch", URL, tool_use_id="failed"), ({}, ""))
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["sources", "complete", source_id, "--why", "Try again"]), 1)
            self.assertIn("reserved", error.getvalue())
            other, _ = self.web("PreToolUse", "WebFetch", URL, tool_use_id="other")
            self.assertEqual(other["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("Refreshed", self.context(self.web("PostToolUse", "WebFetch", URL, tool_use_id="slow")[0]))

    def test_a_reserved_grant_names_its_expiry_in_the_denial_and_in_complete(self) -> None:
        source_id = add(ALIAS)
        with patch("source_store.time", wraps=time) as clock:
            clock.time.return_value = 1000
            self.assertEqual(main(["sources", "complete", source_id, "--why", "Read it again"]), 0)
            expiry = datetime.fromtimestamp(1000 + WINDOW_SECONDS).strftime("%H:%M")
            # This call never reports back: the user denied the prompt or an interrupt stopped it.
            self.assertIn("refresh", self.context(self.web("PreToolUse", "WebFetch", URL, tool_use_id="lost")[0]))
            clock.time.return_value = 1100
            decision, _ = self.web("PreToolUse", "WebFetch", URL, tool_use_id="next")
            reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn(f"reserved by another WebFetch call until {expiry}", reason)
            self.assertNotIn("bkf sources complete", reason)
            self.assertNotIn("already used", reason)
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["sources", "complete", source_id, "--why", "Try again"]), 1)
            self.assertIn(f"reserved by another WebFetch call until {expiry}", error.getvalue())
            self.assertIn(f"after {expiry}", error.getvalue())
            clock.time.return_value = 1000 + WINDOW_SECONDS
            decision, _ = self.web("PreToolUse", "WebFetch", URL, tool_use_id="after")
            self.assertIn(f"bkf sources complete {source_id}", decision["hookSpecificOutput"]["permissionDecisionReason"])
            self.assertEqual(main(["sources", "complete", source_id, "--why", "Try again"]), 0)

    def test_a_used_grant_says_so_and_still_offers_complete(self) -> None:
        source_id = add(ALIAS)
        with patch("source_store.time", wraps=time) as clock:
            clock.time.return_value = 1000
            self.assertEqual(main(["sources", "complete", source_id, "--why", "Read it again"]), 0)
            self.web("PreToolUse", "WebFetch", URL, tool_use_id="first")
            self.web("PostToolUse", "WebFetch", URL, tool_use_id="first")
            decision, _ = self.web("PreToolUse", "WebFetch", URL, tool_use_id="second")
        reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
        expiry = datetime.fromtimestamp(1000 + WINDOW_SECONDS).strftime("%H:%M")
        self.assertIn(f"already used and would have expired at {expiry}", reason)
        self.assertNotIn("reserved", reason)
        self.assertIn(f"bkf sources complete {source_id}", reason)

    def test_urls_a_browser_would_fetch_are_captured_once_by_the_hooks(self) -> None:
        url = "https://fonts.example.org/css?family=Roboto|Open+Sans"
        for value in (url, f"  {url}\n", url.replace("|", "%7C")):
            with self.subTest(value=value):
                result, error = self.web("PostToolUse", "WebFetch", value)
                self.assertEqual(error, "")
        match = lookup_url(url)
        self.assertEqual(len(list((self.root / "records").glob("*/*.md"))), 1)
        self.assertIn("Roboto%7COpen+Sans", parse_markdown(match.path).frontmatter["ext"]["url"])
        self.assertEqual(self.web("PostToolUse", "WebFetch", url), ({}, ""))
        decision, _ = self.web("PreToolUse", "WebFetch", f" {url} ")
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        response = {"results": [{"content": [{"url": url, "title": "Fonts"}]}]}
        self.web("PostToolUse", "WebSearch", "fonts", tool_response=response)
        log = self.root / "searches" / f"{date.today().isoformat()}.jsonl"
        self.assertEqual(json.loads(log.read_text())["urls"], [url.replace("|", "%7C")])

    def test_a_source_record_without_id_does_not_stop_search_suggestions(self) -> None:
        broken_id = add("https://example.com/zebra/one", manual=True, title="Zebra stripes one")
        good_id = add("https://example.com/zebra/two", manual=True, title="Zebra stripes two")
        broken = lookup_url("https://example.com/zebra/one").path
        parsed = parse_markdown(broken)
        del parsed.frontmatter["ext"]["id"]
        del parsed.frontmatter["ext"]["status"]
        broken.write_text(render_record(parsed.frontmatter, parsed.body))
        output, error = self.web("PreToolUse", "WebSearch", "Zebra stripes")
        self.assertIn(str(broken), error)
        self.assertIn("ext.id", error)
        context = self.context(output)
        self.assertIn(f"- {good_id} (pending)", context)
        self.assertNotIn(broken_id, context)

    def test_parallel_pre_fetch_reserves_one_grant(self) -> None:
        import source_hooks

        source_id = add(ALIAS)
        self.assertEqual(main(["sources", "complete", source_id, "--why", "Review examples"]), 0)

        def request(index: int) -> dict:
            return source_hooks.handle({
                "hook_event_name": "PreToolUse", "tool_name": "WebFetch", "tool_input": {"url": URL},
                "session_id": f"session-{index}", "tool_use_id": f"tool-{index}",
            })["hookSpecificOutput"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            decisions = list(pool.map(request, range(4)))
        self.assertEqual(sum(result.get("permissionDecision") == "deny" for result in decisions), 3)

    def test_refresh_keeps_known_metadata_and_records_consultation_after_window_expires(self) -> None:
        source_id = add(ALIAS)
        match = lookup_url(URL)
        parsed = parse_markdown(match.path)
        parsed.frontmatter["ext"]["consulted"] = ["2000-01-01"]
        match.path.write_text(render_record(parsed.frontmatter, parsed.body), encoding="utf-8")
        self.fetch.side_effect = lambda url, **_: FetchedPage(url, NEW_PAGE)
        with patch("source_store.time", wraps=time) as clock:
            clock.time.return_value = 1000
            self.assertEqual(main(["sources", "complete", source_id, "--why", "Verify the dates"]), 0)
            self.web("PreToolUse", "WebFetch", ALIAS, tool_use_id="tool-1")
            clock.time.return_value = 2800
            output, error = self.web("PostToolUse", "WebFetch", ALIAS, tool_use_id="tool-1")
        self.assertEqual(error, "")
        for part in (source_id, "published", "updated", "consulted", "snapshot"):
            self.assertIn(part, self.context(output))
        updated = parse_markdown(match.path)
        ext = updated.frontmatter["ext"]
        self.assertEqual(ext["published"], "2024-12-01")
        self.assertEqual(ext["updated"], "2025-01-02")
        self.assertEqual(ext["consulted"], ["2000-01-01", date.today().isoformat()])
        for field in ("id", "url", "aliases", "title", "author", "status", "kind", "via"):
            self.assertEqual(ext[field], parsed.frontmatter["ext"][field])
        self.assertEqual(updated.body, parsed.body)
        self.assertIn("New snapshot", match.path.with_suffix(".txt").read_text())
        self.assertEqual(self.web("PostToolUse", "WebFetch", ALIAS, tool_use_id="tool-1"), ({}, ""))

    def test_refresh_preserves_snapshot_and_provenance_when_one_anchor_disappears(self) -> None:
        url = URL + "/2024/12/01/guide"
        source_id = add(url, manual=True, title="Ratchets")
        match = lookup_url(url)
        snapshot = match.path.with_suffix(".txt")
        text = "## Guide\nFirst anchor\nSecond anchor\n"
        with patch.object(sys, "stdin", io.StringIO(text)):
            self.assertEqual(main(["sources", "snapshot", source_id, "--from", "-", "--note", "Rendered page"]), 0)
        parsed = parse_markdown(match.path)
        claims = ('- c1 (sec. Guide): First claim — "First anchor"\n'
                  '- c2 (sec. Guide): Second claim — "Second anchor"\n')
        body = parsed.body.replace("## Key claims\n", f"## Key claims\n\n{claims}")
        parsed.frontmatter["ext"]["consulted"] = ["2000-01-01"]
        match.path.write_text(render_record(parsed.frontmatter, body))
        finish(source_id, status="used", description="Ratchets guide")
        self.fetch.side_effect = lambda url, **_: FetchedPage(
            url, "<h2>Guide</h2><p>First anchor</p>",
        )
        self.assertEqual(main(["sources", "complete", source_id, "--why", "Check the guide"]), 0)
        self.web("PreToolUse", "WebFetch", url, tool_use_id="refresh")
        output, error = self.web("PostToolUse", "WebFetch", url, tool_use_id="refresh")
        for message in (self.context(output), error):
            self.assertIn("c2 anchor missing", message)
            self.assertNotIn("c1 anchor missing", message)
        self.assertEqual(snapshot.read_text(), SNAPSHOT_HEADER + "\n" + text)
        ext = parse_markdown(match.path).frontmatter["ext"]
        self.assertEqual((ext["snapshot"], ext["snapshot_note"]), ("manual", "Rendered page"))
        self.assertEqual(ext["published"], "2024-12-01")
        self.assertEqual(ext["published_from"], "url")
        self.assertEqual(ext["consulted"], ["2000-01-01", date.today().isoformat()])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["sources", "check", source_id]), 0)

    def test_refresh_rejects_a_false_section_but_keeps_anchors_after_literal_heading_text(self) -> None:
        source_id = add(URL, fetch=lambda url: FetchedPage(url, "<h2>Installation</h2><p>Run setup.</p>"))
        path = lookup_url(URL).path
        snapshot = path.with_suffix(".txt")
        original = snapshot.read_text()
        claim = '- c1 (sec. Installation): Run setup — "Run setup."\n'
        path.write_text(path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claim}"))
        finish(source_id, status="used", description="Setup guide")

        candidates = (
            ("<h2>Examples</h2><p>## Installation</p><p>Run setup.</p>", False),
            ("<h2>Installation</h2><p>## Example syntax</p><p>Run setup.</p>", True),
        )
        for html, accepted in candidates:
            with self.subTest(accepted=accepted):
                self.fetch.side_effect = lambda url, **_: FetchedPage(url, html)
                self.assertEqual(main(["sources", "complete", source_id, "--why", "Check setup"]), 0)
                self.web("PreToolUse", "WebFetch", URL, tool_use_id=str(accepted))
                output, error = self.web("PostToolUse", "WebFetch", URL, tool_use_id=str(accepted))
                if accepted:
                    self.assertEqual(error, "")
                    self.assertIn("snapshot rewritten", self.context(output))
                    self.assertIn("## Example syntax", snapshot.read_text())
                else:
                    self.assertIn("c1 anchor missing", self.context(output))
                    self.assertIn("c1 anchor missing", error)
                    self.assertEqual(snapshot.read_text(), original)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["sources", "check", source_id]), 0)

    def test_missing_and_blank_snapshots_allow_refresh_without_duplicate_dates(self) -> None:
        source_id = add(ALIAS)
        snapshot = lookup_url(URL).path.with_suffix(".txt")
        snapshot.unlink()
        for blank in (False, True):
            if blank:
                snapshot.write_text("\n  \n")
            self.assertIn(f"registered as {source_id}", self.context(self.web("PreToolUse", "WebFetch", URL)[0]))
            result, error = self.web("PostToolUse", "WebFetch", URL)
            self.assertEqual(error, "")
            self.assertIn("snapshot", self.context(result))
            self.assertTrue(lookup_url(URL).has_snapshot)
        self.assertEqual(parse_markdown(lookup_url(URL).path).frontmatter["ext"]["consulted"],
                         [date.today().isoformat()])

    def test_search_suggests_five_distinct_sources_and_a_previous_query(self) -> None:
        paths = []
        for i in range(6):
            url = f"https://example.com/tool/{i}"
            add(url, manual=True, title=f"Ratchets guide {i}")
            paths.append(str(lookup_url(url).path))
        urls = [f"https://example.net/{i}" for i in range(12)]
        response = {"query": "https://example.net/echo", "results": [
            {"tool_use_id": "websearch", "content": [{"url": url, "title": "Result"} for url in urls]},
            {"url": urls[0], "title": "Duplicate"},
            "Summary mentioning https://example.net/not-a-result",
        ]}
        self.assertEqual(self.web("PostToolUse", "WebSearch", " Ratchets\tGUIDE ",
                                  session_id="previous", agent_id="a", tool_response=response), ({}, ""))
        log = self.root / "searches" / f"{date.today().isoformat()}.jsonl"
        entry = json.loads(log.read_text())
        self.assertTrue(entry["time"])
        self.assertEqual(entry["session_id"], "previous")
        self.assertEqual(entry["agent_id"], "a")
        self.assertEqual(entry["query"], " Ratchets\tGUIDE ")
        self.assertEqual(entry["urls"], urls)
        self.assertIn(log.relative_to(self.root).as_posix(), self.git("ls-files"))
        result, error = self.web("PreToolUse", "WebSearch", "ratchets guide")
        self.assertEqual(error, "")
        context = self.context(result)
        self.assertEqual(sum(path in context for path in paths), 5)
        self.assertEqual(context.count("pending"), 5)
        self.assertIn("Pending: Ratchets guide", context)
        self.assertIn(entry["time"], context)
        self.assertIn("previous", context)
        self.assertIn("12 URLs", context)
        self.assertEqual([line.removeprefix("- ") for line in context.splitlines() if line.startswith("- https:")],
                         urls[:10])
        self.assertNotIn("permissionDecision", result["hookSpecificOutput"])

    def test_search_query_with_url_and_empty_results_logs_no_urls(self) -> None:
        query = "read https://example.net/echo"
        self.web("PostToolUse", "WebSearch", query,
                 tool_response={"query": query, "results": [], "metadata": {"url": URL}})
        log = self.root / "searches" / f"{date.today().isoformat()}.jsonl"
        self.assertEqual(json.loads(log.read_text())["urls"], [])

    def test_malformed_record_does_not_block_lookup_capture_or_check(self) -> None:
        bad_id = add(manual=True, title="A corrupted record")
        good_id = add(URL, manual=True, title="A good record")
        bad_path = self.root / "records" / bad_id / f"{bad_id}.md"
        for frontmatter in ("ext: [", "ext:\n  published: 2026-02-31"):
            bad_path.write_text(f"---\n{frontmatter}\n---\n")
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(lookup_url(URL).id, good_id)
            self.assertIn(str(bad_path), error.getvalue())
        self.fetch.side_effect = lambda url, **_: FetchedPage(url, "<p>New text</p>")
        result, error = self.web("PostToolUse", "WebFetch", "https://example.org/new")
        self.assertIn("Registered as", self.context(result))
        self.assertIn(str(bad_path), error)
        catalog = (self.root / "records" / "MAP.md").read_text()
        self.assertIn(f"/{good_id}/{good_id}.md", catalog)
        self.assertNotIn(f"/{bad_id}/{bad_id}.md", catalog)
        output, error = self.web("PreToolUse", "WebSearch", "A good record")
        self.assertIn(good_id, self.context(output))
        self.assertIn(str(bad_path), error)
        orphan = self.root / "records" / "orphan"
        orphan.mkdir()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["sources", "check"]), 1)
        self.assertIn(str(bad_path), output.getvalue())
        self.assertIn(str(orphan / "orphan.md"), output.getvalue())
        self.assertIn(f"{good_id}: warning: pending", output.getvalue())

    def test_refresh_keeps_manual_snapshot_until_fetch_produces_text(self) -> None:
        self.fetch.side_effect = HTTPError(URL, 403, "Forbidden", {}, None)
        self.web("PostToolUse", "WebFetch", URL)
        match = lookup_url(URL)
        snapshot = match.path.with_suffix(".txt")
        with patch.object(sys, "stdin", io.StringIO("Text from the rendered page")):
            self.assertEqual(main(["sources", "snapshot", match.id, "--from", "-", "--note", "Rendered page"]), 0)

        decision, _ = self.web("PreToolUse", "WebFetch", URL)
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        pages = (None, "<script>no readable text</script>")
        for index, page in enumerate(pages):
            self.assertEqual(main(["sources", "complete", match.id, "--why", "Read the updated page"]), 0)
            self.fetch.side_effect = lambda url, **_: FetchedPage(url, page)
            self.web("PreToolUse", "WebFetch", URL, tool_use_id=f"attempt-{index}")
            _, error = self.web("PostToolUse", "WebFetch", URL, tool_use_id=f"attempt-{index}")
            self.assertIn("snapshot unavailable", error)
            self.assertEqual(snapshot.read_text(), SNAPSHOT_HEADER + "\nText from the rendered page")
            ext = parse_markdown(match.path).frontmatter["ext"]
            self.assertEqual((ext["snapshot"], ext["snapshot_note"]), ("manual", "Rendered page"))

        self.fetch.side_effect = lambda url, **_: FetchedPage(url, NEW_PAGE)
        self.assertEqual(main(["sources", "complete", match.id, "--why", "Read the updated page"]), 0)
        self.web("PreToolUse", "WebFetch", URL, tool_use_id="successful")
        self.assertEqual(self.web("PostToolUse", "WebFetch", URL, tool_use_id="successful")[1], "")
        self.assertIn("New snapshot", snapshot.read_text())
        ext = parse_markdown(match.path).frontmatter["ext"]
        self.assertEqual(ext["snapshot"], "web")
        self.assertNotIn("snapshot_note", ext)
        committed = self.git("show", f"HEAD:{match.path.relative_to(self.root)}")
        self.assertIn("snapshot: web", committed)
        self.assertNotIn("snapshot_note", committed)
        self.assertEqual(self.web("PreToolUse", "WebSearch", "unrelated zebra"), ({}, ""))

    def test_last_search_and_pending_are_scoped_to_session_and_agent(self) -> None:
        for session, agent, query in (("s", "a", "first"), ("s", "a", "latest"),
                                      ("s", "b", "other"), ("other", "a", "different session")):
            self.web("PostToolUse", "WebSearch", query, session_id=session, agent_id=agent,
                     tool_response={"results": []})
        ids = {}
        for session, agent, suffix, via in (
            ("s", "a", "one", "latest"), ("s", "b", "two", "other"),
            ("s", "c", "three", "direct fetch"), ("other", "a", "four", "different session"),
            ("s", None, "five", "direct fetch"),
        ):
            url = f"https://example.org/{suffix}"
            self.fetch.side_effect = lambda url, **_: FetchedPage(url, "<title>Testing</title><p>Text</p>")
            result, _ = self.web("PostToolUse", "WebFetch", url, session_id=session, agent_id=agent)
            match = lookup_url(url)
            ext = parse_markdown(match.path).frontmatter["ext"]
            self.assertEqual((ext["via"], ext["session_id"], ext.get("agent_id")), (via, session, agent))
            context = self.context(result)
            self.assertIn(f"Registered as {match.id} (pending). Close it with bkf sources finish {match.id}", context)
            self.assertIn('--status used --description "<description>"', context)
            self.assertIn('--status discarded --description "<description>" --reason "<reason>"', context)
            self.assertEqual(context.count("[--id NEW]"), 2)
            ids[suffix] = match.id
        finish(ids["two"], status="discarded", description="Duplicate", reason=f'copy-of:{ids["one"]}')
        result, _ = self.invoke("Stop")
        self.assertEqual(result["decision"], "block")
        for suffix in ("one", "three", "five"):
            self.assertIn(f'bkf sources finish {ids[suffix]} ', result["reason"])
        for suffix in ("two", "four"):
            self.assertNotIn(f'bkf sources finish {ids[suffix]} ', result["reason"])
        self.assertEqual(self.invoke("Stop", stop_hook_active=True), ({}, ""))
        result, _ = self.invoke("SubagentStop", agent_id="a")
        self.assertEqual(result["decision"], "block")
        self.assertIn(f'bkf sources finish {ids["one"]} ', result["reason"])
        self.assertIn("[--id NEW]", result["reason"])
        self.assertNotIn(f'bkf sources finish {ids["three"]} ', result["reason"])
        self.assertNotIn(f'bkf sources finish {ids["five"]} ', result["reason"])
        self.assertEqual(self.invoke("SubagentStop", agent_id="b"), ({}, ""))
        self.assertEqual(self.invoke("SubagentStop", agent_id="a", stop_hook_active=True), ({}, ""))

    def test_successful_webfetch_stays_pending_if_raw_fetch_gets_a_404(self) -> None:
        self.fetch.side_effect = HTTPError(URL, 404, "Not found", {}, None)
        result, error = self.web("PostToolUse", "WebFetch", URL)
        match = lookup_url(URL)
        self.assertIn(f"Registered as {match.id} (pending)", self.context(result))
        snapshot_command = f"bkf sources snapshot {match.id} --from"
        self.assertIn(snapshot_command, self.context(result))
        self.assertIn(snapshot_command, self.invoke("Stop")[0]["reason"])
        self.assertIn("HTTP 404", error)
        self.assertFalse(match.has_snapshot)
        self.assertEqual(parse_markdown(match.path).frontmatter["ext"]["status"], "pending")
        self.assertEqual(self.web("PostToolUseFailure", "WebFetch", ALIAS), ({}, ""))
        self.assertIsNone(lookup_url(ALIAS))

    def test_capture_includes_the_other_page_redirect_warning(self) -> None:
        self.fetch.return_value = FetchedPage(ALIAS, "<p>Different page</p>")
        self.fetch.side_effect = None
        result, error = self.web("PostToolUse", "WebFetch", URL)
        warning = error.strip().removeprefix("bkf sources: warning: ")
        self.assertIn(f"{URL} redirected to {ALIAS}", warning)
        self.assertIn(warning, self.context(result))
        self.assertIsNone(lookup_url(ALIAS))

    def test_refresh_follows_a_script_redirect(self) -> None:
        source_id = add(URL, manual=True, title="Ratchet testing")
        pages = {
            URL: FetchedPage(URL, "<script>location.replace('/redirect')</script>"),
            ALIAS: FetchedPage(ALIAS, NEW_PAGE),
        }
        self.fetch.side_effect = lambda url, **_: pages[url]
        original = parse_markdown(lookup_url(URL).path).frontmatter["ext"]
        result, error = self.web("PostToolUse", "WebFetch", URL)
        for message in (self.context(result), error):
            self.assertIn(f"{URL} redirected to {ALIAS}", message)
        self.assertIn("snapshot rewritten", self.context(result))
        match = lookup_url(URL)
        self.assertEqual(match.id, source_id)
        ext = parse_markdown(match.path).frontmatter["ext"]
        self.assertEqual(ext["redirected_to"], ALIAS)
        for field in ("url", "aliases", "title", "author", "published", "updated"):
            self.assertEqual(ext[field], original[field])
        self.assertNotIn("published_from", ext)
        self.assertIsNone(lookup_url(ALIAS))
        self.assertEqual(match.path.with_suffix(".txt").read_text(), "New snapshot\n")
        self.assertEqual([call.args[0] for call in self.fetch.call_args_list], [URL, ALIAS])

    def test_refresh_redirect_preserves_established_alias_and_saved_evidence(self) -> None:
        source_id = add(URL, fetch=lambda url: FetchedPage(ALIAS, PAGE + "<h2>Setup</h2><p>Run setup.</p>"))
        path = lookup_url(URL).path
        snapshot = path.with_suffix(".txt")
        original = snapshot.read_text()
        claim = '- c1 (sec. Setup): Run it — "Run setup."\n'
        path.write_text(path.read_text().replace("## Key claims\n", f"## Key claims\n\n{claim}"))
        finish(source_id, status="used", description="Setup guide")
        self.assertEqual(lookup_url(ALIAS).id, source_id)
        destination = "https://example.org/other"
        self.fetch.side_effect = lambda url, **_: FetchedPage(destination, NEW_PAGE)
        self.assertEqual(main(["sources", "complete", source_id, "--why", "Check the guide"]), 0)
        self.web("PreToolUse", "WebFetch", URL, tool_use_id="refresh")
        output, error = self.web("PostToolUse", "WebFetch", URL, tool_use_id="refresh")
        for message in (self.context(output), error):
            self.assertIn(f"{URL} redirected to {destination}", message)
            self.assertIn("c1 anchor missing", message)
        self.assertEqual(snapshot.read_text(), original)
        self.assertEqual(lookup_url(ALIAS).id, source_id)
        self.assertIsNone(lookup_url(destination))

    def test_complete_extends_an_existing_store_schema_and_appends_reasons(self) -> None:
        source_id = add(ALIAS)
        path = self.root / "ext-schema.yaml"
        old_schema = json.loads(path.read_text())
        fields = old_schema["properties"]["ext"]["properties"]
        for field in ("session_id", "agent_id", "completions"):
            fields.pop(field)
        path.write_text(json.dumps(old_schema))

        for reason in ("Check new date", "Check a new section"):
            self.assertEqual(main(["sources", "complete", source_id, "--why", reason]), 0)
        committed = json.loads(self.git("show", "HEAD:ext-schema.yaml"))
        fields = committed["properties"]["ext"]["properties"]
        self.assertTrue({"session_id", "agent_id", "completions"} <= fields.keys())
        ext = parse_markdown(lookup_url(URL).path).frontmatter["ext"]
        self.assertEqual([entry["why"] for entry in ext["completions"]], ["Check new date", "Check a new section"])
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["validate", str(self.root)]), 0, stdout.getvalue())

    def test_handlers_do_nothing_without_a_store(self) -> None:
        missing = self.root.parent / "missing"
        with patch.dict(os.environ, {"BKF_SOURCES_DIR": str(missing)}):
            for event in ("PreToolUse", "PostToolUse"):
                self.assertEqual(self.web(event, "WebFetch", URL), ({}, ""))
                self.assertEqual(self.web(event, "WebSearch", "query"), ({}, ""))
            for event in ("Stop", "SubagentStop"):
                self.assertEqual(self.invoke(event, agent_id="a"), ({}, ""))
        self.assertFalse(missing.exists())
        self.fetch.assert_not_called()

    def test_internal_error_allows_the_tool_call(self) -> None:
        with patch("source_store._lookup_url", side_effect=RuntimeError("lookup failed")):
            result, error = self.web("PreToolUse", "WebFetch", URL)
        self.assertEqual(result, {})
        self.assertIn("lookup failed", error)

    def test_parallel_search_log_appends_commit_each_entry(self) -> None:
        import source_hooks

        def record(index: int) -> None:
            source_hooks.handle({"hook_event_name": "PostToolUse", "tool_name": "WebSearch",
                                 "tool_input": {"query": f"query {index}"}, "session_id": "s"})

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(record, range(4)))
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "5")
        content = self.git("show", f"HEAD:searches/{date.today().isoformat()}.jsonl")
        self.assertEqual({json.loads(line)["query"] for line in content.splitlines()},
                         {f"query {i}" for i in range(4)})

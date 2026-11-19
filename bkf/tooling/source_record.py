"""Define the source record schema, identifiers and claim format."""

from __future__ import annotations

import io
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from markdown_it import MarkdownIt
from ruamel.yaml import YAML

from bkf_common import ParsedMarkdown
from search import STOPWORDS
from source_page import (
    INVALID_URL_CHARS, KINDS, SNAPSHOT_HEADER, SNAPSHOT_HEADING, UNKNOWN,
    clean, clean_heading, encode_snapshot, normalize_url, site_domain, site_name,
)


ID_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
REASON_PATTERN = rf"^(?:dead|paywall|copy-of:{ID_PATTERN}|marketing|outdated)$"
DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
NONEMPTY = {"type": "string", "pattern": r"\S"}
KNOWN_DATE = {"type": "string", "pattern": DATE_PATTERN, "format": "date"}
MAYBE_DATE = {"anyOf": [KNOWN_DATE, {"const": UNKNOWN}]}
WEB_URL = {
    "type": "string",
    "pattern": rf"^[Hh][Tt][Tt][Pp][Ss]?://[^{INVALID_URL_CHARS}]+(?![\s\S])",
    "format": "http-url",
}
REDIRECT_FIELDS = {"redirected_to": WEB_URL}
PUBLICATION_FIELDS = {"published_from": {"const": "url"}}
CAPTURE_FIELDS = {
    "session_id": NONEMPTY,
    "agent_id": NONEMPTY,
    "completions": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"date": KNOWN_DATE, "why": NONEMPTY},
            "required": ["date", "why"],
            "additionalProperties": False,
        },
    },
}
SNAPSHOT_FIELDS = {
    "snapshot": {"enum": ["web", "manual", "none"]},
    "snapshot_note": NONEMPTY,
}
SNAPSHOT_NOTE_RULE = {
    "if": {"properties": {"snapshot": {"const": "manual"}}, "required": ["snapshot"]},
    "then": {"required": ["snapshot_note"]},
    "else": {"not": {"required": ["snapshot_note"]}},
}
EXT_FIELDS = {
    "type": {"const": "source"},
    "id": {"type": "string", "pattern": f"^{ID_PATTERN}$"},
    "url": {"anyOf": [WEB_URL, {"const": UNKNOWN}]},
    "aliases": {"type": "array", "items": WEB_URL, "uniqueItems": True},
    **REDIRECT_FIELDS,
    "title": NONEMPTY,
    "author": NONEMPTY,
    "published": MAYBE_DATE,
    **PUBLICATION_FIELDS,
    "updated": MAYBE_DATE,
    "consulted": {"type": "array", "minItems": 1, "items": KNOWN_DATE},
    "kind": {"enum": list(KINDS)},
    "via": NONEMPTY,
    "status": {"enum": ["pending", "used", "discarded"]},
    "reason": {"type": "string", "pattern": REASON_PATTERN},
    **SNAPSHOT_FIELDS,
    **CAPTURE_FIELDS,
}
SOURCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["ext"],
    "properties": {
        "ext": {
            "type": "object",
            "required": [field for field in EXT_FIELDS
                         if field not in {"reason", "updated", "snapshot_note", *REDIRECT_FIELDS,
                                          *CAPTURE_FIELDS, *PUBLICATION_FIELDS}],
            "properties": EXT_FIELDS,
            "unevaluatedProperties": False,
            "if": {"properties": {"status": {"const": "discarded"}}, "required": ["status"]},
            "then": {"required": ["reason"]},
            "else": {"not": {"required": ["reason"]}},
            "allOf": [SNAPSHOT_NOTE_RULE],
        }
    },
}
FORMATS = FormatChecker(formats=["date"])


@FORMATS.checks("http-url", raises=ValueError)
def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return True
    return not re.search(r"%(?![0-9A-Fa-f]{2})", value) and bool(normalize_url(value))


SOURCE_VALIDATOR = Draft202012Validator(SOURCE_SCHEMA, format_checker=FORMATS)

RECORD_BODY = "\n## Key claims\n\n## Notes\n"
CLAIM = re.compile(r'^\s*-\s+(c\d+)\s+\(sec\. (.+?)\):\s+.+?\s+—\s+"(.+)"\s*$')
QUOTES = str.maketrans("‘’‚‛“”„‟", "''''\"\"\"\"")
MARKDOWN = MarkdownIt()
ORG_WORDS = {"association", "co", "company", "corp", "corporation", "foundation", "group",
             "inc", "institute", "labs", "llc", "ltd", "team", "university"}
GENERIC_LABELS = {"ai", "www", "docs", "github", "gitlab"}
GENERIC_TITLES = {"", "access denied", "documentation", "error", "forbidden", "home", "homepage",
                  "just a moment", "not found", "page not found", "untitled", "welcome"}
GENERIC_PATH_SEGMENTS = {"docs", "documentation", "home", "index"}


def _ascii_words(value: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", folded)


def _path_words(url: str, excluded: set[str]) -> list[str]:
    for segment in reversed(urlsplit(url).path.split("/")):
        slug = re.sub(r"\.(?:html?|md|php)$", "", unquote(segment), flags=re.IGNORECASE)
        if slug.casefold() in GENERIC_PATH_SEGMENTS or re.fullmatch(r"v?\d+(?:\.\d+)*", slug, re.IGNORECASE):
            continue
        words = [word for word in _ascii_words(slug) if word not in excluded]
        if words:
            return words
    return []


def source_id_base(author: str, person: bool | None, title: str, url: str, *, site: str = "") -> str:
    site_label = _ascii_words(site_name(url))
    label = site_label
    names = [name.strip() for name in author.split(",")]
    if person is not False and len(names) > 1 and all(len(name.split()) > 1 for name in names):
        author = names[0]
    words = [word for word in _ascii_words(author) if word != UNKNOWN]
    if words:
        is_org = person is False or (person is None and (
            bool(ORG_WORDS.intersection(words)) or bool(label and words[0] == label[0])
        ))
        if is_org:
            label = words
        else:
            surname = author.partition(",")[0] if "," in author else author.split()[-1]
            label = [word for word in _ascii_words(surname) if word != UNKNOWN] or words[-1:]
    raw_title = _ascii_words(title)
    domain_words = _ascii_words(site_domain(url))
    site_words = [word for word in _ascii_words(site) if word != UNKNOWN]
    generic_labels = GENERIC_LABELS | {UNKNOWN}
    if not set(label) - generic_labels:
        candidates = [site_words, site_label]
        if raw_title == domain_words:
            candidates.append(domain_words)
        label = next((words for words in candidates if set(words) - generic_labels), [])

    excluded = STOPWORDS | set(label) | {UNKNOWN} | (GENERIC_LABELS.intersection(site_label) - {"ai"})
    title_words = [word for word in raw_title if word not in excluded]
    if (not title_words or " ".join(raw_title) in GENERIC_TITLES
            or raw_title in (domain_words, site_words)):
        title_words = _path_words(url, excluded)
    return "-".join(label + title_words[:4])[:120].rstrip("-") or "source"


def render_record(metadata: dict, body: str) -> str:
    yaml = YAML()
    yaml.width = 4096
    output = io.StringIO()
    yaml.dump(metadata, output)
    return f"---\n{output.getvalue()}---\n{body}"


def catalog_description(text: str) -> str:
    # Inventory rows embed descriptions in Markdown. Keep source text literal.
    return re.sub(r"([\\\[<])", r"\\\1", text)


def key_claims(body: str) -> str:
    tokens = MARKDOWN.parse(body)
    lines = body.splitlines()
    for index, token in enumerate(tokens):
        if (token.type == "heading_open" and token.tag == "h2" and token.level == 0
                and tokens[index + 1].content == "Key claims"):
            end = next((item.map[0] for item in tokens[index + 1:]
                        if item.type == "heading_open" and item.level == 0 and item.tag in {"h1", "h2"}),
                       len(lines))
            return "\n".join(lines[token.map[1]:end]).strip()
    return ""


def _snapshot(path: Path) -> str:
    try:
        return path.with_suffix(".txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def manual_snapshot_command(source_id: str) -> str:
    return f'bkf sources snapshot {source_id} --from FILE --note "<where the text came from>"'


def normalize_manual_headings(content: str) -> str:
    lines = io.StringIO(content, newline="").readlines()
    tokens = MARKDOWN.parse(content.removeprefix("\ufeff"))
    headings = set()
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.markup.startswith("#"):
            line_number = token.map[0]
            line = lines[line_number]
            ending = line[len(line.rstrip("\r\n")):]
            lines[line_number] = clean_heading(tokens[index + 1].content) + ending
            headings.add(line_number)
    return encode_snapshot(((line, index in headings) for index, line in enumerate(lines)), marked=True)


def _snapshot_sections(snapshot: str, *, manual: bool) -> dict[str, list[str]]:
    lines = io.StringIO(snapshot.translate(QUOTES), newline=None).readlines()
    escaped = bool(lines and lines[0].removesuffix("\n") == SNAPSHOT_HEADER)
    if escaped:
        lines = lines[1:]
    fenced = set()
    if manual and not escaped:
        for token in MARKDOWN.parse(snapshot.removeprefix("\ufeff")):
            if token.type == "fence":
                fenced.update(range(*token.map))
    starts = [index for index, line in enumerate(lines) if line.startswith(SNAPSHOT_HEADING) and index not in fenced]
    if escaped:
        lines = [line.removeprefix("\\") for line in lines]
    sections = defaultdict(list)
    for start, end in zip(starts, starts[1:] + [len(lines)]):
        heading = clean_heading(lines[start].removeprefix(SNAPSHOT_HEADING))
        sections[heading].append(clean("".join(lines[start:end])))
    return sections


def check_claims(path: Path, body: str, ext: dict, *, candidate: str | None = None) -> list[str]:
    used = ext.get("status") == "used"
    kind = ext.get("snapshot")
    claims = key_claims(body)
    if not used and not claims:
        return []
    snapshot = candidate if candidate is not None else (_snapshot(path) if kind != "none" else "")
    if used and not snapshot.strip():
        restore = manual_snapshot_command(path.stem)
        if kind == "web":
            restore = f"fetch the registered URL again to restore {path.stem}.txt"
        return [f"used record has no snapshot text. Its claims cannot be verified. To restore the text, {restore}"]
    if used and not claims:
        return ["used record needs ## Key claims"]
    sections = _snapshot_sections(snapshot, manual=kind == "manual")
    errors = []
    for line in claims.splitlines():
        if not line.strip():
            continue
        claim = CLAIM.fullmatch(line.translate(QUOTES))
        if not claim or not clean_heading(claim[2]) or not clean(claim[3]):
            errors.append(f"invalid Key claims entry: {line.strip()}")
            continue
        claim_id, heading, anchor = claim.groups()
        if not any(clean(anchor) in section for section in sections.get(clean_heading(heading), ())):
            errors.append(f'{claim_id} anchor missing from section "{heading}" in {path.stem}.txt: {anchor}')
    return errors


def check_record(path: Path, parsed: ParsedMarkdown) -> tuple[list[str], bool]:
    metadata = parsed.frontmatter
    ext = metadata.get("ext")
    errors = []
    if not clean(metadata.get("description")):
        errors.append("description is required")
    if metadata.get("bkf") != "document":
        errors.append("bkf must be document")
    tags = metadata.get("tags")
    if not isinstance(tags, list) or not tags or not all(clean(tag) for tag in tags):
        errors.append("tags must contain non-empty values")
    for error in SOURCE_VALIDATOR.iter_errors({"ext": ext}):
        location = ".".join(map(str, error.absolute_path))
        errors.append(f"{location}: {error.message}")
    ext = ext if isinstance(ext, dict) else {}
    if ext.get("id") != path.stem:
        errors.append("ext.id must match the record filename")
    errors.extend(check_claims(path, parsed.body, ext))
    return errors, ext.get("status") == "pending"

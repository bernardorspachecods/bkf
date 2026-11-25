"""Load attached-text search configuration and cut sidecars into located passages."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bkf_common import BKFInputError, SEARCH_CONFIG_NAME, read_text_preserving_newlines

WORD_TOKEN = re.compile(r"\S+")


@dataclass(frozen=True)
class LabelRule:
    label: str
    when: tuple[tuple[str, re.Pattern[str]], ...] | None = None


@dataclass(frozen=True)
class Locator:
    pattern: re.Pattern[str]
    labels: tuple[LabelRule, ...]


@dataclass(frozen=True)
class AttachedTextEntry:
    documents: str
    text: str
    locator: Locator | None
    words: int = 220
    stride: int = 160


@dataclass(frozen=True)
class SearchConfig:
    attached_text: tuple[AttachedTextEntry, ...]
    embeddings: EmbeddingsConfig | None


@dataclass(frozen=True)
class EmbeddingsConfig:
    model: str = "BAAI/bge-small-en-v1.5"
    mode: str = "lexical"


@dataclass(frozen=True)
class TextPassage:
    text: str
    start: int
    end: int
    locator: dict | None


def _fail(key: str, message: str) -> BKFInputError:
    return BKFInputError(f"{SEARCH_CONFIG_NAME}: `{key}` {message}")


def _mapping(value: object, key: str) -> dict:
    if not isinstance(value, dict):
        raise _fail(key, "must be a mapping")
    if any(not isinstance(name, str) for name in value):
        raise _fail(key, "must have string keys")
    return value


def _unknown_keys(value: dict, allowed: set[str], prefix: str) -> None:
    for key in value:
        if key not in allowed:
            raise _fail(f"{prefix}.{key}" if prefix else str(key), "is not a known key")


def _compile(pattern: object, key: str) -> re.Pattern[str]:
    if not isinstance(pattern, str):
        raise _fail(key, "must be a regex string")
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise _fail(key, f"is not a valid regex: {exc}") from exc


def _locator(value: object) -> Locator:
    data = _mapping(value, "locator")
    _unknown_keys(data, {"pattern", "labels"}, "locator")
    pattern = _compile(data.get("pattern"), "locator.pattern")
    names = set(pattern.groupindex)
    if not names:
        raise _fail("locator.pattern", "must contain at least one named group")
    if "label" in names:
        raise _fail("locator.pattern", "must not use the named group `label`")

    labels = data.get("labels")
    if not isinstance(labels, list) or not labels:
        raise _fail("locator.labels", "must be a non-empty list")
    rules: list[LabelRule] = []
    for index, raw_rule in enumerate(labels):
        key = f"locator.labels[{index}]"
        rule = _mapping(raw_rule, key)
        _unknown_keys(rule, {"when", "label"}, key)
        label = rule.get("label")
        if not isinstance(label, str):
            raise _fail(f"{key}.label", "must be a string")
        try:
            fields = {field for _, field, _, _ in string.Formatter().parse(label) if field is not None}
        except ValueError as exc:
            raise _fail(f"{key}.label", f"has invalid placeholders: {exc}") from exc
        if any(not field or field not in names for field in fields):
            raise _fail(f"{key}.label", "may use only named groups from locator.pattern")
        when_value = rule.get("when")
        if when_value is None:
            when = None
            if index != len(labels) - 1:
                raise _fail(f"{key}.when", "may be omitted only on the last rule")
        else:
            when_mapping = _mapping(when_value, f"{key}.when")
            compiled: list[tuple[str, re.Pattern[str]]] = []
            for group, condition in when_mapping.items():
                if group not in names:
                    raise _fail(f"{key}.when.{group}", "is not a named group of locator.pattern")
                compiled.append((group, _compile(condition, f"{key}.when.{group}")))
            when = tuple(compiled)
        rules.append(LabelRule(label, when))
    if rules[-1].when is not None:
        raise _fail("locator.labels", "the last rule must omit `when`")
    return Locator(pattern, tuple(rules))


def load_search_config(bundle_root: Path) -> SearchConfig | None:
    """Load and validate `search.yaml`, returning None when it is absent."""
    path = bundle_root / SEARCH_CONFIG_NAME
    if not path.is_file():
        return None
    yaml = YAML(typ="safe")
    yaml.version = (1, 2)
    yaml.allow_duplicate_keys = False
    try:
        data = yaml.load(read_text_preserving_newlines(path))
    except (YAMLError, BKFInputError) as exc:
        raise BKFInputError(f"cannot use {SEARCH_CONFIG_NAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise BKFInputError(f"{SEARCH_CONFIG_NAME} must be a mapping")
    _unknown_keys(data, {"attached_text", "embeddings"}, "")
    raw_entries = data.get("attached_text", [])
    if not isinstance(raw_entries, list):
        raise _fail("attached_text", "must be a list")
    entries: list[AttachedTextEntry] = []
    for index, raw_entry in enumerate(raw_entries):
        prefix = f"attached_text[{index}]"
        item = _mapping(raw_entry, prefix)
        _unknown_keys(item, {"documents", "text", "locator", "chunk"}, prefix)
        documents = item.get("documents")
        if not isinstance(documents, str) or not documents.strip():
            raise _fail(f"{prefix}.documents", "must be a non-empty string")
        text_path = item.get("text")
        if not isinstance(text_path, str) or not text_path.strip():
            raise _fail(f"{prefix}.text", "must be a non-empty string")
        relative_path = Path(text_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise _fail(f"{prefix}.text", "must be relative and contain no `..`")
        if re.search(r"\{(?!stem\})[^{}]*\}", text_path):
            raise _fail(f"{prefix}.text", "may use `{stem}` as its only placeholder")
        # Reject unmatched or otherwise unsupported braces as well.
        if text_path.replace("{stem}", "").find("{") >= 0 or text_path.replace("{stem}", "").find("}") >= 0:
            raise _fail(f"{prefix}.text", "may use `{stem}` as its only placeholder")
        locator = _locator(item["locator"]) if "locator" in item else None
        chunk = item.get("chunk", {})
        chunk_mapping = _mapping(chunk, f"{prefix}.chunk")
        _unknown_keys(chunk_mapping, {"words", "stride"}, f"{prefix}.chunk")
        words = chunk_mapping.get("words", 220)
        stride = chunk_mapping.get("stride", 160)
        if isinstance(words, bool) or not isinstance(words, int) or words <= 0:
            raise _fail(f"{prefix}.chunk.words", "must be a positive integer")
        if isinstance(stride, bool) or not isinstance(stride, int) or not 0 < stride <= words:
            raise _fail(f"{prefix}.chunk.stride", "must be an integer with 0 < stride <= words")
        entries.append(AttachedTextEntry(documents, text_path, locator, words, stride))
    embeddings = None
    if "embeddings" in data:
        raw_embeddings = _mapping(data["embeddings"], "embeddings")
        _unknown_keys(raw_embeddings, {"model", "mode"}, "embeddings")
        model = raw_embeddings.get("model", "BAAI/bge-small-en-v1.5")
        if not isinstance(model, str) or not model.strip():
            raise _fail("embeddings.model", "must be a non-empty string")
        mode = raw_embeddings.get("mode", "lexical")
        if not isinstance(mode, str) or mode not in {"lexical", "hybrid"}:
            raise _fail("embeddings.mode", "must be `lexical` or `hybrid`")
        embeddings = EmbeddingsConfig(model.strip(), mode)
    return SearchConfig(tuple(entries), embeddings)


def embeddings_config(root: Path) -> EmbeddingsConfig:
    """Return the configured embeddings model for a bundle, or its defaults."""
    config = load_search_config(root)
    return config.embeddings if config is not None and config.embeddings is not None else EmbeddingsConfig()


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a slash-separated glob to a full-path regex with segment-aware `**`."""
    segments = pattern.split("/")
    result = "^"
    for index, segment in enumerate(segments):
        if segment == "**":
            if index == 0 and index == len(segments) - 1:
                result += ".*"
            elif index == 0:
                result += "(?:[^/]+/)*"
            elif index == len(segments) - 1:
                result += "(?:/[^/]+)*"
            else:
                result += "(?:/[^/]+)*/"
            continue
        if index > 0 and not (segments[index - 1] == "**" and index - 1 < len(segments) - 1):
            result += "/"
        for char in segment:
            if char == "*":
                result += "[^/]*"
            elif char == "?":
                result += "[^/]"
            else:
                result += re.escape(char)
    return re.compile(result + "$")


def attached_text_for(
    config: SearchConfig, bundle_root: Path, document: Path
) -> tuple[Path, AttachedTextEntry] | None:
    """Return the first matching document's existing sidecar, if configured."""
    try:
        relative = document.relative_to(bundle_root).as_posix()
    except ValueError:
        return None
    for entry in config.attached_text:
        if _glob_regex(entry.documents).fullmatch(relative) is None:
            continue
        sidecar = document.parent / entry.text.replace("{stem}", document.stem)
        return (sidecar, entry) if sidecar.is_file() else None
    return None


def read_attached_text(path: Path) -> str:
    """Read UTF-8 sidecar text while preserving line endings and replacing invalid bytes."""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as source:
        return source.read()


def _marker_locator(match: re.Match[str], locator: Locator) -> dict:
    groups = match.groupdict()
    selected = locator.labels[-1]
    for rule in locator.labels:
        if rule.when is None or all(pattern.fullmatch(groups.get(name) or "") for name, pattern in rule.when):
            selected = rule
            break
    return {"label": selected.label.format_map(groups), **groups}


def _cut_segment(text: str, start: int, end: int, entry: AttachedTextEntry, locator: dict | None) -> list[TextPassage]:
    words = list(WORD_TOKEN.finditer(text, start, end))
    count = len(words)
    if not count:
        return []
    result: list[TextPassage] = []
    for first in range(0, max(1, count - entry.words + entry.stride), entry.stride):
        last = min(first + entry.words, count)
        if last - first < 25 and first != 0:
            continue
        char_start = words[first].start()
        char_end = words[last - 1].end()
        passage_slice = text[char_start:char_end]
        result.append(TextPassage(" ".join(passage_slice.split()), char_start, char_end, locator))
    return result


def text_passages(text: str, entry: AttachedTextEntry) -> list[TextPassage]:
    """Split sidecar text at marker lines and return offset-preserving word windows."""
    if entry.locator is None:
        return _cut_segment(text, 0, len(text), entry, None)
    passages: list[TextPassage] = []
    segment_start = 0
    segment_locator: dict | None = None
    offset = 0
    while offset < len(text):
        lf = text.find("\n", offset)
        cr = text.find("\r", offset)
        endings = [position for position in (lf, cr) if position >= 0]
        if not endings:
            line = text[offset:]
        else:
            end = min(endings)
            end += 2 if text.startswith("\r\n", end) else 1
            line = text[offset:end]
        content = line[:-2] if line.endswith("\r\n") else line[:-1] if line.endswith(("\n", "\r")) else line
        match = entry.locator.pattern.fullmatch(content)
        if match is not None:
            passages.extend(_cut_segment(text, segment_start, offset, entry, segment_locator))
            segment_start = offset + len(line)
            segment_locator = _marker_locator(match, entry.locator)
        offset += len(line)
    passages.extend(_cut_segment(text, segment_start, len(text), entry, segment_locator))
    return passages

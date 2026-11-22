"""Rewrite bundle-root-absolute Markdown link destinations after a file move.

rewrite_markdown and rewrite_html are pure text functions. apply_moves and
planned_updates read and write the files of one bundle.
"""

import contextlib
import io
import os
import posixpath
import re
from pathlib import Path
from urllib.parse import quote, unquote

import generate_inventory
from bkf_common import MAP_NAME, find_bundles, in_nested_bundle, is_bundle_root_map, read_text_preserving_newlines

# A NUL marks characters that sit inside inline code, so no link pattern matches them.
_MASK = "\x00"
# Container prefix before a fence: indentation, blockquote markers and list markers.
_FENCE_PREFIX = r"[ \t>]*(?:(?:[-*+]|\d+[.)])[ \t]+[ \t>]*)*"
_FENCE_OPEN = re.compile(r"^" + _FENCE_PREFIX + r"(`{3,}|~{3,})")
_FENCE_CLOSE = re.compile(r"^" + _FENCE_PREFIX + r"(`{3,}|~{3,})[ \t]*$")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
# Inline link or image: the destination follows "](" and ends at whitespace or ")".
_INLINE_DEST = re.compile(r"\]\([ \t]*(<[^<>\n\x00]*>|[^\s)\x00]*)")
# Reference definition at the start of a line: "[label]: destination".
_REF_DEST = re.compile(r"^ {0,3}\[[^\]\n\x00]+\]:[ \t]*(<[^<>\n\x00]*>|\S+)")


def _markdown_lines(text: str) -> list[tuple[str, str, list[tuple[int, int]]]]:
    """Return (line, body, destination spans) for each line of text.

    body is the line without its line break. Fenced code has no destination
    spans; inline code is masked before the link patterns are matched.
    """
    lines = []
    fence = None  # (marker character, length) of the open fenced code block
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if fence:
            close = _FENCE_CLOSE.match(body)
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= fence[1]:
                fence = None
            lines.append((line, body, []))
            continue
        opening = _FENCE_OPEN.match(body)
        if opening:
            fence = (opening.group(1)[0], len(opening.group(1)))
            lines.append((line, body, []))
            continue
        lines.append((line, body, _destination_spans(body)))
    return lines


def _destination_spans(body: str) -> list[tuple[int, int]]:
    masked = _CODE_SPAN.sub(lambda m: _MASK * len(m.group(0)), body)
    spans = [m.span(1) for m in _INLINE_DEST.finditer(masked)]
    ref = _REF_DEST.match(masked)
    if ref:
        spans.append(ref.span(1))
    return spans


def rewrite_markdown(text: str, moves: dict[str, str]) -> str:
    """Return text with link destinations that point to a key of moves replaced.

    moves maps an old bundle-root-relative file path to its new path. Only
    destinations starting with "/" are candidates; fragments and titles are kept.
    """
    return "".join(
        _rewrite_line(body, spans, moves) + line[len(body):]
        for line, body, spans in _markdown_lines(text)
    )


def markdown_link_paths(text: str) -> list[str]:
    """Return the percent-decoded bundle-root-relative paths of the absolute link destinations in text.

    Fragments are dropped. Links inside code spans and fenced code are not returned.
    """
    paths = []
    for _line, body, spans in _markdown_lines(text):
        for start, end in spans:
            dest = body[start:end]
            inner = dest[1:-1] if dest.startswith("<") and dest.endswith(">") else dest
            if inner.startswith("/"):
                paths.append(unquote(inner.partition("#")[0][1:]))
    return paths


def _rewrite_line(body: str, spans: list[tuple[int, int]], moves: dict[str, str]) -> str:
    result = body
    # Replace from the end so earlier offsets stay valid.
    for start, end in sorted(spans, reverse=True):
        dest = body[start:end]
        new = _retarget(dest, moves)
        if new != dest:
            result = result[:start] + new + result[end:]
    return result


def _retarget(dest: str, moves: dict[str, str]) -> str:
    angled = dest.startswith("<") and dest.endswith(">")
    inner = dest[1:-1] if angled else dest
    if not inner.startswith("/"):
        return dest
    path, hash_mark, fragment = inner.partition("#")
    old = unquote(path[1:])
    if old not in moves:
        return dest
    new = "/" + quote(moves[old], safe="/") + hash_mark + fragment
    return f"<{new}>" if angled else new


# Markup that is not a link: comments, and tags whose attributes are scanned.
_HTML_TAG = re.compile(
    r"<!--.*?-->"
    r"|<[A-Za-z][^\s/>]*(?:\s+[^\s\"'>/=]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?)*\s*/?>",
    re.DOTALL,
)
_HTML_ATTR = re.compile(
    r"""\s+([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|[^\s"'=<>`]+))?"""
)
_RAW_TEXT_END = {
    "script": re.compile(r"</script\s*>", re.IGNORECASE),
    "style": re.compile(r"</style\s*>", re.IGNORECASE),
}
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:")


def rewrite_html(text: str, old_path: str, new_path: str, moves: dict[str, str]) -> str:
    """Return HTML text with relative href/src values recomputed after a move.

    text is the content of the file that lived at old_path and now lives at
    new_path. Links to moved files are retargeted, and links from a moved file
    are re-based on its new directory. Script and style content and comments
    are left alone.
    """
    out = []
    last = 0
    pos = 0
    while True:
        match = _HTML_TAG.search(text, pos)
        if match is None:
            break
        markup = match.group(0)
        pos = match.end()
        if markup.startswith("<!--"):
            continue
        name = re.match(r"<([A-Za-z][^\s/>]*)", markup).group(1).lower()
        out.append(text[last : match.start()])
        out.append(_rewrite_tag(markup, old_path, new_path, moves))
        last = match.end()
        if name in _RAW_TEXT_END and not markup.endswith("/>"):
            # The raw content up to the closing tag is copied verbatim.
            end = _RAW_TEXT_END[name].search(text, pos)
            pos = end.start() if end else len(text)
    out.append(text[last:])
    return "".join(out)


def _rewrite_tag(tag: str, old_path: str, new_path: str, moves: dict[str, str]) -> str:
    name_end = re.match(r"<[A-Za-z][^\s/>]*", tag).end()
    result = tag
    for attr in reversed(list(_HTML_ATTR.finditer(tag, name_end))):
        if attr.group(1).lower() not in ("href", "src"):
            continue
        if attr.group(2) is not None:
            group = 2
        elif attr.group(3) is not None:
            group = 3
        else:
            continue
        start, end = attr.span(group)
        value = tag[start:end]
        new = _retarget_html(value, old_path, new_path, moves)
        if new != value:
            result = result[:start] + new + result[end:]
    return result


def _retarget_html(value: str, old_path: str, new_path: str, moves: dict[str, str]) -> str:
    if not value or value.startswith(("/", "#", "//")) or _SCHEME.match(value):
        return value
    cut = min((i for i in (value.find("?"), value.find("#")) if i >= 0), default=len(value))
    path_part, suffix = value[:cut], value[cut:]
    if not path_part:
        return value
    old_dir = posixpath.dirname(old_path)
    new_dir = posixpath.dirname(new_path)
    target = posixpath.normpath(posixpath.join(old_dir, unquote(path_part)))
    if target == ".." or target.startswith(("../", "/")):
        return value
    new_target = moves.get(target, target)
    if new_target == target and old_dir == new_dir:
        return value
    relative = os.path.relpath(new_target, new_dir or ".").replace(os.sep, "/")
    new = quote(relative, safe="/") + suffix
    return value if new == value else new


def find_outermost_bundle_root(cwd: Path) -> Path | None:
    """Return the topmost directory at or above cwd whose MAP.md is a bundle root, or None.

    The climb stops at the first directory holding `.git` (a folder, or a file in a linked worktree),
    so a worktree inside another checkout never resolves to that checkout's bundle.
    """
    found = None
    for directory in (cwd, *cwd.parents):
        if is_bundle_root_map(directory / MAP_NAME):
            found = directory
        if (directory / ".git").exists():
            break
    return found


_SKIPPED_DIRECTORIES = {".git", "node_modules"}


def bundle_files(root: Path) -> list[str]:
    """Return the bundle-relative paths of the Markdown and HTML files of root, outside nested bundles."""
    found = []
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name not in _SKIPPED_DIRECTORIES]
        for filename in filenames:
            if not filename.endswith((".md", ".html")):
                continue
            path = Path(directory) / filename
            if not in_nested_bundle(root, path):
                found.append(path.relative_to(root).as_posix())
    return sorted(found)


def _rewritten_texts(texts: dict[str, str], moves: dict[str, str]) -> dict[str, str]:
    """Return the new text of each file whose links change, keyed by its current path.

    texts maps each file's current (post-move) bundle-relative path to its content.
    """
    previous = {new: old for old, new in moves.items()}
    changed = {}
    for current, text in texts.items():
        if current.endswith(".md"):
            new = rewrite_markdown(text, moves)
        elif current.endswith(".html"):
            new = rewrite_html(text, previous.get(current, current), current, moves)
        else:
            continue
        if new != text:
            changed[current] = new
    return changed


def relative_to_bundle(path: str, bundle: str) -> str | None:
    """Return a top-relative path in the coordinates of bundle ("" for the top), or None when it is outside."""
    if not bundle:
        return path
    return path[len(bundle) + 1 :] if path.startswith(bundle + "/") else None


def bundle_chain(top: Path) -> list[str]:
    """Return top and every bundle nested below it, as top-relative paths ("" for top)."""
    return [
        "" if path == top else path.relative_to(top).as_posix() for path in find_bundles(top)
    ]


def owning_bundle(bundles: list[str], path: str) -> str:
    """Return the deepest bundle of the chain that contains path."""
    return max((bundle for bundle in bundles if relative_to_bundle(path, bundle) is not None), key=len)


def bundle_moves(top: Path, moves: dict[str, str]) -> tuple[dict[str, dict[str, str]], list[tuple[str, str]]]:
    """Return each bundle's moves in its own coordinates, and the moves that cross a bundle boundary.

    moves maps old to new paths relative to top. A move applies to every bundle of
    the chain that holds both its paths, including a bundle nested in that bundle;
    a move whose two paths lie in different bundles is returned as crossing.
    """
    bundles = bundle_chain(top)
    crossing = [(old, new) for old, new in moves.items() if owning_bundle(bundles, old) != owning_bundle(bundles, new)]
    inside = {old: new for old, new in moves.items() if (old, new) not in crossing}
    per_bundle = {}
    for bundle in bundles:
        local = {}
        for old, new in inside.items():
            local_old, local_new = relative_to_bundle(old, bundle), relative_to_bundle(new, bundle)
            if local_old is not None and local_new is not None:
                local[local_old] = local_new
        if local:
            per_bundle[bundle] = local
    return per_bundle, crossing


def join_bundle(bundle: str, rel: str) -> str:
    return f"{bundle}/{rel}" if bundle else rel


def planned_updates(top: Path, moves: dict[str, str]) -> list[str]:
    """Return the sorted top-relative paths of the files that apply_chain would change, without writing.

    Call it while the files are still at their old paths.
    """
    planned = []
    for bundle, local in bundle_moves(top, moves)[0].items():
        directory = top / bundle
        texts = {
            local.get(rel, rel): read_text_preserving_newlines(directory / rel)
            for rel in bundle_files(directory)
        }
        planned += [join_bundle(bundle, rel) for rel in _rewritten_texts(texts, local)]
    return sorted(planned)


def apply_chain(top: Path, moves: dict[str, str], write: bool) -> list[str]:
    """Rewrite links in every bundle of the chain after files were moved on disk.

    moves maps old to new paths relative to top, and the files must already be at
    their new paths. Return the sorted top-relative paths of the files that changed,
    or would change when write is false. Crossing moves are not applied.
    """
    changed = []
    for bundle, local in bundle_moves(top, moves)[0].items():
        changed += [join_bundle(bundle, rel) for rel in apply_moves(top / bundle, local, write)]
    return sorted(changed)


def refresh_inventories(top: Path) -> int:
    """Regenerate the map inventories of every bundle of the chain; return the worst exit status."""
    status = 0
    with contextlib.redirect_stdout(io.StringIO()):
        for bundle in bundle_chain(top):
            status = max(status, generate_inventory.process_bundle(top / bundle, None, False, True))
    return status


def apply_moves(root: Path, moves: dict[str, str], write: bool) -> list[str]:
    """Rewrite links in the bundle at root after files were moved on disk.

    moves maps each old bundle-relative file path to its new path, and the files
    must already be at their new paths. Return the sorted paths of the files that
    changed, or would change when write is false.
    """
    texts = {rel: read_text_preserving_newlines(root / rel) for rel in bundle_files(root)}
    changed = _rewritten_texts(texts, moves)
    if write:
        for rel, new in changed.items():
            with (root / rel).open("w", encoding="utf-8", newline="") as target:
                target.write(new)
    return sorted(changed)

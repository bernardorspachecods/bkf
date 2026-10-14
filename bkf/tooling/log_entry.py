"""Append user ideas and feedback to a BKF bundle."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import bkf_common


TARGETS = {"idea": "ideas.md", "feedback": "feedback.md"}
EXCERPT_LIMIT = 5000


def _git_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip()).resolve()


def display_path(path: Path, cwd: Path) -> str:
    """Render a path relative to git, or home-relative when there is no repo."""
    root = _git_root(cwd)
    if root is not None:
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            pass
    absolute = str(path.resolve())
    home = str(Path.home())
    return "~" + absolute[len(home):] if absolute == home or absolute.startswith(home + os.sep) else absolute


def _all_bundle_roots(cwd: Path) -> list[Path]:
    roots = [cwd] if bkf_common.is_bundle_root_map(cwd / bkf_common.MAP_NAME) else []
    pending = bkf_common.nested_bundle_roots(cwd)
    while pending:
        root = pending.pop(0)
        roots.append(root)
        pending.extend(bkf_common.nested_bundle_roots(root))
    return roots


def _target_file(kind: str, cwd: Path) -> Path:
    filename = TARGETS[kind]
    for directory in (cwd, *cwd.parents):
        if bkf_common.is_bundle_root_map(directory / bkf_common.MAP_NAME):
            candidate = directory / filename
            if candidate.is_file():
                return candidate

    matches = [root / filename for root in _all_bundle_roots(cwd) if (root / filename).is_file()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"no bundle containing {filename} was found above or below {cwd}")
    paths = ", ".join(path.relative_to(cwd).as_posix() for path in matches)
    raise ValueError(f"several bundles containing {filename} were found below {cwd}: {paths}")


def _heading(text: str) -> tuple[str, bool]:
    collapsed = " ".join(text.split())
    if len(text.splitlines()) == 1 and len(collapsed) <= 70:
        return collapsed, False
    first = " ".join(text.splitlines()[0].split()) if text.splitlines() else ""
    if len(first) <= 60:
        return first, True
    prefix = first[:60]
    if len(first) > 60 and not first[60].isspace() and any(char.isspace() for char in prefix):
        prefix = prefix.rsplit(None, 1)[0]
    return prefix.rstrip() + "…", True


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.splitlines())


def _excerpt(context: str | None) -> str:
    if not context or not context.strip():
        return ""
    value = context.strip()
    if len(value) > EXCERPT_LIMIT:
        start = len(value) - EXCERPT_LIMIT
        if start and start < len(value) and not value[start].isspace() and not value[start - 1].isspace():
            while start < len(value) and not value[start].isspace():
                start += 1
        while start < len(value) and value[start].isspace():
            start += 1
        omitted = start
        value = f"[message truncated: {omitted} earlier characters omitted]\n{value[start:]}"
    return _quote(value)


def _entry(kind: str, text: str, cwd: Path, context: str | None) -> str:
    heading, quote_text = _heading(text)
    date = dt.date.today().isoformat()
    label = "Raised" if kind == "idea" else "Noticed"
    lines = [f"## {date}: {heading}", ""]
    if quote_text:
        lines.extend((_quote(text), ""))
    lines.append(f"{label} by the user, working in {_working_folder(cwd)}.")
    excerpt = _excerpt(context)
    if excerpt:
        lines.extend(("", "Just before, the agent had said:", excerpt))
    return "\n".join(lines)


def _working_folder(cwd: Path) -> str:
    root = _git_root(cwd)
    if root is not None:
        try:
            relative = cwd.resolve().relative_to(root)
            suffix = relative.as_posix()
            return f"{root.name}/{suffix}" if suffix and suffix != "." else root.name
        except ValueError:
            pass
    absolute = str(cwd.resolve())
    home = str(Path.home())
    return "~" + absolute[len(home):] if absolute == home or absolute.startswith(home + os.sep) else absolute


def write_entry(kind: str, text: str, cwd: Path | str, context: str | None = None) -> Path:
    """Insert one user idea or feedback entry and return its file path."""
    if kind not in TARGETS:
        raise ValueError("kind must be 'idea' or 'feedback'")
    text = text.strip()
    if not text:
        raise ValueError("text must not be empty")
    directory = Path(cwd).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError(f"working directory does not exist: {directory}")
    target = _target_file(kind, directory)
    body = _entry(kind, text, directory, context)
    for _attempt in range(3):
        temporary: Path | None = None
        try:
            original_stat = target.stat()
            content = target.read_text(encoding="utf-8")
            read_stat = target.stat()
            if not _same_file_version(original_stat, read_stat):
                continue
            updated = _insert_entry(content, body)

            descriptor, name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(updated)
            os.chmod(temporary, stat.S_IMODE(read_stat.st_mode))

            current_stat = target.stat()
            if not _same_file_version(read_stat, current_stat):
                continue
            os.replace(temporary, target)
            temporary = None
            return target
        except OSError as exc:
            raise ValueError(f"could not write {target}: {exc.strerror or exc}") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
    raise ValueError(f"{target} changed during all 3 write attempts; no entry was added")


def _same_file_version(first: os.stat_result, second: os.stat_result) -> bool:
    return first.st_mtime_ns == second.st_mtime_ns and first.st_size == second.st_size


def _insert_entry(content: str, body: str) -> str:
    """Place a new entry before the first heading, or after an introduction."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.splitlines(keepends=True)
    offset = 0
    search_from = 0
    if lines and lines[0].removesuffix("\n") == "---":
        offset = len(lines[0])
        frontmatter_closed = False
        for line in lines[1:]:
            offset += len(line)
            if line.removesuffix("\n") == "---":
                search_from = offset
                frontmatter_closed = True
                break
        if not frontmatter_closed:
            search_from = len(content)

    heading_at = -1
    position = search_from
    for line in content[search_from:].splitlines(keepends=True):
        if line.startswith("## "):
            heading_at = position
            break
        position += len(line)
    if heading_at >= 0:
        prefix = content[:heading_at]
        suffix = content[heading_at:]
        trailing_newlines = len(prefix) - len(prefix.rstrip("\n"))
        separator = "\n" * max(0, 2 - trailing_newlines) if prefix else ""
        result = prefix + separator + body + "\n\n" + suffix
    else:
        trailing_newlines = len(content) - len(content.rstrip("\n"))
        separator = "" if not content else "\n" * max(0, 2 - trailing_newlines)
        result = content + separator + body
    return result.rstrip("\n") + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf log", description=__doc__)
    parser.add_argument("kind", choices=tuple(TARGETS))
    parser.add_argument("text")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--context")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    try:
        path = write_entry(args.kind, args.text, args.cwd, args.context)
    except Exception as exc:
        print(f"bkf log: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Manage the machine-wide BKF bundle of source records."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from fcntl import LOCK_EX, LOCK_SH, flock
from functools import partial
from http.client import HTTPException
from pathlib import Path
from typing import Callable, Iterator
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlsplit

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bkf_common import BKFInputError, ParsedMarkdown, parse_markdown, read_text_preserving_newlines
from generate_inventory import END_MARKER, START_MARKER, update_map, write_atomically
from source_page import (
    KINDS, UNKNOWN, FetchBudget, FetchError, FetchedPage, PageDetails, clean, encode_url, extract_page, fetch_page,
    infer_kind, iso_date, normalize_url, repository_owner, site_name,
)
from source_record import (
    ID_PATTERN, REASON_PATTERN, RECORD_BODY, SNAPSHOT_NOTE_RULE, SOURCE_SCHEMA, catalog_description,
    check_claims, check_record, manual_snapshot_command, normalize_manual_headings, render_record, source_id_base,
)


CATALOG = Path("records/MAP.md")
SCHEMA = Path("ext-schema.yaml")
STORE_MARKER = "<!-- BKF:SOURCES-STORE -->"
HOOK_STATE = Path(".git/bkf-sources")
WINDOW_SECONDS = 30 * 60
INVENTORY = f"## Member inventory\n\n{START_MARKER}\n{END_MARKER}\n"
FetchIdentity = tuple[str, str | None, str]


class StoreError(ValueError):
    """An invalid source or store operation."""


@dataclass(frozen=True)
class SourceMatch:
    id: str
    path: Path
    has_snapshot: bool


@dataclass(frozen=True)
class Registration:
    id: str
    already_registered: bool = False
    has_snapshot: bool = False
    redirect_warning: str = ""


@dataclass(frozen=True)
class _PageResult:
    details: PageDetails
    final_url: str
    dead: bool = False
    failure: str = ""
    lossy_urls: tuple[str, ...] = ()
    reached: bool = True


def resolve_store_path(directory: str | Path | None = None) -> Path:
    selected = directory if directory is not None else os.environ.get("BKF_SOURCES_DIR") or "~/sources"
    return Path(selected).expanduser().resolve()


def _is_store(root: Path) -> bool:
    return (
        (root / ".git").is_dir() and not (root / ".git").is_symlink()
        and (root / CATALOG).is_file() and (root / SCHEMA).is_file()
        and (root / "MAP.md").is_file()
        and STORE_MARKER in parse_markdown(root / "MAP.md").body.splitlines()
    )


def open_store(directory: str | Path | None = None) -> Path | None:
    root = resolve_store_path(directory)
    return root if _is_store(root) else None


def _require_store(directory: str | Path | None) -> Path:
    root = resolve_store_path(directory)
    if not _is_store(root):
        raise StoreError(f"{root} is not a sources store. Run bkf sources init --dir PATH.")
    return root


def _git(root: Path, *args: str) -> str:
    # A caller can be inside another repository or running in one of its Git hooks.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["LC_ALL"] = "C"
    command = ["git", "-C", str(root), "-c", "user.name=BKF Sources",
               "-c", "user.email=bkf-sources@localhost"]
    if args[0] != "init":
        command.extend([f"--git-dir={root / '.git'}", f"--work-tree={root}"])
    for attempt in range(6):
        result = subprocess.run([*command, *args], env=env, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        detail = result.stderr.strip() or result.stdout.strip()
        if attempt == 5 or ".lock" not in detail or "file exists" not in detail.lower():
            raise StoreError(f"git {args[0]} failed: {detail}")
        time.sleep(0.05 * 2 ** attempt)


def _commit(root: Path, message: str, *files: Path) -> None:
    paths = [path.as_posix() for path in files]
    _git(root, "add", "--intent-to-add", "--", *paths)
    _git(root, "commit", "--no-gpg-sign", "--only", "-m", message, "--", *paths)


def _warn(message: str) -> None:
    print(f"bkf sources: warning: {message}", file=sys.stderr)


def commit_files(
    root: Path, message: str, *files: Path, removed: Path | None = None, skip_unchanged: bool = False,
) -> None:
    try:
        # An earlier add may have saved the record without committing it.
        if removed is not None and _git(root, "ls-files", "--with-tree=HEAD", "--", removed.as_posix()):
            files += (removed,)
        if skip_unchanged and not _git(
            root, "status", "--porcelain", "--untracked-files=all", "--", *(path.as_posix() for path in files),
        ):
            return
        _commit(root, message, *files)
    except (OSError, StoreError) as exc:
        _warn(f"files saved in {root}, but commit failed: {exc}")


def _commit_record(
    root: Path, message: str, path: Path, catalog_changed: bool = False, schema_changed: bool = False,
    *, skip_unchanged: bool = False,
) -> None:
    files = [path.relative_to(root)]
    if catalog_changed:
        files.append(CATALOG)
    if schema_changed:
        files.append(SCHEMA)
    commit_files(root, message, *files, skip_unchanged=skip_unchanged)


def _schema_upgrade(root: Path) -> tuple[str, dict | None]:
    # Extend existing stores in place, preserving any other schema rules.
    path = root / SCHEMA
    try:
        original = read_text_preserving_newlines(path)
        schema = YAML(typ="safe").load(original)
        ext = schema["properties"]["ext"]
        properties = ext["properties"]
        built_in = SOURCE_SCHEMA["properties"]["ext"]["properties"]
        changes = {key: value for key, value in built_in.items() if properties.get(key) != value}
        rules = ext.get("allOf", [])
        if not isinstance(rules, list):
            raise TypeError("ext.allOf must be a list")
    except (YAMLError, KeyError, TypeError, AttributeError) as exc:
        raise StoreError(f"{path}: cannot extend the source schema: {exc}") from exc
    if not changes and SNAPSHOT_NOTE_RULE in rules:
        return original, None
    properties.update(changes)
    if SNAPSHOT_NOTE_RULE not in rules:
        ext["allOf"] = [*rules, SNAPSHOT_NOTE_RULE]
    return original, schema


def _extend_schema(root: Path, *, rollback: ExitStack | None = None) -> bool:
    original, schema = _schema_upgrade(root)
    if schema is None:
        return False
    path = root / SCHEMA
    write_atomically(path, json.dumps(schema, indent=2) + "\n")
    if rollback is not None:
        rollback.callback(write_atomically, path, original)
    return True


@contextmanager
def store_lock(root: Path, *, shared: bool = False) -> Iterator[None]:
    # Use the stable .git directory inode so lookups never create lock files.
    descriptor = os.open(root / ".git", os.O_RDONLY)
    try:
        flock(descriptor, LOCK_SH if shared else LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _refresh_map(root: Path, relative_path: Path) -> bool:
    path = root / relative_path
    original, updated = update_map(root, path, on_parse_error=_warn if relative_path == CATALOG else None)
    if original == updated:
        return False
    write_atomically(path, updated)
    return True


def init_store(directory: str | Path | None = None) -> Path:
    root = resolve_store_path(directory)
    if _is_store(root):
        with store_lock(root), ExitStack() as rollback:
            if _extend_schema(root, rollback=rollback):
                _commit(root, "Upgrade sources store schema", SCHEMA)
            rollback.pop_all()
        return root
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise StoreError(f"refusing to initialize non-empty directory or file: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    # Publish the initialized, committed bundle in one rename. The destination
    # must still be absent or empty, so concurrent writers cannot be overwritten.
    with tempfile.TemporaryDirectory(prefix=".bkf-sources-", dir=root.parent) as temporary:
        staging = Path(temporary) / "store"
        (staging / "records").mkdir(parents=True)
        _git(staging, "init", "--quiet")
        root_map = Path("MAP.md")
        ignore = Path(".gitignore")
        (staging / root_map).write_text(
            '---\nbkf_version: "0.2"\ndescription: Routes to the machine-wide source catalog.\n---\n\n'
            f"# Sources\n\n{STORE_MARKER}\n\n{INVENTORY}\n"
            "## Artifact references\n\n- [Source record schema](/ext-schema.yaml)\n", encoding="utf-8",
        )
        (staging / CATALOG).write_text(
            "---\ndescription: Catalogs registered sources.\n---\n\n"
            f"# Source catalog\n\n{INVENTORY}", encoding="utf-8",
        )
        (staging / SCHEMA).write_text(json.dumps(SOURCE_SCHEMA, indent=2) + "\n", encoding="utf-8")
        (staging / ignore).write_text("*.txt\n", encoding="utf-8")
        _refresh_map(staging, root_map)
        _refresh_map(staging, CATALOG)
        _commit(staging, "Initialize sources store", root_map, CATALOG, SCHEMA, ignore)
        try:
            staging.rename(root)
        except OSError:
            if not _is_store(root):
                raise
    return root


def _record_paths(root: Path) -> list[Path]:
    return sorted(
        path for path in (root / "records").glob("*/*.md")
        if path.stem == path.parent.name and not path.parent.is_symlink()
        and not path.is_symlink() and path.is_file()
    )


def _metadata(path: Path) -> ParsedMarkdown:
    try:
        return parse_markdown(path)
    except BKFInputError as exc:
        raise StoreError(f"{path}: {exc}") from exc


def _readable_records(root: Path) -> Iterator[tuple[Path, ParsedMarkdown]]:
    for path in _record_paths(root):
        try:
            parsed = _metadata(path)
        except StoreError as exc:
            _warn(str(exc))
            continue
        yield path, parsed


def _find_url(root: Path, keys: set[str]) -> Path | None:
    if not keys:
        return None
    for path, parsed in _readable_records(root):
        ext = parsed.frontmatter.get("ext")
        if not isinstance(ext, dict) or ext.get("type") != "source":
            continue
        urls = [ext.get("url")]
        # Older registrations included the unrelated destination itself in
        # aliases. A redirect recorded during refresh leaves prior aliases intact.
        aliases, redirect = ext.get("aliases"), ext.get("redirected_to")
        if isinstance(aliases, list) and (not redirect or redirect not in aliases):
            urls.extend(aliases)
        for url in urls:
            if not isinstance(url, str) or url == UNKNOWN:
                continue
            try:
                key = _validate_url(url)
            except StoreError as exc:
                _warn(f"{path}: {exc}")
                continue
            if key in keys:
                return path
    return None


def _has_snapshot(path: Path) -> bool:
    try:
        with path.with_suffix(".txt").open(encoding="utf-8") as snapshot:
            return any(line.strip() for line in snapshot)
    except FileNotFoundError:
        return False


def lookup_url(url: str, *, directory: str | Path | None = None) -> SourceMatch | None:
    """Find a canonical URL or alias, with the record path and snapshot availability."""
    url = encode_url(url)
    if url == UNKNOWN:
        return None
    root = _require_store(directory)
    with store_lock(root, shared=True):
        return _lookup_url(root, url)


def _lookup_url(root: Path, url: str) -> SourceMatch | None:
    path = _find_url(root, {_validate_url(url)})
    return SourceMatch(path.stem, path, _has_snapshot(path)) if path is not None else None


def _validate_url(url: str) -> str:
    try:
        return normalize_url(encode_url(url))
    except ValueError as exc:
        raise StoreError(f"invalid URL: {exc}") from exc


def _content_selectors(key: str) -> tuple[list[tuple[str, str]], str]:
    parts = urlsplit(key)
    refs = [(name, value) for name, value in parse_qsl(parts.query, keep_blank_values=True)
            if name.lower() == "ref"]
    return refs, parts.fragment


def _same_page_variants(url_key: str, result: _PageResult) -> dict[str, str]:
    selectors = _content_selectors(url_key)
    variants = {link: key for link in (result.details.url, result.final_url)
                if _content_selectors(key := _validate_url(link)) == selectors}
    return variants if url_key in variants.values() else {}


def _unavailable(url: str, failure: str, *, dead: bool = False, reached: bool = False) -> _PageResult:
    details = PageDetails(url, UNKNOWN, UNKNOWN, None, UNKNOWN, UNKNOWN, (), "")
    return _PageResult(details, url, dead, failure, reached=reached)


def _read_page(url: str, fetch: Callable[[str], FetchedPage]) -> _PageResult:
    try:
        page = fetch(url)
    except HTTPError as exc:
        with exc:
            page = FetchedPage(exc.geturl(), None)
            failure = f"HTTP {exc.code}"
            dead = exc.code in {404, 410}
    except (OSError, HTTPException, UnicodeError, ValueError) as exc:
        return _unavailable(url, str(exc) or type(exc).__name__)
    else:
        failure, dead = "non-HTML response", False
    try:
        _validate_url(page.url)
    except StoreError:
        return _unavailable(url, "invalid final URL")
    if page.html is None:
        return _unavailable(page.url, failure, dead=dead, reached=True)
    details = extract_page(page)
    return _PageResult(
        details, page.url,
        failure="" if details.snapshot else "page contained no readable text",
        lossy_urls=(page.url,) if page.lossy else (),
    )


def _get_page(url: str, fetch: Callable[[str], FetchedPage] | None) -> _PageResult:
    budget = FetchBudget()
    fetch = fetch or partial(fetch_page, budget=budget)

    def resolve() -> _PageResult:
        first = _read_page(url, fetch)
        if (target := first.details.client_redirect) is None:
            return first
        budget.remaining()
        last = _read_page(target, fetch)
        return _PageResult(
            last.details, last.final_url, last.dead, last.failure, first.lossy_urls + last.lossy_urls,
            last.reached,
        )

    try:
        return budget.run(resolve)
    except FetchError as exc:
        return _unavailable(url, str(exc))


def _warn_lossy(source_id: str, result: _PageResult) -> None:
    for url in dict.fromkeys(result.lossy_urls):
        _warn(f"{source_id}: decoding {url} required replacement characters")


def register(
    url: str | None = None, *, directory: str | Path | None = None, manual: bool = False,
    title: str | None = None, author: str | None = None, published: str | None = None,
    kind: str | None = None, via: str = "user", fetch: Callable[[str], FetchedPage] | None = None,
    session_id: str | None = None, agent_id: str | None = None,
) -> Registration:
    """Register a source and indicate whether the URL was already in the store."""
    root = _require_store(directory)
    url = encode_url(url or "")
    if kind is not None and kind not in KINDS:
        raise StoreError(f"unknown kind: {kind}")
    via = clean(via)
    if not via:
        raise StoreError("--via needs a non-empty value")
    if manual:
        title = clean(title)
        if not title:
            raise StoreError("--manual requires a non-empty --title")
        if published and published != UNKNOWN and not iso_date(published):
            raise StoreError("--published must be a date (YYYY-MM-DD) or unknown")
        url = url or UNKNOWN
    elif not url or url == UNKNOWN:
        raise StoreError("add needs an HTTP(S) URL or --manual --title TITLE")
    elif any(value is not None for value in (title, author, published)):
        raise StoreError("--title, --author, and --published require --manual")

    keys = {_validate_url(url)} if url != UNKNOWN else set()
    stored_url = url
    redirected_to = None
    aliases = []
    if manual:
        details = PageDetails(url, title, clean(author) or UNKNOWN, None,
                              iso_date(published) or UNKNOWN, UNKNOWN, (), "")
        result = _PageResult(details, url)
    else:
        with store_lock(root, shared=True):
            if existing := _find_url(root, keys):
                return Registration(existing.stem, already_registered=True)
        result = _get_page(url, fetch)
        details, final_url = result.details, result.final_url
        variants = _same_page_variants(next(iter(keys)), result)
        if variants:
            stored_url = next(iter(variants))
            aliases = [link for link in dict.fromkeys((url, *variants)) if link != stored_url]
            keys.update(variants.values())
        else:
            redirected_to = final_url

    failure = result.failure
    with store_lock(root):
        if existing := _find_url(root, keys):
            return Registration(existing.stem, already_registered=True)
        # A successful WebFetch already read the source. A raw 404/410 from a
        # different client only explains why we could not save its snapshot.
        dead = result.dead and session_id is None
        author, person = details.author, details.person
        if not manual and author == UNKNOWN:
            author, person = repository_owner(details.url) or site_name(details.url) or UNKNOWN, False
        base = source_id_base(details.first_author or author, person, details.title, details.url, site=details.site)
        source_id = base
        number = 2
        while (root / "records" / source_id).exists() or (root / "records" / source_id).is_symlink():
            source_id = f"{base}-{number}"
            number += 1
        ext = {
            "type": "source", "id": source_id, "url": stored_url, "aliases": aliases,
            "title": details.title, "author": author, "published": details.published,
            "updated": details.updated, "consulted": [date.today().isoformat()],
            "kind": kind or infer_kind(details.url, details.json_types), "via": via,
            "status": "discarded" if dead else "pending",
        }
        if details.published_from:
            ext["published_from"] = details.published_from
        if redirected_to is not None:
            ext["redirected_to"] = redirected_to
        if dead:
            ext["reason"] = "dead"
            failure += " (discarded as dead)"
        if session_id is not None:
            ext["session_id"] = session_id
            if agent_id is not None:
                ext["agent_id"] = agent_id
        ext["snapshot"] = "web" if details.snapshot else "none"
        metadata = {
            "bkf": "document", "description": catalog_description(f"Pending: {details.title}"),
            "tags": ["source"], "ext": ext,
        }
        folder = root / "records" / source_id
        with ExitStack() as rollback:
            schema_changed = (
                session_id is not None or redirected_to is not None or details.published_from is not None
            ) and _extend_schema(root, rollback=rollback)
            with tempfile.TemporaryDirectory(prefix="bkf-source-", dir=root / ".git") as temporary:
                staged = Path(temporary) / source_id
                staged.mkdir()
                filename = f"{source_id}.md"
                (staged / filename).write_text(render_record(metadata, RECORD_BODY), encoding="utf-8")
                if details.snapshot:
                    (staged / f"{source_id}.txt").write_text(details.snapshot, encoding="utf-8")
                staged.rename(folder)
                rollback.callback(shutil.rmtree, folder)
            catalog_changed = _refresh_map(root, CATALOG)
            rollback.pop_all()
        _commit_record(root, f"Add source {source_id}", folder / filename, catalog_changed, schema_changed)
    redirect_warning = ""
    if redirected_to is not None:
        warning = f"{source_id}: {url} redirected to {redirected_to}. Check whether the cited page is gone."
        guidance = " If so, close the pending record with --status discarded --reason dead." if not dead else ""
        redirect_warning = warning + guidance
        _warn(redirect_warning)
    _warn_lossy(source_id, result)
    if failure:
        guidance = f". Save text read another way with {manual_snapshot_command(source_id)}" if not dead else ""
        _warn(f"{source_id}: snapshot unavailable ({failure}){guidance}")
    return Registration(source_id, has_snapshot=bool(details.snapshot), redirect_warning=redirect_warning)


def add(
    url: str | None = None, *, directory: str | Path | None = None, manual: bool = False,
    title: str | None = None, author: str | None = None, published: str | None = None,
    kind: str | None = None, via: str = "user", fetch: Callable[[str], FetchedPage] | None = None,
) -> str:
    """Register a source with an optional fetch replacement, returning its current id."""
    return register(url, directory=directory, manual=manual, title=title, author=author,
                    published=published, kind=kind, via=via, fetch=fetch).id


def _record_path(root: Path, source_id: str) -> Path:
    if not re.fullmatch(ID_PATTERN, source_id):
        raise StoreError(f"invalid source id: {source_id}")
    return root / "records" / source_id / f"{source_id}.md"


def _path_for_id(root: Path, source_id: str) -> Path:
    path = _record_path(root, source_id)
    if not path.is_file() or path.parent.is_symlink() or path.is_symlink():
        raise StoreError(f"unknown source id: {source_id}")
    return path


def _write_snapshot(root: Path, path: Path, content: str, record: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix="bkf-snapshot-", dir=root / ".git") as temporary:
        staged = Path(temporary) / "snapshot"
        staged.write_text(content, encoding="utf-8", newline="")
        with ExitStack() as rollback:
            if record is not None:
                original = read_text_preserving_newlines(path)
                write_atomically(path, record)
                rollback.callback(write_atomically, path, original)
            staged.replace(path.with_suffix(".txt"))
            rollback.pop_all()


def _record_consultation(ext: dict) -> bool:
    today = date.today().isoformat()
    if today in ext["consulted"]:
        return False
    ext["consulted"].append(today)
    return True


def _snapshot_rejection(path: Path, parsed: ParsedMarkdown, content: str, *, kind: str) -> str:
    ext = parsed.frontmatter["ext"] | {"snapshot": kind}
    errors = check_claims(path, parsed.body, ext, candidate=content)
    return "snapshot replacement rejected:\n" + "\n".join(errors) if errors else ""


def save_snapshot(source_id: str, content: str, *, note: str, directory: str | Path | None = None) -> None:
    root = _require_store(directory)
    if not content.strip():
        raise StoreError("snapshot needs non-empty text")
    note = note.strip()
    if not note:
        raise StoreError("--note needs a non-empty value")
    content = normalize_manual_headings(content)
    with store_lock(root):
        path = _path_for_id(root, source_id)
        parsed = _metadata(path)
        ext = parsed.frontmatter.get("ext")
        if not isinstance(ext, dict) or ext.get("type") != "source":
            raise StoreError(f"{source_id}: invalid source metadata")
        if ext.get("snapshot") == "web":
            raise StoreError(f"{source_id}: a web snapshot cannot be replaced by hand")
        if ext.get("snapshot") not in ("none", "manual"):
            raise StoreError(f"{source_id}: invalid snapshot metadata")
        rejection = _snapshot_rejection(path, parsed, content, kind="manual")
        consulted = _record_consultation(ext)
        if rejection:
            if consulted:
                write_atomically(path, render_record(parsed.frontmatter, parsed.body))
                _commit_record(root, f"Consult source {source_id}", path)
            raise StoreError(f"{source_id}: {rejection}")
        ext["snapshot"] = "manual"
        ext["snapshot_note"] = note
        with ExitStack() as rollback:
            schema_changed = _extend_schema(root, rollback=rollback)
            _write_snapshot(root, path, content, render_record(parsed.frontmatter, parsed.body))
            rollback.pop_all()
        _commit_record(
            root, f"Save snapshot for source {source_id}", path, schema_changed=schema_changed, skip_unchanged=True,
        )


def rename(
    directory: str | Path, old_id: str, new_id: str, *,
    _update: Callable[[ParsedMarkdown], None] | None = None,
) -> str:
    """Move a pending source to a new id."""
    root = _require_store(directory)
    with store_lock(root):
        old = _path_for_id(root, old_id)
        new = _record_path(root, new_id)
        if os.path.lexists(new.parent):
            raise StoreError(f"source id already exists: {new_id}")
        for candidate in (old.parent / new.name, old.parent / new.with_suffix(".txt").name):
            if os.path.lexists(candidate):
                raise StoreError(f"cannot rename source: {candidate} already exists")
        parsed = _metadata(old)
        ext = parsed.frontmatter.get("ext")
        if not isinstance(ext, dict) or ext.get("type") != "source":
            raise StoreError(f"{old_id}: invalid source metadata")
        if ext.get("status") != "pending":
            operation = "rename" if _update is None else "finish"
            raise StoreError(f"{old_id}: {operation} requires a pending record")
        if _update is not None:
            _update(parsed)
        ext["id"] = new_id

        with tempfile.TemporaryDirectory(prefix="bkf-source-", dir=root / ".git") as temporary:
            backup = Path(temporary) / old.name
            updated = Path(temporary) / new.name
            updated.write_text(render_record(parsed.frontmatter, parsed.body), encoding="utf-8")
            shutil.copymode(old, updated)
            with ExitStack() as rollback:
                old.parent.rename(new.parent)
                rollback.callback(new.parent.rename, old.parent)
                moved = new.parent / old.name
                moved.rename(backup)
                rollback.callback(backup.rename, moved)
                updated.rename(new)
                rollback.callback(new.unlink)
                snapshot = moved.with_suffix(".txt")
                new_snapshot = new.with_suffix(".txt")
                if os.path.lexists(snapshot):
                    snapshot.rename(new_snapshot)
                    rollback.callback(new_snapshot.rename, snapshot)
                window = _window_path(root, old_id)
                new_window = _window_path(root, new_id)
                if window.exists():
                    if os.path.lexists(new_window):
                        raise StoreError(f"completion window already exists for {new_id}")
                    window.rename(new_window)
                    rollback.callback(new_window.rename, window)
                _refresh_map(root, CATALOG)
                rollback.pop_all()

        commit_files(root, f"Rename source {old_id} to {new_id}",
                     new.relative_to(root), CATALOG, removed=old.relative_to(root))
    return new_id


def finish(
    source_id: str, *, status: str, description: str, reason: str | None = None,
    kind: str | None = None, directory: str | Path | None = None, new_id: str | None = None,
) -> str:
    root = _require_store(directory)
    description = clean(description)
    if not description:
        raise StoreError("--description needs a non-empty value")
    if status == "discarded":
        if not reason or not re.fullmatch(REASON_PATTERN, reason):
            raise StoreError("--status discarded needs --reason dead, paywall, copy-of:<id>, marketing, or outdated")
    elif status != "used" or reason is not None:
        raise StoreError("use --status used without --reason, or --status discarded with --reason")
    if kind is not None and kind not in KINDS:
        raise StoreError(f"unknown kind: {kind}")

    def close_pending(parsed: ParsedMarkdown) -> None:
        metadata = parsed.frontmatter
        ext = metadata.get("ext")
        if not isinstance(ext, dict) or ext.get("status") != "pending":
            raise StoreError(f"{source_id}: finish requires a pending record")
        metadata["description"] = catalog_description(description)
        ext["status"] = status
        if reason is not None:
            ext["reason"] = reason
        if kind is not None:
            ext["kind"] = kind
        errors, _ = check_record(_record_path(root, source_id), parsed)
        if errors:
            raise StoreError(f"{source_id}: " + "\n".join(errors))

    if new_id is not None:
        return rename(root, source_id, new_id, _update=close_pending)

    with store_lock(root):
        path = _path_for_id(root, source_id)
        parsed = _metadata(path)
        close_pending(parsed)
        original = read_text_preserving_newlines(path)
        write_atomically(path, render_record(parsed.frontmatter, parsed.body))
        try:
            catalog_changed = _refresh_map(root, CATALOG)
        except (OSError, BKFInputError):
            write_atomically(path, original)
            raise
        _commit_record(root, f"Finish source {source_id}", path, catalog_changed)
    return source_id


def _window_path(root: Path, source_id: str) -> Path:
    return root / HOOK_STATE / f"window-{source_id}"


def _completion_window(root: Path, source_id: str) -> dict | None:
    try:
        window = json.loads(_window_path(root, source_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    # Previous versions recorded only the expiration time.
    return window if isinstance(window, dict) else {"expires": float(window)}


def grant_state(root: Path, source_id: str) -> tuple[str, str] | None:
    """Describe an unexpired completion grant as (open, reserved or used) and its local HH:MM expiry."""
    window = _completion_window(root, source_id)
    if window is None or time.time() >= window["expires"]:
        return None
    state = "used" if window.get("used") else "reserved" if window.get("reserved_for") else "open"
    return state, datetime.fromtimestamp(window["expires"]).strftime("%H:%M")


def reserve_completion(root: Path, source_id: str, identity: FetchIdentity | None) -> bool | None:
    """Reserve an active grant under the store lock, or return None outside its window."""
    window = _completion_window(root, source_id)
    now = time.time()
    if window is None or now >= window["expires"]:
        return None
    if not identity or window.get("used") or window.get("reserved_for"):
        return False
    window["reserved_for"] = identity
    write_atomically(_window_path(root, source_id), json.dumps(window))
    return True


def settle_completion(
    root: Path, source_id: str, identity: FetchIdentity | None, *, succeeded: bool,
) -> bool | None:
    """Consume or release the matching reservation under the store lock."""
    window = _completion_window(root, source_id)
    if window is None:
        return None
    if identity and list(identity) == window.get("reserved_for"):
        if window.get("used"):
            return False
        if succeeded:
            window["used"] = True
        else:
            del window["reserved_for"]
        write_atomically(_window_path(root, source_id), json.dumps(window))
        return succeeded
    return False if time.time() < window["expires"] else None


def complete(source_id: str, *, why: str, directory: str | Path | None = None) -> None:
    root = _require_store(directory)
    why = why.strip()
    if not why:
        raise StoreError("--why needs a non-empty value")
    with store_lock(root):
        path = _path_for_id(root, source_id)
        if (state := grant_state(root, source_id)) is not None and state[0] == "reserved":
            raise StoreError(
                f"{source_id}: the completion grant is reserved by another WebFetch call until {state[1]}. "
                "That call has not reported back (it may still be running, or the permission prompt, "
                f"another hook or an interrupt stopped it). Run complete again after {state[1]}."
            )
        parsed = _metadata(path)
        ext = parsed.frontmatter["ext"]
        ext.setdefault("completions", []).append({"date": date.today().isoformat(), "why": why})
        schema_changed = _extend_schema(root)
        window = _window_path(root, source_id)
        window.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="window-", dir=window.parent) as temporary:
            staged = Path(temporary) / "expiry"
            staged.write_text(json.dumps({"expires": time.time() + WINDOW_SECONDS}), encoding="utf-8")
            original = read_text_preserving_newlines(path)
            write_atomically(path, render_record(parsed.frontmatter, parsed.body))
            try:
                staged.replace(window)
            except OSError:
                write_atomically(path, original)
                raise
        _commit_record(root, f"Complete source {source_id}", path, schema_changed=schema_changed)


def refresh(root: Path, source_id: str, url: str, *, fetch: Callable[[str], FetchedPage] | None = None) -> list[str]:
    result = _get_page(url, fetch)
    details, failure = result.details, result.failure
    redirected_to = None if _same_page_variants(_validate_url(url), result) else result.final_url
    changed = []
    rejection = ""
    with store_lock(root):
        path = _path_for_id(root, source_id)
        parsed = _metadata(path)
        ext = parsed.frontmatter["ext"]
        if redirected_to is not None:
            previous = ext.get("redirected_to")
            if previous != redirected_to:
                # Avoid reactivating aliases copied from a legacy redirect destination.
                aliases = ext.get("aliases")
                if previous and isinstance(aliases, list) and previous in aliases:
                    ext["aliases"] = []
                    changed.append("aliases")
                ext["redirected_to"] = redirected_to
                changed.append("redirected_to")
        else:
            if result.reached and (previous := ext.pop("redirected_to", None)) is not None:
                aliases = ext.get("aliases")
                if isinstance(aliases, list) and previous in aliases:
                    ext["aliases"] = [alias for alias in aliases if alias != previous]
                changed.append("redirected_to")
            for field in ("title", "author", "published", "updated"):
                value = getattr(details, field)
                if ext.get(field) == UNKNOWN and value != UNKNOWN:
                    ext[field] = value
                    changed.append(field)
            if "published" in changed and details.published_from:
                ext["published_from"] = details.published_from
        if _record_consultation(ext):
            changed.append("consulted")
        # A redirect landing is another page: it never replaces text already saved.
        keep = redirected_to is not None and _has_snapshot(path)
        if details.snapshot:
            rejection = _snapshot_rejection(path, parsed, details.snapshot, kind="web")
        replace = bool(details.snapshot and not keep and not rejection)
        if replace and ext["snapshot"] != "web":
            ext["snapshot"] = "web"
            ext.pop("snapshot_note", None)
            changed.append("snapshot metadata")
        with ExitStack() as rollback:
            schema_changed = (
                "redirected_to" in changed or ("published" in changed and details.published_from is not None)
            ) and _extend_schema(root, rollback=rollback)
            record = render_record(parsed.frontmatter, parsed.body) if changed else None
            if replace:
                _write_snapshot(root, path, details.snapshot, record)
            elif record is not None:
                write_atomically(path, record)
            rollback.pop_all()
        if changed:
            _commit_record(root, f"Refresh source {source_id}", path, schema_changed=schema_changed)
    if redirected_to is not None:
        warning = f"{url} redirected to {redirected_to}"
        changed.append(warning)
        _warn(f"{source_id}: {warning}. Check whether the cited page is gone.")
    _warn_lossy(source_id, result)
    if replace:
        changed.append("snapshot rewritten")
    elif rejection:
        changed.append(rejection)
        _warn(f"{source_id}: {rejection}")
    elif failure:
        changed.append(f"snapshot unavailable ({failure})")
        _warn(f"{source_id}: snapshot unavailable ({failure})")
    return changed


def pending_sources(root: Path, session_id: str, *, agent_id: str | None = None) -> list[SourceMatch]:
    pending = []
    with store_lock(root, shared=True):
        for path, parsed in _readable_records(root):
            ext = parsed.frontmatter.get("ext")
            if (isinstance(ext, dict) and ext.get("type") == "source"
                    and ext.get("status") == "pending" and ext.get("session_id") == session_id
                    and (agent_id is None or ext.get("agent_id") == agent_id)):
                pending.append(SourceMatch(path.stem, path, _has_snapshot(path)))
    return pending


def check(ids: list[str], *, directory: str | Path | None = None) -> int:
    root = _require_store(directory)
    failed = False
    with store_lock(root, shared=True):
        _, upgrade = _schema_upgrade(root)
        if upgrade is not None:
            print(f"{root / SCHEMA}: error: source schema is out of date. "
                  f"Run bkf sources init --dir {shlex.quote(str(root))}.")
            failed = True
        selected = ids or sorted(path.name for path in (root / "records").iterdir() if path.is_dir())
        for source_id in selected:
            try:
                path = _path_for_id(root, source_id) if ids else (
                    root / "records" / source_id / f"{source_id}.md"
                )
                if not path.is_file() or path.parent.is_symlink() or path.is_symlink():
                    raise StoreError(f"{path}: missing record file")
                errors, pending = check_record(path, _metadata(path))
            except (OSError, StoreError, UnicodeError) as exc:
                errors, pending = [str(exc)], False
            for error in errors:
                print(f"{source_id}: error: {error}")
            if pending:
                print(f"{source_id}: warning: pending")
            if not errors and not pending:
                print(f"{source_id}: ok")
            failed = failed or bool(errors)
    return int(failed)

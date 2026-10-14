"""Print the format update documents needed by BKF bundles."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from bkf_common import BKFInputError, find_bundles, is_bundle_root_map, parse_markdown
from validate_bundle import SUPPORTED_VERSION, VERSION_RE


UPDATE_FILE_RE = re.compile(r"^(\d+)-(\d+)\.md$")


def _version_text(version: tuple[int, int]) -> str:
    return f"{version[0]}.{version[1]}"


def _declared_version(bundle: Path) -> tuple[int, int] | None:
    try:
        value = parse_markdown(bundle / "MAP.md").frontmatter.get("bkf_version")
    except (BKFInputError, OSError):
        return None
    if not isinstance(value, str) or VERSION_RE.fullmatch(value) is None:
        return None
    match = VERSION_RE.fullmatch(value)
    assert match is not None
    return int(match.group(1)), int(match.group(2))


def _update_files(updates_dir: Path) -> list[tuple[tuple[int, int], Path]]:
    if not updates_dir.is_dir():
        return []
    found: list[tuple[tuple[int, int], Path]] = []
    for path in updates_dir.iterdir():
        match = UPDATE_FILE_RE.fullmatch(path.name)
        if not path.is_file() or match is None:
            continue
        found.append(((int(match.group(1)), int(match.group(2))), path))
    return sorted(found, key=lambda item: item[0])


def report_bundle(bundle: Path, updates_dir: Path) -> tuple[str, bool]:
    """Print one bundle report; return its status and whether reporting found an error."""
    declared = _declared_version(bundle)
    if declared is None:
        print(f"Bundle: {bundle}")
        print("Declared version: invalid or unavailable")
        print(f"Supported version: {_version_text(SUPPORTED_VERSION)}")
        print("Status: error (cannot read a valid bkf_version from MAP.md)")
        return "error", True

    print(f"Bundle: {bundle}")
    print(f"Declared version: {_version_text(declared)}")
    print(f"Supported version: {_version_text(SUPPORTED_VERSION)}")
    if declared == SUPPORTED_VERSION:
        print("Status: current (bundle is up to date)")
        return "current", False
    if declared > SUPPORTED_VERSION:
        print("Status: ahead (the installed bkf is older; update this checkout)")
        return "ahead", False

    print("Status: behind")
    applicable = [
        (version, path)
        for version, path in _update_files(updates_dir)
        if declared < version <= SUPPORTED_VERSION
    ]
    for version, path in applicable:
        print(f"--- BKF {_version_text(version)} ---")
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"error: cannot read update document {path.name}: {exc}", file=sys.stderr)
            return "behind", True
        sys.stdout.write(contents)
        if contents and not contents.endswith(("\n", "\r")):
            sys.stdout.write("\n")

    if not any(version == SUPPORTED_VERSION for version, _ in applicable):
        print(
            f"error: installed bkf update document for {_version_text(SUPPORTED_VERSION)} "
            "is missing from the updates directory",
            file=sys.stderr,
        )
        return "behind", True
    return "behind", False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, metavar="PATH", help="directory to search (default: .)")
    return parser


def main(argv: list[str] | None = None, *, updates_dir: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    roots = [path.resolve() for path in (args.paths or [Path.cwd()])]
    invalid = [path for path in roots if not path.is_dir()]
    if invalid:
        for path in invalid:
            print(f"error: path is not a directory: {path}", file=sys.stderr)
        return 2

    source_updates = updates_dir or Path(__file__).resolve().parents[1] / "updates"
    bundles: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for bundle in find_bundles(root):
            if not is_bundle_root_map(bundle / "MAP.md"):
                continue
            resolved = bundle.resolve()
            if resolved not in seen:
                bundles.append(resolved)
                seen.add(resolved)

    if not bundles:
        searched = ", ".join(str(root) for root in roots)
        print(f"no BKF bundles found under {searched}", file=sys.stderr)
        return 1

    has_noncurrent = False
    has_error = False
    for index, bundle in enumerate(bundles):
        if index:
            print()
        status, error = report_bundle(bundle, source_updates)
        has_noncurrent = has_noncurrent or status != "current"
        has_error = has_error or error
    if has_error or has_noncurrent:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

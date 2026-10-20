"""Print the bundle maps that orient an agent at session start."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path


OUTPUT_LIMIT = 6000
VALIDATION_TIMEOUT = 5
WARNING_LIMIT = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf orient", description=__doc__)
    parser.add_argument("--cwd", type=Path, help="directory to orient from (defaults to the current directory)")
    parser.add_argument("--no-validate", action="store_true", help="skip the validation health line")
    parser.add_argument("--debug", action="store_true", help="print failures to stderr and return 1")
    return parser


def _bundle_root(cwd: Path, is_bundle_root_map) -> Path | None:
    roots = [
        directory
        for directory in cwd.parents
        if (directory / "MAP.md").is_file() and is_bundle_root_map(directory / "MAP.md")
    ]
    if (cwd / "MAP.md").is_file() and is_bundle_root_map(cwd / "MAP.md"):
        roots.append(cwd)
    return min(roots, key=lambda directory: len(directory.parts)) if roots else None


def _validate(root: Path, find_bundles, Validator) -> str:
    result: list[str] = []
    failures: list[BaseException] = []

    def validate() -> None:
        try:
            errors = 0
            warnings: list[str] = []
            for bundle in find_bundles(root):
                validator = Validator(bundle)
                validator.validate()
                errors += sum(finding.severity == "ERROR" for finding in validator.findings)
                warnings.extend(
                    f"  {finding.code} {(bundle / finding.path).relative_to(root).as_posix()}"
                    for finding in validator.findings
                    if finding.severity == "WARNING"
                )
            line = "bkf validate: ok" if errors == 0 else f"bkf validate: {errors} errors (run bkf validate)"
            if warnings:
                line += f"\nbkf validate: {len(warnings)} warnings (run bkf validate)"
                line += "".join("\n" + warning for warning in warnings[:WARNING_LIMIT])
                if len(warnings) > WARNING_LIMIT:
                    line += f"\n  ... {len(warnings) - WARNING_LIMIT} more"
            result.append(line)
        except BaseException as exc:
            failures.append(exc)

    worker = threading.Thread(target=validate, daemon=True)
    worker.start()
    worker.join(timeout=VALIDATION_TIMEOUT)
    if worker.is_alive():
        return "bkf validate: skipped (timeout)"
    if failures:
        raise failures[0]
    return result[0]


def _render(root: Path, cwd: Path, map_paths: list[Path], entries_by_map: list[list[object]], health: str | None) -> str:
    relative_cwd = cwd.relative_to(root).as_posix() or "."
    omitted = [0] * len(map_paths)

    def build_lines() -> list[str]:
        lines = [f"orientation (from {relative_cwd})"]
        if health is not None:
            lines.append(health)
        for index, (map_path, entries) in enumerate(zip(map_paths, entries_by_map)):
            map_label = "/" + map_path.relative_to(root).as_posix()
            lines.append(map_label)
            lines.extend(
                f"  /{entry.path.relative_to(root).as_posix()}  {entry.description}"
                for entry in entries
            )
            if omitted[index]:
                lines.append(f"  ... {omitted[index]} more rows, read {map_label}")
        return lines

    lines = build_lines()
    while sum(len(line) + 1 for line in lines) > OUTPUT_LIMIT:
        index = next(
            (
                candidate
                for candidate in range(len(map_paths) - 1, -1, -1)
                if entries_by_map[candidate]
            ),
            None,
        )
        if index is None:
            break
        entries_by_map[index].pop()
        omitted[index] += 1
        lines = build_lines()
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from bkf_common import MAP_NAME, find_bundles, inventory_entries, is_bundle_root_map
        cwd = (args.cwd or Path.cwd()).resolve()
        root = _bundle_root(cwd, is_bundle_root_map)
        if root is None:
            return 0

        directories = [directory for directory in reversed(cwd.parents) if directory.is_relative_to(root)]
        if cwd.is_relative_to(root):
            directories.append(cwd)
        map_paths = [directory / MAP_NAME for directory in directories if (directory / MAP_NAME).is_file()]
        entries_by_map = [inventory_entries(root, map_path) for map_path in map_paths]
        health = None
        if not args.no_validate:
            from validate_bundle import Validator

            health = _validate(root, find_bundles, Validator)
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        sys.stdout.write(_render(root, cwd, map_paths, entries_by_map, health))
        return 0
    except Exception as exc:
        if args.debug:
            print(f"bkf orient: {exc}", file=sys.stderr)
            return 1
        detail = " ".join(str(exc).split()) or "no details"
        message = f"bkf hook orient failed: {type(exc).__name__}: {detail}"
        if len(message) > 300:
            message = message[:299] + "…"
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        print(message, file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

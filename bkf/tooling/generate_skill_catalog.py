#!/usr/bin/env python3
"""Generate the skill catalog, with writing available only by explicit flag."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_catalog_common import (
    CATALOG_RELATIVE,
    generate_catalog,
    validate_repository,
    write_catalog,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write only the generated catalog")
    mode.add_argument("--check", action="store_true", help="fail when the committed catalog is stale")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if args.write:
        target = write_catalog(root)
        print(f"wrote {target.relative_to(root).as_posix()}")
        return 0
    if args.check:
        report = validate_repository(root, check_catalog=True)
        if report["catalog"]["status"] == "valid":
            print(f"catalog is up to date: {CATALOG_RELATIVE.as_posix()}")
            return 0
        print(f"catalog check failed: {report['catalog']['status']}")
        for finding in report["issues"]:
            if finding["code"].startswith("CATALOG_"):
                print(f"{finding['code']}: {finding['explanation']}")
        return 1
    sys.stdout.write(generate_catalog(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())

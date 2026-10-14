#!/usr/bin/env python3
"""Validate the reusable skill catalog without modifying the repository."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from catalog_common import validate_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="also compare the generated catalog")
    parser.add_argument("--catalog", type=Path, help="catalog path used with --check")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_repository(args.root, check_catalog=args.check, catalog_path=args.catalog)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"packages: {report['summary']['packages']}")
        print(f"issues: {report['summary']['issues']}")
        for finding in report["issues"]:
            location = f":{finding['line']}" if finding["line"] else ""
            print(f"{finding['severity'].upper()} {finding['code']} {finding['path']}{location} — {finding['explanation']}")
    return 0 if report["status"] == "valid" else 1


if __name__ == "__main__":
    sys.exit(main())

"""Check or regenerate the shared library lists and skill catalog."""

from __future__ import annotations

import argparse
from pathlib import Path

import generate_inventory
import generate_skill_catalog
import validate_skill_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd(), help="repository root")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check inventories, tagged lists, and catalog (default)")
    mode.add_argument("--write", action="store_true", help="write inventories, tagged lists, and catalog")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    library = root / "agent-skills" / "library"
    skills = root / "agent-skills" / "skills"
    mode = "--write" if args.write else "--check"

    inventory_status = generate_inventory.main([str(library), "--skills", str(skills), mode])
    if args.write:
        catalog_status = generate_skill_catalog.main([str(root), "--write"])
    else:
        catalog_status = validate_skill_catalog.main([str(root), "--check"])
    return max(inventory_status, catalog_status)


if __name__ == "__main__":
    raise SystemExit(main())

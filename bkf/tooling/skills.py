"""Check or regenerate the map inventories, the injected module text in skills, and the skill catalog."""

from __future__ import annotations

import argparse
from pathlib import Path

import generate_inventory
import generate_skill_catalog
import validate_skill_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf skills", description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd(), help="repository root")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check inventories, injected text, and catalog (default)")
    mode.add_argument("--write", action="store_true", help="write inventories, injected text, and catalog")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    bundle = root / "agent-skills" / "modules"
    skills = root / "agent-skills" / "skills"
    mode = "--write" if args.write else "--check"

    inventory_status = generate_inventory.main([str(bundle), "--skills", str(skills), mode])
    if args.write:
        catalog_status = generate_skill_catalog.main([str(root), "--write"])
    else:
        catalog_status = validate_skill_catalog.main([str(root), "--check"])
    return max(inventory_status, catalog_status)


if __name__ == "__main__":
    raise SystemExit(main())

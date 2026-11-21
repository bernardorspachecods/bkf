"""Register and maintain sources in the machine-wide BKF store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bkf_common import BKFInputError, read_text_preserving_newlines
from source_page import KINDS
from source_store import StoreError, check, complete, finish, init_store, register, save_snapshot


ALREADY_REGISTERED = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bkf sources", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="initialize the store or upgrade its schema")
    add = commands.add_parser("add", help="register a URL or enter a source manually")
    snapshot = commands.add_parser("snapshot", help="save source text read elsewhere")
    close = commands.add_parser("finish", help="close a pending record")
    reopen = commands.add_parser("complete", help="record why a source needs a fresh consultation")
    inspect = commands.add_parser("check", help="check the store schema, source metadata, and claim anchors")
    for command in (init, add, snapshot, close, reopen, inspect):
        command.add_argument("--dir", help="store directory (default: BKF_SOURCES_DIR or ~/sources)")
    add.add_argument("source_url", metavar="URL", nargs="?")
    add.add_argument("--manual", action="store_true", help="register without fetching")
    add.add_argument("--url", help="source URL for manual entry (default: unknown)")
    add.add_argument("--title")
    add.add_argument("--author")
    add.add_argument("--published")
    add.add_argument("--kind", choices=KINDS)
    add.add_argument("--via", default="user")
    snapshot.add_argument("id", metavar="ID")
    snapshot.add_argument("--from", dest="source_file", metavar="FILE", required=True, help="read UTF-8 text from FILE (or - for stdin)")
    snapshot.add_argument("--note", metavar="TEXT", required=True, help="where the text came from")
    close.add_argument("id", metavar="ID")
    close.add_argument("--status", choices=("used", "discarded"), required=True)
    close.add_argument("--description", required=True)
    close.add_argument("--reason")
    close.add_argument("--kind", choices=KINDS)
    close.add_argument("--id", dest="new_id", metavar="NEW", help="rename the pending record before closing it")
    reopen.add_argument("id", metavar="ID")
    reopen.add_argument("--why", required=True)
    inspect.add_argument("ids", metavar="ID", nargs="*")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            print(init_store(args.dir))
        elif args.command == "add":
            if args.manual and args.source_url is not None:
                parser.error("use --url in manual mode")
            if not args.manual and args.url is not None:
                parser.error("--url requires --manual")
            result = register(
                args.url if args.manual else args.source_url, directory=args.dir, manual=args.manual,
                title=args.title, author=args.author, published=args.published, kind=args.kind, via=args.via,
            )
            print(result.id)
            return ALREADY_REGISTERED if result.already_registered else 0
        elif args.command == "snapshot":
            content = sys.stdin.read() if args.source_file == "-" else read_text_preserving_newlines(Path(args.source_file))
            save_snapshot(args.id, content, note=args.note, directory=args.dir)
        elif args.command == "finish":
            print(finish(args.id, status=args.status, description=args.description, reason=args.reason,
                         kind=args.kind, directory=args.dir, new_id=args.new_id))
        elif args.command == "complete":
            complete(args.id, why=args.why, directory=args.dir)
        else:
            return check(args.ids, directory=args.dir)
    except (BKFInputError, OSError, StoreError, UnicodeError) as exc:
        print(f"bkf sources: {exc}", file=sys.stderr)
        return 1
    return 0

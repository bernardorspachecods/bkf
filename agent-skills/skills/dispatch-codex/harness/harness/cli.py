import argparse
import math
import sys

from .gate import run_gate


def _parser():
    parser = argparse.ArgumentParser(prog="harness")
    subparsers = parser.add_subparsers(dest="area", required=True)
    gate_parser = subparsers.add_parser("gate")
    gate_subparsers = gate_parser.add_subparsers(dest="action", required=True)
    run_parser = gate_subparsers.add_parser("run")
    run_parser.add_argument("--cwd", required=True)
    run_parser.add_argument("--timeout", required=True, type=float)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--note", action="append", default=[])
    run_parser.add_argument("commands", nargs=argparse.REMAINDER)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite number greater than zero")
    commands = args.commands
    if commands and commands[0] == "--":
        commands = commands[1:]
    try:
        result = run_gate(args.cwd, args.timeout, args.out, commands, args.note)
    except (OSError, ValueError) as error:
        print("harness: {0}".format(error), file=sys.stderr)
        return 2
    return 1 if result["red"] else 0

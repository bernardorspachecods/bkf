import argparse
import math
import sys

from .agent import run_agent
from .gate import run_gate
from .inject import InjectionError, inject_rules
from .verdict import checked_ok, read_verdict
from .engine.pipeline import main as run_workflow


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
    inject_parser = subparsers.add_parser("inject")
    inject_parser.add_argument("prompt_file")
    verdict_parser = subparsers.add_parser("verdict")
    verdict_subparsers = verdict_parser.add_subparsers(dest="action", required=True)
    read_parser = verdict_subparsers.add_parser("read")
    read_parser.add_argument("file")
    checked_parser = verdict_subparsers.add_parser("checked")
    checked_parser.add_argument("file")
    checked_parser.add_argument("--min", required=True, type=int)
    agent_parser = subparsers.add_parser("agent")
    agent_subparsers = agent_parser.add_subparsers(dest="action", required=True)
    agent_run_parser = agent_subparsers.add_parser("run")
    agent_run_parser.add_argument("--dir", required=True)
    agent_run_parser.add_argument("--prompt", required=True)
    agent_run_parser.add_argument("--out-prefix", required=True)
    agent_run_parser.add_argument("--model", required=True)
    agent_run_parser.add_argument("--effort", required=True)
    agent_run_parser.add_argument("--sandbox", default="workspace-write")
    agent_run_parser.add_argument("--tier")
    agent_run_parser.add_argument("--backend", default="codex")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("definition_path")
    run_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.area == "run":
        return run_workflow(args.definition_path, args.arguments)
    if args.area == "agent":
        return run_agent(
            args.dir,
            args.prompt,
            args.out_prefix,
            args.model,
            args.effort,
            sandbox=args.sandbox,
            tier=args.tier,
            backend=args.backend,
        )
    if args.area == "inject":
        try:
            inject_rules(args.prompt_file)
        except InjectionError as error:
            print(str(error), file=sys.stderr)
            return 1
        except OSError as error:
            print("harness: {0}".format(error), file=sys.stderr)
            return 2
        return 0
    if args.area == "verdict":
        if args.action == "read":
            verdict = read_verdict(args.file)
            if verdict is None:
                return 1
            print(verdict)
            return 0
        return 0 if checked_ok(args.file, args.min) else 1
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

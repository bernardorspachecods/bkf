"""Check one parallel branch against its gate, without reading its content."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path


def _git(checkout: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=checkout, check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ValueError(f"git {' '.join(args)} failed in {checkout}: {detail.strip()}") from exc
    return result.stdout


def changed_files(checkout: Path, base: str) -> list[str]:
    """Return the files that differ from base in the checkout, untracked ones included."""
    tracked = _git(checkout, "diff", "--name-only", "-z", base).split("\0")
    untracked = _git(checkout, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return sorted({path for path in (*tracked, *untracked) if path})


def _tail(text: str, lines: int = 5) -> str:
    kept = [line for line in text.strip().splitlines() if line.strip()]
    return " | ".join(kept[-lines:])


def run_gate(
    checkout: Path,
    base: str,
    allow: list[str],
    checks: list[str],
    allow_empty: bool = False,
    timeout: int = 300,
) -> list[tuple[str, bool, str]]:
    """Return one (name, passed, detail) result per gate check."""
    files = changed_files(checkout, base)
    outside = [path for path in files if not any(fnmatch.fnmatchcase(path, pattern) for pattern in allow)]
    results = [
        (
            "scope",
            not outside,
            f"{len(files)} changed files" if not outside else "outside the allowed files: " + ", ".join(outside),
        ),
        (
            "nonempty",
            bool(files) or allow_empty,
            f"{len(files)} changed files" if files else f"no changes against {base}",
        ),
    ]
    for command in checks:
        try:
            done = subprocess.run(
                command, shell=True, cwd=checkout, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            results.append((f"check {command!r}", False, f"no result after {timeout} seconds"))
            continue
        output = _tail(done.stdout + "\n" + done.stderr)
        results.append(
            (f"check {command!r}", done.returncode == 0, f"exit {done.returncode}" + (f": {output}" if output else ""))
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bkf gate",
        description=(
            "Check a parallel branch against its gate before merging it: every changed file "
            "must match an --allow pattern, the branch must have changed something, and every "
            "--check command must exit 0. It reads no file content."
        ),
    )
    parser.add_argument("--base", required=True, help="git ref the branch started from")
    parser.add_argument(
        "--allow",
        action="append",
        required=True,
        metavar="PATTERN",
        help="allowed file pattern, repeatable; * also matches /",
    )
    parser.add_argument(
        "--check", action="append", default=[], metavar="COMMAND", help="completeness command, repeatable"
    )
    parser.add_argument("--allow-empty", action="store_true", help="do not fail a branch that changed nothing")
    parser.add_argument("--timeout", type=int, default=300, help="seconds each --check may run (default 300)")
    parser.add_argument("checkout", nargs="?", default=".", help="the branch's checkout (default: current directory)")
    args = parser.parse_args(argv)

    try:
        results = run_gate(Path(args.checkout), args.base, args.allow, args.check, args.allow_empty, args.timeout)
    except ValueError as exc:
        print(f"bkf gate: {exc}", file=sys.stderr)
        return 2
    for name, passed, detail in results:
        print(f"{name}: {'pass' if passed else 'fail'} - {detail}")
    passed = all(result[1] for result in results)
    print(f"gate: {'pass' if passed else 'fail'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

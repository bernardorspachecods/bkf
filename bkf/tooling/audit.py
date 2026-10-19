"""Build the whole-repository structure report behind the `bkf:` prompt prefix."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

SUMMARY_LIMIT = 3000
LISTED_PATHS = 15
LISTED_FINDINGS = 5
REPORT_KEEP = 20
GIT_STATES = (
    ("staged", "changes staged for commit"),
    ("modified", "tracked files with unstaged changes"),
    ("deleted", "tracked files deleted from the working tree"),
    ("untracked", "files git does not track"),
)


@dataclass
class Change:
    path: str
    state: str


@dataclass
class BundleAudit:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stale_inventory: bool = False


@dataclass
class Audit:
    repo: Path
    branch: str
    head: str
    changes: list[Change]
    bundles: list[BundleAudit]


def _git(repo: Path, *args: str) -> str | None:
    from hook_events import _git as run

    output = run(repo, *args)
    return os.fsdecode(output).rstrip("\r\n") if output is not None else None


def classify(code: str) -> list[str]:
    """Map a porcelain XY code to the states it represents; one path can hold several."""
    if code == "??":
        return ["untracked"]
    states = []
    if code[0] not in " ?":
        states.append("deleted" if code[0] == "D" else "staged")
    if code[1] == "D":
        states.append("deleted")
    elif code[1] not in " ?":
        states.append("modified")
    return list(dict.fromkeys(states))


def git_changes(repo: Path) -> list[Change]:
    status = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if not status:
        return []
    entries = status.split("\0")
    changes: list[Change] = []
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        code, path = entry[:2], entry[3:]
        if "R" in code or "C" in code:
            index += 1
        for state in classify(code):
            changes.append(Change(path, state))
        index += 1
    return changes


def bundle_roots(repo: Path) -> list[Path]:
    from bkf_common import find_bundles, is_bundle_root_map, nested_bundle_roots

    if (repo / "MAP.md").is_file() and is_bundle_root_map(repo / "MAP.md"):
        return find_bundles(repo)
    roots: list[Path] = []
    for nested in nested_bundle_roots(repo):
        roots.extend(find_bundles(nested))
    return roots


def audit_bundle(root: Path) -> BundleAudit:
    import generate_inventory
    from hook_events import _run
    from validate_bundle import Validator

    result = BundleAudit(root)
    validator = Validator(root)
    validator.validate()
    for finding in validator.findings:
        line = f"{finding.code} {finding.path}: {finding.message}"
        (result.errors if finding.severity == "ERROR" else result.warnings).append(line)
    code, _ = _run(generate_inventory.main, [str(root), "--check"])
    result.stale_inventory = code == 1
    return result


def run(cwd: Path) -> Audit | None:
    """Audit the git repository containing `cwd`; return None outside one."""
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return None
    repo = Path(top).resolve()
    branch = _git(repo, "branch", "--show-current") or "(detached)"
    head = _git(repo, "rev-parse", "--short", "HEAD") or "(no commits)"
    bundles = [audit_bundle(root) for root in bundle_roots(repo)]
    return Audit(repo, branch, head, git_changes(repo), bundles)


def _area(repo: Path, audit: Audit, change: Change) -> str:
    """Name the deepest bundle that holds the change, or `(outside any bundle)`."""
    target = repo / change.path
    best = None
    for bundle in audit.bundles:
        if bundle.root == target or bundle.root in target.parents:
            if best is None or len(bundle.root.parts) > len(best.parts):
                best = bundle.root
    if best is None:
        return "(outside any bundle)"
    return best.relative_to(repo).as_posix() or "."


def render(audit: Audit) -> str:
    lines = [
        "# BKF audit",
        "",
        f"Repository `{audit.repo}` on `{audit.branch}` at `{audit.head}`.",
        "",
        "## Git changes",
        "",
    ]
    if not audit.changes:
        lines += ["Working tree is clean.", ""]
    for state, meaning in GIT_STATES:
        paths = [change.path for change in audit.changes if change.state == state]
        if not paths:
            continue
        lines += [f"### {state.capitalize()} ({len(paths)}): {meaning}", ""]
        by_area: dict[str, list[str]] = {}
        for change in audit.changes:
            if change.state == state:
                by_area.setdefault(_area(audit.repo, audit, change), []).append(change.path)
        for area, area_paths in sorted(by_area.items()):
            lines.append(f"- `{area}` ({len(area_paths)})")
            lines += [f"  - `{path}`" for path in sorted(area_paths)]
        lines.append("")
    lines += ["## Bundles", ""]
    if not audit.bundles:
        lines += ["No BKF bundle found in this repository.", ""]
    for bundle in audit.bundles:
        label = bundle.root.relative_to(audit.repo).as_posix() or "."
        status = "ok" if not (bundle.errors or bundle.warnings or bundle.stale_inventory) else "needs attention"
        lines += [f"### `{label}`: {status}", ""]
        if bundle.stale_inventory:
            lines.append(f"- Inventory is stale. Fix with `bkf inventory {label} --write`.")
        lines += [f"- ERROR {item}" for item in bundle.errors]
        lines += [f"- WARNING {item}" for item in bundle.warnings]
        if status == "ok":
            lines.append("- Validation passes and the inventory is current.")
        lines.append("")
    return "\n".join(lines)


def summary(audit: Audit, report_path: Path | None) -> str:
    counts = {state: sum(change.state == state for change in audit.changes) for state, _ in GIT_STATES}
    lines = [f"BKF audit of {audit.repo} ({audit.branch} at {audit.head})."]
    lines.append("Git: " + (", ".join(f"{n} {state}" for state, n in counts.items() if n) or "clean"))
    untracked = sorted(change.path for change in audit.changes if change.state == "untracked")
    if untracked:
        lines.append("Untracked:")
        lines += [f"  {path}" for path in untracked[:LISTED_PATHS]]
        if len(untracked) > LISTED_PATHS:
            lines.append(f"  ... and {len(untracked) - LISTED_PATHS} more")
    for bundle in audit.bundles:
        label = bundle.root.relative_to(audit.repo).as_posix() or "."
        if not (bundle.errors or bundle.warnings or bundle.stale_inventory):
            lines.append(f"Bundle {label}: ok")
            continue
        lines.append(
            f"Bundle {label}: {len(bundle.errors)} errors, {len(bundle.warnings)} warnings"
            + (", inventory stale" if bundle.stale_inventory else "")
        )
        lines += [f"  {item}" for item in bundle.errors[:LISTED_FINDINGS]]
        if len(bundle.errors) > LISTED_FINDINGS:
            lines.append(f"  ... and {len(bundle.errors) - LISTED_FINDINGS} more errors")
    if report_path is not None:
        lines.append(f"Full report: {report_path}")
    text = "\n".join(lines)
    if len(text) > SUMMARY_LIMIT:
        text = text[: SUMMARY_LIMIT - 1].rstrip() + "…"
        if report_path is not None:
            text += f"\nFull report: {report_path}"
    return text


def write_report(audit: Audit, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"bkf-audit-{time.strftime('%Y%m%d-%H%M%S')}.md"
    path.write_text(render(audit) + "\n", encoding="utf-8")
    for old in sorted(report_dir.glob("bkf-audit-*.md"))[:-REPORT_KEEP]:
        old.unlink(missing_ok=True)
    return path

#!/usr/bin/env python3
"""Merge queue for sessions that finish work in separate worktrees of one repo.

The queue lives in `<git-common-dir>/bkf-merge-queue/`, which every worktree of
the repository shares and git never tracks. One JSON file per session sits in
`entries/`; `integration.json` exists only while an integration is running.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def fail(message, code=1):
    print(message)
    raise SystemExit(code)


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and result.returncode:
        fail(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result


def out(repo, *args):
    return git(repo, *args).stdout.strip()


def queue_path(repo):
    common = out(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common) / "bkf-merge-queue"


def queue_dir(repo):
    path = queue_path(repo)
    (path / "entries").mkdir(parents=True, exist_ok=True)
    return path


def slug(session):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", session).strip("-") or "session"


def load_entries(qdir):
    entries = [json.loads(p.read_text()) for p in (qdir / "entries").glob("*.json")]
    return sorted(entries, key=lambda e: e["registered"])


def is_stale(repo, entry):
    tip = git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{entry['branch']}", check=False)
    return tip.returncode != 0 or tip.stdout.strip() != entry["head"]


def split_paths(text):
    return [p for p in text.split(",") if p]


def register(args):
    repo = Path.cwd()
    for level in ("fast", "full"):
        if getattr(args, level) != "pass":
            fail(f"Refused: the {level} tests must pass on the branch before it joins the queue.")
    head = out(repo, "rev-parse", f"refs/heads/{args.branch}")
    base = out(repo, "merge-base", args.target, head)
    entry = {
        "session": args.session,
        "branch": args.branch,
        "head": head,
        "registered": time.time(),
        "worktree": out(repo, "rev-parse", "--show-toplevel"),
        "plans": split_paths(args.plans),
        "deviations": split_paths(args.deviations),
        "base_tested": args.base,
        "files": out(repo, "diff", "--name-only", f"{base}..{head}").splitlines(),
        "tests": {"fast": args.fast, "full": args.full},
    }
    qdir = queue_dir(repo)
    (qdir / "entries" / f"{slug(args.session)}.json").write_text(json.dumps(entry, indent=2))
    print(f"Registered {args.session} ({args.branch} at {head[:10]}).")


def describe(entry, stale):
    flag = "  STALE: the branch moved after it registered" if stale else ""
    lines = [
        f"- {entry['session']}  branch {entry['branch']}  head {entry['head'][:10]}{flag}",
        f"    plans: {', '.join(entry['plans']) or '-'}",
        f"    deviations: {', '.join(entry['deviations']) or '-'}",
        f"    files: {', '.join(entry['files']) or '-'}",
        f"    tested on base {entry['base_tested'][:10]}: fast {entry['tests']['fast']}, "
        f"full {entry['tests']['full']}",
    ]
    return "\n".join(lines)


def list_queue(args):
    repo = Path.cwd()
    entries = load_entries(queue_dir(repo))
    if not entries:
        print("The queue is empty.")
    for entry in entries:
        print(describe(entry, is_stale(repo, entry)))


def busy(args):
    """Exit 1 while the queue has entries or an integration is running; create nothing."""
    path = queue_path(Path.cwd())
    if (path / "integration.json").exists():
        fail("An integration is in progress: do not merge into main directly.")
    names = [json.loads(p.read_text())["session"] for p in (path / "entries").glob("*.json")]
    if names:
        fail(f"The merge queue has entries ({', '.join(names)}): use git-merge-queue.")


def unregister(args):
    entry = queue_dir(Path.cwd()) / "entries" / f"{slug(args.session)}.json"
    if not entry.exists():
        fail(f"No queue entry for {args.session}.")
    entry.unlink()
    print(f"Removed the entry of {args.session}.")


def checkout_of(repo, branch):
    """Path of the worktree that has `branch` checked out, or None."""
    path = None
    for line in out(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def run_check(command, cwd, label):
    result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        print(f"{label} check failed ({command}):")
        print((result.stdout + result.stderr).strip()[-2000:])
    return result.returncode == 0


def save_state(qdir, state):
    (qdir / "integration.json").write_text(json.dumps(state, indent=2))


def discard_integration(repo, state):
    git(repo, "worktree", "remove", "--force", state["worktree"], check=False)
    git(repo, "branch", "-D", state["branch"], check=False)


def clean_session(repo, entry):
    """Remove an integrated session's worktree and branch; return a note if one stayed."""
    wt, branch = entry["worktree"], entry["branch"]
    main_checkout = out(repo, "worktree", "list", "--porcelain").splitlines()[0][len("worktree "):]
    if Path(wt).resolve() == Path(main_checkout).resolve():
        return f"Left {wt}: it is the main checkout (branch {branch} stays)."
    removed = git(repo, "worktree", "remove", wt, check=False) if Path(wt).exists() else None
    if removed is not None and removed.returncode:
        return f"Left {wt}: {removed.stderr.strip()} (branch {branch} stays)."
    deleted = git(repo, "branch", "-d", branch, check=False)
    if deleted.returncode:
        return f"Left branch {branch}: {deleted.stderr.strip()}"
    print(f"Removed {wt} and branch {branch}.")
    return None


def merge_entry(args, qdir, state, entries):
    """Merge the next pending entry. Returns an exit code to stop with, else None."""
    wt = state["worktree"]
    slug_ = state["pending"][0]
    entry = entries[slug_]
    if state.get("current") != slug_:
        before = out(wt, "rev-parse", "HEAD")
        state["before"] = before
        merged = git(wt, "merge", "--no-ff", "-m",
                     f"Merge {entry['branch']} ({entry['session']})", entry["head"], check=False)
        if merged.returncode:
            conflicts = out(wt, "diff", "--name-only", "--diff-filter=U").splitlines()
            state["current"] = slug_
            save_state(qdir, state)
            print(f"Conflict merging {entry['session']} ({entry['branch']}).")
            print(f"Conflicting files: {', '.join(conflicts) or 'see git status'}")
            print(f"Resolve and commit in {wt}, then run `integrate --resume`.")
            print(f"Ask {entry['session']} about its intent if the plans do not settle it.")
            return 2
    else:
        merging = git(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False)
        landed = git(wt, "merge-base", "--is-ancestor", entry["head"], "HEAD", check=False)
        if merging.returncode == 0 or landed.returncode != 0:
            print(f"The conflict for {entry['session']} in {wt} is not resolved and committed yet.")
            return 2
    state.pop("current", None)
    if not run_check(args.fast_check, wt, "Fast"):
        git(wt, "reset", "--hard", state["before"])
        state["dropped"].append({"entry": slug_, "reason": "fast check failed"})
        print(f"Dropped {entry['session']}: its changes broke the fast check.")
    else:
        state["done"].append(slug_)
    state["pending"].pop(0)
    save_state(qdir, state)
    return None


def integrate(args):
    repo = Path.cwd()
    qdir = queue_dir(repo)
    state_path = qdir / "integration.json"

    if args.abort:
        if not state_path.exists():
            fail("No integration in progress.")
        discard_integration(repo, json.loads(state_path.read_text()))
        state_path.unlink()
        print("Integration discarded. The queue entries are untouched.")
        return
    if state_path.exists() != args.resume:
        fail("An integration is in progress: use --resume to continue or --abort to drop it."
             if state_path.exists() else "No integration in progress to resume.")

    if args.resume:
        state = json.loads(state_path.read_text())
    else:
        entries = load_entries(qdir)
        usable = []
        for entry in entries:
            if is_stale(repo, entry):
                print(describe(entry, True))
                print("  Skipped: it stays queued until its session registers again.")
            else:
                usable.append(entry)
        if not usable:
            fail("Nothing to integrate.", 0)
        branch = f"bkf-integration-{int(time.time())}"
        wt = tempfile.mkdtemp(prefix="bkf-integration-")
        git(repo, "worktree", "add", "-q", "-b", branch, wt, args.target)
        state = {"worktree": wt, "branch": branch, "target": args.target,
                 "target_tip": out(repo, "rev-parse", args.target),
                 "pending": [slug(e["session"]) for e in usable], "done": [], "dropped": []}
        save_state(qdir, state)

    entries = {slug(e["session"]): e for e in load_entries(qdir)}
    while state["pending"]:
        stop = merge_entry(args, qdir, state, entries)
        if stop:
            raise SystemExit(stop)

    if state["done"] and not run_check(args.full_check, state["worktree"], "Full"):
        print(f"Main untouched. Inspect {state['worktree']}, then `integrate --resume` to rerun "
              "the full check or `integrate --abort` to discard.")
        raise SystemExit(3)

    target = state["target"]
    if state["done"]:
        if out(repo, "rev-parse", target) != state["target_tip"]:
            print(f"{target} moved while the integration ran; it was not overwritten. "
                  "Abort and run the integration again.")
            raise SystemExit(4)
        tip = out(state["worktree"], "rev-parse", "HEAD")
        where = checkout_of(repo, target)
        if where:
            git(where, "merge", "--ff-only", tip)
        else:
            git(repo, "update-ref", f"refs/heads/{target}", tip)
        for key in state["done"]:
            (qdir / "entries" / f"{key}.json").unlink(missing_ok=True)
        leftovers = [clean_session(repo, entries[key]) for key in state["done"]]

    print(f"Merged into {target}: {', '.join(entries[k]['session'] for k in state['done']) or 'nothing'}.")
    for line in filter(None, leftovers if state["done"] else []):
        print(line)
    for item in state["dropped"]:
        print(f"Left in the queue ({item['reason']}): {entries[item['entry']]['session']}")
    discard_integration(repo, state)
    state_path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser("register", help="Add this session's branch to the queue")
    reg.add_argument("--session", required=True, help="Name and ref other sessions can message")
    reg.add_argument("--branch", required=True)
    reg.add_argument("--plans", required=True, help="Comma-separated paths of the plans it ran")
    reg.add_argument("--deviations", default="",
                     help="Comma-separated paths of where the run records its deviations")
    reg.add_argument("--base", required=True, help="SHA of the main the tests ran against")
    reg.add_argument("--fast", required=True, help="Result of the fast check: pass or fail")
    reg.add_argument("--full", required=True, help="Result of the full suite: pass or fail")
    reg.add_argument("--target", default="main")
    reg.set_defaults(run=register)

    lst = sub.add_parser("list", help="Show the queue")
    lst.set_defaults(run=list_queue)

    bsy = sub.add_parser("busy", help="Exit 1 if the queue has entries or an integration runs")
    bsy.set_defaults(run=busy)

    unreg = sub.add_parser("unregister", help="Remove a session's entry from the queue")
    unreg.add_argument("--session", required=True)
    unreg.set_defaults(run=unregister)

    integ = sub.add_parser("integrate", help="Merge the queue into the target and test once")
    integ.add_argument("--fast-check", help="Command run after each merge")
    integ.add_argument("--full-check", help="Command run once on the combined result")
    integ.add_argument("--target", default="main")
    integ.add_argument("--resume", action="store_true", help="Continue after resolving a conflict")
    integ.add_argument("--abort", action="store_true", help="Discard the integration in progress")
    integ.set_defaults(run=integrate)

    args = parser.parse_args()
    if args.command == "integrate" and not args.abort and not (args.fast_check and args.full_check):
        parser.error("integrate needs --fast-check and --full-check unless --abort")
    args.run(args)


if __name__ == "__main__":
    main()

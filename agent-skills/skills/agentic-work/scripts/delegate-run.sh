#!/usr/bin/env bash
# Run one Codex agent task in a prepared git worktree and record the results.
# Usage: [DELEGATE_IN_PLACE=1] delegate-run.sh <name> <brief-file> [base-ref] [model] [effort]
# DELEGATE_IN_PLACE=1 runs in the main checkout instead of a new worktree.
# Without DELEGATE_IN_PLACE the agent works in <run>/worktree, on a new branch delegate/<name> made from the base.
# The run folder is the record: base, diffstat.txt, last-message.md and exit (the agent's exit status).
# DELEGATE_RERUN=1 relaunches an existing run folder; the worktree is reused when it is there.
# DELEGATE_UNIT_DIR=<unit folder> lets `ponte gate` write the receipt there.
# New worktrees run the repository's committed .plan-run.json setup; its bridge can run allowed pnpm scripts.
# Codex only: a Claude implementer is a subagent (git tag agentic-work-claude-launcher has the launcher with a Claude backend).
# Without a model and effort: gpt-6-luna and high.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=/dev/null
. "$here/../../../harness/scripts/lib.sh"

name=${1:?task name}
brief=${2:?brief file}
base=${3:-HEAD}
model=${4:-gpt-6-luna}
effort=${5:-high}
export HARNESS_BACKEND=codex

repo=$(git rev-parse --show-toplevel)
base=$(git -C "$repo" rev-parse "$base")
repo_name=$(basename "$repo")
runs="${DELEGATE_RUNS_DIR:-$HOME/.delegate-runs}/${repo_name}/${name}"

progress() { printf '[delegate] %s · %s\n' "$name" "$*" >&2 || true; }

if [[ -e "$runs/base" && -z "${DELEGATE_RERUN:-}" ]]; then
  printf 'Error: run folder already exists: %s\nSet DELEGATE_RERUN=1 to relaunch it.\n' "$runs" >&2
  exit 1
fi

mkdir -p "$runs"
cp "$brief" "$runs/brief.md"
# Every implementer works under the implementation guide; the harness injects the modules it names.
roles=$(cd "$here/../roles" && pwd)
cat >>"$runs/brief.md" <<ROLE

---
## Role
Open and follow the role guide: $roles/agentic-work-implementation.md (read-only). It says how to work inside the brief and what to verify before you hand over.
ROLE

if [ -n "${DELEGATE_IN_PLACE:-}" ]; then
  # Run in the main checkout; snapshot its current state (tracked files) as the diff base.
  worktree="$repo"
  base=$(git -C "$repo" stash create || true)
  base=${base:-$(git -C "$repo" rev-parse HEAD)}
  echo "$base" >"$runs/base"
  git -C "$repo" status --short >"$runs/status-before.txt"
else
  echo "$base" >"$runs/base"
  worktree="$runs/worktree"
  created=
  if [ ! -d "$worktree" ]; then
    if git -C "$repo" show-ref --verify --quiet "refs/heads/delegate/$name"; then
      git -C "$repo" worktree add "$worktree" "delegate/$name" >"$runs/worktree.log" 2>&1 || {
        printf 'Error: the delegate worktree could not be made; see %s/worktree.log\n' "$runs" >&2
        printf '%s\n' "$runs"
        exit 1
      }
    else
      git -C "$repo" worktree add -b "delegate/$name" "$worktree" "$base" >"$runs/worktree.log" 2>&1 || {
        printf 'Error: the delegate worktree could not be made; see %s/worktree.log\n' "$runs" >&2
        printf '%s\n' "$runs"
        exit 1
      }
    fi
    created=1
  fi
  if [ -n "$created" ] && ! harness prepare --run "$runs" --repo "$repo" --tree "$worktree" >"$runs/prepare.log" 2>&1; then
    printf 'Error: preparing the delegate worktree failed; see %s/prepare.log\n' "$runs" >&2
    printf '%s\n' "$runs"
    exit 1
  fi
fi

unset HARNESS_BRIDGE_BASE_FILE HARNESS_BRIDGE_LOG HARNESS_BRIDGE_UNIT HARNESS_BRIDGE_RECEIPT_DIR HARNESS_BRIDGE_GATE_BRIEF
pnpm_bridge=
if git -C "$repo" cat-file -e "$base:.plan-run.json" 2>/dev/null && \
  git -C "$repo" show "$base:.plan-run.json" 2>/dev/null | python3 -c 'import json,sys; value=json.load(sys.stdin); sys.exit(0 if isinstance(value,dict) and isinstance(value.get("bridge"),dict) else 1)' 2>/dev/null; then
  pnpm_bridge=1
fi
# With a unit folder, the agent's `ponte gate` writes the gate receipt there, so the loop can skip a gate that already passed.
gate_receipt=
if [ -n "${DELEGATE_UNIT_DIR:-}" ] && PYTHONPATH="$here/../../../harness" python3 -c 'import sys; from harness.gate import gate_commands; sys.exit(0 if gate_commands([sys.argv[1]]) else 1)' "$runs/brief.md"; then
  gate_receipt=1
fi
if [ -n "$pnpm_bridge" ] || [ -n "$gate_receipt" ]; then
  export HARNESS_BRIDGE_BASE_FILE="$runs/base"
  export HARNESS_BRIDGE_LOG="$runs/porteiro.log"
  export HARNESS_BRIDGE_UNIT="$name"
fi
if [ -n "$gate_receipt" ]; then
  export HARNESS_BRIDGE_RECEIPT_DIR="$DELEGATE_UNIT_DIR"
  export HARNESS_BRIDGE_GATE_BRIEF="$runs/brief.md"
  cat >>"$runs/brief.md" <<'GATE'

## Gate receipt

Run the unit's whole gate with `.plan-porteiro/ponte gate` as your last step, after your final edit.
It runs outside your sandbox and writes the proof the reviewer uses instead of running the gate again.
Any edit after it makes that proof stale, so run it again then.
GATE
fi
if [ -n "$pnpm_bridge" ]; then
  cat >>"$runs/brief.md" <<'BRIDGE'

## Command bridge

Some commands cannot run in your sandbox, such as those that need a local database or the network.
Ask for them with `.plan-porteiro/ponte pnpm <script> [args...]`; it runs outside the sandbox and returns output and exit code.
Only pnpm scripts listed in the repository's `.plan-run.json` are allowed, and a script you changed is refused.
Pass arguments, not shell syntax.
Run the checks named in the brief this way before you finish, and fix what fails.
BRIDGE
fi

rm -f "$runs/exit"
if [ -n "${DELEGATE_IN_PLACE:-}" ]; then
  progress "a correr (no lugar)"
else
  progress "a correr (em worktree)"
fi

set +e
agent_run "$worktree" "$runs/brief.md" "$runs/run" workspace-write
code=$?
set -e
echo "$code" >"$runs/exit"
for f in events.jsonl stderr.log last-message.md; do
  [ ! -e "$runs/run.$f" ] || mv "$runs/run.$f" "$runs/$f"
done

if [ -n "${DELEGATE_IN_PLACE:-}" ]; then
  git -C "$worktree" diff --stat "$base" >"$runs/diffstat.txt" 2>&1 || true
  git -C "$worktree" status --short >"$runs/status-after.txt"
else
  git -C "$worktree" add -N . >/dev/null 2>&1 || true
  git -C "$worktree" diff --stat "$base" >"$runs/diffstat.txt" 2>&1 || true
fi

if [ "$code" -eq 0 ]; then
  if [ -n "${DELEGATE_IN_PLACE:-}" ]; then
    changed=$( {
      git -C "$worktree" diff --name-only -z "$base" || true
      git -C "$worktree" ls-files --others --exclude-standard -z || true
    } | tr -cd '\000' | wc -c | tr -d '[:space:]') || changed=0
  else
    changed=$(git -C "$worktree" diff --name-only -z "$base" | tr -cd '\000' | wc -c | tr -d '[:space:]') || changed=0
  fi
  progress "concluído · $changed ficheiros"
else
  progress "falhou · exit=$code"
fi

echo "$runs"
exit "$code"

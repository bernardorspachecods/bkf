#!/usr/bin/env bash
# Run one agent task (Codex, or Claude with HARNESS_BACKEND=claude) in a prepared git worktree and record the results.
# Usage: [DELEGATE_IN_PLACE=1] delegate-run.sh <name> <brief-file> [base-ref] [model] [effort]
# DELEGATE_IN_PLACE=1 runs in the main checkout instead of a new worktree.
# DELEGATE_RERUN=1 allows reusing a run folder that already has a status file.
# New worktrees run the repository's committed .plan-run.json setup; its bridge can run allowed pnpm scripts.
# Without a model and effort: gpt-6-luna and high on Codex, sonnet and high on Claude.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
. "$here/../../../harness/scripts/lib.sh"

name=${1:?task name}
brief=${2:?brief file}
base=${3:-HEAD}
if [ "${HARNESS_BACKEND:-codex}" = claude ]; then
  model=${4:-sonnet}
  effort=${5:-high}
else
  model=${4:-gpt-6-luna}
  effort=${5:-high}
fi

repo=$(git rev-parse --show-toplevel)
base=$(git -C "$repo" rev-parse "$base")
repo_name=$(basename "$repo")
worktree="$(dirname "$repo")/${repo_name}-delegate/${name}"
branch="delegate/${name}"
runs="${DELEGATE_RUNS_DIR:-$HOME/.delegate-runs}/${repo_name}/${name}"

progress() { printf '[delegate] %s · %s\n' "$name" "$*" >&2 || true; }

if [[ -e "$runs/status" && -z "${DELEGATE_RERUN:-}" ]]; then
  printf 'Error: run folder already exists: %s\nSet DELEGATE_RERUN=1 to relaunch it.\n' "$runs" >&2
  exit 1
fi

mkdir -p "$runs" "$(dirname "$worktree")"
cp "$brief" "$runs/brief.md"

if [ -n "${DELEGATE_IN_PLACE:-}" ]; then
  # Run in the main checkout; snapshot its current state (tracked files) as the diff base.
  worktree="$repo"
  base=$(git -C "$repo" stash create || true)
  base=${base:-$(git -C "$repo" rev-parse HEAD)}
  echo "$base" >"$runs/base"
  git -C "$repo" status --short >"$runs/status-before.txt"
elif [ ! -d "$worktree" ]; then
  echo "$base" >"$runs/base"
  git -C "$repo" worktree add -b "$branch" "$worktree" "$base" >"$runs/setup.log" 2>&1
  if ! harness prepare --run "$runs" --repo "$repo" --tree "$worktree" >"$runs/prepare.log" 2>&1; then
    echo "prepare-failed" >"$runs/status"
    printf 'Error: preparing the delegate worktree failed; see %s/prepare.log\n' "$runs" >&2
    printf '%s\n' "$runs"
    exit 1
  fi
else
  echo "$base" >"$runs/base"
fi

unset HARNESS_BRIDGE_BASE_FILE HARNESS_BRIDGE_LOG HARNESS_BRIDGE_UNIT
if git -C "$repo" cat-file -e "$base:.plan-run.json" 2>/dev/null && \
  git -C "$repo" show "$base:.plan-run.json" 2>/dev/null | python3 -c 'import json,sys; value=json.load(sys.stdin); sys.exit(0 if isinstance(value,dict) and isinstance(value.get("bridge"),dict) else 1)' 2>/dev/null; then
  export HARNESS_BRIDGE_BASE_FILE="$runs/base"
  export HARNESS_BRIDGE_LOG="$runs/porteiro.log"
  export HARNESS_BRIDGE_UNIT="$name"
  cat >>"$runs/brief.md" <<'BRIDGE'

## Command bridge

Some commands cannot run in your sandbox because PostgreSQL shared memory and network access are restricted.
Ask for them with `.plan-porteiro/ponte pnpm <script> [args...]`; it runs outside the sandbox and returns output and exit code.
Only pnpm scripts listed in the repository's `.plan-run.json` are allowed, and a script you changed is refused.
Pass arguments, not shell syntax.
Run the checks named in the brief this way before you finish, and fix what fails.
BRIDGE
fi

echo "$worktree" >"$runs/worktree"
echo "running" >"$runs/status"

if [ -n "${DELEGATE_IN_PLACE:-}" ]; then
  progress "a correr (no lugar)"
else
  progress "a correr (em worktree)"
fi

set +e
agent_run "$worktree" "$runs/brief.md" "$runs/run" workspace-write
code=$?
set -e
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

echo "exit=$code" >"$runs/status"
echo "$runs"
exit "$code"

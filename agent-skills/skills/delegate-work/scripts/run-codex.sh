#!/usr/bin/env bash
# Run one Codex task in its own git worktree and record the results.
# Usage: [CODEX_IN_PLACE=1] run-codex.sh <name> <brief-file> [base-ref] [model] [effort]
# CODEX_IN_PLACE=1 runs in the main checkout instead of a new worktree.
# CODEX_RERUN=1 is the intended value to allow reusing a run folder with a status file.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
. "$here/../../dispatch-agents/scripts/lib-codex.sh"

name=${1:?task name}
brief=${2:?brief file}
base=${3:-HEAD}
model=${4:-gpt-6-luna}
effort=${5:-xhigh}

repo=$(git rev-parse --show-toplevel)
base=$(git -C "$repo" rev-parse "$base")
repo_name=$(basename "$repo")
worktree="$(dirname "$repo")/${repo_name}-codex/${name}"
branch="codex/${name}"
runs="${CODEX_RUNS_DIR:-$HOME/.codex-runs}/${repo_name}/${name}"

progress() { printf '[delegate] %s · %s\n' "$name" "$*" >&2 || true; }

if [[ -e "$runs/status" && -z "${CODEX_RERUN:-}" ]]; then
  printf 'Error: run folder already exists: %s\nSet CODEX_RERUN=1 to relaunch it.\n' "$runs" >&2
  exit 1
fi

mkdir -p "$runs" "$(dirname "$worktree")"
cp "$brief" "$runs/brief.md"

if [ -n "${CODEX_IN_PLACE:-}" ]; then
  # Run in the main checkout; snapshot its current state (tracked files) as the diff base.
  worktree="$repo"
  base=$(git -C "$repo" stash create || true)
  base=${base:-$(git -C "$repo" rev-parse HEAD)}
  git -C "$repo" status --short >"$runs/status-before.txt"
elif [ ! -d "$worktree" ]; then
  git -C "$repo" worktree add -b "$branch" "$worktree" "$base" >"$runs/setup.log" 2>&1
fi

echo "$worktree" >"$runs/worktree"
echo "running" >"$runs/status"

if [ -n "${CODEX_IN_PLACE:-}" ]; then
  progress "a correr (no lugar)"
else
  progress "a correr (em worktree)"
fi

set +e
codex_run "$worktree" "$runs/brief.md" "$runs/run" workspace-write
code=$?
set -e
for f in events.jsonl stderr.log last-message.md; do
  [ ! -e "$runs/run.$f" ] || mv "$runs/run.$f" "$runs/$f"
done

if [ -n "${CODEX_IN_PLACE:-}" ]; then
  git -C "$worktree" diff --stat "$base" >"$runs/diffstat.txt" 2>&1 || true
  git -C "$worktree" status --short >"$runs/status-after.txt"
  echo "$base" >"$runs/base"
else
  git -C "$worktree" add -N . >/dev/null 2>&1 || true
  git -C "$worktree" diff --stat "$base" >"$runs/diffstat.txt" 2>&1 || true
fi

if [ "$code" -eq 0 ]; then
  if [ -n "${CODEX_IN_PLACE:-}" ]; then
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

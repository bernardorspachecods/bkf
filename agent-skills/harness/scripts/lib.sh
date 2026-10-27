# Shell helpers for the workflow runners: validation, harness CLI and Codex wrappers.
# Source it; it defines functions only. The caller sets $model and $effort before agent_run.

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

valid_name() { [[ $1 =~ ^[A-Za-z0-9._-]+$ && $1 != . && $1 != .. ]]; }

# Run the harness CLI from any script.
harness() { PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" python3 -m harness "$@"; }

# Run the agent backend (codex, or claude with HARNESS_BACKEND) in <dir> with the prompt on stdin. Events and errors go to <out-prefix>.*
# The sandbox is workspace-write unless the fourth argument names another.
# PLAN_CODEX_TIER (for example fast) sets the Codex's service tier; unset keeps the account default.
agent_run() { # <dir> <prompt-file> <out-prefix> [sandbox]
  local -a args=(agent run --dir "$1" --prompt "$2" --out-prefix "$3" --model "$model" --effort "$effort" --sandbox "${4:-workspace-write}")
  [ -z "${PLAN_CODEX_TIER:-}" ] || args+=(--tier "$PLAN_CODEX_TIER")
  harness "${args[@]}"
}

# Kept as a named helper for scripts/test-inject.sh and maintainers.
inject_rules() { harness inject "$1"; }

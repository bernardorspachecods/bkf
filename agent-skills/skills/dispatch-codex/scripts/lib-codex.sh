# Shared by phase-codex.sh, research-run.sh and plan-run.sh: run a Codex agent, read a reviewer's verdict.
# Source it; it defines functions only. The caller sets $model and $effort before codex_run and
# $min_checked (0 turns the check off) before checked_ok, and reads $reason after run_agents fails.

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

valid_name() { [[ $1 =~ ^[A-Za-z0-9._-]+$ && $1 != . && $1 != .. ]]; }

# Run codex in <dir> with the prompt on stdin. Events and errors go to <out-prefix>.*
# The sandbox is workspace-write unless the fourth argument names another.
codex_run() { # <dir> <prompt-file> <out-prefix> [sandbox]
  codex exec \
    --skip-git-repo-check \
    -C "$1" \
    -m "$model" \
    -c "model_reasoning_effort=\"$effort\"" \
    -s "${4:-workspace-write}" \
    --json \
    -o "$3.last-message.md" \
    - <"$2" >"$3.events.jsonl" 2>"$3.stderr.log"
}

# Print the verdict word from the last non-empty line of a problems file; fail if it is not exact.
read_verdict() { # <problems-file>
  local last
  last=$(awk 'NF{l=$0} END{print l}' "$1" 2>/dev/null | tr -d '[:space:]')
  case "$last" in
    VERDICT:pass) echo pass ;;
    VERDICT:back) echo back ;;
    VERDICT:escalate) echo escalate ;;
    *) return 1 ;;
  esac
}

# True when the file has a "## What I checked" section with at least $min_checked non-empty lines
# (or the check is off).
checked_ok() { # <problems-file>
  [ "$min_checked" -gt 0 ] || return 0
  awk -v min="$min_checked" '
    /^## What I checked/ { on = 1; next }
    on && /^#+ / { exit }
    on && NF { n++ }
    END { exit !(n >= min) }' "$1"
}

# Run the agents that have no output yet, in parallel, each in its own folder.
run_agents() { # <phase-dir> <output-file> <folder>...
  local pd=$1 out=$2 f pids=() p code bad=""
  shift 2
  for f in "$@"; do
    [ -s "$pd/$f/$out" ] && continue
    (
      codex_run "$pd/$f" "$pd/$f/brief.md" "$pd/$f/run" workspace-write
      code=$?
      [ "$code" -eq 0 ] || echo "exit=$code (see $pd/$f/run.stderr.log)" >"$pd/$f/failed"
      exit "$code"
    ) &
    pids+=($!)
  done
  for p in "${pids[@]+"${pids[@]}"}"; do wait "$p" || true; done
  for f in "$@"; do
    [ -s "$pd/$f/$out" ] || bad="$bad$f: $(cat "$pd/$f/failed" 2>/dev/null || echo "wrote no $out"); "
    rm -f "$pd/$f/failed"
  done
  [ -z "$bad" ] || { reason="$bad"; return 1; }
}

# After a record is kept, remind the user when the repository's AGENTS.md does not point to records/.
records_note() { # <repo>
  grep -qs 'records/' "$1/AGENTS.md" ||
    printf 'Note: %s/AGENTS.md does not mention records/. Add a line saying records/ holds the history of past runs, not rules, to be opened only when asked.\n' "$1"
}

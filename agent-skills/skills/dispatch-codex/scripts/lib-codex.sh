# Shared by phase-codex.sh and the run scripts: agent execution, verdict checks and step boards.
# Source it; it defines functions only. The caller sets $model and $effort before codex_run and
# $min_checked (0 turns the check off) before checked_ok, and reads $reason after run_agents fails.

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

valid_name() { [[ $1 =~ ^[A-Za-z0-9._-]+$ && $1 != . && $1 != .. ]]; }

# Run codex in <dir> with the prompt on stdin. Events and errors go to <out-prefix>.*
# The sandbox is workspace-write unless the fourth argument names another.
# PLAN_CODEX_TIER (for example fast) sets Codex's service tier; unset keeps the account default.
codex_run() { # <dir> <prompt-file> <out-prefix> [sandbox]
  codex exec \
    ${PLAN_CODEX_TIER:+-c "service_tier=\"$PLAN_CODEX_TIER\""} \
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

# Print the current state of a step-based run. The caller sets $run and $board_title.
# Specs are <id>|<label>|<directory>|<agent folders>|<agent output file>.
board_steps() { # <step-spec>...
  local run_dir=${run:-} title=${board_title:-Run} run_name status_log
  local start_stamp= start_time now_time event_state stopped_id running_id
  local spec id label step_dir agent_folders output_file agent_path agent first_pending_seen=0
  local step_running icon
  local -a agents=()

  run_name=${run_dir##*/}
  status_log=$run_dir/status.log
  if [ -r "$status_log" ]; then
    start_stamp=$(awk -F '\t' 'NR == 2 { print $1; exit }' "$status_log" 2>/dev/null) || start_stamp=
  fi
  start_time=${start_stamp#*T}
  start_time=${start_time:0:5}
  [ -n "$start_time" ] || start_time=--:--
  now_time=$(date '+%H:%M' 2>/dev/null) || now_time=--:--
  printf '%s %s · início %s → agora %s\n\n' "$title" "$run_name" "$start_time" "$now_time" || true

  for spec in "$@"; do
    id= label= step_dir= agent_folders= output_file=
    IFS='|' read -r id label step_dir agent_folders output_file <<<"$spec"

    event_state=
    if [ -r "$status_log" ]; then
      event_state=$(awk -F '\t' '
        $2 == "resume" { stopped = ""; active = ""; next }
        index($2, "STOPPED at ") == 1 {
          stopped = substr($2, 12)
          sub(/:.*/, "", stopped)
          active = ""
          next
        }
        index($2, "start ") == 1 {
          event = substr($2, 7)
          if (event ~ / /) { sub(/ .*/, "", event); active = event }
          else active = ""
          next
        }
        index($2, "done ") == 1 {
          event = substr($2, 6)
          sub(/ .*/, "", event)
          if (active == event) active = ""
          next
        }
        END { printf "%s|%s", stopped, active }
      ' "$status_log" 2>/dev/null) || event_state='|'
    else
      event_state='|'
    fi
    stopped_id=${event_state%%|*}
    running_id=${event_state#*|}

    step_running=0
    if [ -e "$run_dir/.done-$id" ]; then
      icon=✓
    elif [ "$stopped_id" = "$id" ]; then
      icon=✗
      first_pending_seen=1
    elif [ "$first_pending_seen" -eq 0 ]; then
      first_pending_seen=1
      icon=○
      if [ "$running_id" = "$id" ]; then icon=◐; step_running=1; fi
    else
      icon=○
    fi
    printf '%s %s\n' "$icon" "$label" || true

    agents=()
    if [ -n "$agent_folders" ]; then read -r -a agents <<<"$agent_folders"; fi
    for agent in "${agents[@]+"${agents[@]}"}"; do
      agent_path=$run_dir/$step_dir/$agent
      if [ -n "$output_file" ] && [ -s "$agent_path/$output_file" ]; then
        icon=✓
      elif [ -e "$agent_path/failed" ]; then
        icon=✗
      elif [ "$step_running" -eq 1 ]; then
        icon=◐
      else
        icon=○
      fi
      printf '    %s %s\n' "$icon" "$agent" || true
    done
  done
  return 0
}

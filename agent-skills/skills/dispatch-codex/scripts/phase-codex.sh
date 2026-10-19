#!/usr/bin/env bash
# Run one phase: one or more Codex agents in parallel, each reviewed by a second Codex run.
# Usage:
#   phase-codex.sh start [-m model] [-e effort] [-f file] <run> <name> <agent-brief> <review-brief> [<name> <agent-brief> <review-brief>]...
#   phase-codex.sh join <run>
#   phase-codex.sh clean <run>
# Each agent writes one file (-f, default output.md); the reviewer reads a copy and ends problems.md with a verdict line.
# State lives in ${PHASE_RUNS_DIR:-$HOME/.phase-runs}/<run>. It must not be under /tmp:
# the workspace-write sandbox leaves /tmp writable, so a folder there is not isolated.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"
root=${PHASE_RUNS_DIR:-$HOME/.phase-runs}
# Optional limits, off by default: PHASE_MAX_ROUNDS escalates a `back` verdict at that round;
# PHASE_MIN_CHECKED requires a "## What I checked" section of at least that many lines in problems.md.
max_rounds=${PHASE_MAX_ROUNDS:-0}
min_checked=${PHASE_MIN_CHECKED:-0}

log() { # <run-dir> <name> <round> <event>
  printf '%s\t%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$2" "$3" "$4" >>"$1/log.tsv"
}

# One agent: work, review, repeat by verdict. Runs as its own subshell; never exits the parent.
agent() { # <run-dir> <name> <agent-brief> <review-brief>
  local dir=$1/$2 name=$2 agent_brief=$3 review_brief=$4
  local work=$dir/work review=$dir/review round=0 prev="" verdict
  mkdir -p "$work" "$review" "$dir/rounds"
  cp "$agent_brief" "$dir/agent-brief.md"
  cp "$review_brief" "$dir/review-brief.md"

  fail() { echo "failed: $2" >"$dir/status"; log "$1" "$name" "$round" "failed: $2"; }

  while :; do
    round=$((round + 1))
    local rd=$dir/rounds/$round
    mkdir -p "$rd"

    # Agent
    echo "working round $round" >"$dir/status"
    log "$1" "$name" "$round" "agent start"
    {
      cat "$dir/agent-brief.md"
      printf '\n\n---\nWrite your result to %s in the current directory. Write nothing else.\n' "$outfile"
      if [ -n "$prev" ]; then
        printf '\nA reviewer sent your file back. %s already holds your previous round; fix it so the problems below are gone, keeping what was fine.\n\nProblems from the review:\n\n' "$outfile"
        cat "$prev"
      fi
    } >"$rd/agent-prompt.md"
    codex_run "$work" "$rd/agent-prompt.md" "$rd/agent"
    local code=$?
    if [ "$code" -ne 0 ]; then fail "$1" "agent exit=$code (see $rd/agent.stderr.log)"; return 1; fi
    if [ ! -s "$work/$outfile" ]; then fail "$1" "agent wrote no $outfile"; return 1; fi

    # Review: a snapshot copy, so the reviewer cannot change the agent's file
    echo "reviewing round $round" >"$dir/status"
    log "$1" "$name" "$round" "review start"
    cp "$work/$outfile" "$review/$outfile"
    rm -f "$review/previous-problems.md"
    [ -n "$prev" ] && cp "$prev" "$review/previous-problems.md"
    local attempt=0 checked=0
    while [ "$attempt" -lt 3 ]; do
      attempt=$((attempt + 1))
      rm -f "$review/problems.md"
      {
        cat "$dir/review-brief.md"
        printf '\n\n---\nThe file to review is %s in the current directory. Do not edit it.\n' "$outfile"
        if [ -n "$prev" ]; then
          printf 'The problems you listed in the previous round are in previous-problems.md.\n'
        else
          printf 'This is the first round; there is no previous list.\n'
        fi
        if [ "$min_checked" -gt 0 ]; then
          printf 'Begin problems.md with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems.\n'
        fi
        printf 'Write your list of problems to problems.md. Its last line must be exactly one of:\nVERDICT: pass\nVERDICT: back\nVERDICT: escalate\n'
        if [ "$attempt" -gt 1 ]; then
          printf 'Your previous attempt left no usable problems.md (missing, or without a "## What I checked" section). Write the file this time; the brief and the role guide hold everything you need.\n'
        fi
      } >"$rd/review-prompt.md"
      codex_run "$review" "$rd/review-prompt.md" "$rd/review"
      code=$?
      if [ "$code" -ne 0 ]; then fail "$1" "review exit=$code (see $rd/review.stderr.log)"; return 1; fi
      if [ ! -s "$review/problems.md" ]; then
        log "$1" "$name" "$round" "review attempt $attempt wrote no problems.md"
        continue
      fi
      if checked_ok "$review/problems.md"; then checked=1; break; fi
      log "$1" "$name" "$round" "review attempt $attempt has no usable 'What I checked' section"
    done
    if [ "$checked" -eq 0 ]; then fail "$1" "reviewer left no usable problems.md after $attempt attempts (see $rd/review.last-message.md)"; return 1; fi
    cp "$review/problems.md" "$rd/problems.md"
    if ! verdict=$(read_verdict "$rd/problems.md"); then
      fail "$1" "last line of $rd/problems.md is not a valid verdict"; return 1
    fi
    echo "$verdict" >"$rd/verdict"
    log "$1" "$name" "$round" "verdict $verdict"

    case "$verdict" in
      pass) echo passed >"$dir/status"; return 0 ;;
      escalate) echo escalated >"$dir/status"; return 2 ;;
      back)
        if [ "$max_rounds" -gt 0 ] && [ "$round" -ge "$max_rounds" ]; then
          echo escalated >"$dir/status"
          log "$1" "$name" "$round" "round cap $max_rounds reached"
          return 2
        fi
        prev=$rd/problems.md ;;
    esac
  done
}

cmd_start() {
  model=gpt-6-luna effort=xhigh outfile=output.md
  while getopts 'm:e:f:' opt; do
    case $opt in
      m) model=$OPTARG ;;
      e) effort=$OPTARG ;;
      f) outfile=$OPTARG ;;
      *) exit 1 ;;
    esac
  done
  shift $((OPTIND - 1))
  [ "$#" -ge 4 ] && [ $(( ($# - 1) % 3 )) -eq 0 ] || die 'usage: start [-m model] [-e effort] [-f file] <run> <name> <agent-brief> <review-brief> ...'

  local run=$1; shift
  local dir=$root/$run
  [ ! -e "$dir" ] || die "run already exists: $dir (clean it first)"
  command -v codex >/dev/null || die 'codex not found'

  # Validate all arguments before creating anything
  local args=("$@") i
  for ((i = 0; i < ${#args[@]}; i += 3)); do
    [[ ${args[i]} =~ ^[A-Za-z0-9._-]+$ ]] || die "bad agent name: ${args[i]}"
    [ -f "${args[i+1]}" ] || die "no such brief: ${args[i+1]}"
    [ -f "${args[i+2]}" ] || die "no such brief: ${args[i+2]}"
  done
  for ((i = 0; i < ${#args[@]}; i += 3)); do
    for ((j = i + 3; j < ${#args[@]}; j += 3)); do
      [ "${args[i]}" != "${args[j]}" ] || die "duplicate agent name: ${args[i]}"
    done
  done

  mkdir -p "$dir"
  [[ $outfile =~ ^[A-Za-z0-9._-]+$ ]] || die "bad output file name: $outfile"
  printf '%s\n' "$model $effort" >"$dir/settings"
  echo "$outfile" >"$dir/outfile"
  : >"$dir/names"
  local pids=()
  for ((i = 0; i < ${#args[@]}; i += 3)); do
    echo "${args[i]}" >>"$dir/names"
    ( agent "$dir" "${args[i]}" "${args[i+1]}" "${args[i+2]}" ) &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "$pid" || true; done

  printf 'Run folder: %s\n' "$dir"
  local n bad=0
  while read -r n; do
    printf '%s\t%s\n' "$n" "$(cat "$dir/$n/status")"
    [ "$(cat "$dir/$n/status")" = passed ] || bad=1
  done <"$dir/names"
  printf 'Log: %s/log.tsv\nProblems and verdicts per round: %s/<name>/rounds/<n>/\n' "$dir" "$dir"
  exit "$bad"
}

cmd_join() {
  [ "$#" -eq 1 ] || die 'usage: join <run>'
  local dir=$root/$1 n bad=0
  [ -f "$dir/names" ] || die "no such run: $dir"
  while read -r n; do
    if [ "$(cat "$dir/$n/status" 2>/dev/null)" != passed ]; then
      printf '%s is not passed: %s\n' "$n" "$(cat "$dir/$n/status" 2>/dev/null)" >&2
      bad=1
    fi
  done <"$dir/names"
  [ "$bad" -eq 0 ] || die 'not every agent passed; nothing joined'
  : >"$dir/joined.md"
  while read -r n; do
    printf '# %s\n\n' "$n" >>"$dir/joined.md"
    cat "$dir/$n/work/$(cat "$dir/outfile")" >>"$dir/joined.md"
    printf '\n\n' >>"$dir/joined.md"
  done <"$dir/names"
  echo "$dir/joined.md"
}

cmd_clean() {
  [ "$#" -eq 1 ] || die 'usage: clean <run>'
  [[ $1 =~ ^[A-Za-z0-9._-]+$ && $1 != . && $1 != .. ]] || die "bad run name: $1"
  local dir=$root/$1
  [ -f "$dir/names" ] || die "not a research run: $dir"
  rm -rf "$dir"
  echo "removed $dir"
}

sub=${1:-}
[ "$#" -gt 0 ] && shift
case "$sub" in
  start) cmd_start "$@" ;;
  join) cmd_join "$@" ;;
  clean) cmd_clean "$@" ;;
  *) die 'usage: phase-codex.sh start|join|clean ...' ;;
esac

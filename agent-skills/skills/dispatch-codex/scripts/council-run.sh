#!/usr/bin/env bash
# Run the middle of a council with Codex: five advisors apart, an anonymized packet, five reviewers apart,
# then the completeness check of the chairman's report. The coordinator writes the brief and the report.
# Usage:
#   council-run.sh start   [-m model] [-e effort] <name> <brief.md>
#   council-run.sh resume  [-m model] [-e effort] <name>
#   council-run.sh check   [-m model] [-e effort] <name> <report.md>   (exit 0 pass, 1 back, 2 escalate)
#   council-run.sh status  <name>
#   council-run.sh finish  [--discard] <name>
# Every agent works in its own folder and writes one file: the advisors get the brief and a perspective,
# the reviewers only the packet, and the key that maps labels to perspectives stays in 02-packet/, which no
# reviewer's folder holds. The sandbox confines writes, not reads, so the briefs tell each agent to open only
# its own folder; that part is an instruction, not a barrier. start stops at READY with the advice, the key and
# the reviews ready for the coordinator. A phase that stops (an agent failed or wrote nothing) is rerun by
# `resume`, which redoes only the agents without output.
# State lives in ${COUNCIL_RUNS_DIR:-$HOME/.council-runs}/<name>. It must not be under /tmp: the
# workspace-write sandbox leaves /tmp writable.
# Limits: COUNCIL_MAX_ROUNDS (default 3) escalates a check that keeps sending the report back;
# COUNCIL_MIN_CHECKED (default 3) is the least number of lines the check gives under "What I checked".
# COUNCIL_GUIDES points at the folder with the role guides.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
root=${COUNCIL_RUNS_DIR:-$HOME/.council-runs}
guides=${COUNCIL_GUIDES:-$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)/agent-skills/library/workflow-types/council}
max_rounds=${COUNCIL_MAX_ROUNDS:-3}
min_checked=${COUNCIL_MIN_CHECKED:-3}
model=gpt-6-luna effort=xhigh

# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"

note() { printf '%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$run/status.log"; }
progress() { printf '[council] %s\n' "$*" >&2; }

perspectives() { printf '%s\n' contrarian first-principles expansionist outsider executor; }
perspective_title() { # <name> -> the heading in council-advisor.md
  case $1 in
    contrarian) echo Contrarian ;;
    first-principles) echo 'First principles' ;;
    expansionist) echo Expansionist ;;
    outsider) echo Outsider ;;
    executor) echo Executor ;;
  esac
}

load_run() { # <name>
  valid_name "$1" || die "bad run name: $1"
  run=$root/$1
  [ -d "$run" ] || die "no such run: $run"
  if [ -f "$run/settings" ]; then read -r model effort <"$run/settings"; fi
}

brief_body() { sed '/^# /d' "$run/00-input/brief.md"; }   # the brief, without its title line

# ---- Briefs: fixed templates, so the coordinator never writes them by hand ----

advisor_brief() { # <perspective>
  printf '# Brief: advice\n\n## The question\n'
  brief_body
  printf '\n## Your perspective\n%s. Open and follow the role guide: %s/council-advisor.md (read-only), and read the section of your perspective in it. Four other advisors have the same question with other perspectives; you do not see their work.\n' "$(perspective_title "$1")" "$guides"
  printf '\n## Rules\n- Write your response to advice.md in the current directory, in the parts the guide gives. Write nothing else.\n- Do not name your perspective in the text.\n- Open only files in the current directory and what the guide points to. Other advisors work in sibling folders; do not look at them.\n- Do not run git commands that change state.\n'
}

reviewer_brief() {
  printf '# Brief: review of the responses\n\n## Input\nThe file packet.md in the current directory: the question and five responses under labels A to E (read-only).\n'
  printf '\n## Role\nOpen and follow the role guide: %s/council-reviewer.md (read-only). Do not try to find out who wrote which response.\n' "$guides"
  printf '\n## Rules\n- Write your review to review.md in the current directory. Write nothing else.\n- Open only files in the current directory and the role guide. Other files under the run folder, such as other reviews and the key, are not for you.\n- Do not run git commands that change state.\n'
}

# ---- Phases: each returns nonzero (with $reason) when it stops ----

# Run the agents that have no output yet, in parallel, and report each as it exits.
run_council_agents() { # <phase-dir> <output-file> <stage> <folder>...
  local pd=$1 out=$2 stage=$3 f label pids=() p code bad=""
  shift 3
  for f in "$@"; do
    [ -s "$pd/$f/$out" ] && continue
    label=$f
    case "$stage" in
      review) label="revisor $f" ;;
    esac
    (
      codex_run "$pd/$f" "$pd/$f/brief.md" "$pd/$f/run" workspace-write
      code=$?
      [ "$code" -eq 0 ] || echo "exit=$code (see $pd/$f/run.stderr.log)" >"$pd/$f/failed"
      progress "$stage · $label · concluído"
      exit "$code"
    ) &
    pids+=("$!")
  done
  for p in "${pids[@]+"${pids[@]}"}"; do wait "$p" || true; done
  for f in "$@"; do
    [ -s "$pd/$f/$out" ] || bad="$bad$f: $(cat "$pd/$f/failed" 2>/dev/null || echo "wrote no $out"); "
    rm -f "$pd/$f/failed"
  done
  [ -z "$bad" ] || { reason="$bad"; return 1; }
}

run_advisors() {
  local d=$run/01-advisors p
  for p in $(perspectives); do
    mkdir -p "$d/$p"
    [ -s "$d/$p/advice.md" ] || advisor_brief "$p" >"$d/$p/brief.md"
  done
  # shellcheck disable=SC2046
  run_council_agents "$d" advice.md advisors $(perspectives)
}

run_packet() {
  local d=$run/02-packet p i=0 label labels shuffled
  mkdir -p "$d"
  for p in $(perspectives); do
    [ -s "$run/01-advisors/$p/advice.md" ] || { reason="$p has no advice, so the packet is not made"; return 1; }
  done
  labels=(A B C D E)
  shuffled=$(perspectives | sort -R)
  : >"$d/key.md"
  {
    printf '# The question\n'
    brief_body
    printf '\n'
  } >"$d/packet.md"
  for p in $shuffled; do
    label=${labels[$i]}; i=$((i + 1))
    printf '%s: %s\n' "$label" "$p" >>"$d/key.md"
    printf '\n---\n\n# Response %s\n\n' "$label" >>"$d/packet.md"
    cat "$run/01-advisors/$p/advice.md" >>"$d/packet.md"
    printf '\n' >>"$d/packet.md"
    # A response that names its own perspective gives the reviewers a hint; say so, do not change it.
    if grep -qiE "$(printf '%s' "$p" | tr '-' ' ')|$p" "$run/01-advisors/$p/advice.md"; then
      note "packet: response $label may name its own perspective ($p); anonymization is weaker"
    fi
  done
}

run_review() {
  local d=$run/03-review n
  for n in 1 2 3 4 5; do
    mkdir -p "$d/$n"
    cp "$run/02-packet/packet.md" "$d/$n/packet.md"
    [ -s "$d/$n/review.md" ] || reviewer_brief >"$d/$n/brief.md"
  done
  run_council_agents "$d" review.md review 1 2 3 4 5
}

pipeline() {
  local st dir
  printf 'Run folder: %s\n' "$run"
  for st in advisors packet review; do
    [ -e "$run/.done-$st" ] && continue
    case $st in advisors) dir=01-advisors ;; packet) dir=02-packet ;; review) dir=03-review ;; esac
    note "start $st ($model $effort)"
    case $st in advisors|review) progress "$st · início" ;; esac
    reason=""
    if "run_$st"; then
      touch "$run/.done-$st"; note "done $st"
      progress "$st · concluído"
    else
      note "STOPPED at $st: $reason"
      note "Read $run/$dir, fix the cause, then: council-run.sh resume $(basename "$run")"
      progress "$st · parou"
      printf 'STOPPED at %s: %s\nSee %s/status.log\n' "$st" "$reason" "$run"
      return 1
    fi
  done
  note "READY: advice in $run/01-advisors, key in $run/02-packet/key.md, reviews in $run/03-review"
  printf 'READY\nAdvice: %s/01-advisors/<perspective>/advice.md\nKey: %s/02-packet/key.md\nReviews: %s/03-review/<n>/review.md\nSee %s/status.log\n' "$run" "$run" "$run" "$run"
}

# ---- Commands ----

cmd_start() {
  while getopts 'm:e:' o; do case $o in m) model=$OPTARG ;; e) effort=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 2 ] || die 'usage: start [-m model] [-e effort] <name> <brief.md>'
  valid_name "$1" || die "bad run name: $1"
  [ -s "$2" ] || die "missing or empty brief: $2"
  command -v codex >/dev/null || die 'codex not found'
  [ -d "$guides" ] || die "no role guides at $guides (set COUNCIL_GUIDES)"
  run=$root/$1
  [ ! -e "$run" ] || die "run already exists: $run (finish it, or resume it)"
  mkdir -p "$run/00-input"
  cp "$2" "$run/00-input/brief.md"
  printf '%s %s\n' "$model" "$effort" >"$run/settings"
  printf 'time\tevent\n' >"$run/status.log"
  note "start $1 ($model $effort)"
  pipeline
}

cmd_resume() {
  local fm="" fe=""
  while getopts 'm:e:' o; do case $o in m) fm=$OPTARG ;; e) fe=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 1 ] || die 'usage: resume [-m model] [-e effort] <name>'
  load_run "$1"
  [ -z "$fm" ] || model=$fm
  [ -z "$fe" ] || effort=$fe
  printf '%s %s\n' "$model" "$effort" >"$run/settings"
  note "resume"
  pipeline
}

cmd_check() {
  local fm="" fe=""
  while getopts 'm:e:' o; do case $o in m) fm=$OPTARG ;; e) fe=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 2 ] || die 'usage: check [-m model] [-e effort] <name> <report.md>'
  load_run "$1"
  [ -z "$fm" ] || model=$fm
  [ -z "$fe" ] || effort=$fe
  [ -s "$2" ] || die "missing or empty report: $2"
  [ -e "$run/.done-review" ] || die 'the council has not reached READY'
  command -v codex >/dev/null || die 'codex not found'
  local d=$run/04-check n rd attempt=0 ok=0 code verdict prev="" p k
  mkdir -p "$d/rounds"
  for n in $(ls "$d/rounds"); do [ -f "$d/rounds/$n/problems.md" ] || rm -rf "$d/rounds/$n"; done   # a round that never finished
  n=$(( $(ls "$d/rounds" | wc -l | tr -d ' ') + 1 ))
  rd=$d/rounds/$n; mkdir -p "$rd/review"
  cp "$2" "$run/report.md"
  cp "$run/report.md" "$rd/review/report.md"
  cp "$run/00-input/brief.md" "$rd/review/question.md"
  cp "$run/02-packet/key.md" "$rd/review/key.md"
  for p in $(perspectives); do cp "$run/01-advisors/$p/advice.md" "$rd/review/advice-$p.md"; done
  for k in 1 2 3 4 5; do cp "$run/03-review/$k/review.md" "$rd/review/review-$k.md"; done
  if [ "$n" -gt 1 ] && [ -f "$d/rounds/$((n - 1))/problems.md" ]; then
    prev=$d/rounds/$((n - 1))/problems.md
    cp "$prev" "$rd/review/previous-problems.md"
  fi
  {
    printf '# Brief: completeness check of the report\n\n## Inputs (read-only, in your working directory)\n- question.md: the question\n- advice-<perspective>.md: the five responses; key.md maps the labels the reviews use to perspectives\n- review-1.md to review-5.md: the five reviews\n- report.md: the chairman'"'"'s report to check\n'
    printf '\n## Role\nOpen and follow the role guide: %s/council-completeness.md (read-only). You are not the author of any of these files.\n' "$guides"
  } >"$rd/review-brief.md"
  while [ "$attempt" -lt 3 ]; do
    attempt=$((attempt + 1))
    rm -f "$rd/review/problems.md"
    {
      cat "$rd/review-brief.md"
      if [ -n "$prev" ]; then printf '\nThe cuts you listed in the previous round are in previous-problems.md; the report was corrected, check whether they are gone.\n'; fi
      printf '\n---\nBegin problems.md with a section headed "## What I checked": one line per response or review you went through and where you found it in the report. Then list what was left out or cut. Write it to problems.md. Its last line must be exactly one of:\nVERDICT: pass\nVERDICT: back\nVERDICT: escalate\nDo not edit any other file.\n'
      if [ "$attempt" -gt 1 ]; then printf 'Your previous attempt left no usable problems.md (missing, or without a "## What I checked" section). Write the file this time.\n'; fi
    } >"$rd/review-prompt.md"
    codex_run "$rd/review" "$rd/review-prompt.md" "$rd/review-run" workspace-write
    code=$?
    if [ "$code" -ne 0 ]; then progress 'check · parou'; die "check exit=$code (see $rd/review-run.stderr.log)"; fi
    if [ ! -s "$rd/review/problems.md" ]; then note "check attempt $attempt wrote no problems.md"; continue; fi
    if checked_ok "$rd/review/problems.md"; then ok=1; break; fi
  done
  if [ "$ok" -ne 1 ]; then progress 'check · parou'; die "the check left no usable problems.md after $attempt attempts (see $rd/review-run.last-message.md)"; fi
  cp "$rd/review/problems.md" "$rd/problems.md"
  if ! verdict=$(read_verdict "$rd/problems.md"); then progress 'check · parou'; die "last line of $rd/problems.md is not a valid verdict"; fi
  if [ "$verdict" = back ] && [ "$n" -ge "$max_rounds" ]; then verdict=escalate; note "check: round cap $max_rounds reached"; fi
  echo "$verdict" >"$rd/verdict"
  note "check round $n ($model $effort): $verdict"
  case $verdict in
    pass) progress "check · ronda $n · passou" ;;
    back) progress "check · ronda $n · devolvida" ;;
    escalate) progress "check · ronda $n · escalada" ;;
  esac
  printf 'Completeness check, round %s: %s\nProblems: %s/problems.md\n' "$n" "$verdict" "$rd"
  case $verdict in pass) exit 0 ;; back) exit 1 ;; *) exit 2 ;; esac
}

cmd_status() {
  [ "$#" -eq 1 ] || die 'usage: status <name>'
  load_run "$1"
  cat "$run/status.log"
}

cmd_finish() {
  local discard=0
  [ "${1:-}" = --discard ] && { discard=1; shift; }
  [ "$#" -eq 1 ] || die 'usage: finish [--discard] <name>'
  load_run "$1"
  if [ "$discard" -eq 1 ]; then
    rm -rf "$run"
    printf 'Removed %s\n' "$run"
    return 0
  fi
  [ -s "$run/report.md" ] || die 'there is no report in this run: nothing to keep'
  local repo dest
  repo=$(git rev-parse --show-toplevel 2>/dev/null) || die 'run finish inside the repository the council goes to'
  dest=$repo/records/councils/$1
  [ ! -e "$dest" ] || die "already exists: $dest"
  mkdir -p "$dest"
  # Keep the record (brief, briefs, advice, key, packet, reviews, checks, report); leave out the
  # script's own state and the raw Codex output.
  local skip=(--exclude '*.events.jsonl' --exclude '*.stderr.log' --exclude '*.last-message.md' \
    --exclude '.*' --exclude settings --exclude status.log)
  local dskip=(-x '*.events.jsonl' -x '*.stderr.log' -x '*.last-message.md' -x '.*' -x settings -x status.log)
  rsync -a "${skip[@]}" "$run/" "$dest/" || die "copy to $dest failed; nothing deleted"
  diff -rq "${dskip[@]}" "$run" "$dest" >/dev/null || die "copy to $dest does not match; nothing deleted"
  rm -rf "$run"
  printf 'Kept in %s; removed %s\n' "$dest" "$run"
  records_note "$repo"
}

sub=${1:-}
[ "$#" -gt 0 ] && shift
case "$sub" in
  start) cmd_start "$@" ;;
  resume) cmd_resume "$@" ;;
  check) cmd_check "$@" ;;
  status) cmd_status "$@" ;;
  finish) cmd_finish "$@" ;;
  *) die 'usage: council-run.sh start|resume|check|status|finish ...' ;;
esac

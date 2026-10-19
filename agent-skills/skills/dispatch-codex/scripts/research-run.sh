#!/usr/bin/env bash
# Run the unattended phases of a research with Codex: source map completion, collection and digest,
# every agent reviewed by another. The coordinator only writes the inputs and reads the result.
# Usage:
#   research-run.sh start   [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>
#   research-run.sh resume  [-m model] [-e effort] <name>
#   research-run.sh deliver [-m model] [-e effort] <name> <delivery.md>
#   research-run.sh status  <name>
#   research-run.sh finish  [--delivery-only] <name>
# sourcemap.md: one niche per line, numbered ("1. **Name.** where to look"). collectors.txt: one
# collector per line, "name: 1,2,5" (the niches it covers). Niches the map agent adds are shared out
# round-robin. State lives in ${RESEARCH_RUNS_DIR:-$HOME/.research-runs}/<name>, one folder per phase.
# It must not be under /tmp: the workspace-write sandbox leaves /tmp writable.
# finish leaves out the folders of failed or redone attempts unless --keep-attempts is given.
# Limits: RESEARCH_MAX_ROUNDS (default 3) escalates a review that keeps sending work back;
# RESEARCH_MIN_CHECKED (default 3) is the least number of lines a reviewer must give under
# "What I checked". RESEARCH_GUIDES points at the folder with the role guides.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
phase=$here/phase-codex.sh
root=${RESEARCH_RUNS_DIR:-$HOME/.research-runs}
guides=${RESEARCH_GUIDES:-$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)/agent-skills/library/workflow-types/research}
max_rounds=${RESEARCH_MAX_ROUNDS:-3}
min_checked=${RESEARCH_MIN_CHECKED:-3}
model=gpt-6-luna effort=xhigh

# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"

note() { printf '%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$run/status.log"; }

objective_body() { sed '/^# /d' "$1"; }              # the objective, without its title line
max_niche() { grep -Eo '^[0-9]+\.' "$1" | tr -d . | sort -n | tail -1; }
niche_lines() { # <comma-list> <sourcemap>
  awk -v nums=",$1," '/^[0-9]+\. / { split($0, p, "."); if (index(nums, "," p[1] ",")) print }' "$2"
}

load_run() { # <name>
  valid_name "$1" || die "bad run name: $1"
  run=$root/$1
  [ -d "$run" ] || die "no such run: $run"
  if [ -f "$run/settings" ]; then read -r model effort <"$run/settings"; fi
}

# ---- Briefs: fixed templates, so the coordinator never writes them by hand ----

brief_collector() { # <name> <niches-file>
  {
    printf '# Brief: collection (collector %s)\n\n## Objective\n' "$1"
    objective_body "$run/00-input/objective.md"
    printf '\n## Where to look\nThese are your niches. Another collector covers the rest, so stay inside these. "Counterweight" means look here for evidence against the common view; "(agent)" only says who suggested the niche and does not change what you do.\n\n'
    cat "$2"
    printf '\n## Role\nOpen and follow the role guide: %s/research-collection.md (read-only). It says how to collect, what to record and when to stop. The objective above is the filter for what is relevant.\n' "$guides"
    printf '\n## Rules\n- You need web access to open sources. If you cannot open web pages at all, stop and say so in your output; do not fill in from memory.\n- Do not run git commands that change state, and do not edit any file other than your output file.\n'
  }
}

review_collector() { # <name> <niches-file>
  {
    printf '# Brief: review of the collection (collector %s)\n\n## Objective\n' "$1"
    objective_body "$run/00-input/objective.md"
    printf '\n## Map of sources for the collector you review\nThese are the niches the collector was told to search. "(agent)" marks niches a cheap agent added to the map. "Counterweight" marks niches where evidence against the common view was to be sought.\n\n'
    cat "$2"
    printf '\n## Role\nOpen and follow the role guide: %s/research-review-collection.md (read-only). You are not the author of the collected file. Do not reopen the sources to check whether findings are true; check the four questions against the objective.\n' "$guides"
  }
}

brief_digest() {
  {
    printf '# Brief: digest\n\n## Objective\n'
    objective_body "$run/00-input/objective.md"
    printf '\n## Inputs (read-only)\n- The collected sources, joined in one file, one heading per collector: %s\n- The notes of the reviews of the collection: %s\n  They record limits the reviewers accepted; carry them into the weak points.\n' "$run/02-collection/joined.md" "$run/02-collection/review-notes.md"
    printf '\n## Role\nOpen and follow the role guide: %s/research-digest.md (read-only). You do not search for new sources.\n' "$guides"
  }
}

review_digest() {
  {
    printf '# Brief: review of the digest\n\n## Objective\n'
    objective_body "$run/00-input/objective.md"
    printf '\n## Inputs (read-only)\n- The collected sources, joined in one file: %s\n\n## Role\nOpen and follow the role guide: %s/research-review-digest.md (read-only). You are not the author of the digest. You do not search for new sources.\n' "$run/02-collection/joined.md" "$guides"
  }
}

# ---- Stages: each one writes its own folder and returns nonzero (with $reason) when it stops ----

run_map() {
  local d=$run/01-map sm=$run/00-input/sourcemap.md max
  mkdir -p "$d/work"
  max=$(max_niche "$sm")
  [ -n "$max" ] || { reason="sourcemap.md has no numbered niche lines"; return 1; }
  {
    printf '# Brief: complete the source map\n\n## Objective\n'
    objective_body "$run/00-input/objective.md"
    printf '\n## Input\nThe list so far (read-only): %s\n' "$sm"
    printf '\n## Task\nComplete the list with more niches and example sites where the objective'"'"'s question can be answered, without collecting findings. Bring counterweight: independent voices, critics, people who use the thing, issue trackers, since the list leans toward those who speak for themselves. Limit additions to what serves the priorities in the objective, or the list grows without end. Judge a source by the question it answers, not by type of site; leave out copies and derived content and point to origins. Do a few web searches only to check that a niche exists; do not read pages in depth.\n'
    printf '\n---\nWrite only the new niches to additions.md in the current directory, one niche per line, numbered continuing from %s, in the style of the list: a bold name, example sites, why it serves the objective, "Counterweight." where it applies, and ending with "(agent)". No other text, no headings.\n' "$((max + 1))"
  } >"$d/prompt.md"
  codex_run "$d/work" "$d/prompt.md" "$d/run"
  local code=$?
  [ "$code" -eq 0 ] || { reason="map agent exit=$code (see $d/run.stderr.log)"; return 1; }
  [ -s "$d/work/additions.md" ] || { reason="map agent wrote no additions.md"; return 1; }
  local bad
  bad=$(grep -Eo '^[0-9]+\.' "$d/work/additions.md" | tr -d . | awk -v m="$max" '$1 <= m')
  [ -z "$bad" ] || { reason="additions.md reuses niche numbers up to $max"; return 1; }
  grep -Eq '^[0-9]+\. ' "$d/work/additions.md" || { reason="additions.md has no numbered niche lines"; return 1; }
  { cat "$sm"; printf '\n'; grep -E '^[0-9]+\. ' "$d/work/additions.md"; } >"$d/sourcemap.md"
  note "map: $(grep -cE '^[0-9]+\. ' "$d/work/additions.md") niche(s) added by the agent"
}

run_collection() {
  local sm=$run/01-map/sourcemap.md orig_max b=$run/.briefs/collection
  orig_max=$(max_niche "$run/00-input/sourcemap.md")
  rm -rf "$b"; mkdir -p "$b"
  local names=() lists=() line n l k found i idx
  while IFS= read -r line || [ -n "$line" ]; do
    case $line in ''|'#'*) continue ;; esac
    n=$(printf '%s' "${line%%:*}" | tr -d ' '); l=$(printf '%s' "${line#*:}" | tr -d ' ')
    valid_name "$n" || { reason="bad collector name in collectors.txt: $n"; return 1; }
    [[ $l =~ ^[0-9]+(,[0-9]+)*$ ]] || { reason="bad niche list for $n in collectors.txt: $l"; return 1; }
    names+=("$n"); lists+=("$l")
  done <"$run/00-input/collectors.txt"
  [ "${#names[@]}" -gt 0 ] || { reason="collectors.txt has no collector"; return 1; }
  for k in $(grep -Eo '^[0-9]+\.' "$run/00-input/sourcemap.md" | tr -d .); do
    found=0
    for l in "${lists[@]}"; do case ",$l," in *",$k,"*) found=1 ;; esac; done
    [ "$found" -eq 1 ] || { reason="niche $k is not assigned to any collector"; return 1; }
  done
  i=0
  for k in $(grep -Eo '^[0-9]+\.' "$sm" | tr -d . | awk -v m="$orig_max" '$1 > m' | sort -n); do
    idx=$((i % ${#names[@]})); lists[$idx]="${lists[$idx]},$k"; i=$((i + 1))
  done
  local args=()
  for i in "${!names[@]}"; do
    niche_lines "${lists[$i]}" "$sm" >"$b/niches-${names[$i]}.md"
    brief_collector "${names[$i]}" "$b/niches-${names[$i]}.md" >"$b/brief-${names[$i]}.md"
    review_collector "${names[$i]}" "$b/niches-${names[$i]}.md" >"$b/review-${names[$i]}.md"
    args+=("${names[$i]}" "$b/brief-${names[$i]}.md" "$b/review-${names[$i]}.md")
  done
  PHASE_RUNS_DIR=$run PHASE_MAX_ROUNDS=$max_rounds PHASE_MIN_CHECKED=$min_checked \
    "$phase" start -m "$model" -e "$effort" -f sources.md 02-collection "${args[@]}" >"$b/phase.out" 2>&1
  local rc=$?
  phase_summary 02-collection
  [ "$rc" -eq 0 ] || { reason="collection did not pass for every collector: $summary"; return 1; }
  PHASE_RUNS_DIR=$run "$phase" join 02-collection >/dev/null || { reason="join failed"; return 1; }
  : >"$run/02-collection/review-notes.md"
  for n in "${names[@]}"; do
    for k in $(ls "$run/02-collection/$n/rounds" | sort -n); do
      printf '# Review of %s, round %s\n\n' "$n" "$k" >>"$run/02-collection/review-notes.md"
      cat "$run/02-collection/$n/rounds/$k/problems.md" >>"$run/02-collection/review-notes.md"
      printf '\n\n' >>"$run/02-collection/review-notes.md"
    done
  done
}

run_digest() {
  local b=$run/.briefs/digest
  rm -rf "$b"; mkdir -p "$b"
  brief_digest >"$b/brief.md"
  review_digest >"$b/review.md"
  PHASE_RUNS_DIR=$run PHASE_MAX_ROUNDS=$max_rounds PHASE_MIN_CHECKED=$min_checked \
    "$phase" start -m "$model" -e "$effort" -f digest.md 03-digest digest "$b/brief.md" "$b/review.md" >"$b/phase.out" 2>&1
  local rc=$?
  phase_summary 03-digest
  [ "$rc" -eq 0 ] || { reason="digest did not pass: $summary"; return 1; }
  cp "$run/03-digest/digest/work/digest.md" "$run/03-digest/digest.md"
}

# One line per agent: its status and how many rounds it took; also written to status.log.
phase_summary() { # <phase-folder>
  local d=$run/$1 n
  summary=""
  [ -f "$d/names" ] || return 0
  while read -r n; do
    summary="$summary$n=$(cat "$d/$n/status" 2>/dev/null) ($(ls "$d/$n/rounds" 2>/dev/null | wc -l | tr -d ' ') round(s)); "
  done <"$d/names"
  note "$1: $summary"
}

archive_stage() { # <folder>
  [ -e "$run/$1" ] && mv "$run/$1" "$run/$1.attempt-$(date +%s)"
  return 0
}

pipeline() {
  local st dir
  printf 'Run folder: %s\n' "$run"
  for st in map collection digest; do
    [ -e "$run/.done-$st" ] && continue
    case $st in map) dir=01-map ;; collection) dir=02-collection ;; digest) dir=03-digest ;; esac
    archive_stage "$dir"
    note "start $st ($model $effort)"
    reason=""
    if "run_$st"; then
      touch "$run/.done-$st"; note "done $st"
    else
      note "STOPPED at $st: $reason"
      note "Read the rounds in $run/$dir, fix the cause (objective, map or briefs), then: research-run.sh resume $(basename "$run")"
      printf 'STOPPED at %s: %s\nSee %s/status.log\n' "$st" "$reason" "$run"
      return 1
    fi
  done
  note "READY: digest at $run/03-digest/digest.md"
  printf 'READY: %s/03-digest/digest.md\nSee %s/status.log\n' "$run" "$run"
}

# ---- Commands ----

cmd_start() {
  while getopts 'm:e:' o; do case $o in m) model=$OPTARG ;; e) effort=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 4 ] || die 'usage: start [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>'
  valid_name "$1" || die "bad run name: $1"
  local f
  for f in "$2" "$3" "$4"; do [ -s "$f" ] || die "missing or empty input: $f"; done
  command -v codex >/dev/null || die 'codex not found'
  run=$root/$1
  [ ! -e "$run" ] || die "run already exists: $run (finish it, or resume it)"
  mkdir -p "$run/00-input"
  cp "$2" "$run/00-input/objective.md"; cp "$3" "$run/00-input/sourcemap.md"; cp "$4" "$run/00-input/collectors.txt"
  printf '%s %s\n' "$model" "$effort" >"$run/settings"
  printf 'time\tevent\n' >"$run/status.log"
  note "start $1 ($model $effort, max $max_rounds rounds)"
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

cmd_deliver() {
  local fm="" fe=""
  while getopts 'm:e:' o; do case $o in m) fm=$OPTARG ;; e) fe=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 2 ] || die 'usage: deliver [-m model] [-e effort] <name> <delivery.md>'
  load_run "$1"
  [ -z "$fm" ] || model=$fm
  [ -z "$fe" ] || effort=$fe
  [ -s "$2" ] || die "missing or empty delivery: $2"
  [ -s "$run/03-digest/digest.md" ] || die 'there is no digest yet: the run has not reached READY'
  command -v codex >/dev/null || die 'codex not found'
  local d=$run/04-delivery-review n rd attempt=0 ok=0 code verdict prev=""
  mkdir -p "$d/rounds"
  for n in $(ls "$d/rounds"); do [ -f "$d/rounds/$n/problems.md" ] || rm -rf "$d/rounds/$n"; done   # a round that never finished
  n=$(( $(ls "$d/rounds" | wc -l | tr -d ' ') + 1 ))
  rd=$d/rounds/$n; mkdir -p "$rd/review"
  cp "$2" "$run/delivery.md"
  cp "$run/delivery.md" "$rd/review/delivery.md"
  cp "$run/03-digest/digest.md" "$rd/review/digest.md"
  if [ "$n" -gt 1 ] && [ -f "$d/rounds/$((n - 1))/problems.md" ]; then
    prev=$d/rounds/$((n - 1))/problems.md
    cp "$prev" "$rd/review/previous-problems.md"
  fi
  {
    printf '# Brief: review of the delivery\n\n## Objective\n'
    objective_body "$run/00-input/objective.md"
    printf '\n## Inputs (read-only, in your working directory)\n- digest.md: the digest the delivery was written from\n- delivery.md: the delivery to review\n'
    printf '\n## Role\nOpen and follow the role guide: %s/research-review-delivery.md (read-only). You are not the author of either file. Do not reopen the sources.\n' "$guides"
  } >"$rd/review-brief.md"
  while [ "$attempt" -lt 3 ]; do
    attempt=$((attempt + 1))
    rm -f "$rd/review/problems.md"
    {
      cat "$rd/review-brief.md"
      if [ -n "$prev" ]; then printf '\nThe cuts you listed in the previous round are in previous-problems.md; the delivery was corrected, check whether they are gone.\n'; fi
      printf '\n---\nBegin problems.md with a section headed "## What I checked": one line per part of the digest you went through and where you found it in the delivery. Then list what was left out or cut. Write it to problems.md. Its last line must be exactly one of:\nVERDICT: pass\nVERDICT: back\nVERDICT: escalate\nDo not edit any other file.\n'
      if [ "$attempt" -gt 1 ]; then printf 'Your previous attempt left no usable problems.md (missing, or without a "## What I checked" section). Write the file this time.\n'; fi
    } >"$rd/review-prompt.md"
    codex_run "$rd/review" "$rd/review-prompt.md" "$rd/review-run"
    code=$?
    [ "$code" -eq 0 ] || die "review exit=$code (see $rd/review-run.stderr.log)"
    if [ ! -s "$rd/review/problems.md" ]; then note "delivery review attempt $attempt wrote no problems.md"; continue; fi
    if checked_ok "$rd/review/problems.md"; then ok=1; break; fi
  done
  [ "$ok" -eq 1 ] || die "reviewer left no usable problems.md after $attempt attempts (see $rd/review-run.last-message.md)"
  cp "$rd/review/problems.md" "$rd/problems.md"
  verdict=$(read_verdict "$rd/problems.md") || die "last line of $rd/problems.md is not a valid verdict"
  if [ "$verdict" = back ] && [ "$n" -ge "$max_rounds" ]; then verdict=escalate; note "delivery review: round cap $max_rounds reached"; fi
  echo "$verdict" >"$rd/verdict"
  note "delivery review round $n ($model $effort): $verdict"
  printf 'Review of the delivery, round %s: %s\nProblems: %s/problems.md\n' "$n" "$verdict" "$rd"
  case $verdict in pass) exit 0 ;; back) exit 1 ;; *) exit 2 ;; esac
}

cmd_status() {
  [ "$#" -eq 1 ] || die 'usage: status <name>'
  load_run "$1"
  cat "$run/status.log"
}

# The run's history as a readable summary, without paths: what each phase did, with what, and what went wrong.
write_summary() {
  local log=$run/status.log out=$run/status.md st dir me rounds notes n add cnt last verdict tab
  tab=$(printf '\t')
  {
    printf '# Run summary\n\nRun: %s\n\n' "$(basename "$run")"
    printf '| Phase | Model and effort | Result | Rounds | Notes |\n|---|---|---|---|---|\n'
    for st in map collection digest; do
      case $st in map) dir=01-map ;; collection) dir=02-collection ;; digest) dir=03-digest ;; esac
      me=$(awk -F'\t' -v s="start $st (" 'index($2, s) == 1 { l = $2 } END { print l }' "$log" | sed -E 's/^[^(]*\(//; s/\)$//')
      rounds="-"
      if [ -f "$run/$dir/names" ]; then
        rounds=""
        while read -r n; do rounds="$rounds$n: $(ls "$run/$dir/$n/rounds" 2>/dev/null | wc -l | tr -d ' '), "; done <"$run/$dir/names"
        rounds=${rounds%, }
      fi
      notes=$(awk -F'\t' -v s="STOPPED at $st: " 'index($2, s) == 1 { r = substr($2, length(s) + 1); sub(/ *\(see [^)]*\)/, "", r); sub(/[ ;]+$/, "", r); k++; o = o (o ? "; " : "") "attempt " k " stopped: " r } END { print o }' "$log")
      if [ "$st" = map ]; then
        add=$(awk -F'\t' 'index($2, "map: ") == 1 { l = substr($2, 6) } END { print l }' "$log")
        notes="$add${notes:+; $notes}"
      elif [ -f "$run/$dir/log.tsv" ]; then
        cnt=$(grep -c 'review attempt' "$run/$dir/log.tsv")
        [ "$cnt" -eq 0 ] || notes="${notes:+$notes; }reviewer retried $cnt time(s)"
      fi
      printf '| %s | %s | done | %s | %s |\n' "$dir" "$me" "$rounds" "$notes"
    done
    cnt=$(grep -c "${tab}delivery review round" "$log")
    if [ "$cnt" -gt 0 ]; then
      last=$(grep "${tab}delivery review round" "$log" | tail -1 | cut -f2)
      verdict=${last##*: }
      me=$(printf '%s' "$last" | sed -E 's/^[^(]*\(([^)]*)\).*/\1/')
      notes=$(awk -F'\t' 'index($2, "delivery review round ") == 1 { split($2, a, ": "); v = a[2]; r = $2; sub(/^delivery review round /, "", r); sub(/ .*/, "", r); rounds[++k] = r ": " v } END { for (i = 1; i < k; i++) o = o (o ? "; " : "") "round " rounds[i]; print o }' "$log")
      cnt=$(grep -c 'delivery review attempt' "$log")
      [ "$cnt" -eq 0 ] || notes="${notes:+$notes; }reviewer retried $cnt time(s)"
      printf '| delivery review | %s | %s | %s | %s |\n' "$me" "$verdict" "$(grep -c "${tab}delivery review round" "$log")" "$notes"
    fi
  } >"$out"
}

cmd_finish() {
  local only=0 keep=0
  while [ "${1:-}" = --delivery-only ] || [ "${1:-}" = --keep-attempts ]; do
    case $1 in --delivery-only) only=1 ;; --keep-attempts) keep=1 ;; esac
    shift
  done
  [ "$#" -eq 1 ] || die 'usage: finish [--delivery-only] [--keep-attempts] <name>'
  load_run "$1"
  [ -s "$run/delivery.md" ] || die 'there is no delivery in this run: nothing to keep'
  local repo dest
  repo=$(git rev-parse --show-toplevel 2>/dev/null) || die 'run finish inside the repository the research goes to'
  dest=$repo/records/research/$1
  [ ! -e "$dest" ] || die "already exists: $dest"
  mkdir -p "$dest"
  write_summary
  if [ "$only" -eq 1 ]; then
    cp "$run/delivery.md" "$dest/delivery.md"
    cmp -s "$run/delivery.md" "$dest/delivery.md" || die "copy to $dest does not match; nothing deleted"
  else
    # Keep the record (inputs, outputs, briefs, prompts, problems, verdicts, logs); leave out the
    # script's own state and the raw Codex output.
    local skip=(--exclude '*.events.jsonl' --exclude '*.stderr.log' --exclude '*.last-message.md' \
      --exclude review --exclude .briefs --exclude '.done-*' \
      --exclude names --exclude outfile --exclude settings --exclude status --exclude status.log)
    local dskip=(-x '*.events.jsonl' -x '*.stderr.log' -x '*.last-message.md' -x review -x .briefs -x '.done-*' \
      -x names -x outfile -x settings -x status -x status.log)
    if [ "$keep" -eq 0 ]; then skip+=(--exclude '*.attempt-*'); dskip+=(-x '*.attempt-*'); fi   # failed or redone phases
    rsync -a "${skip[@]}" "$run/" "$dest/" || die "copy to $dest failed; nothing deleted"
    diff -rq "${dskip[@]}" "$run" "$dest" >/dev/null || die "copy to $dest does not match; nothing deleted"
  fi
  rm -rf "$run"
  printf 'Kept in %s; removed %s\n' "$dest" "$run"
  records_note "$repo"
}

sub=${1:-}
[ "$#" -gt 0 ] && shift
case "$sub" in
  start) cmd_start "$@" ;;
  resume) cmd_resume "$@" ;;
  deliver) cmd_deliver "$@" ;;
  status) cmd_status "$@" ;;
  finish) cmd_finish "$@" ;;
  *) die 'usage: research-run.sh start|resume|deliver|status|finish ...' ;;
esac

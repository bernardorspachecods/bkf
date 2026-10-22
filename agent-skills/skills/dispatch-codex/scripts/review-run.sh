#!/usr/bin/env bash
# Run a two-axis code review with Codex: a Standards agent and a Spec agent review a pinned diff apart,
# a checker per axis confirms each finding, and the script writes the report. The coordinator names the
# target and the criteria and adds the one-line summary.
# Usage (run start, resume and finish inside the repository under review):
#   review-run.sh start   [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... [-g command]... <name> <target>
#   review-run.sh resume  [-m model] [-e effort] <name>
#   review-run.sh status  <name>
#   review-run.sh board   <name>
#   review-run.sh finish  [--discard] <name>
# target: `working-tree` (tracked changes against HEAD plus new files), or a git revision range such as
# `main...feature` (three dots, so the comparison is against the merge-base), passed to git diff as it is.
# -s gives the spec and each -d a file of documented coding standards. An axis with no criteria is not
# run and the report says so; with neither, there is nothing to review. -2 adds a second independent
# reviewer per axis, with the findings merged before the check.
# Each -g gives a command that verifies the change (tests, type check, lint). The script runs them itself, in
# the repository and outside any agent, before the agents start, and records command, output and exit code in
# gate.md, which the agents receive and the report shows. A red command does not stop the review but
# stands in the report. With no -g the report says the repository's checks were not run: a gap, not a pass.
# REVIEW_GATE_TIMEOUT (default 900 seconds) limits each command; a command that hits it is red. A run on a
# revision range runs the commands in the current checkout, which may not be the target; the file says so.
# Every agent works in its own folder and writes one file. The sandbox confines writes, not reads, so the
# briefs tell each agent to open only its own folder and the repository; that is an instruction, not a
# barrier. `resume` redoes only the agents without output.
# State lives in ${REVIEW_RUNS_DIR:-$HOME/.review-runs}/<name>. It must not be under /tmp: the
# workspace-write sandbox leaves /tmp writable. REVIEW_GUIDES points at the folder with the role guides.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
root=${REVIEW_RUNS_DIR:-$HOME/.review-runs}
guides=${REVIEW_GUIDES:-$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)/agent-skills/library/workflow-types/code-review}
min_checked=0
gate_timeout=${REVIEW_GATE_TIMEOUT:-900}
model=gpt-6-luna effort=xhigh

# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"

note() { printf '%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$run/status.log"; }
progress() {
  local current_board
  current_board=$(board 2>/dev/null) || current_board=
  printf '[review] %s\n\n%s\n' "$*" "$current_board" >&2 || true
  return 0
}

load_run() { # <name>
  valid_name "$1" || die "bad run name: $1"
  run=$root/$1
  [ -d "$run" ] || die "no such run: $run"
  repo=$(cat "$run/repo")
  if [ -f "$run/settings" ]; then read -r model effort <"$run/settings"; fi
  second=$(cat "$run/second" 2>/dev/null || echo 0)
}

# The axes that have criteria, in report order.
axes() {
  [ -d "$run/00-input/standards" ] && echo standards
  [ -s "$run/00-input/spec.md" ] && echo spec
  return 0
}
axis_title() { case $1 in standards) echo Standards ;; spec) echo Spec ;; esac; }

board() { # print the review and check steps with their axis agents
  local a review_agents="" check_agents=""
  for a in $(axes); do
    review_agents="${review_agents:+$review_agents }$a"
    [ "$second" -eq 1 ] && review_agents="$review_agents $a-2"
    check_agents="${check_agents:+$check_agents }$a"
  done
  (
    board_title=Revisão
    board_steps \
      "review|Revisores|01-review|$review_agents|report.md" \
      "check|Verificação|02-check|$check_agents|checked.md" 2>/dev/null
  ) || true
  return 0
}

# ---- Briefs: fixed templates, so the coordinator never writes them by hand ----

axis_brief() { # <axis>
  local a=$1
  printf '# Brief: %s review\n\n## What to review\nThe diff is `diff.patch` in the current directory (read-only)' "$(axis_title "$a")"
  [ -s "$run/00-input/commits.txt" ] && printf ', and the commits in `commits.txt`'
  printf '.\n'
  printf '\n## Gate\nThe script ran the repository'"'"'s own checks before you started: their commands, output and exit codes are in `gate.md` here (read-only). Take them as given.\n'
  case $a in
    standards) printf '\n## Criteria\nThe documented standards are the files in `standards/` here (read-only).\n' ;;
    spec) printf '\n## Criteria\nThe originating spec is `spec.md` here (read-only).\n' ;;
  esac
  printf '\n## The repository\nIt is at %s. Open it read-only to see the code around the diff. Change nothing in it.\n' "$repo"
  printf '\n## Role\nOpen and follow the role guide: %s/code-review-axis.md (read-only), the section "%s". You are not the author of the change.\n' "$guides" "$(axis_title "$a")"
  printf '\n## Rules\n- Write your report to report.md in the current directory. Write nothing else.\n- Open only files in the current directory, the repository and the role guide. Other folders under the run folder are not for you.\n- Do not run git commands that change state.\n'
}

check_brief() { # <axis>
  local a=$1
  printf '# Brief: check of the %s findings\n\n## Inputs (read-only, in the current directory)\n- diff.patch: the diff under review\n' "$(axis_title "$a")"
  case $a in
    standards) printf -- '- standards/: the documented standards\n' ;;
    spec) printf -- '- spec.md: the originating spec\n' ;;
  esac
  printf -- '- gate.md: the repository'"'"'s own checks, run by the script before the review\n'
  printf -- '- reports/: the findings of the reviewer(s) of this axis\n'
  printf '\n## The repository\nIt is at %s. Open it read-only to see the code around a hunk. Change nothing in it.\n' "$repo"
  printf '\n## Role\nOpen and follow the role guide: %s/code-review-check.md (read-only). You are not the author of the findings.\n' "$guides"
  printf '\n## Rules\n- Write your result to checked.md in the current directory. Write nothing else.\n- Open only files in the current directory, the repository and the role guide.\n- Do not run git commands that change state.\n'
}

# ---- Gate: the script runs the repository's checks itself, so no agent's reading stands in for them ----

# Run one command with a time limit, in its own process group so a timeout also stops its children.
# Prints nothing; the exit code is the command's, or 124 when the limit was hit.
run_limited() { # <seconds> <command>
  perl -e 'setpgrp(0,0); $SIG{ALRM}=sub{ $SIG{TERM}="IGNORE"; kill("TERM",-$$); exit 124 }; alarm shift;
    my $p=fork; if(!$p){ exec @ARGV or exit 127 } waitpid($p,0); exit($? >> 8)' "$1" bash -c "$2"
}

run_gates() { # <command>...   writes $run/00-input/gate.md
  local out=$run/00-input/gate.md n=$# red=0 c code tmp head target
  target=$(cat "$run/00-input/target")
  head=$(git -C "$repo" rev-parse --short HEAD 2>/dev/null || echo unknown)
  tmp=$(mktemp)
  for c in "$@"; do
    local log; log=$(mktemp)
    (cd "$repo" && run_limited "$gate_timeout" "$c") >"$log" 2>&1
    code=$?
    {
      printf '### `%s`\n\n' "$c"
      if [ "$code" -eq 124 ]; then printf 'exit code: 124 (timed out after %s seconds)\n\n' "$gate_timeout"; else printf 'exit code: %s\n\n' "$code"; fi
      printf '~~~~\n'; tail -n 100 "$log"; printf '~~~~\n\n'
    } >>"$tmp"
    [ "$code" -eq 0 ] || red=$((red + 1))
    rm -f "$log"
  done
  {
    printf '# Gate\n\n'
    if [ "$n" -eq 0 ]; then
      printf 'No gate commands were given (-g), so the repository'"'"'s checks were not run. This is a gap, not a pass.\n'
    else
      printf 'The script ran these commands in %s (HEAD %s) before any agent started, outside the agents.\n' "$repo" "$head"
      [ "$target" = working-tree ] || printf 'The target is a revision range, so the commands ran in the current checkout, which may not be the target.\n'
      if [ "$red" -eq 0 ]; then printf '\nResult: all green (%s commands).\n\n' "$n"; else printf '\nResult: RED, %s of %s commands failed. A reviewer cannot override a red result.\n\n' "$red" "$n"; fi
      cat "$tmp"
    fi
  } >"$out"
  rm -f "$tmp"
}

# ---- Phases: each returns nonzero (with $reason) when it stops ----

run_review_axis() { # <phase-dir> <axis> <second-reviewer> [<reason-file>]
  local d=$1 a=$2 second_axis=$3 reason_file=${4:-}
  local names=("$a")
  [ "$second_axis" -eq 1 ] && names+=("$a-2")
  if run_agents "$d" report.md "${names[@]}"; then
    progress "review · $a · concluído"
    return 0
  fi
  [ -z "$reason_file" ] || printf '%s\n' "$reason" >"$reason_file"
  return 1
}

run_review() {
  local d=$run/01-review a f tmp p1 p2 code bad=""
  local axis_list=()
  for a in $(axes); do
    axis_list+=("$a")
    for f in "$a" $([ "$second" -eq 1 ] && echo "$a-2"); do
      mkdir -p "$d/$f"
      cp "$run/00-input/diff.patch" "$d/$f/diff.patch"
      cp "$run/00-input/gate.md" "$d/$f/gate.md"
      [ -s "$run/00-input/commits.txt" ] && cp "$run/00-input/commits.txt" "$d/$f/commits.txt"
      case $a in
        standards) rm -rf "$d/$f/standards"; cp -R "$run/00-input/standards" "$d/$f/standards" ;;
        spec) cp "$run/00-input/spec.md" "$d/$f/spec.md" ;;
      esac
      [ -s "$d/$f/report.md" ] || axis_brief "$a" >"$d/$f/brief.md"
    done
  done
  [ "${#axis_list[@]}" -gt 0 ] || return 0
  if [ "${#axis_list[@]}" -eq 2 ]; then
    tmp=$run/.axis-reasons
    mkdir -p "$tmp" || { reason="could not create a temporary directory for review progress"; return 1; }
    run_review_axis "$d" standards "$second" "$tmp/standards.reason" &
    p1=$!
    run_review_axis "$d" spec "$second" "$tmp/spec.reason" &
    p2=$!
    wait "$p1"; code=$?
    [ "$code" -eq 0 ] || bad="$(cat "$tmp/standards.reason" 2>/dev/null)"
    wait "$p2"; code=$?
    [ "$code" -eq 0 ] || bad="$bad$(cat "$tmp/spec.reason" 2>/dev/null)"
    rm -rf "$tmp"
    [ -z "$bad" ] || { reason="$bad"; return 1; }
    return 0
  fi
  run_review_axis "$d" "${axis_list[0]}" "$second"
}

run_check() {
  local d=$run/02-check a r
  for a in $(axes); do
    mkdir -p "$d/$a/reports"
    cp "$run/00-input/diff.patch" "$d/$a/diff.patch"
    cp "$run/00-input/gate.md" "$d/$a/gate.md"
    case $a in
      standards) rm -rf "$d/$a/standards"; cp -R "$run/00-input/standards" "$d/$a/standards" ;;
      spec) cp "$run/00-input/spec.md" "$d/$a/spec.md" ;;
    esac
    cp "$run/01-review/$a/report.md" "$d/$a/reports/reviewer-1.md"
    if [ "$second" -eq 1 ]; then cp "$run/01-review/$a-2/report.md" "$d/$a/reports/reviewer-2.md"; fi
    [ -s "$d/$a/checked.md" ] || check_brief "$a" >"$d/$a/brief.md"
  done
  # shellcheck disable=SC2046
  run_agents "$d" checked.md $(axes)
}

write_report() {
  local a
  {
    printf '# Code review\n\nTarget: %s\n\n' "$(cat "$run/00-input/target")"
    printf '> The checkers confirm the findings below against the diff. They do not show what the reviewers missed: a clean axis is not a clean diff.\n\n'
    printf '## Gate\n\n'
    sed -e '1,2d' -e 's/^### /#### /' "$run/00-input/gate.md"
    printf '\n'
    for a in standards spec; do
      printf '## %s\n\n' "$(axis_title "$a")"
      if [ -s "$run/02-check/$a/checked.md" ]; then
        cat "$run/02-check/$a/checked.md"
      elif [ "$a" = standards ]; then
        printf 'Not run: no standards sources were given.\n'
      else
        printf 'Not run: no spec available.\n'
      fi
      printf '\n'
    done
  } >"$run/report.md"
}

pipeline() {
  local st
  printf 'Run folder: %s\n' "$run"
  for st in review check; do
    [ -e "$run/.done-$st" ] && continue
    note "start $st ($model $effort)"
    progress "$st · início"
    reason=""
    if "run_$st"; then
      touch "$run/.done-$st"; note "done $st"
      if [ "$st" = check ]; then
        progress 'check · ronda 1 · passou'
      fi
      progress "$st · concluído"
    else
      note "STOPPED at $st: $reason"
      note "Read $run/*$st*, fix the cause, then: review-run.sh resume $(basename "$run")"
      progress "$st · parou"
      printf 'STOPPED at %s: %s\nSee %s/status.log\n' "$st" "$reason" "$run"
      return 1
    fi
  done
  write_report
  note "READY: report at $run/report.md"
  printf 'READY: %s/report.md\nSee %s/status.log\n' "$run" "$run"
}

# ---- Commands ----

cmd_start() {
  local spec="" stds=() second=0 gates=()
  while getopts 'm:e:2s:d:g:' o; do
    case $o in m) model=$OPTARG ;; e) effort=$OPTARG ;; 2) second=1 ;; s) spec=$OPTARG ;; d) stds+=("$OPTARG") ;; g) gates+=("$OPTARG") ;; *) exit 1 ;; esac
  done
  shift $((OPTIND - 1))
  [ "$#" -eq 2 ] || die 'usage: start [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... [-g command]... <name> <target>'
  valid_name "$1" || die "bad run name: $1"
  local name=$1 target=$2 f
  [ -z "$spec" ] || [ -s "$spec" ] || die "missing or empty spec: $spec"
  for f in "${stds[@]+"${stds[@]}"}"; do [ -s "$f" ] || die "missing or empty standards file: $f"; done
  [ -n "$spec" ] || [ "${#stds[@]}" -gt 0 ] || die 'no criteria: give a spec (-s), standards (-d), or both'
  command -v codex >/dev/null || die 'codex not found'
  repo=$(git rev-parse --show-toplevel 2>/dev/null) || die 'run start inside the repository under review'
  [ -d "$guides" ] || die "no role guides at $guides (set REVIEW_GUIDES)"
  run=$root/$name
  [ ! -e "$run" ] || die "run already exists: $run (finish it, or resume it)"

  # Pin the diff before creating anything, so a bad ref or an empty diff fails here and not inside the agents
  local diff commits=""
  if [ "$target" = working-tree ]; then
    diff=$(mktemp)
    git -C "$repo" diff HEAD >"$diff"
    git -C "$repo" ls-files --others --exclude-standard | while IFS= read -r f; do
      (cd "$repo" && git diff --no-index -- /dev/null "$f") >>"$diff"
    done
  else
    diff=$(mktemp)
    git -C "$repo" diff "$target" >"$diff" 2>/dev/null || { rm -f "$diff"; die "git diff $target failed: check that the refs resolve"; }
    commits=$(git -C "$repo" log --oneline "$target" 2>/dev/null || true)
  fi
  [ -s "$diff" ] || { rm -f "$diff"; die "the diff for $target is empty"; }

  mkdir -p "$run/00-input"
  mv "$diff" "$run/00-input/diff.patch"
  [ -z "$commits" ] || printf '%s\n' "$commits" >"$run/00-input/commits.txt"
  echo "$target" >"$run/00-input/target"
  if [ -n "$spec" ]; then cp "$spec" "$run/00-input/spec.md"; fi
  if [ "${#stds[@]}" -gt 0 ]; then
    mkdir -p "$run/00-input/standards"
    for f in "${stds[@]}"; do cp "$f" "$run/00-input/standards/"; done
  fi
  echo "$repo" >"$run/repo"
  echo "$second" >"$run/second"
  printf '%s %s\n' "$model" "$effort" >"$run/settings"
  printf 'time\tevent\n' >"$run/status.log"
  note "start $name ($model $effort, target $target, second reviewer $second)"
  board >&2 || true
  note "gate: ${#gates[@]} commands"
  run_gates "${gates[@]+"${gates[@]}"}"
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

cmd_status() {
  [ "$#" -eq 1 ] || die 'usage: status <name>'
  load_run "$1"
  cat "$run/status.log"
}

cmd_board() {
  [ "$#" -eq 1 ] || die 'usage: board <name>'
  load_run "$1"
  board
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
  [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$repo" ] || die "run finish inside the reviewed repository: $repo"
  local dest=$repo/records/reviews/$1
  [ ! -e "$dest" ] || die "already exists: $dest"
  mkdir -p "$dest"
  # Keep the record (pinned diff, criteria, briefs, reports, checks, report); leave out the script's own
  # state and the raw Codex output.
  local skip=(--exclude '*.events.jsonl' --exclude '*.stderr.log' --exclude '*.last-message.md' \
    --exclude '.*' --exclude repo --exclude second --exclude settings --exclude status.log)
  local dskip=(-x '*.events.jsonl' -x '*.stderr.log' -x '*.last-message.md' -x '.*' -x repo -x second -x settings -x status.log)
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
  status) cmd_status "$@" ;;
  board) cmd_board "$@" ;;
  finish) cmd_finish "$@" ;;
  *) die 'usage: review-run.sh start|resume|status|board|finish ...' ;;
esac

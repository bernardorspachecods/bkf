#!/usr/bin/env bash
# Run a two-axis code review with Codex: a Standards agent and a Spec agent review a pinned diff apart,
# a checker per axis confirms each finding, and the script writes the report. The coordinator names the
# target and the criteria and adds the one-line summary.
# Usage (run start, resume and finish inside the repository under review):
#   review-run.sh start   [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... <name> <target>
#   review-run.sh resume  [-m model] [-e effort] <name>
#   review-run.sh status  <name>
#   review-run.sh finish  [--discard] <name>
# target: `working-tree` (tracked changes against HEAD plus new files), or a git revision range such as
# `main...feature` (three dots, so the comparison is against the merge-base), passed to git diff as it is.
# -s gives the spec and each -d a file of documented coding standards. An axis with no criteria is not
# run and the report says so; with neither, there is nothing to review. -2 adds a second independent
# reviewer per axis, with the findings merged before the check.
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
model=gpt-6-luna effort=xhigh

# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"

note() { printf '%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$run/status.log"; }

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

# ---- Briefs: fixed templates, so the coordinator never writes them by hand ----

axis_brief() { # <axis>
  local a=$1
  printf '# Brief: %s review\n\n## What to review\nThe diff is `diff.patch` in the current directory (read-only)' "$(axis_title "$a")"
  [ -s "$run/00-input/commits.txt" ] && printf ', and the commits in `commits.txt`'
  printf '.\n'
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
  printf -- '- reports/: the findings of the reviewer(s) of this axis\n'
  printf '\n## The repository\nIt is at %s. Open it read-only to see the code around a hunk. Change nothing in it.\n' "$repo"
  printf '\n## Role\nOpen and follow the role guide: %s/code-review-check.md (read-only). You are not the author of the findings.\n' "$guides"
  printf '\n## Rules\n- Write your result to checked.md in the current directory. Write nothing else.\n- Open only files in the current directory, the repository and the role guide.\n- Do not run git commands that change state.\n'
}

# ---- Phases: each returns nonzero (with $reason) when it stops ----

run_review() {
  local d=$run/01-review a f
  local names=()
  for a in $(axes); do
    for f in "$a" $([ "$second" -eq 1 ] && echo "$a-2"); do
      mkdir -p "$d/$f"
      cp "$run/00-input/diff.patch" "$d/$f/diff.patch"
      [ -s "$run/00-input/commits.txt" ] && cp "$run/00-input/commits.txt" "$d/$f/commits.txt"
      case $a in
        standards) rm -rf "$d/$f/standards"; cp -R "$run/00-input/standards" "$d/$f/standards" ;;
        spec) cp "$run/00-input/spec.md" "$d/$f/spec.md" ;;
      esac
      [ -s "$d/$f/report.md" ] || axis_brief "$a" >"$d/$f/brief.md"
      names+=("$f")
    done
  done
  run_agents "$d" report.md "${names[@]}"
}

run_check() {
  local d=$run/02-check a r
  for a in $(axes); do
    mkdir -p "$d/$a/reports"
    cp "$run/00-input/diff.patch" "$d/$a/diff.patch"
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
    reason=""
    if "run_$st"; then
      touch "$run/.done-$st"; note "done $st"
    else
      note "STOPPED at $st: $reason"
      note "Read $run/*$st*, fix the cause, then: review-run.sh resume $(basename "$run")"
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
  local spec="" stds=() second=0
  while getopts 'm:e:2s:d:' o; do
    case $o in m) model=$OPTARG ;; e) effort=$OPTARG ;; 2) second=1 ;; s) spec=$OPTARG ;; d) stds+=("$OPTARG") ;; *) exit 1 ;; esac
  done
  shift $((OPTIND - 1))
  [ "$#" -eq 2 ] || die 'usage: start [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... <name> <target>'
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
  finish) cmd_finish "$@" ;;
  *) die 'usage: review-run.sh start|resume|status|finish ...' ;;
esac

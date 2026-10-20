#!/usr/bin/env bash
# Run a plan with Codex: each unit is implemented by one agent and reviewed by another. The coordinator
# only writes the goal and the unit briefs, and says which units run together.
# Usage (run start, resume and finish inside the repository the plan changes):
#   plan-run.sh start   [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>
#   plan-run.sh resume  [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name>
#   plan-run.sh status  <name>
#   plan-run.sh finish  [--discard] <name>
# plan.txt: one step per line, in order. A line holds the paths of unit briefs (relative to plan.txt),
# separated by spaces. One brief is a unit run in your checkout. Several on one line are a parallel group:
# each runs in its own git worktree, made from the state of your checkout when the group starts (untracked
# files included, ignored ones not), and when all have passed an integration agent applies their diffs to your checkout
# and a reviewer checks the combined result. Blank lines and lines starting with # are ignored.
# State lives in ${PLAN_RUNS_DIR:-$HOME/.plan-runs}/<name>, one numbered folder per unit. It must not be
# under /tmp: the workspace-write sandbox leaves /tmp writable. The unit briefs are read from
# <run>/00-input/units/ on every run, so a brief can be corrected there before `resume`.
# -p sets checkpoints by step number: `each`, or numbers like `2,4`. After such a step passes the run
# pauses (exit 3, `PAUSED` in status.log) so the user can read it; `resume` goes on. On resume, -p replaces
# the list (`-p none` clears it). With no -p the run goes through every step.
# The agents never change git state. A unit's base is the checkout as the previous step left it (a git tree of
# the working files, untracked ones included); the reviewer reads the diff from it. Changes made in the checkout
# between steps, or while a unit is stopped, therefore never land in the next unit's diff.
# Limits: PLAN_MAX_ROUNDS (default 3) escalates a review that keeps sending work back;
# PLAN_MIN_CHECKED (default 3) is the least number of lines a reviewer must give under
# "What I checked". PLAN_GUIDES points at the folder with the role guides.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
root=${PLAN_RUNS_DIR:-$HOME/.plan-runs}
guides=${PLAN_GUIDES:-$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)/agent-skills/library/workflow-types/plan}
max_rounds=${PLAN_MAX_ROUNDS:-3}
min_checked=${PLAN_MIN_CHECKED:-3}
model=gpt-6-luna effort=xhigh review_effort=

# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"

note() { printf '%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$run/status.log"; }
valid_pause() { [[ $1 =~ ^(none|each|[0-9]+(,[0-9]+)*)$ ]]; }

# Reviewers (and the final review) may use their own reasoning effort: -r, default the implementers' effort.
review_run() { # same arguments as codex_run
  local saved=$effort code
  effort=${review_effort:-$effort}
  codex_run "$@"; code=$?
  effort=$saved
  return $code
}

load_run() { # <name>
  valid_name "$1" || die "bad run name: $1"
  run=$root/$1
  [ -d "$run" ] || die "no such run: $run"
  repo=$(cat "$run/repo")
  if [ -f "$run/settings" ]; then read -r model effort review_effort <"$run/settings"; fi
  pause=$(cat "$run/pause" 2>/dev/null || true)
}

# True when the run should pause after this step and has not yet.
pause_here() { # <step>
  [ -e "$run/.paused-S$1" ] && return 1
  case "$pause" in
    each) return 0 ;;
    ''|none) return 1 ;;
  esac
  case ",$pause," in *",$1,"*) return 0 ;; esac
  return 1
}

# ---- The diff of a unit: the checkout as a tree before it, against the checkout as a tree after it ----
# A snapshot is a git tree built in a throwaway index: tracked and untracked files alike (ignored ones left out),
# whatever HEAD is. So edits to files git did not track yet show up, a commit made meanwhile changes nothing,
# and nothing in the real index or the working files is touched. Runs begun with the older script keep a commit
# as base and a list of untracked files (no `base-format` file in the folder); make_patch still reads those.

snapshot_tree() { # <checkout>: prints the id of a tree holding the checkout as it is now
  local tmp t
  tmp=$(mktemp -u "${TMPDIR:-/tmp}/plan-run-index.XXXXXX") || return 1
  GIT_INDEX_FILE=$tmp git -C "$1" read-tree HEAD >/dev/null 2>&1 || { rm -f "$tmp"; return 1; }
  GIT_INDEX_FILE=$tmp git -C "$1" add -A >/dev/null 2>&1
  t=$(GIT_INDEX_FILE=$tmp git -C "$1" write-tree 2>/dev/null)
  rm -f "$tmp"
  [ -n "$t" ] || return 1
  echo "$t"
}

snapshot_commit() { # <checkout>: like snapshot_tree, as a commit, for `git worktree add`
  local t
  t=$(snapshot_tree "$1") || return 1
  GIT_AUTHOR_NAME=plan-run GIT_AUTHOR_EMAIL=plan-run@localhost GIT_COMMITTER_NAME=plan-run GIT_COMMITTER_EMAIL=plan-run@localhost \
    git -C "$1" commit-tree "$t" -p HEAD -m "plan-run snapshot"
}

snapshot_base() { # <dir> <checkout>
  local t
  t=$(snapshot_tree "$2") || die "cannot snapshot the checkout $2"
  echo "$t" >"$1/base"
  echo tree >"$1/base-format"
}

make_patch() { # <dir> <out-file> <checkout>
  local f cur
  if [ "$(cat "$1/base-format" 2>/dev/null)" = tree ]; then
    cur=$(snapshot_tree "$3") || return 1
    git -C "$3" diff --no-ext-diff "$(cat "$1/base")" "$cur" >"$2"
    return 0
  fi
  git -C "$3" diff "$(cat "$1/base")" >"$2"
  git -C "$3" ls-files --others --exclude-standard | sort >"$1/untracked-after.txt"
  comm -13 "$1/untracked-before.txt" "$1/untracked-after.txt" | while IFS= read -r f; do
    [ -f "$3/$f" ] && (cd "$3" && git diff --no-index -- /dev/null "$f") >>"$2"
  done
  return 0
}

# ---- Prompts: fixed templates, so the coordinator never writes them by hand ----

implement_prompt() { # <unit-brief> <round> <resumed> <prev-problems> <prev-handoff>
  cat "$1"
  printf '\n\n---\n## Role\nOpen and follow the role guide: %s/plan-implementation.md (read-only). It says how to work inside the brief, what to verify and what the handoff holds.\n' "$guides"
  printf '\n## Rules\n- The current directory is the repository: do the work here.\n- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.\n'
  if [ "$2" -eq 1 ] && [ "$3" -eq 1 ]; then
    printf '\nAn earlier attempt at this unit was stopped. The checkout may already hold its work. Judge it against the brief, keep what is right and fix the rest.\n'
  fi
  if [ -n "$4" ]; then
    printf '\nA reviewer sent your work back. The work from the earlier round is in the checkout. Fix the problems below and only those, keeping what was fine, and verify again.\n\nProblems from the review:\n\n'
    cat "$4"
    printf '\n\nYour handoff from the previous round, for you to resume from:\n\n'
    cat "$5"
    printf '\n'
  fi
}

integrate_prompt() { # <group-brief> <failed-patches-or-empty> <prev-problems> <prev-handoff>
  cat "$1"
  printf '\n\n---\n## Role\nOpen and follow the role guide: %s/plan-integration.md (read-only). It says how to bring the units of a parallel group together and what the handoff holds.\n' "$guides"
  printf '\n## Rules\n- The current directory is the repository: work here.\n- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n- Do not write the handoff to a file. Your final message is the handoff, and nothing else.\n'
  if [ -n "$2" ]; then
    printf '\n## What to do\nThe diffs of these units did not apply to the checkout. Bring what each one meant into the checkout, resolving the conflict, and change nothing else:\n%s\n' "$2"
  fi
  if [ -n "$3" ]; then
    printf '\nA reviewer found problems in the combined result. Fix those and only those, then verify again.\n\nProblems from the review:\n\n'
    cat "$3"
    printf '\n\nYour handoff from the previous round, for you to resume from:\n\n'
    cat "$4"
    printf '\n'
  fi
}

review_prompt() { # <brief> <patch> <previous-problems-or-empty> <attempt>
  printf '# Review\n\n## The brief\n\n'
  cat "$1"
  printf '\n\n---\n## Inputs (read-only)\n- The diff, new files included: %s\n- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.\n- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.\n' "$2"
  printf '\n## Role\nOpen and follow the role guide: %s/plan-review.md (read-only). You are not the author of the work.\n' "$guides"
  if [ -n "$3" ]; then
    printf '\nThe problems you listed in the previous round are below. The work was corrected; check whether they are gone.\n\n'
    cat "$3"
    printf '\n'
  fi
  printf '\n---\nYour final message is the review, and nothing else. Begin it with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:\nVERDICT: pass\nVERDICT: back\nVERDICT: escalate\n'
  if [ "$4" -gt 1 ]; then
    printf 'Your previous attempt left no usable review (no "## What I checked" section, or no verdict line). Follow the form this time.\n'
  fi
}

# ---- Stages: each one writes its own folder and returns nonzero (with $reason) when it stops ----

# One review of a round. Sets $verdict; returns nonzero (with $reason) when no usable review comes out.
do_review() { # <label> <checkout> <brief> <round-dir> <prev-problems-or-empty>
  local attempt=0 checked=0 code
  while [ "$attempt" -lt 3 ]; do
    attempt=$((attempt + 1))
    rm -f "$4/review.last-message.md"
    review_prompt "$3" "$4/diff.patch" "$5" "$attempt" >"$4/review-prompt.md"
    review_run "$2" "$4/review-prompt.md" "$4/review" read-only
    code=$?
    [ "$code" -eq 0 ] || { reason="$1: review exit=$code (see $4/review.stderr.log)"; return 1; }
    if [ -s "$4/review.last-message.md" ] && checked_ok "$4/review.last-message.md" && read_verdict "$4/review.last-message.md" >/dev/null; then
      checked=1; break
    fi
    note "$1: review attempt $attempt was not usable"
  done
  [ "$checked" -eq 1 ] || { reason="$1: the reviewer left no usable review after $attempt attempts (see $4/review.last-message.md)"; return 1; }
  cp "$4/review.last-message.md" "$4/problems.md"
  verdict=$(read_verdict "$4/problems.md")
  echo "$verdict" >"$4/verdict"
  note "$1: round $(basename "$4"): verdict $verdict"
}

run_unit() { # <unit-dir-name> <checkout> [<step>]
  local u=$1 co=$2 d=$run/$1 k=${3:-}
  local round=0 resumed=0 prev="" prevh="" rd code from=""
  # The base is the checkout as the previous step left it, so that whatever changed in the checkout between that
  # and the (re)start of this unit never lands in its diff. Only a plain (non-group) step has one.
  if [ -n "$k" ]; then
    if [ "$k" -gt 1 ]; then from=$run/state-after-S$((k - 1)); else from=$run/plan-base/base; fi
    if [ "$k" -eq 1 ] && [ "$(cat "$run/plan-base/base-format" 2>/dev/null)" != tree ]; then from=""; fi
    [ -f "$from" ] || from=""
  fi
  mkdir -p "$d"
  if [ -f "$d/base" ]; then
    resumed=1
    [ -d "$d/rounds" ] && mv "$d/rounds" "$d/rounds.attempt-$(date +%s)"
  fi
  if [ -n "$from" ]; then
    cp "$from" "$d/base"; echo tree >"$d/base-format"
  elif [ "$resumed" -eq 0 ]; then
    snapshot_base "$d" "$co"
  fi
  mkdir -p "$d/rounds"
  cp "$run/00-input/units/$u.md" "$d/brief.md"

  while :; do
    round=$((round + 1))
    rd=$d/rounds/$round
    mkdir -p "$rd"

    echo "implementing round $round" >"$d/status"
    note "$u round $round: implement"
    implement_prompt "$d/brief.md" "$round" "$resumed" "$prev" "$prevh" >"$rd/implement-prompt.md"
    codex_run "$co" "$rd/implement-prompt.md" "$rd/implement" workspace-write
    code=$?
    [ "$code" -eq 0 ] || { reason="$u: implementer exit=$code (see $rd/implement.stderr.log)"; return 1; }
    [ -s "$rd/implement.last-message.md" ] || { reason="$u: implementer left no handoff"; return 1; }
    cp "$rd/implement.last-message.md" "$rd/handoff.md"
    cp "$rd/handoff.md" "$d/handoff.md"
    make_patch "$d" "$rd/diff.patch" "$co"
    [ -s "$rd/diff.patch" ] || { reason="$u: the diff is empty after round $round, so nothing was changed"; return 1; }

    echo "reviewing round $round" >"$d/status"
    note "$u round $round: review"
    do_review "$u" "$co" "$d/brief.md" "$rd" "$prev" || return 1

    case "$verdict" in
      pass) echo passed >"$d/status"; cp "$rd/diff.patch" "$d/final.patch"; return 0 ;;
      escalate) echo escalated >"$d/status"; reason="$u: the reviewer escalated (see $rd/problems.md)"; return 1 ;;
      back)
        if [ "$round" -ge "$max_rounds" ]; then
          echo escalated >"$d/status"
          reason="$u: round cap $max_rounds reached (see $rd/problems.md)"
          return 1
        fi
        prev=$rd/problems.md prevh=$rd/handoff.md ;;
    esac
  done
}

# Bring the units of a parallel group together in the checkout and review the combined result.
run_integration() { # <step> <unit-dir-name>...
  local k=$1; shift
  local idir=$run/S$k-integration name=S$k-integration u round=0 prev="" prevh="" rd code failed
  mkdir -p "$idir"
  if [ -f "$idir/base" ]; then
    [ -d "$idir/rounds" ] && mv "$idir/rounds" "$idir/rounds.attempt-$(date +%s)"
  else
    snapshot_base "$idir" "$repo"
  fi
  mkdir -p "$idir/rounds"
  {
    printf '# Integration of a parallel group\n\nThe units below were implemented apart, each in its own copy of the repository, and their diffs were brought together in this checkout. Check the combined result against every brief and against each other: contradictions between units, a "Receives" that the other unit did not leave ready as stated, duplicated or clashing names, and each unit'"'"'s own criteria. Use the section "The integration review" of the review guide.\n'
    for u in "$@"; do printf '\n## Unit %s\n\n' "$u"; cat "$run/$u/brief.md"; printf '\n'; done
  } >"$idir/brief.md"

  while :; do
    round=$((round + 1))
    rd=$idir/rounds/$round
    mkdir -p "$rd"
    failed=""
    if [ "$round" -eq 1 ]; then
      note "$name: apply the diffs"
      for u in "$@"; do
        [ -e "$idir/.applied-$u" ] && continue
        if git -C "$repo" apply --check "$run/$u/final.patch" 2>"$rd/apply-$u.err" && git -C "$repo" apply "$run/$u/final.patch" 2>>"$rd/apply-$u.err"; then
          touch "$idir/.applied-$u"
        else
          failed="$failed- $u: $run/$u/final.patch"$'\n'
          note "$name: $u did not apply (see $rd/apply-$u.err)"
        fi
      done
    fi
    if [ -n "$failed" ] || [ "$round" -gt 1 ]; then
      echo "integrating round $round" >"$idir/status"
      note "$name round $round: integrate"
      integrate_prompt "$idir/brief.md" "$failed" "$prev" "$prevh" >"$rd/integrate-prompt.md"
      codex_run "$repo" "$rd/integrate-prompt.md" "$rd/integrate" workspace-write
      code=$?
      [ "$code" -eq 0 ] || { reason="$name: integrator exit=$code (see $rd/integrate.stderr.log)"; return 1; }
      [ -s "$rd/integrate.last-message.md" ] || { reason="$name: integrator left no handoff"; return 1; }
      cp "$rd/integrate.last-message.md" "$rd/handoff.md"
      for u in "$@"; do touch "$idir/.applied-$u"; done
    fi
    make_patch "$idir" "$rd/diff.patch" "$repo"
    [ -s "$rd/diff.patch" ] || { reason="$name: the combined diff is empty"; return 1; }

    echo "reviewing round $round" >"$idir/status"
    note "$name round $round: review"
    do_review "$name" "$repo" "$idir/brief.md" "$rd" "$prev" || return 1

    case "$verdict" in
      pass) echo passed >"$idir/status"; return 0 ;;
      escalate) echo escalated >"$idir/status"; reason="$name: the reviewer escalated (see $rd/problems.md)"; return 1 ;;
      back)
        if [ "$round" -ge "$max_rounds" ]; then
          echo escalated >"$idir/status"
          reason="$name: round cap $max_rounds reached (see $rd/problems.md)"
          return 1
        fi
        prev=$rd/problems.md prevh=$rd/handoff.md ;;
    esac
  done
}

remove_worktrees() {
  local w
  for w in "$run"/worktrees/*; do
    [ -d "$w" ] && git -C "$repo" worktree remove --force "$w" >/dev/null 2>&1
  done
  rm -rf "$run/worktrees"
  git -C "$repo" worktree prune >/dev/null 2>&1
  return 0
}

# One step: a single unit in the checkout, or a parallel group in worktrees plus its integration.
run_step() { # <step> <unit-dir-name>...
  local k=$1; shift
  local u pids=() bad="" gb
  if [ "$#" -eq 1 ]; then
    [ -e "$run/.done-$1" ] || run_unit "$1" "$repo" "$k" || return 1
    touch "$run/.done-$1"
    return 0
  fi
  if [ ! -e "$run/.group-ready-S$k" ]; then
    gb=$(snapshot_commit "$repo") || gb=$(git -C "$repo" rev-parse HEAD)
    mkdir -p "$run/worktrees"
    for u in "$@"; do
      [ -d "$run/worktrees/$u" ] && continue
      git -C "$repo" worktree add --detach "$run/worktrees/$u" "$gb" >"$run/$u.worktree.log" 2>&1 \
        || { reason="could not create the worktree for $u (see $run/$u.worktree.log)"; return 1; }
    done
    touch "$run/.group-ready-S$k"
  fi
  for u in "$@"; do
    [ -e "$run/.done-$u" ] && continue
    (
      mkdir -p "$run/$u"
      rm -f "$run/$u/reason"
      reason=""
      if run_unit "$u" "$run/worktrees/$u"; then touch "$run/.done-$u"; else echo "$reason" >"$run/$u/reason"; exit 1; fi
    ) &
    pids+=($!)
  done
  for u in "${pids[@]+"${pids[@]}"}"; do wait "$u" || true; done
  for u in "$@"; do
    [ -e "$run/.done-$u" ] || bad="$bad$(cat "$run/$u/reason" 2>/dev/null || echo "$u stopped"); "
  done
  [ -z "$bad" ] || { reason="$bad"; return 1; }
  [ -e "$run/.done-S$k-integration" ] || run_integration "$k" "$@" || return 1
  touch "$run/.done-S$k-integration"
  remove_worktrees
  return 0
}

# The last review: does the whole result meet the goal. A report, with no verdict loop.
run_report() {
  local code u
  make_patch "$run/plan-base" "$run/cumulative.patch" "$repo"
  {
    printf '# Final review of the plan\n\n## The goal\n\n'
    cat "$run/00-input/goal.md"
    printf '\n\n## The unit briefs, in order\n'
    for u in $(all_units); do printf '\n### %s\n\n' "$u"; cat "$run/$u/brief.md"; printf '\n'; done
    printf '\n## Inputs (read-only)\n- The diff of the whole plan, new files included: %s\n- The reviews of each unit and of each parallel group: ' "$run/cumulative.patch"
    for u in $(all_units); do printf '%s/rounds/*/problems.md ' "$run/$u"; done
    printf '%s/S*-integration/rounds/*/problems.md' "$run"
    printf '\n- The repository is your current directory. Open it read-only. Do not change anything. Do not open the handoffs.\n'
    printf '\n## Role\nOpen and follow the role guide: %s/plan-review.md (read-only), section "The final review". You are not the author of the work.\n' "$guides"
    printf '\n---\nYour final message is the report, and nothing else.\n'
  } >"$run/report-prompt.md"
  review_run "$repo" "$run/report-prompt.md" "$run/report" read-only
  code=$?
  [ "$code" -eq 0 ] || { reason="final review exit=$code (see $run/report.stderr.log)"; return 1; }
  [ -s "$run/report.last-message.md" ] || { reason="final review wrote no report"; return 1; }
  cp "$run/report.last-message.md" "$run/report.md"
}

all_units() { tr ' ' '\n' <"$run/00-input/order" | grep -v '^$'; }

pipeline() {
  local k=0 line
  printf 'Run folder: %s\n' "$run"
  while IFS= read -r line; do
    k=$((k + 1))
    [ -e "$run/.done-S$k" ] && continue
    note "start step $k: $line ($model $effort)"
    reason=""
    # shellcheck disable=SC2086
    if run_step "$k" $line; then
      touch "$run/.done-S$k"; note "done step $k"
      snapshot_tree "$repo" >"$run/state-after-S$k" 2>/dev/null || rm -f "$run/state-after-S$k"
      if pause_here "$k"; then
        touch "$run/.paused-S$k"
        note "PAUSED after step $k: read $run, then: plan-run.sh resume $(basename "$run")"
        printf 'PAUSED after step %s (%s). Read it in %s, then: plan-run.sh resume %s\nSee %s/status.log\n' "$k" "$line" "$run" "$(basename "$run")" "$run"
        return 3
      fi
    else
      note "STOPPED at step $k: $reason"
      note "Read the rounds in $run, fix the cause (the briefs in $run/00-input/units/, or the checkout), then: plan-run.sh resume $(basename "$run")"
      printf 'STOPPED at step %s (%s): %s\nSee %s/status.log\n' "$k" "$line" "$reason" "$run"
      return 1
    fi
  done <"$run/00-input/order"
  if [ ! -e "$run/.done-report" ]; then
    note "start final review ($model $effort)"
    reason=""
    if run_report; then
      touch "$run/.done-report"; note "done final review"
    else
      note "STOPPED at the final review: $reason"
      printf 'STOPPED at the final review: %s\nSee %s/status.log\n' "$reason" "$run"
      return 1
    fi
  fi
  note "READY: report at $run/report.md"
  printf 'READY: %s/report.md\nSee %s/status.log\n' "$run" "$run"
}

# ---- Commands ----

cmd_start() {
  pause=""
  while getopts 'm:e:r:p:' o; do case $o in m) model=$OPTARG ;; e) effort=$OPTARG ;; r) review_effort=$OPTARG ;; p) pause=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 3 ] || die 'usage: start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>'
  valid_name "$1" || die "bad run name: $1"
  [ -z "$pause" ] || valid_pause "$pause" || die "bad checkpoints: $pause (use each, none, or step numbers like 2,4)"
  local name=$1 goal=$2 plan=$3 pdir line f i=0 w u order=""
  [ -s "$goal" ] || die "missing or empty goal: $goal"
  [ -s "$plan" ] || die "missing or empty plan: $plan"
  pdir=$(cd "$(dirname "$plan")" && pwd)
  command -v codex >/dev/null || die 'codex not found'
  repo=$(git rev-parse --show-toplevel 2>/dev/null) || die 'run start inside the repository the plan changes'
  [ -d "$guides" ] || die "no role guides at $guides (set PLAN_GUIDES)"
  run=$root/$name
  [ ! -e "$run" ] || die "run already exists: $run (finish it, or resume it)"

  # Validate the whole plan before creating anything
  local steps=()
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%%#*}
    # shellcheck disable=SC2086
    set -- $line
    [ "$#" -gt 0 ] || continue
    for w in "$@"; do
      f=$w; case $f in /*) ;; *) f=$pdir/$f ;; esac
      [ -s "$f" ] || die "missing or empty unit brief: $w"
      valid_name "$(basename "$f" .md)" || die "bad unit name (from the file name): $w"
    done
    steps+=("$*")
  done <"$plan"
  [ "${#steps[@]}" -gt 0 ] || die "plan.txt has no step"

  mkdir -p "$run/00-input/units"
  cp "$goal" "$run/00-input/goal.md"
  : >"$run/00-input/order"
  for line in "${steps[@]}"; do
    order=""
    for w in $line; do
      f=$w; case $f in /*) ;; *) f=$pdir/$f ;; esac
      i=$((i + 1))
      u=$(printf '%02d-%s' "$i" "$(basename "$f" .md)")
      cp "$f" "$run/00-input/units/$u.md"
      order="$order${order:+ }$u"
    done
    echo "$order" >>"$run/00-input/order"
  done
  echo "$repo" >"$run/repo"
  echo "$pause" >"$run/pause"
  mkdir -p "$run/plan-base"
  snapshot_base "$run/plan-base" "$repo"
  printf '%s %s %s\n' "$model" "$effort" "$review_effort" >"$run/settings"
  printf 'time\tevent\n' >"$run/status.log"
  note "start $name ($model $effort, review ${review_effort:-$effort}, max $max_rounds rounds, ${#steps[@]} step(s), $i unit(s), repo $repo)"
  pipeline
}

cmd_resume() {
  local fm="" fe="" fr="" fp=""
  while getopts 'm:e:r:p:' o; do case $o in m) fm=$OPTARG ;; e) fe=$OPTARG ;; r) fr=$OPTARG ;; p) fp=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 1 ] || die 'usage: resume [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name>'
  load_run "$1"
  if [ -n "$fp" ]; then
    valid_pause "$fp" || die "bad checkpoints: $fp (use each, none, or step numbers like 2,4)"
    pause=$fp; echo "$pause" >"$run/pause"
  fi
  [ -z "$fm" ] || model=$fm
  [ -z "$fe" ] || effort=$fe
  [ -z "$fr" ] || review_effort=$fr
  [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$repo" ] || die "run resume inside the plan's repository: $repo"
  printf '%s %s %s\n' "$model" "$effort" "$review_effort" >"$run/settings"
  note "resume"
  pipeline
}

cmd_status() {
  [ "$#" -eq 1 ] || die 'usage: status <name>'
  load_run "$1"
  cat "$run/status.log"
}

# The run's history as a readable summary: per unit and per group integration, the rounds and how it ended.
write_summary() {
  local d r n last k=0 line
  {
    printf '# Plan summary\n\nRun: %s\n\n| Step | Unit | Rounds | Last verdict |\n|---|---|---|---|\n' "$(basename "$run")"
    while IFS= read -r line; do
      k=$((k + 1))
      for d in $line; do
        n=$(ls "$run/$d/rounds" 2>/dev/null | wc -l | tr -d ' ')
        last=$(ls "$run/$d/rounds" 2>/dev/null | sort -n | tail -1)
        r=$(cat "$run/$d/rounds/$last/verdict" 2>/dev/null || echo "-")
        printf '| %s | %s | %s | %s |\n' "$k" "$d" "$n" "$r"
      done
      if [ -d "$run/S$k-integration" ]; then
        n=$(ls "$run/S$k-integration/rounds" 2>/dev/null | wc -l | tr -d ' ')
        last=$(ls "$run/S$k-integration/rounds" 2>/dev/null | sort -n | tail -1)
        r=$(cat "$run/S$k-integration/rounds/$last/verdict" 2>/dev/null || echo "-")
        printf '| %s | integration | %s | %s |\n' "$k" "$n" "$r"
      fi
    done <"$run/00-input/order"
    printf '\nThe final review is in report.md.\n'
  } >"$run/status.md"
}

cmd_finish() {
  local discard=0
  [ "${1:-}" = --discard ] && { discard=1; shift; }
  [ "$#" -eq 1 ] || die 'usage: finish [--discard] <name>'
  load_run "$1"
  remove_worktrees
  if [ "$discard" -eq 1 ]; then
    rm -rf "$run"
    printf 'Removed %s\n' "$run"
    return 0
  fi
  [ -s "$run/report.md" ] || die 'there is no final review in this run: nothing to keep'
  [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$repo" ] || die "run finish inside the plan's repository: $repo"
  local dest=$repo/records/plans/$1
  [ ! -e "$dest" ] || die "already exists: $dest"
  mkdir -p "$dest"
  write_summary
  # Keep the record (inputs, briefs, prompts, handoffs, reviews, verdicts, diffs, report); leave out the
  # script's own state and the raw Codex output.
  local skip=(--exclude '*.events.jsonl' --exclude '*.stderr.log' --exclude '*.last-message.md' \
    --exclude '.*' --exclude '*.attempt-*' --exclude 'untracked-*.txt' --exclude base --exclude plan-base \
    --exclude '*.worktree.log' --exclude repo --exclude pause --exclude settings --exclude status --exclude status.log)
  local dskip=(-x '*.events.jsonl' -x '*.stderr.log' -x '*.last-message.md' \
    -x '.*' -x '*.attempt-*' -x 'untracked-*.txt' -x base -x plan-base \
    -x '*.worktree.log' -x repo -x pause -x settings -x status -x status.log)
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
  *) die 'usage: plan-run.sh start|resume|status|finish ...' ;;
esac

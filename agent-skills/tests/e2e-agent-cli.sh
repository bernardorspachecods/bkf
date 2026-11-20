#!/usr/bin/env bash
# End-to-end check of the agent CLI: bkf task, launch and hooks, the delegate scripts, the merge queue (bkf merge),
# a plan run, the bkf suites, and (with AGENTIC_ROOT) the Agentic app's bkf client. No model is called and
# nothing is written under the real home, the user's task store or the user's tmux server: the run uses a
# sandbox home, a temporary task store and a throwaway tmux server (tmux -L <unique>), killed on exit.
# Usage: agent-skills/tests/e2e-agent-cli.sh
#   AGENTIC_ROOT=<Agentic checkout>  also runs the app cases (the bkf contract and the build); without it they are SKIP.
# Prints PASS <case>, FAIL <case>: <why> or SKIP <case>: <why>, one line per case. Exit 0 only when no case fails.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
bkf_root=$(git -C "$here" rev-parse --show-toplevel)
real_home=$HOME
real_tasks=$real_home/.local/state/bkf/tasks
failed=0
CASE= WHY=

begin() { CASE=$1; WHY=; }
# check WHY COMMAND...: records WHY when the command fails.
check() { local why=$1; shift; "$@" >/dev/null 2>&1 || WHY="${WHY:+$WHY; }$why"; }
# eq GOT WANT WHY: records WHY with both values when they differ.
eq() { [ "$1" = "$2" ] || WHY="${WHY:+$WHY; }$3 (got '$1', expected '$2')"; }
end() {
  if [ -z "$WHY" ]; then echo "PASS $CASE"; else echo "FAIL $CASE: $WHY"; failed=1; fi
}
skip() { echo "SKIP $1: $2"; }

# ---- Preconditions: a case that cannot run here is SKIP with its reason.
missing=
command -v tmux >/dev/null || missing="tmux is not installed"
command -v uv >/dev/null || missing="${missing:+$missing; }uv is not installed"
py=
[ -z "$missing" ] && py="$(uv tool dir)/bkf-tooling/bin/python3"
if [ -n "$missing" ]; then bkf_missing=$missing; elif [ ! -x "$py" ]; then bkf_missing="the bkf tool environment is missing ($py)"; else bkf_missing=; fi
uv_tool_dir=$(uv tool dir 2>/dev/null)
# Session names only: windows and the attached flag change whenever the user works in their own tmux.
tmux_ls_before=$(command tmux ls -F '#{session_name}' 2>&1 | sort)
real_tasks_before=$(ls -A "$real_tasks" 2>/dev/null | sort)

# ---- Sandbox: a home of its own, a temporary task store, a throwaway tmux server, and fake agents first on PATH.
work=$(mktemp -d "${TMPDIR:-/tmp}/e2e-agent-cli.XXXXXX")
work=$(cd "$work" && pwd -P)
sock="e2e-agent-cli-$$"
cleanup() {
  command tmux -L "$sock" kill-server 2>/dev/null
  if [ -n "${E2E_KEEP:-}" ]; then echo "kept sandbox: $work" >&2; else rm -rf "$work"; fi
}
trap cleanup EXIT

export HOME=$work/home
mkdir -p "$HOME" "$work/bin" "$work/calls" "$work/behave" "$work/repos" "$work/state"
export UV_TOOL_DIR=$uv_tool_dir
export E2E=$work BKF_TASKS_DIR=$work/tasks BKF_TMUX_SOCKET=$sock SHELL=/bin/sh
export XDG_STATE_HOME=$work/xdg-state
unset TMUX TMUX_PANE TERM_PROGRAM BKF_TASK BKF_DELEGATED
export PATH=$work/bin:$PATH

if [ -z "$bkf_missing" ]; then
  # The bkf shim runs this worktree's tooling, not the installed copy.
  cat >"$work/bin/bkf" <<SHIM
#!/usr/bin/env bash
PYTHONPATH="$bkf_root/bkf/tooling" exec "$py" -m bkf_cli "\$@"
SHIM
  chmod +x "$work/bin/bkf"
fi

# Fake Claude: records its call under $E2E/calls, then runs the behaviour a case wrote to $E2E/behave/claude.
cat >"$work/bin/claude" <<'FAKE'
#!/usr/bin/env bash
prefix=$(mktemp "$E2E/calls/claude.XXXXXX")
printf '%s\n' "$@" >"$prefix.args"
if [ "$#" -gt 0 ]; then printf '%s' "${!#}" >"$prefix.prompt"; fi
{
  printf 'pwd=%s\n' "$(pwd -P)"
  printf 'BKF_TASK=%s\n' "${BKF_TASK-unset}"
  printf 'BKF_DELEGATED=%s\n' "${BKF_DELEGATED-unset}"
} >"$prefix.env"
if [ -f "$E2E/behave/claude" ]; then bash "$E2E/behave/claude" "$prefix"; fi
FAKE
chmod +x "$work/bin/claude"

# Fake Codex: the fake the plan tests use (it records prompts, edits the checkout as FAKE_IMPLS says, and writes verdicts).
python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import plan_test_support as p; sys.stdout.write(p._FAKE_CODEX)' \
  "$bkf_root/agent-skills/skills/agentic-work/tests" >"$work/bin/codex" 2>"$work/codex-fake.err" || true
chmod +x "$work/bin/codex"

behave() { printf '%s\n' "$2" >"$E2E/behave/$1"; }
unbehave() { rm -f "$E2E/behave/$1"; }
clear_calls() { rm -f "$work"/calls/*; }
status_is() { [ "$(field "$1" status)" = "$2" ]; }
attention_is() { [ "$(field "$1" attention.reason)" = "$2" ]; }
first_call() { ls "$work"/calls/claude.*.env 2>/dev/null | head -1 | sed 's/\.env$//'; }
has_call() { [ -n "$(first_call)" ]; }
env_field() { sed -n "s/^$2=//p" "$1.env"; }
json_field() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."):
    v = None if v is None else v.get(k)
print("" if v is None else v)' "$1" "$2"; }

# A tmux call on the throwaway server only.
t() { command tmux -L "$sock" "$@"; }
# wait_for SECONDS COMMAND...: true once the command succeeds, false after the time.
wait_for() {
  local secs=$1 i
  shift
  for ((i = 0; i < secs * 10; i++)); do "$@" && return 0; sleep 0.1; done
  "$@"
}

# A git repository with one commit and a tracked seed.txt, under the sandbox.
mkrepo() {
  local dir=$work/repos/$1
  mkdir -p "$dir"
  printf 'seed\n' >"$dir/seed.txt"
  git init -q -b main "$dir"
  git -C "$dir" add -A
  git -C "$dir" -c user.email=e2e@example.invalid -c user.name=e2e commit -q -m init
  printf '%s\n' "$dir"
}

# A bkf task id found by its title (the newest one).
card_by_title() {
  bkf task list --json | python3 -c 'import json,sys
found = [t for t in json.load(sys.stdin)["tasks"] if t["title"] == sys.argv[1]]
print(found[-1]["id"] if found else "")' "$1"
}
# One field of a card: <card id> <dotted key>.
field() {
  bkf task show "$1" --json | python3 -c 'import json,sys
v = json.load(sys.stdin)
for k in sys.argv[1].split("."):
    v = None if v is None else v.get(k)
print("" if v is None else v)' "$2"
}
# A new window of the main session that runs a script (text on $2, in a file of the run folder) with the
# given VAR=value environment; the window stays after the script ends. Prints the window id.
spawn() {
  local name=$1 dir=$2 text=$3 file kv
  shift 3
  mkdir -p "$work/run"
  file=$work/run/$name.sh
  printf '%s\n' "$text" >"$file"
  local -a envs=()
  for kv in "$@"; do envs+=(-e "$kv"); done
  t new-window -d -P -F '#{window_id}' -t main: -n "$name" -c "$dir" ${envs[@]+"${envs[@]}"} "sh '$file'; sleep 600"
}
window_index() { t list-windows -t main -F '#{window_index} #{window_name}' | awk -v n="$1" '{name=substr($0, index($0, " ")+1)} name==n {print $1}'; }
window_id_named() { t list-windows -t main -F '#{window_id} #{window_name}' | awk -v n="$1" '{name=substr($0, index($0, " ")+1)} name==n {print $1}'; }

# ---- Cases.

case_handoff() {
  begin "handoff from inside tmux"
  local repo prompt out win card prefix
  repo=$(mkrepo handoff)
  prompt=$work/handoff-prompt.md
  printf 'Handoff line one.\nLine two: "quoted" text, a $ sign that stays literal.\n' >"$prompt"
  clear_calls
  behave claude 'while [ ! -e "$E2E/release-handoff" ]; do sleep 0.1; done
bkf task attention "$BKF_TASK" --set paused --note "handoff done"'
  out=$work/out-handoff
  win=$(spawn caller-handoff "$repo" "bkf launch claude --dir '$repo' --prompt-file '$prompt' --title 'handoff e2e' >'$out.stdout' 2>'$out.stderr'; echo \$? >'$out.rc'")
  wait_for 30 test -s "$out.rc"
  eq "$(cat "$out.rc" 2>/dev/null)" 0 "bkf launch from the window exits 0"
  card=$(card_by_title 'handoff e2e')
  check "the card exists" test -n "$card"
  if [ -n "$card" ]; then
    eq "$(head -1 "$out.stdout")" "$card" "the launch prints the card id first"
    wait_for 10 has_call
    eq "$(field "$card" kind)" handoff "the card is a handoff"
    eq "$(field "$card" status)" working "the card is working while the session runs"
    eq "$(field "$card" session.tmux_window)" "$(window_id_named 'handoff e2e')" "the card names the window that runs it"
    eq "$(window_index 'handoff e2e')" "$(( $(window_index caller-handoff) + 1 ))" "the window is placed right after the caller"
    prefix=$(first_call)
    eq "$(cat "$prefix.prompt" 2>/dev/null)" "$(cat "$prompt")" "the agent got the whole prompt"
    eq "$(env_field "$prefix" BKF_TASK)" "$card" "the agent runs with BKF_TASK set to the card"
    eq "$(env_field "$prefix" BKF_DELEGATED)" unset "a handoff session is not delegated"
    eq "$(env_field "$prefix" pwd)" "$repo" "the agent starts in the folder it was given"
    touch "$work/release-handoff"
    wait_for 20 attention_is "$card" paused
    eq "$(field "$card" status)" working "the card stays working while it waits for its owner"
    eq "$(field "$card" attention.note)" "handoff done" "the card keeps the note the agent gave"
  fi
  unbehave claude
  end
}

case_handoff_parent() {
  begin "handoff with parent"
  local repo prompt parent out child
  repo=$(mkrepo parent)
  prompt=$work/handoff-prompt.md
  parent=$(bkf task new --repo "$repo" --title 'parent e2e')
  clear_calls
  unbehave claude
  out=$work/out-parent
  spawn caller-parent "$repo" "bkf launch claude --dir '$repo' --prompt-file '$prompt' --title 'child e2e' >'$out.stdout' 2>'$out.stderr'; echo \$? >'$out.rc'" "BKF_TASK=$parent" >/dev/null
  wait_for 30 test -s "$out.rc"
  eq "$(cat "$out.rc" 2>/dev/null)" 0 "bkf launch from the window exits 0"
  child=$(card_by_title 'child e2e')
  check "the child card exists" test -n "$child"
  if [ -n "$child" ]; then
    eq "$(field "$child" parent)" "$parent" "the new card's parent is the card named by BKF_TASK"
  fi
  end
}

case_hook() {
  begin "task session hook"
  local repo task unit unknown rc1 rc2 rc3 o1 o2 o3
  repo=$(mkrepo hook)
  task=$(bkf task new --repo "$repo" --title 'hook task')
  unit=$(bkf task new --repo "$repo" --title 'hook unit' --kind unit)
  unknown=t20990101-000000-dead
  o1=$(BKF_TASK=$task bkf hooks run task); rc1=$?
  o2=$(BKF_TASK=$unit bkf hooks run task); rc2=$?
  o3=$(BKF_TASK=$unknown bkf hooks run task); rc3=$?
  eq "$rc1$rc2$rc3" 000 "the hook exits 0 for every id"
  case "$o1" in *"This session works on task $task (task): hook task"*) ;; *) WHY="${WHY:+$WHY; }the task card gets its session text (got '$o1')" ;; esac
  eq "$o2" "" "a unit card gets no text (its owner moves it)"
  eq "$o3" "" "an unknown id gets no text"
  end
}

case_app_style() {
  begin "app-style launch from outside tmux"
  local repo card slug session window worktree expected_session json_out prefix
  repo=$(mkrepo app-style)
  card=$(bkf task new --repo "$repo" --title 'App style task')
  slug="app-style-task-${card: -4}"
  clear_calls
  unbehave claude
  json_out=$work/app.json
  env -u TMUX -u TMUX_PANE -u TERM_PROGRAM bkf launch claude --dir "$repo" --task "$card" --no-attach --json --size 120x40 \
    >"$json_out" 2>"$work/app.err"
  eq "$?" 0 "the launch exits 0 ($(cat "$work/app.err" | head -1))"
  session=$(json_field "$json_out" session)
  window=$(json_field "$json_out" window)
  expected_session=$(python3 -c 'import hashlib, os, re, sys
repo = sys.argv[1]
slug = re.sub(r"[^a-z0-9]+", "-", os.path.basename(repo).lower()).strip("-")[:41].rstrip("-") or "repo"
print(slug + "-" + hashlib.sha1(repo.encode()).hexdigest()[:6])' "$repo")
  eq "$session" "$expected_session" "the session is <slug>-<hash6> of the repository"
  eq "$(bkf launch --session-name --dir "$repo")" "$session" "--session-name prints the same session"
  eq "$(t list-windows -t "=$session" 2>/dev/null | wc -l | tr -d ' ')" 1 "the session has exactly one window"
  eq "$(json_field "$json_out" task)" "$card" "--json names the card"
  eq "$(json_field "$json_out" worktree)" "$repo/.claude/worktrees/$slug" "the worktree is under the repository's .claude/worktrees"
  eq "$(json_field "$json_out" branch)" "task/$slug" "the branch is task/<slug>"
  check "the worktree exists" test -d "$repo/.claude/worktrees/$slug"
  wait_for 10 has_call
  prefix=$(first_call)
  worktree=$repo/.claude/worktrees/$slug
  eq "$(env_field "$prefix" pwd)" "$(cd "$worktree" 2>/dev/null && pwd -P)" "the agent runs in the task worktree"
  eq "$(env_field "$prefix" BKF_TASK)" "$card" "the agent runs with BKF_TASK set to the card"
  check "the worktree folder is excluded in the repository" bash -c \
    'grep -qx "/.claude/worktrees/" "$(git -C "$1" rev-parse --path-format=absolute --git-common-dir)/info/exclude"' _ "$repo"
  eq "$(field "$card" status)" working "the card is working"
  eq "$(field "$card" session.tmux_session)" "$session" "the card names the session"
  eq "$(field "$card" session.tmux_window)" "$window" "the card names the window"
  end
}

case_delegate() {
  begin "delegate run"
  local repo ok_runs fail_runs prompt
  repo=$(mkrepo delegate)
  prompt=$work/delegate-brief.md
  printf 'Change seed.txt by appending a line.\n' >"$prompt"
  mkdir -p "$work/state/delegate-ok" "$work/state/delegate-fail"
  ok_runs=$work/delegate-runs/delegate/edit-ok
  fail_runs=$work/delegate-runs/delegate/edit-fail
  (
    cd "$repo" && DELEGATE_RUNS_DIR=$work/delegate-runs FAKE_STATE=$work/state/delegate-ok \
      FAKE_IMPLS='{"1":"echo change >> seed.txt"}' FAKE_REVIEW_VERDICTS='["pass"]' \
      bash "$bkf_root/agent-skills/skills/agentic-work/scripts/delegate-run.sh" edit-ok "$prompt" >"$work/delegate-ok.out" 2>&1
  )
  eq "$?" 0 "delegate-run exits 0 for a passing agent"
  local ok_card
  ok_card=$(cat "$ok_runs/task" 2>/dev/null)
  check "the run folder names its card" test -n "$ok_card"
  if [ -n "$ok_card" ]; then
    eq "$(field "$ok_card" status)" working "the unit card stays working while it waits for its owner"
    eq "$(field "$ok_card" attention.reason)" paused "the unit card waits for its owner: paused"
    eq "$(field "$ok_card" attention.note)" "1 files changed" "the card notes the changed file count"
    eq "$(field "$ok_card" kind)" unit "the card is a unit card"
    case "$(field "$ok_card" worktree.path)" in */.claude/worktrees/*) ;; *) WHY="${WHY:+$WHY; }the worktree is under .claude/worktrees" ;; esac
  fi
  (
    cd "$repo" && DELEGATE_RUNS_DIR=$work/delegate-runs FAKE_STATE=$work/state/delegate-fail \
      FAKE_IMPLS='{"1":"exit 3"}' FAKE_REVIEW_VERDICTS='["pass"]' \
      bash "$bkf_root/agent-skills/skills/agentic-work/scripts/delegate-run.sh" edit-fail "$prompt" >"$work/delegate-fail.out" 2>&1
  )
  eq "$?" 3 "delegate-run exits with the agent's status 3"
  local fail_card
  fail_card=$(cat "$fail_runs/task" 2>/dev/null)
  check "the failed run folder names its card" test -n "$fail_card"
  if [ -n "$fail_card" ]; then
    eq "$(field "$fail_card" status)" failed "the card is failed"
    eq "$(field "$fail_card" exit)" 3 "the card records exit 3"
  fi
  end
}

case_merge_queue() {
  begin "merge queue"
  local repo card_a card_b wt_a wt_b branch_a branch_b
  repo=$(mkrepo merge)
  card_a=$(bkf task new --repo "$repo" --title 'merge a')
  card_b=$(bkf task new --repo "$repo" --title 'merge b')
  bkf task worktree "$card_a" >/dev/null && bkf task worktree "$card_b" >/dev/null
  wt_a=$(field "$card_a" worktree.path); branch_a=$(field "$card_a" worktree.branch)
  wt_b=$(field "$card_b" worktree.path); branch_b=$(field "$card_b" worktree.branch)
  check "both cards have a worktree and a branch" test -n "$wt_a" -a -n "$branch_a" -a -n "$wt_b" -a -n "$branch_b"
  bkf task start "$card_a" --worktree "$wt_a" --branch "$branch_a" >/dev/null
  bkf task start "$card_b" --worktree "$wt_b" --branch "$branch_b" >/dev/null
  printf 'a\n' >"$wt_a/feature-a.txt"
  git -C "$wt_a" add feature-a.txt
  git -C "$wt_a" -c user.email=e2e@example.invalid -c user.name=e2e commit -q -m a
  printf 'b\n' >"$wt_b/feature-b.txt"
  git -C "$wt_b" add feature-b.txt
  git -C "$wt_b" -c user.email=e2e@example.invalid -c user.name=e2e commit -q -m b
  (cd "$wt_a" && BKF_TASK=$card_a bkf merge enter >"$work/mq-a-enter.out" 2>&1)
  eq "$?" 0 "session a enters the queue ($(head -1 "$work/mq-a-enter.out"))"
  (cd "$wt_b" && BKF_TASK=$card_b bkf merge enter >"$work/mq-b-enter.out" 2>&1)
  eq "$?" 0 "session b enters behind a"
  eq "$(field "$card_a" status)" to-merge "the card of a is to-merge once queued"
  (cd "$wt_b" && BKF_TASK=$card_b bkf merge wait --timeout 0 >/dev/null 2>&1)
  eq "$?" 75 "b does not get the turn while a holds it"
  (cd "$wt_a" && BKF_TASK=$card_a bkf merge wait --timeout 5 >/dev/null 2>&1)
  eq "$?" 0 "a gets the turn at once"
  (cd "$wt_a" && BKF_TASK=$card_a bkf merge verify >/dev/null 2>&1 && BKF_TASK=$card_a bkf merge land >"$work/mq-a-land.out" 2>&1)
  eq "$?" 0 "a verifies and lands ($(tail -1 "$work/mq-a-land.out"))"
  (cd "$wt_b" && BKF_TASK=$card_b bkf merge wait --timeout 5 >/dev/null 2>&1)
  eq "$?" 0 "b gets the turn when a has landed"
  (cd "$wt_b" && git merge -q main -m "merge main into b" && BKF_TASK=$card_b bkf merge verify >/dev/null 2>&1 \
    && BKF_TASK=$card_b bkf merge land >"$work/mq-b-land.out" 2>&1)
  eq "$?" 0 "b merges main, verifies and lands"
  eq "$(git -C "$repo" show main:feature-a.txt 2>/dev/null)" a "a's change is on main"
  eq "$(git -C "$repo" show main:feature-b.txt 2>/dev/null)" b "b's change is on main"
  eq "$(bkf merge status --json --task "$card_b" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task"]["in_queue"])')" False \
    "b is no longer in the queue"
  eq "$(bkf merge status --repo "$repo" --json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["queues"][0]["entries"]))')" 0 \
    "the queue is empty"
  bkf task close "$card_a" >/dev/null && bkf task close "$card_b" >/dev/null
  check "closing the cards deletes them" bash -c '[ -z "$(bkf task list --repo "$1")" ]' _ "$repo"
  end
}

case_plan() {
  begin "plan run"
  local repo plan_dir plan_runs run_card unit_card
  repo=$(mkrepo plan)
  plan_dir=$work/plan
  mkdir -p "$plan_dir" "$work/guides" "$work/state/plan"
  printf 'Goal\n' >"$plan_dir/goal.md"
  printf 'guide\n' >"$work/guides/agentic-work-implementation.md"
  printf 'guide\n' >"$work/guides/agentic-work-review.md"
  printf '## Result\nImplement it.\n' >"$plan_dir/unit.md"
  printf 'unit.md\n' >"$plan_dir/plan.txt"
  plan_runs=$work/plan-runs
  (
    cd "$repo" && PLAN_RUNS_DIR=$plan_runs PLAN_GUIDES=$work/guides FAKE_STATE=$work/state/plan \
      FAKE_IMPLS='{}' FAKE_REVIEW_VERDICTS='["pass"]' HARNESS_BACKEND=codex \
      bash "$bkf_root/agent-skills/skills/agentic-work/scripts/plan-run.sh" start --in-place sample \
      "$plan_dir/goal.md" "$plan_dir/plan.txt" >"$work/plan.out" 2>"$work/plan.err"
  )
  eq "$?" 0 "plan-run exits 0 ($(head -1 "$work/plan.err"))"
  run_card=$(cat "$plan_runs/sample/task" 2>/dev/null)
  unit_card=$(cat "$plan_runs/sample/01-unit/task" 2>/dev/null)
  check "the run and unit cards exist" test -n "$run_card" -a -n "$unit_card"
  if [ -n "$run_card" ] && [ -n "$unit_card" ]; then
    eq "$(field "$run_card" status)" working "the run card stays working at the final report"
    eq "$(field "$run_card" attention.reason)" paused "the run card waits for its owner: paused"
    check "the passed unit's card is closed" bash -c '! bkf task show "$1" >/dev/null 2>&1' _ "$unit_card"
  fi
  end
}

# A suite: its command runs in the bkf worktree; PASS when it exits 0.
suite() {
  local name=$1 log
  log=$work/suite-$(echo "$name" | tr -c 'a-z0-9' '-').log
  shift
  if (cd "$bkf_root" && "$@") >"$log" 2>&1; then
    echo "PASS $name"
  else
    echo "FAIL $name: exit $? (last line: $(tail -n 1 "$log" | tr -d '\r'))"
    failed=1
  fi
}

case_no_leftovers() {
  begin "no leftovers"
  local tmux_ls_after real_tasks_after
  t kill-server 2>/dev/null
  check "the throwaway tmux server is gone" bash -c '! command tmux -L "$1" ls >/dev/null 2>&1' _ "$sock"
  tmux_ls_after=$(command tmux ls -F '#{session_name}' 2>&1 | sort)
  eq "$tmux_ls_after" "$tmux_ls_before" "the user's default tmux server has no new session"
  real_tasks_after=$(ls -A "$real_tasks" 2>/dev/null | sort)
  eq "$real_tasks_after" "$real_tasks_before" "the real task store has nothing new"
  end
}

# ---- Run the cases.

if [ -n "$bkf_missing" ]; then
  for c in "handoff from inside tmux" "handoff with parent" "task session hook" "app-style launch from outside tmux" \
    "delegate run" "merge queue" "plan run"; do
    skip "$c" "$bkf_missing"
  done
  skip "bkf suites" "$bkf_missing"
else
  t new-session -d -s main -n boot "sleep 3600"
  case_handoff
  case_handoff_parent
  case_hook
  case_app_style
  case_delegate
  case_merge_queue
  case_plan

  if [ -n "${AGENTIC_ROOT:-}" ] && [ -d "$AGENTIC_ROOT" ]; then
    app_log=$work/app-contract.log
    (cd "$AGENTIC_ROOT" && AGENTIC_BKF_LIVE="$work/bin/bkf" swift run AgenticFoundationRunner >"$app_log" 2>&1)
    contract_rc=$?
    live_lines=$(grep -c '^[A-Z]* bkf live' "$app_log")
    live_bad=$(grep '^[A-Z]* bkf live' "$app_log" | grep -v '^PASS ' | head -3)
    if [ "$contract_rc" -eq 0 ] && [ "$live_lines" -gt 0 ] && [ -z "$live_bad" ]; then
      echo "PASS app contract"
    else
      echo "FAIL app contract: exit $contract_rc, $live_lines bkf live lines, not passing: ${live_bad:-none} (log $app_log)"
      failed=1
    fi
    app_build_log=$work/app-build.log
    (cd "$AGENTIC_ROOT" && scripts/check.sh >"$app_build_log" 2>&1)
    if [ $? -eq 0 ]; then echo "PASS app build"; else echo "FAIL app build: $(tail -n 1 "$app_build_log") (log $app_build_log)"; failed=1; fi
  else
    skip "app contract" "set AGENTIC_ROOT to the Agentic checkout to run it"
    skip "app build" "set AGENTIC_ROOT to the Agentic checkout to run it"
  fi

  suite "bkf tooling tests" env PYTHONPATH=bkf/tooling "$py" -m unittest discover -s bkf/tooling/tests
  suite "harness tests" env PYTHONPATH=agent-skills/harness python3 -m unittest discover -s agent-skills/harness/tests
  suite "harness inject shell test" bash agent-skills/harness/tests/test-inject.sh
  suite "agentic-work tests" env PYTHONPATH=agent-skills/harness python3 -m unittest discover -s agent-skills/skills/agentic-work/tests
  suite "agentic-work delegate shell test" bash agent-skills/skills/agentic-work/tests/test-delegate-run.sh
  suite "agentic-work plan gate shell test" bash agent-skills/skills/agentic-work/tests/test-plan-run-gate.sh
  suite "bkf skills check" bkf skills --check .
  suite "bkf validate" bkf validate .
fi

case_no_leftovers
exit "$failed"

#!/usr/bin/env bash
# Tests delegate-run.sh with a fake `codex`, in a throwaway repository: no model is called.
# Usage: test-delegate-run.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/../scripts/delegate-run.sh
work=$(mktemp -d "${TMPDIR:-/tmp}/delegate-test.XXXXXX")
work=$(cd "$work" && pwd -P)
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

mkdir -p "$work/bin" "$work/repo" "$work/runs"
# The fake Codex writes a file in the directory it is given (-C) and records the model (-m) it got.
cat >"$work/bin/codex" <<'F'
#!/usr/bin/env bash
dir="" out="" model=""
while [ "$#" -gt 0 ]; do
  case "$1" in -C) dir=$2; shift 2 ;; -o) out=$2; shift 2 ;; -m) model=$2; shift 2 ;; -c|-s) shift 2 ;; *) shift ;; esac
done
if [ -n "${FAKE_REVIEW_VERDICT:-}" ]; then
  cat >/dev/null
  printf '%s\n' '## What I checked' '' '- patch' '- brief' '- result' '' \
    '## Problems' '' 'Fix the change.' '' "VERDICT: $FAKE_REVIEW_VERDICT" >"$out"
  printf '%s\n' '{"type":"thread.started","thread_id":"test-review"}' '{"type":"turn.completed","usage":{"input_tokens":1}}'
  exit 0
fi
echo "$model" >"$FAKE_MODEL"
echo started >"$FAKE_RUN_MARKER"
if [ -n "${FAKE_PROMPT:-}" ]; then cat >"$FAKE_PROMPT"; else cat >/dev/null; fi
bkf task show "$(cat "$FAKE_TASK_FILE")" | sed -n 's/^status: //p' >"$FAKE_STATUS_SEEN"
if [ -n "${FAKE_EXIT:-}" ]; then exit "$FAKE_EXIT"; fi
if [ -n "${FAKE_PREPARED:-}" ]; then
  if [ -f "$dir/prepared.txt" ]; then echo yes >"$FAKE_PREPARED"; else echo no >"$FAKE_PREPARED"; fi
fi
if [ -n "${FAKE_BASE_VISIBLE:-}" ] && [ -s "$FAKE_BASE_VISIBLE" ]; then echo yes >"$FAKE_BASE_SEEN"; fi
echo "made by the agent" >"$dir/made.txt"
# With FAKE_PONTE_GATE, the agent asks the bridge for the gate as its last step, or records that no bridge is there.
if [ -n "${FAKE_PONTE_GATE:-}" ]; then
  if [ -x "$dir/.plan-porteiro/ponte" ]; then
    "$dir/.plan-porteiro/ponte" gate >"$FAKE_PONTE_GATE" 2>&1; echo "exit=$?" >>"$FAKE_PONTE_GATE"
  else
    echo "no bridge" >"$FAKE_PONTE_GATE"
  fi
fi
echo done >"$out"
F
chmod +x "$work/bin/codex"
# The `bkf` shim runs this worktree's tooling, not the installed copy, with a task store of its own.
repo_root=$(git -C "$here" rev-parse --show-toplevel)
bkf_python="$(uv tool dir)/bkf-tooling/bin/python3"
cat >"$work/bin/bkf" <<SHIM
#!/usr/bin/env bash
PYTHONPATH="$repo_root/bkf/tooling" exec "$bkf_python" -m bkf_cli "\$@"
SHIM
chmod +x "$work/bin/bkf"
export PATH="$work/bin:$PATH" BKF_TASKS_DIR="$work/tasks"
unset BKF_TASK

# One field of a run's task card: <run folder> <dotted field, such as status or worktree.path>.
card_field() {
  bkf task show "$(cat "$1/task")" --json | python3 -c '
import json, sys
value = json.load(sys.stdin)
for key in sys.argv[1].split("."):
    value = value[key]
print("" if value is None else value)' "$2"
}

git -C "$work/repo" init -q
git -C "$work/repo" config user.email t@example.com
git -C "$work/repo" config user.name t
echo base >"$work/repo/file.txt"
git -C "$work/repo" add file.txt
git -C "$work/repo" commit -qm base
printf '# Brief\n\nMake made.txt.\n' >"$work/brief.md"

run() { # <name> [env assignments...]; runs the script inside the repo, with the brief in $BRIEF_FILE (default $work/brief.md)
  local name=$1; shift
  local brief=${BRIEF_FILE:-$work/brief.md}
  rm -f "$work/$name.agent-ran" "$work/$name.prompt" "$work/$name.prepared" "$work/$name.base.seen" "$work/$name.status.seen"
  (cd "$work/repo" && env -u DELEGATE_IN_PLACE -u DELEGATE_RERUN -u HARNESS_BRIDGE_BASE_FILE \
    -u HARNESS_BRIDGE_LOG -u HARNESS_BRIDGE_UNIT -u DELEGATE_UNIT_DIR -u HARNESS_BRIDGE_RECEIPT_DIR \
    -u HARNESS_BRIDGE_GATE_BRIEF -u BKF_TASK PATH="$work/bin:$PATH" DELEGATE_RUNS_DIR="$work/runs" FAKE_MODEL="$work/model.txt" \
    FAKE_RUN_MARKER="$work/$name.agent-ran" FAKE_PROMPT="$work/$name.prompt" \
    FAKE_PREPARED="$work/$name.prepared" FAKE_BASE_VISIBLE="$work/runs/repo/$name/base" \
    FAKE_BASE_SEEN="$work/$name.base.seen" FAKE_TASK_FILE="$work/runs/repo/$name/task" \
    FAKE_STATUS_SEEN="$work/$name.status.seen" \
    "$@" \
    bash "$script" "$name" "$brief") >"$work/out.txt" 2>"$work/err.txt"
}

plan_unit() (
  command=$1; shift
  cd "$work/repo" && PLAN_GUIDES="$here/../roles" bash "$here/../scripts/plan-unit.sh" \
    "$command" "$work/brief.md" --dir "$work/units" "$@"
)

# In place: the agent works in the checkout; the run folder holds the status, the base and the diff base to read.
plan_unit begin >"$work/begin.log" 2>&1 || { cat "$work/begin.log"; exit 1; }
unit_dir="$work/units/brief"
run inplace DELEGATE_IN_PLACE=1 DELEGATE_UNIT_DIR="$unit_dir"; code=$?
runs=$work/runs/repo/inplace
check "in place: exits 0" '[ $code -eq 0 ]'
check "in place: the agent's file is in the checkout" '[ -f "$work/repo/made.txt" ]'
check "in place: the card is in review" '[ "$(card_field "$runs" status)" = review ]'
check "in place: the card is a unit with the codex session" '[ "$(card_field "$runs" kind)" = unit ] && [ "$(card_field "$runs" session.agent)" = codex ]'
check "in place: the card's note counts the changed file" '[ "$(card_field "$runs" note)" = "1 files changed" ]'
check "in place: the card names the checkout and the run folder" '[ "$(card_field "$runs" worktree.path)" = "$work/repo" ] && [ "$(card_field "$runs" run_dir)" = "$runs" ]'
check "in place: the agent ran while the card was working" '[ "$(cat "$work/inplace.status.seen")" = working ]'
check "in place: the worktree is the checkout" '[ "$(cat "$runs/worktree")" = "$work/repo" ]'
check "in place: the base is recorded" '[ -s "$runs/base" ]'
check "in place: the status files are kept" '[ -f "$runs/status-before.txt" ] && grep -q made.txt "$runs/status-after.txt"'
check "in place: the default Codex model is used" '[ "$(cat "$work/model.txt")" = "gpt-6-luna" ]'
check "in place: the script prints the run folder" '[ "$(tail -1 "$work/out.txt")" = "$runs" ]'
check "role: the agent's prompt points to the implementation guide" 'grep -q "role guide: .*/roles/agentic-work-implementation.md" "$work/inplace.prompt"'
check "unit folder: holds the same card id even without a gate" 'cmp -s "$runs/task" "$unit_dir/task"'
rm "$work/repo/made.txt"

# A second launch with the same name is refused until DELEGATE_RERUN=1.
run inplace DELEGATE_IN_PLACE=1; code=$?
check "rerun: refused without DELEGATE_RERUN" '[ $code -ne 0 ] && grep -q DELEGATE_RERUN "$work/err.txt"'
old_task=$(cat "$runs/task")
for round in 2 3; do
  FAKE_REVIEW_VERDICT=back plan_unit check --review-model test >"$work/review.log" 2>&1; code=$?
  check "back before round $round: the card stays in review" '[ $code -eq 1 ] && [ "$(card_field "$runs" status)" = review ]'
  run inplace DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1 DELEGATE_UNIT_DIR="$unit_dir"; code=$?
  check "round $round: a card in review is reused" '[ $code -eq 0 ] && [ "$(cat "$runs/task")" = "$old_task" ] && [ "$(card_field "$runs" status)" = review ]'
  check "round $round: the card is working while the agent runs" '[ "$(cat "$work/inplace.status.seen")" = working ]'
done
FAKE_REVIEW_VERDICT=pass plan_unit check --review-model test >"$work/review.log" 2>&1; code=$?
check "back, back, pass: only one card exists and it is done" '[ $code -eq 0 ] && [ "$(bkf task list --kind unit)" = "$old_task  done  unit  inplace" ]'
run inplace DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1 DELEGATE_UNIT_DIR="$unit_dir"; code=$?
check "rerun: a done card is replaced" '[ $code -eq 0 ] && [ "$(cat "$runs/task")" != "$old_task" ] && [ "$(card_field "$runs" status)" = review ]'
check "unit folder: points to the replacement card" 'cmp -s "$runs/task" "$unit_dir/task"'
removed_task=$(cat "$runs/task")
bkf task delete "$removed_task"
run inplace DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1; code=$?
check "rerun: a deleted card is replaced" '[ $code -eq 0 ] && [ "$(cat "$runs/task")" != "$removed_task" ] && [ "$(card_field "$runs" status)" = review ]'
rm -f "$work/repo/made.txt"

# Worktree: the agent works in a sibling worktree on its own branch and the checkout stays clean.
run isolated; code=$?
wt=$(cat "$work/runs/repo/isolated/worktree")
check "worktree: exits 0" '[ $code -eq 0 ]'
check "worktree: the agent's file is in the worktree only" '[ -f "$wt/made.txt" ] && [ ! -e "$work/repo/made.txt" ]'
# The worktree is the card's: <repo>/.claude/worktrees/<slug> on branch task/<slug>, the slug of the title and the card id.
isolated_slug="isolated-$(cat "$work/runs/repo/isolated/task" | tail -c 5)"
check "worktree: the path is <repo>/.claude/worktrees/<slug>" '[ "$wt" = "$work/repo/.claude/worktrees/$isolated_slug" ] && [ "$(card_field "$work/runs/repo/isolated" worktree.path)" = "$wt" ]'
check "worktree: the branch is task/<slug>" '[ "$(git -C "$wt" branch --show-current)" = "task/$isolated_slug" ] && [ "$(card_field "$work/runs/repo/isolated" worktree.branch)" = "task/$isolated_slug" ]'
check "worktree: the diffstat names the file" 'grep -q made.txt "$work/runs/repo/isolated/diffstat.txt"'
check "worktree: the card is in review" '[ "$(card_field "$work/runs/repo/isolated" status)" = review ]'
check "worktree without bridge: delegated brief has no ponte section" '! grep -q "Command bridge" "$work/runs/repo/isolated/brief.md"'

# A newly created worktree is prepared from the committed declaration before the fake agent starts.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["echo prepared > prepared.txt"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare worktree setup'
run prepared; code=$?
wt=$(cat "$work/runs/repo/prepared/worktree")
check "prepare: exits 0" '[ $code -eq 0 ]'
check "prepare: command ran before the agent" '[ "$(cat "$work/prepared.prepared")" = yes ] && [ -f "$wt/prepared.txt" ]'
check "prepare: output is recorded" 'grep -q "worktree.prepare: 1 command(s) passed" "$work/runs/repo/prepared/prepare.log"'
check "prepare: base exists before agent launch" '[ -s "$work/runs/repo/prepared/base" ] && [ -f "$work/prepared.base.seen" ]'

# A rerun of a failed card reuses its worktree without running preparation again.
run prepared-failed FAKE_EXIT=3; code=$?
failed_wt=$(cat "$work/runs/repo/prepared-failed/worktree")
rm "$failed_wt/prepared.txt"
run prepared-failed DELEGATE_RERUN=1; code=$?
check "rerun of a failed card: the worktree is reused and not prepared again" \
  '[ $code -eq 0 ] && [ "$(cat "$work/prepared-failed.prepared")" = no ] && [ ! -e "$failed_wt/prepared.txt" ] && [ "$(cat "$work/runs/repo/prepared-failed/worktree")" = "$failed_wt" ]'

# A failing preparation marks the run and never launches an agent.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["exit 7"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare failing setup'
run prepare-fail; code=$?
check "prepare failure: the card is failed with note prepare-failed" '[ "$(card_field "$work/runs/repo/prepare-fail" status)" = failed ] && [ "$(card_field "$work/runs/repo/prepare-fail" note)" = prepare-failed ]'
check "prepare failure: no agent is launched" '[ $code -ne 0 ] && [ ! -e "$work/prepare-fail.agent-ran" ]'
check "prepare failure: reports its log and run folder" 'grep -q prepare.log "$work/err.txt" && [ "$(tail -1 "$work/out.txt")" = "$work/runs/repo/prepare-fail" ]'

# A failing agent marks its card failed with the exit status; a rerun reuses that failed card.
run failing DELEGATE_IN_PLACE=1 FAKE_EXIT=3; code=$?
fail_task=$(cat "$work/runs/repo/failing/task")
check "agent failure: exits with the agent's status" '[ $code -eq 3 ]'
check "agent failure: the card is failed with the exit status" '[ "$(card_field "$work/runs/repo/failing" status)" = failed ] && [ "$(card_field "$work/runs/repo/failing" exit)" = 3 ]'
run failing DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1; code=$?
check "rerun of a failed card: the same card is reused" '[ $code -eq 0 ] && [ "$(cat "$work/runs/repo/failing/task")" = "$fail_task" ]'
check "rerun of a failed card: the card is working while the agent runs" '[ "$(cat "$work/failing.status.seen")" = working ]'
check "rerun of a failed card: the card ends in review" '[ "$(card_field "$work/runs/repo/failing" status)" = review ] && [ -z "$(card_field "$work/runs/repo/failing" exit)" ]'

# The base-listed bridge is described to the agent and the run-base file is already present.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["echo prepared > prepared.txt"]},"bridge":{"pnpmScripts":["^test$"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare command bridge'
run bridged; code=$?
check "bridge: delegated brief explains ponte" '[ $code -eq 0 ] && grep -q "Command bridge" "$work/runs/repo/bridged/brief.md" && grep -q "ponte pnpm" "$work/runs/repo/bridged/brief.md"'
check "bridge: base file exists at launch" '[ -s "$work/runs/repo/bridged/base" ] && [ -f "$work/bridged.base.seen" ]'

# In-place mode never applies the worktree preparation commands.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["echo should-not-exist > in-place-prepared.txt"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare in-place setup'
run inplace-prepare DELEGATE_IN_PLACE=1; code=$?
check "in place: does not run worktree prepare" '[ $code -eq 0 ] && [ ! -e "$work/repo/in-place-prepared.txt" ] && [ ! -e "$work/runs/repo/inplace-prepare/prepare.log" ]'

# A gate in the brief and a unit folder: the agent's `ponte gate` writes the receipt there, though .plan-run.json has no bridge.
printf '# Brief\n\nMake made.txt.\n\n```gate\ntest -f made.txt\n```\n' >"$work/gate-brief.md"
rm -rf "$work/unit"; mkdir -p "$work/unit"
BRIEF_FILE="$work/gate-brief.md" run gated DELEGATE_UNIT_DIR="$work/unit" FAKE_PONTE_GATE="$work/gated.ponte"; code=$?
check "receipt: exits 0" '[ $code -eq 0 ]'
check "receipt: the brief names the gate receipt section" 'grep -q "^## Gate receipt" "$work/runs/repo/gated/brief.md"'
check "receipt: the bridge is on without a bridge in .plan-run.json" '! grep -q "Command bridge" "$work/runs/repo/gated/brief.md" && [ "$(tail -1 "$work/gated.ponte")" = exit=0 ]'
check "receipt: ponte gate wrote the receipt in the unit folder" '[ -f "$work/unit/receipt/receipt.json" ] && grep -q "\"red\": 0" "$work/unit/receipt/receipt.json"'
check "receipt: ponte gate printed the gate report to the agent" 'grep -q "test -f made.txt" "$work/gated.ponte"'

# Without DELEGATE_UNIT_DIR the brief has no receipt section, no bridge runs and nothing is written.
BRIEF_FILE="$work/gate-brief.md" run gatedoff FAKE_PONTE_GATE="$work/gatedoff.ponte"; code=$?
check "no unit folder: exits 0" '[ $code -eq 0 ]'
check "no unit folder: the brief has no gate receipt section" '! grep -q "Gate receipt" "$work/runs/repo/gatedoff/brief.md"'
check "no unit folder: no bridge is started" 'grep -qx "no bridge" "$work/gatedoff.ponte"'

# A run launched from a task window (BKF_TASK set) makes its card a child of that task.
parent=$(bkf task new --repo "$work/repo" --title parent --no-parent)
run parented BKF_TASK="$parent"; code=$?
check "parent: the card's parent is the task the run was launched from" '[ $code -eq 0 ] && [ "$(card_field "$work/runs/repo/parented" parent)" = "$parent" ]'

git -C "$work/repo" worktree remove --force "$wt" >/dev/null 2>&1
exit "$fail"

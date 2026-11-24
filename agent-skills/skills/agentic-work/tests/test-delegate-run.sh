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
export PATH="$work/bin:$PATH"
unset BKF_TASK

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
  local repo=${RUN_REPO:-$work/repo}
  rm -f "$work/$name.agent-ran" "$work/$name.prompt" "$work/$name.prepared" "$work/$name.base.seen"
  (cd "$repo" && env -u DELEGATE_IN_PLACE -u DELEGATE_RERUN -u HARNESS_BRIDGE_BASE_FILE \
    -u HARNESS_BRIDGE_LOG -u HARNESS_BRIDGE_UNIT -u DELEGATE_UNIT_DIR -u HARNESS_BRIDGE_RECEIPT_DIR \
    -u HARNESS_BRIDGE_GATE_BRIEF -u BKF_TASK PATH="$work/bin:$PATH" DELEGATE_RUNS_DIR="$work/runs" FAKE_MODEL="$work/model.txt" \
    FAKE_RUN_MARKER="$work/$name.agent-ran" FAKE_PROMPT="$work/$name.prompt" \
    FAKE_PREPARED="$work/$name.prepared" FAKE_BASE_VISIBLE="$work/runs/repo/$name/base" \
    FAKE_BASE_SEEN="$work/$name.base.seen" \
    "$@" \
    bash "$script" "$name" "$brief") >"$work/out.txt" 2>"$work/err.txt"
}

plan_unit() (
  command=$1; shift
  cd "$work/repo" && PLAN_GUIDES="$here/../roles" bash "$here/../scripts/plan-unit.sh" \
    "$command" "$work/brief.md" --dir "$work/units" "$@"
)

# In place: the agent works in the checkout; the run folder holds the base, the status files and the exit status.
plan_unit begin >"$work/begin.log" 2>&1 || { cat "$work/begin.log"; exit 1; }
unit_dir="$work/units/brief"
run inplace DELEGATE_IN_PLACE=1 DELEGATE_UNIT_DIR="$unit_dir"; code=$?
runs=$work/runs/repo/inplace
check "in place: exits 0" '[ $code -eq 0 ]'
check "in place: the agent's file is in the checkout" '[ -f "$work/repo/made.txt" ]'
check "in place: the run folder records exit 0" '[ "$(cat "$runs/exit")" = 0 ]'
check "in place: no worktree is made" '[ ! -e "$runs/worktree" ]'
check "in place: the base is recorded" '[ -s "$runs/base" ]'
check "in place: the status files are kept" '[ -f "$runs/status-before.txt" ] && grep -q made.txt "$runs/status-after.txt"'
check "in place: the default Codex model is used" '[ "$(cat "$work/model.txt")" = "gpt-6-luna" ]'
check "in place: the script prints the run folder" '[ "$(tail -1 "$work/out.txt")" = "$runs" ]'
check "role: the agent's prompt points to the implementation guide" 'grep -q "role guide: .*/roles/agentic-work-implementation.md" "$work/inplace.prompt"'
rm "$work/repo/made.txt"

# In-place from a linked worktree: the run folder uses the main repository name, while the agent stays in the linked worktree.
mkdir -p "$work/linked-tree"
git -C "$work/repo" worktree add --detach "$work/linked-tree/worktree" HEAD >/dev/null
linked_repo=$work/linked-tree/worktree
RUN_REPO="$linked_repo" run linked-inplace DELEGATE_IN_PLACE=1; code=$?
linked_runs=$work/runs/repo/linked-inplace
check "linked worktree in place: exits 0" '[ $code -eq 0 ]'
check "linked worktree in place: the run folder uses the main repository name" '[ -d "$linked_runs" ] && [ ! -e "$work/runs/worktree/linked-inplace" ]'
check "linked worktree in place: the agent works in the linked worktree" '[ -f "$linked_repo/made.txt" ] && [ ! -e "$work/repo/made.txt" ]'
check "linked worktree in place: the run folder records its exit" '[ "$(cat "$linked_runs/exit")" = 0 ]'
rm "$linked_repo/made.txt"

# A second launch with the same name is refused until DELEGATE_RERUN=1.
run inplace DELEGATE_IN_PLACE=1; code=$?
check "rerun: refused without DELEGATE_RERUN" '[ $code -ne 0 ] && grep -q DELEGATE_RERUN "$work/err.txt"'
for round in 2 3; do
  FAKE_REVIEW_VERDICT=back plan_unit check --review-model test >"$work/review.log" 2>&1; code=$?
  check "back before round $round: the reviewer sends the unit back" '[ $code -eq 1 ]'
  run inplace DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1 DELEGATE_UNIT_DIR="$unit_dir"; code=$?
  check "round $round: the run folder is reused and the agent runs again" '[ $code -eq 0 ] && [ "$(cat "$runs/exit")" = 0 ] && [ -f "$work/repo/made.txt" ]'
  rm -f "$work/repo/made.txt"
done
FAKE_REVIEW_VERDICT=pass plan_unit check --review-model test >"$work/review.log" 2>&1; code=$?
check "back, back, pass: the reviewer passes the unit" '[ $code -eq 0 ]'
run inplace DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1 DELEGATE_UNIT_DIR="$unit_dir"; code=$?
check "rerun after a pass: the agent runs again" '[ $code -eq 0 ] && [ "$(cat "$runs/exit")" = 0 ]'
rm -f "$work/repo/made.txt"

# Worktree: the agent works in <run>/worktree on its own branch and the checkout stays clean.
run isolated; code=$?
wt=$work/runs/repo/isolated/worktree
check "worktree: exits 0" '[ $code -eq 0 ]'
check "worktree: the agent's file is in the worktree only" '[ -f "$wt/made.txt" ] && [ ! -e "$work/repo/made.txt" ]'
check "worktree: the worktree is <run>/worktree" '[ -d "$wt" ] && git -C "$work/repo" worktree list | grep -q "$wt"'
check "worktree: the branch is delegate/<name>" '[ "$(git -C "$wt" branch --show-current)" = "delegate/isolated" ]'
check "worktree: the diffstat names the file" 'grep -q made.txt "$work/runs/repo/isolated/diffstat.txt"'
check "worktree: the run folder records exit 0" '[ "$(cat "$work/runs/repo/isolated/exit")" = 0 ]'
check "worktree without bridge: delegated brief has no ponte section" '! grep -q "Command bridge" "$work/runs/repo/isolated/brief.md"'

# A newly created worktree is prepared from the committed declaration before the fake agent starts.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["echo prepared > prepared.txt"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare worktree setup'
run prepared; code=$?
wt=$work/runs/repo/prepared/worktree
check "prepare: exits 0" '[ $code -eq 0 ]'
check "prepare: command ran before the agent" '[ "$(cat "$work/prepared.prepared")" = yes ] && [ -f "$wt/prepared.txt" ]'
check "prepare: output is recorded" 'grep -q "worktree.prepare: 1 command(s) passed" "$work/runs/repo/prepared/prepare.log"'
check "prepare: base exists before agent launch" '[ -s "$work/runs/repo/prepared/base" ] && [ -f "$work/prepared.base.seen" ]'

# A rerun of a failed run reuses its worktree without running preparation again.
run prepared-failed FAKE_EXIT=3; code=$?
failed_wt=$work/runs/repo/prepared-failed/worktree
rm "$failed_wt/prepared.txt"
run prepared-failed DELEGATE_RERUN=1; code=$?
check "rerun of a failed run: the worktree is reused and not prepared again" \
  '[ $code -eq 0 ] && [ "$(cat "$work/prepared-failed.prepared")" = no ] && [ ! -e "$failed_wt/prepared.txt" ] && [ -d "$failed_wt" ]'

# A failing preparation never launches an agent.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["exit 7"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare failing setup'
run prepare-fail; code=$?
check "prepare failure: no agent is launched" '[ $code -ne 0 ] && [ ! -e "$work/prepare-fail.agent-ran" ]'
check "prepare failure: reports its log and run folder" 'grep -q prepare.log "$work/err.txt" && [ "$(tail -1 "$work/out.txt")" = "$work/runs/repo/prepare-fail" ]'

# A failing agent records its exit status in the run folder; a rerun of that run works again.
run failing DELEGATE_IN_PLACE=1 FAKE_EXIT=3; code=$?
check "agent failure: exits with the agent's status" '[ $code -eq 3 ]'
check "agent failure: the run folder records exit 3" '[ "$(cat "$work/runs/repo/failing/exit")" = 3 ]'
run failing DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1; code=$?
check "rerun of a failed run: the run folder is reused" '[ $code -eq 0 ] && [ -s "$work/runs/repo/failing/base" ]'
check "rerun of a failed run: the agent ran and the exit status is replaced" '[ -f "$work/failing.agent-ran" ] && [ "$(cat "$work/runs/repo/failing/exit")" = 0 ]'

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

# Launched through a symlinked skills folder (as ~/.claude/skills is), the script still finds the harness: the gate receipt is enabled.
mkdir -p "$work/linked" "$work/linked-unit"
ln -sfn "$here/../.." "$work/linked/skills"
script=$work/linked/skills/agentic-work/scripts/delegate-run.sh
BRIEF_FILE="$work/gate-brief.md" run linked DELEGATE_UNIT_DIR="$work/linked-unit" FAKE_PONTE_GATE="$work/linked.ponte"; code=$?
script=$here/../scripts/delegate-run.sh
check "symlink: exits 0" '[ $code -eq 0 ]'
check "symlink: the brief names the gate receipt section" 'grep -q "^## Gate receipt" "$work/runs/repo/linked/brief.md"'
check "symlink: ponte gate wrote the receipt in the unit folder" '[ -f "$work/linked-unit/receipt/receipt.json" ]'

# Without DELEGATE_UNIT_DIR the brief has no receipt section, no bridge runs and nothing is written.
BRIEF_FILE="$work/gate-brief.md" run gatedoff FAKE_PONTE_GATE="$work/gatedoff.ponte"; code=$?
check "no unit folder: exits 0" '[ $code -eq 0 ]'
check "no unit folder: the brief has no gate receipt section" '! grep -q "Gate receipt" "$work/runs/repo/gatedoff/brief.md"'
check "no unit folder: no bridge is started" 'grep -qx "no bridge" "$work/gatedoff.ponte"'

git -C "$work/repo" worktree remove --force "$wt" >/dev/null 2>&1
git -C "$work/repo" worktree remove --force "$linked_repo" >/dev/null 2>&1
exit "$fail"

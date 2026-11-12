#!/usr/bin/env bash
# Tests delegate-run.sh with a fake `codex` and a fake `claude`, in a throwaway repository: no model is called.
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
echo "$model" >"$FAKE_MODEL"
echo started >"$FAKE_RUN_MARKER"
if [ -n "${FAKE_PROMPT:-}" ]; then cat >"$FAKE_PROMPT"; else cat >/dev/null; fi
if [ -n "${FAKE_PREPARED:-}" ]; then
  if [ -f "$dir/prepared.txt" ]; then echo yes >"$FAKE_PREPARED"; else echo no >"$FAKE_PREPARED"; fi
fi
if [ -n "${FAKE_BASE_VISIBLE:-}" ] && [ -s "$FAKE_BASE_VISIBLE" ]; then echo yes >"$FAKE_BASE_SEEN"; fi
echo "made by the agent" >"$dir/made.txt"
echo done >"$out"
F
chmod +x "$work/bin/codex"
# The fake Claude reads the prompt, writes the same file in its working directory and prints a result event.
cat >"$work/bin/claude" <<'F'
#!/usr/bin/env bash
model=""
while [ "$#" -gt 0 ]; do
  case "$1" in --model) model=$2; shift 2 ;; *) shift ;; esac
done
cat >/dev/null
echo "$model" >"$FAKE_MODEL"
echo "made by the agent" >made.txt
echo '{"type":"result","subtype":"success","result":"done"}'
F
chmod +x "$work/bin/claude"

git -C "$work/repo" init -q
git -C "$work/repo" config user.email t@example.com
git -C "$work/repo" config user.name t
echo base >"$work/repo/file.txt"
git -C "$work/repo" add file.txt
git -C "$work/repo" commit -qm base
printf '# Brief\n\nMake made.txt.\n' >"$work/brief.md"

run() { # <name> [env assignments...]; runs the script inside the repo
  local name=$1; shift
  rm -f "$work/$name.agent-ran" "$work/$name.prompt" "$work/$name.prepared" "$work/$name.base.seen"
  (cd "$work/repo" && env -u DELEGATE_IN_PLACE -u DELEGATE_RERUN -u HARNESS_BRIDGE_BASE_FILE \
    -u HARNESS_BRIDGE_LOG -u HARNESS_BRIDGE_UNIT PATH="$work/bin:$PATH" DELEGATE_RUNS_DIR="$work/runs" FAKE_MODEL="$work/model.txt" \
    FAKE_RUN_MARKER="$work/$name.agent-ran" FAKE_PROMPT="$work/$name.prompt" \
    FAKE_PREPARED="$work/$name.prepared" FAKE_BASE_VISIBLE="$work/runs/repo/$name/base" \
    FAKE_BASE_SEEN="$work/$name.base.seen" \
    "$@" \
    bash "$script" "$name" "$work/brief.md") >"$work/out.txt" 2>"$work/err.txt"
}

# In place: the agent works in the checkout; the run folder holds the status, the base and the diff base to read.
run inplace DELEGATE_IN_PLACE=1; code=$?
runs=$work/runs/repo/inplace
check "in place: exits 0" '[ $code -eq 0 ]'
check "in place: the agent's file is in the checkout" '[ -f "$work/repo/made.txt" ]'
check "in place: status is exit=0" '[ "$(cat "$runs/status")" = "exit=0" ]'
check "in place: the worktree is the checkout" '[ "$(cat "$runs/worktree")" = "$work/repo" ]'
check "in place: the base is recorded" '[ -s "$runs/base" ]'
check "in place: the status files are kept" '[ -f "$runs/status-before.txt" ] && grep -q made.txt "$runs/status-after.txt"'
check "in place: the default Codex model is used" '[ "$(cat "$work/model.txt")" = "gpt-6-luna" ]'
check "in place: the script prints the run folder" '[ "$(tail -1 "$work/out.txt")" = "$runs" ]'
rm "$work/repo/made.txt"

# A second launch with the same name is refused until DELEGATE_RERUN=1.
run inplace DELEGATE_IN_PLACE=1; code=$?
check "rerun: refused without DELEGATE_RERUN" '[ $code -ne 0 ] && grep -q DELEGATE_RERUN "$work/err.txt"'
run inplace DELEGATE_IN_PLACE=1 DELEGATE_RERUN=1; code=$?
check "rerun: allowed with DELEGATE_RERUN=1" '[ $code -eq 0 ]'
rm -f "$work/repo/made.txt"

# Worktree: the agent works in a sibling worktree on its own branch and the checkout stays clean.
run isolated; code=$?
wt=$(cat "$work/runs/repo/isolated/worktree")
check "worktree: exits 0" '[ $code -eq 0 ]'
check "worktree: the agent's file is in the worktree only" '[ -f "$wt/made.txt" ] && [ ! -e "$work/repo/made.txt" ]'
check "worktree: the branch is delegate/<name>" '[ "$(git -C "$wt" branch --show-current)" = "delegate/isolated" ]'
check "worktree: the diffstat names the file" 'grep -q made.txt "$work/runs/repo/isolated/diffstat.txt"'
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

# A rerun reuses the prepared worktree without running preparation again.
rm "$wt/prepared.txt"
run prepared DELEGATE_RERUN=1; code=$?
check "rerun: existing worktree is not prepared again" '[ $code -eq 0 ] && [ "$(cat "$work/prepared.prepared")" = no ] && [ ! -e "$wt/prepared.txt" ]'

# A failing preparation marks the run and never launches an agent.
cat >"$work/repo/.plan-run.json" <<'JSON'
{"worktree":{"prepare":["exit 7"]}}
JSON
git -C "$work/repo" add .plan-run.json
git -C "$work/repo" commit -qm 'declare failing setup'
run prepare-fail; code=$?
check "prepare failure: status is prepare-failed" '[ "$(cat "$work/runs/repo/prepare-fail/status")" = prepare-failed ]'
check "prepare failure: no agent is launched" '[ $code -ne 0 ] && [ ! -e "$work/prepare-fail.agent-ran" ]'
check "prepare failure: reports its log and run folder" 'grep -q prepare.log "$work/err.txt" && [ "$(tail -1 "$work/out.txt")" = "$work/runs/repo/prepare-fail" ]'

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

# Claude backend: the default model is Claude's and the same file appears.
run viaclaude DELEGATE_IN_PLACE=1 HARNESS_BACKEND=claude; code=$?
check "claude: exits 0" '[ $code -eq 0 ]'
check "claude: the default model is sonnet" '[ "$(cat "$work/model.txt")" = "sonnet" ]'
check "claude: the agent's file is in the checkout" '[ -f "$work/repo/made.txt" ]'

git -C "$work/repo" worktree remove --force "$wt" >/dev/null 2>&1
exit "$fail"

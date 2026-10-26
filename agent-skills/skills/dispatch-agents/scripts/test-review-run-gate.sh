#!/usr/bin/env bash
# Tests the gate step of review-run.sh with a fake `codex`, in a throwaway repository: no model is called.
# Usage: test-review-run-gate.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/review-run-gate-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

# A fake codex. A brief starting "# Brief: check" writes checked.md, any other brief writes report.md, both in the
# agent's folder. It saves a copy of the brief and of the folder listing in $FAKE_STATE.
mkdir -p "$work/bin" "$work/guides" "$work/state"
touch "$work/guides/code-review-axis.md" "$work/guides/code-review-check.md"
cat >"$work/bin/codex" <<'EOF'
#!/usr/bin/env bash
dir="" out=""
while [ "$#" -gt 0 ]; do
  case "$1" in -C) dir=$2; shift 2 ;; -o) out=$2; shift 2 ;; -c|-m|-s) shift 2 ;; *) shift ;; esac
done
prompt=$(cat)
tag=$(basename "$(dirname "$dir")")-$(basename "$dir")
printf '%s\n' "$prompt" >"$FAKE_STATE/brief-$tag.md"
ls "$dir" >"$FAKE_STATE/ls-$tag.txt"
case "$prompt" in
  "# Brief: check"*) echo "no findings" >"$dir/checked.md" ;;
  *) echo "no findings" >"$dir/report.md" ;;
esac
echo done >"$out"
printf '%s\n' '{"type":"turn.completed"}'
EOF
chmod +x "$work/bin/codex"

new_repo() { # <name>
  case_dir=$work/$1; mkdir -p "$case_dir/repo" "$case_dir/runs"
  git -C "$case_dir/repo" init -q . && git -C "$case_dir/repo" config user.email t@t && git -C "$case_dir/repo" config user.name t
  echo base >"$case_dir/repo/a.txt"
  git -C "$case_dir/repo" add -A && git -C "$case_dir/repo" commit -qm init
  echo change >>"$case_dir/repo/a.txt"
  echo "# spec" >"$case_dir/spec.md"
}

run_start() { # <name> [review-run.sh options]...   (the target is always working-tree)
  local n=$1; shift
  (cd "$case_dir/repo" && PATH="$work/bin:$PATH" FAKE_STATE="$work/state" REVIEW_RUNS_DIR="$case_dir/runs" REVIEW_GUIDES="$work/guides" \
    "$here/review-run.sh" start -s "$case_dir/spec.md" "$@" "$n" working-tree) >"$case_dir/out.txt" 2>&1
  code=$?
  run=$case_dir/runs/$n
}

# 1. A green gate is run by the script, recorded, handed to the agents and shown in the report above the axes.
new_repo green
run_start r -g 'echo hello-from-gate'
check "green: the run is ready" "[ $code -eq 0 ] && grep -q READY '$case_dir/out.txt'"
check "green: the command, its output and exit code 0 are recorded" "grep -q 'echo hello-from-gate' '$run/00-input/gate.md' && grep -q 'hello-from-gate' '$run/00-input/gate.md' && grep -q 'exit code: 0' '$run/00-input/gate.md'"
check "green: the reviewer and the checker folders hold gate.md" "[ -s '$run/01-review/spec/gate.md' ] && [ -s '$run/02-check/spec/gate.md' ]"
check "green: the briefs point to gate.md" "grep -q 'gate.md' '$run/01-review/spec/brief.md' && grep -q 'gate.md' '$run/02-check/spec/brief.md'"
check "green: the report shows the gate before the first axis" "awk '/^## Gate/{v=NR} /^## Spec/{s=NR} END{exit !(v && s && v<s)}' '$run/report.md'"
check "green: the report says all green" "grep -q 'all green' '$run/report.md'"

# 2. A red gate does not stop the review, and the report says so with the command and the exit code.
new_repo red
run_start r -g 'echo before; exit 3' -g 'true'
check "red: the run still finishes" "[ $code -eq 0 ] && [ -s '$run/report.md' ]"
check "red: the exit code of the failing command is recorded" "grep -q 'exit code: 3' '$run/00-input/gate.md'"
check "red: the report names the red command" "grep -q 'RED' '$run/report.md' && grep -q 'exit code: 3' '$run/report.md'"
check "red: a later green command is still run and recorded" "grep -c 'exit code:' '$run/00-input/gate.md' | grep -q '^2$'"

# 3. No gate is a gap, not a pass.
new_repo none
run_start r
check "none: the run is ready" "[ $code -eq 0 ] && grep -q READY '$case_dir/out.txt'"
check "none: the report says nothing was run and calls it a gap" "grep -q 'No gate commands' '$run/report.md' && grep -q 'gap' '$run/report.md'"
check "none: the report does not say all green" "! grep -q 'all green' '$run/report.md'"

# 4. The gate runs in the repository under review, outside the agents.
new_repo cwd
run_start r -g 'pwd'
check "cwd: the command ran in the repository" "grep -q \"$(cd "$case_dir/repo" && pwd -P)\" '$run/00-input/gate.md'"
check "cwd: the reviewer already had gate.md when it started" "grep -q '^gate.md$' '$work/state/ls-01-review-spec.txt'"

# 5. A command that hangs is stopped at the limit and counts as red.
new_repo hang
(cd "$case_dir/repo" && REVIEW_GATE_TIMEOUT=1 PATH="$work/bin:$PATH" FAKE_STATE="$work/state" REVIEW_RUNS_DIR="$case_dir/runs" REVIEW_GUIDES="$work/guides" \
  "$here/review-run.sh" start -s "$case_dir/spec.md" -g 'sleep 30' r working-tree) >"$case_dir/out.txt" 2>&1
code=$?; run=$case_dir/runs/r
check "hang: the run finishes quickly instead of waiting" "[ $code -eq 0 ] && [ -s '$run/report.md' ]"
check "hang: the timeout is recorded as red" "grep -qi 'timed out' '$run/00-input/gate.md' && grep -q 'RED' '$run/report.md'"

# 6. resume does not run the gate again.
new_repo resume
run_start r -g "echo once >>$case_dir/gatecount"
rm -f "$run/.done-check" "$run/02-check/spec/checked.md" "$run/report.md"
(cd "$case_dir/repo" && PATH="$work/bin:$PATH" FAKE_STATE="$work/state" REVIEW_RUNS_DIR="$case_dir/runs" REVIEW_GUIDES="$work/guides" "$here/review-run.sh" resume r) >/dev/null 2>&1
check "resume: the gate ran once in all" "[ \"\$(wc -l <'$case_dir/gatecount')\" -eq 1 ]"
check "resume: the report is rebuilt with the gate" "grep -q '^## Gate' '$run/report.md'"

exit "$fail"

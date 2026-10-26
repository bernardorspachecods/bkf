#!/usr/bin/env bash
# Tests the review run board with a fake `codex`: no model is called.
# Usage: test-review-run-board.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/review-run-board-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

mkdir -p "$work/bin" "$work/guides"
touch "$work/guides/code-review-axis.md" "$work/guides/code-review-check.md"
cat >"$work/bin/codex" <<'EOF'
#!/usr/bin/env bash
dir="" out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -C) dir=$2; shift 2 ;;
    -o) out=$2; shift 2 ;;
    -c|-m|-s) shift 2 ;;
    *) shift ;;
  esac
done
prompt=$(cat)
[ -z "${FAKE_DELAY:-}" ] || /bin/sleep "$FAKE_DELAY"
if [ "${FAKE_FAIL:-}" = check ] && [[ "$prompt" == '# Brief: check of the '* ]]; then
  echo 'fake check failure' >&2
  exit 1
fi
case "$prompt" in
  '# Brief: Standards review'*|'# Brief: Spec review'*)
    printf 'No findings.\n' >"$dir/report.md"
    ;;
  '# Brief: check of the Standards findings'*|'# Brief: check of the Spec findings'*)
    printf 'No findings.\n' >"$dir/checked.md"
    ;;
  *)
    echo "unexpected fake codex prompt: $prompt" >&2
    exit 2
    ;;
esac
[ -z "$out" ] || printf 'fake response\n' >"$out"
printf '%s\n' '{"type":"turn.completed"}'
EOF
chmod +x "$work/bin/codex"

new_repo() { # <name>
  case_dir=$work/$1
  mkdir -p "$case_dir/repo" "$case_dir/runs"
  git -C "$case_dir/repo" init -q .
  git -C "$case_dir/repo" config user.email test@example.com
  git -C "$case_dir/repo" config user.name test
  printf 'base\n' >"$case_dir/repo/change.txt"
  git -C "$case_dir/repo" add change.txt
  git -C "$case_dir/repo" commit -qm init
  printf 'change\n' >>"$case_dir/repo/change.txt"
  printf '# Spec\n\nReview the change.\n' >"$case_dir/spec.md"
  printf '# Standards\n\nKeep changes clear.\n' >"$case_dir/standards.md"
}

run_start() { # <name> [env assignments...]
  local n=$1; shift
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" REVIEW_RUNS_DIR="$case_dir/runs" \
    REVIEW_GUIDES="$work/guides" "$@" \
    "$here/review-run.sh" start -s "$case_dir/spec.md" -d "$case_dir/standards.md" -2 "$n" working-tree) \
    >"$case_dir/stdout.txt" 2>"$case_dir/stderr.txt"
  code=$?
  run=$case_dir/runs/$n
}

run_board() { # <name>
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" REVIEW_RUNS_DIR="$case_dir/runs" \
    REVIEW_GUIDES="$work/guides" "$here/review-run.sh" board "$1") \
    >"$case_dir/board.txt" 2>"$case_dir/board.stderr"
  board_code=$?
}

# 1. Both axes, both second reviewers and both checkers finish.
new_repo finished
run_start finished FAKE_DELAY=0.15
finished_code=$code
finished_stdout=$(cat "$case_dir/stdout.txt")
run_board finished
check "finished: every step and axis agent is checked" '[ "$finished_code" -eq 0 ] && grep -qF "✓ Revisores" "$case_dir/board.txt" && grep -qF "✓ standards" "$case_dir/board.txt" && grep -qF "✓ standards-2" "$case_dir/board.txt" && grep -qF "✓ spec" "$case_dir/board.txt" && grep -qF "✓ spec-2" "$case_dir/board.txt" && grep -qF "✓ Verificação" "$case_dir/board.txt"'
check "finished: renderer errors do not change the run exit code" '[ "$finished_code" -eq 0 ] && [ -s "$run/report.md" ]'
check "finished: both checkers are checked" 'grep -qF "✓ standards" "$case_dir/board.txt" && grep -qF "✓ spec" "$case_dir/board.txt" && [ -s "$run/02-check/standards/checked.md" ] && [ -s "$run/02-check/spec/checked.md" ]'
check "board command: renderer errors do not change its exit code" '[ "$board_code" -eq 0 ]'
check "board command: the board is printed on stdout" '[ "$board_code" -eq 0 ] && [ -s "$case_dir/board.txt" ] && [ ! -s "$case_dir/board.stderr" ]'
run_normalized=$(python3 -c 'import os, sys; print(os.path.normpath(sys.argv[1]))' "$run")
expected_stdout=$(printf 'Run folder: %s\nREADY: %s/report.md\nSee %s/status.log' "$run_normalized" "$run_normalized" "$run_normalized")
check "start stdout: READY output is unchanged" '[ "$finished_stdout" = "$expected_stdout" ]'
check "start: the initial board precedes progress" 'awk '\''/^Revisão finished/ && !initial { initial=NR } $0 == "[review] review · início" { progress=NR; exit } END { exit !(initial && progress && initial < progress) }'\'' "$case_dir/stderr.txt"'
check "progress: the line is followed by a blank line and board" 'awk '\''$0 == "[review] review · início" { if (getline <= 0 || $0 != "") exit 1; if (getline <= 0 || index($0, "Revisão finished") != 1) exit 1; found=1; exit } END { exit !found }'\'' "$case_dir/stderr.txt"'
check "running: stderr shows an in-progress step" '[ "$finished_code" -eq 0 ] && grep -qF "◐ Revisores" "$case_dir/stderr.txt"'
echo 'Sample review board from the finished run:'
cat "$case_dir/board.txt"

# 2. A Codex failure in the checker stage crosses that step.
new_repo stopped
run_start stopped FAKE_FAIL=check
check "stopped check: the stderr board has an in-progress line" '[ "$code" -ne 0 ] && grep -qF "◐ Verificação" "$case_dir/stderr.txt"'
run_board stopped
check "stopped check: review passed and check is crossed" '[ "$board_code" -eq 0 ] && grep -qF "✓ Revisores" "$case_dir/board.txt" && grep -qF "✗ Verificação" "$case_dir/board.txt"'

exit "$fail"

#!/usr/bin/env bash
# Tests the council run board with a fake `codex`: no model is called.
# Usage: test-council-run-board.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/council-run-board-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

# The fake writes the requested council artifacts into the -C working directory, as codex does.
mkdir -p "$work/bin" "$work/guides"
cat >"$work/bin/codex" <<'EOF'
#!/usr/bin/env bash
dir="" out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -C) dir=$2; shift 2 ;;
    -o) out=$2; shift 2 ;;
    -m|-c|-s) shift 2 ;;
    *) shift ;;
  esac
done
prompt=$(cat)
if [ -n "${FAKE_DELAY:-}" ]; then /bin/sleep "$FAKE_DELAY"; fi
case "$prompt" in
  "# Brief: advice"*)
    printf 'advice\n' >"$dir/advice.md"
    ;;
  "# Brief: review of the responses"*)
    if [ "${FAKE_FAIL:-}" = review ]; then
      echo 'fake review failure' >&2
      exit 1
    fi
    printf 'review\n' >"$dir/review.md"
    ;;
  "# Brief: completeness check of the report"*)
    printf '## What I checked\n\n- one\n- two\n- three\n\n## Problems\n\nnone\n\nVERDICT: pass\n' >"$dir/problems.md"
    ;;
  *)
    echo "unexpected fake codex prompt" >&2
    exit 2
    ;;
esac
[ -z "$out" ] || printf 'fake response\n' >"$out"
printf '%s\n' '{"type":"turn.completed"}'
EOF
chmod +x "$work/bin/codex"

new_case() { # <name>
  case_dir=$work/$1
  mkdir -p "$case_dir/repo" "$case_dir/state"
  printf '# Brief\n\nWhat should the council consider?\n' >"$case_dir/brief.md"
}

run_start() { # <name> [env assignments...]
  local name=$1
  shift
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" COUNCIL_RUNS_DIR="$case_dir/runs" \
    COUNCIL_GUIDES="$work/guides" FAKE_STATE="$case_dir/state" "$@" \
    "$here/council-run.sh" start "$name" "$case_dir/brief.md") >"$case_dir/stdout.txt" 2>"$case_dir/stderr.txt"
  code=$?
  run=$case_dir/runs/$name
}

run_board() { # <name>
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" COUNCIL_RUNS_DIR="$case_dir/runs" \
    COUNCIL_GUIDES="$work/guides" "$here/council-run.sh" board "$1") >"$case_dir/board.txt" 2>"$case_dir/board.stderr"
  board_code=$?
}

run_resume() { # <name>
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" COUNCIL_RUNS_DIR="$case_dir/runs" \
    COUNCIL_GUIDES="$work/guides" FAKE_STATE="$case_dir/state" \
    "$here/council-run.sh" resume "$1") >"$case_dir/resume.stdout" 2>"$case_dir/resume.stderr"
  resume_code=$?
}

run_check() { # <name>
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" COUNCIL_RUNS_DIR="$case_dir/runs" \
    COUNCIL_GUIDES="$work/guides" FAKE_STATE="$case_dir/state" \
    "$here/council-run.sh" check "$1" "$case_dir/report.md") >"$case_dir/check.stdout" 2>"$case_dir/check.stderr"
  check_code=$?
}

# 1. A complete council has every step and agent checked, and board prints to stdout.
new_case finished
run_start finished
finished_code=$code
finished_stdout=$(cat "$case_dir/stdout.txt")
run_board finished
check "finished: all steps and agents are checked" '[ "$finished_code" -eq 0 ] && grep -qF "✓ Conselheiros" "$case_dir/board.txt" && grep -qF "✓ contrarian" "$case_dir/board.txt" && grep -qF "✓ first-principles" "$case_dir/board.txt" && grep -qF "✓ expansionist" "$case_dir/board.txt" && grep -qF "✓ outsider" "$case_dir/board.txt" && grep -qF "✓ executor" "$case_dir/board.txt" && grep -qF "✓ Pacote anónimo" "$case_dir/board.txt" && grep -qF "✓ Revisores" "$case_dir/board.txt" && grep -qF "✓ 1" "$case_dir/board.txt" && grep -qF "✓ 2" "$case_dir/board.txt" && grep -qF "✓ 3" "$case_dir/board.txt" && grep -qF "✓ 4" "$case_dir/board.txt" && grep -qF "✓ 5" "$case_dir/board.txt"'
check "board command: the board is printed on stdout" '[ "$board_code" -eq 0 ] && [ -s "$case_dir/board.txt" ] && [ ! -s "$case_dir/board.stderr" ]'
expected_stdout=$(printf 'Run folder: %s\nREADY\nAdvice: %s/01-advisors/<perspective>/advice.md\nKey: %s/02-packet/key.md\nReviews: %s/03-review/<n>/review.md\nSee %s/status.log' "$run" "$run" "$run" "$run" "$run")
check "start stdout: READY output is unchanged" '[ "$finished_stdout" = "$expected_stdout" ]'
printf '# Report\n\nSummary.\n' >"$case_dir/report.md"
run_check finished
expected_check_stdout=$(printf 'Completeness check, round 1: pass\nProblems: %s/04-check/rounds/1/problems.md' "$run")
check "check stdout: verdict output is unchanged" '[ "$check_code" -eq 0 ] && [ "$(cat "$case_dir/check.stdout")" = "$expected_check_stdout" ]'
echo 'Sample council board from the finished run:'
cat "$case_dir/board.txt"

# 2. A Codex failure in review stops the run and marks the review step with a cross.
new_case stopped
run_start stopped FAKE_FAIL=review
check "stopped review: the stderr board marks Revisores with ✗" '[ "$code" -ne 0 ] && grep -qF "✗ Revisores" "$case_dir/stderr.txt"'
run_resume stopped
resume_expected=$(printf 'Run folder: %s\nREADY\nAdvice: %s/01-advisors/<perspective>/advice.md\nKey: %s/02-packet/key.md\nReviews: %s/03-review/<n>/review.md\nSee %s/status.log' "$run" "$run" "$run" "$run" "$run")
check "resume stdout: READY output is unchanged" '[ "$resume_code" -eq 0 ] && [ "$(cat "$case_dir/resume.stdout")" = "$resume_expected" ]'

# 3. During the advisor stage, stderr includes the in-progress icon.
new_case running
run_start running FAKE_DELAY=0.2
check "running: stderr shows an in-progress step" '[ "$code" -eq 0 ] && grep -qF "◐ Conselheiros" "$case_dir/stderr.txt"'

exit "$fail"

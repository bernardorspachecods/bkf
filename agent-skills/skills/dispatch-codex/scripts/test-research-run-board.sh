#!/usr/bin/env bash
# Tests the research run board with a fake `codex`: no model is called.
# Usage: test-research-run-board.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/research-run-board-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

# The fake writes the artifact named by each brief to Codex's working directory.
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
[ -z "${FAKE_DELAY:-}" ] || /bin/sleep "$FAKE_DELAY"
if [ "${FAKE_FAIL:-}" = collection ] && [[ "$prompt" == '# Brief: collection (collector '* ]]; then
  echo 'fake collection failure' >&2
  exit 1
fi
case "$prompt" in
  '# Brief: complete the source map'*)
    printf '2. **Independent sources.** Example sites; counterweight. (agent)\n' >"$dir/additions.md"
    ;;
  '# Brief: collection (collector '* )
    printf '# Sources\n\nCollected evidence.\n' >"$dir/sources.md"
    ;;
  '# Brief: review of the collection'*)
    printf '## What I checked\n\n- the objective\n- the collected sources\n- the scope\n\n## Problems\n\nNone.\n\nVERDICT: pass\n' >"$dir/problems.md"
    ;;
  '# Brief: digest'*)
    printf '# Digest\n\nSummary.\n' >"$dir/digest.md"
    ;;
  '# Brief: review of the digest'*)
    printf '## What I checked\n\n- the objective\n- the source collection\n- the digest\n\n## Problems\n\nNone.\n\nVERDICT: pass\n' >"$dir/problems.md"
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

new_case() { # <name>
  case_dir=$work/$1
  mkdir -p "$case_dir/repo" "$case_dir/runs"
  printf '# Objective\n\nFind useful evidence.\n' >"$case_dir/objective.md"
  printf '1. **Primary sources.** Example sites.\n' >"$case_dir/sourcemap.md"
  printf '# Collectors\n\n# one collector\nprimary: 1\n' >"$case_dir/collectors.txt"
}

run_start() { # <name> [env assignments...]
  local n=$1; shift
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" RESEARCH_RUNS_DIR="$case_dir/runs" \
    RESEARCH_GUIDES="$work/guides" "$@" \
    "$here/research-run.sh" start "$n" "$case_dir/objective.md" "$case_dir/sourcemap.md" "$case_dir/collectors.txt") \
    >"$case_dir/stdout.txt" 2>"$case_dir/stderr.txt"
  code=$?
  run=$case_dir/runs/$n
}

run_board() { # <name>
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" RESEARCH_RUNS_DIR="$case_dir/runs" \
    RESEARCH_GUIDES="$work/guides" "$here/research-run.sh" board "$1") \
    >"$case_dir/board.txt" 2>"$case_dir/board.stderr"
  board_code=$?
}

# 1. A complete research run marks all steps and the collector as finished.
new_case finished
run_start finished FAKE_DELAY=0.15
finished_code=$code
finished_stdout=$(cat "$case_dir/stdout.txt")
run_board finished
check "finished: every step and collector is checked" '[ "$finished_code" -eq 0 ] && grep -qF "✓ Mapa" "$case_dir/board.txt" && grep -qF "✓ Recolha" "$case_dir/board.txt" && grep -qF "✓ primary" "$case_dir/board.txt" && grep -qF "✓ Digest" "$case_dir/board.txt"'
check "finished: renderer errors do not change the run exit code" '[ "$finished_code" -eq 0 ] && [ -s "$run/03-digest/digest.md" ]'
check "finished: the collector output file is present" '[ -s "$run/02-collection/primary/work/sources.md" ] && grep -qF "✓ primary" "$case_dir/board.txt"'
check "collector parsing: comments and blank lines are skipped" '[ "$(grep -c "^    " "$case_dir/board.txt")" -eq 1 ]'
check "board command: renderer errors do not change its exit code" '[ "$board_code" -eq 0 ]'
check "board command: the board is printed on stdout" '[ "$board_code" -eq 0 ] && [ -s "$case_dir/board.txt" ] && [ ! -s "$case_dir/board.stderr" ]'
expected_stdout=$(printf 'Run folder: %s\nREADY: %s/03-digest/digest.md\nSee %s/status.log' "$run" "$run" "$run")
check "start stdout: READY output is unchanged" '[ "$finished_stdout" = "$expected_stdout" ]'
check "start: the initial board precedes progress" 'awk '\''/^Pesquisa finished/ && !initial { initial=NR } $0 == "[research] map · início" { progress=NR; exit } END { exit !(initial && progress && initial < progress) }'\'' "$case_dir/stderr.txt"'
check "progress: the line is followed by a blank line and board" 'awk '\''$0 == "[research] map · início" { if (getline <= 0 || $0 != "") exit 1; if (getline <= 0 || index($0, "Pesquisa finished") != 1) exit 1; found=1; exit } END { exit !found }'\'' "$case_dir/stderr.txt"'
check "running: stderr shows an in-progress step" '[ "$finished_code" -eq 0 ] && grep -qF "◐ Mapa" "$case_dir/stderr.txt"'
echo 'Sample research board from the finished run:'
cat "$case_dir/board.txt"

# 2. A collector failure stops collection, marks that step, and leaves the missing output unchecked.
new_case stopped
run_start stopped FAKE_FAIL=collection
check "stopped collection: the stderr board has an in-progress line" '[ "$code" -ne 0 ] && grep -qF "◐ Recolha" "$case_dir/stderr.txt"'
run_board stopped
check "stopped collection: the step is crossed and the collector has no output marker" '[ "$board_code" -eq 0 ] && grep -qF "✗ Recolha" "$case_dir/board.txt" && grep -qF "○ primary" "$case_dir/board.txt" && [ ! -s "$run/02-collection/primary/work/sources.md" ]'

exit "$fail"

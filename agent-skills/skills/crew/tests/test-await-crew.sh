#!/usr/bin/env bash
# Tests await-crew.sh with a fake `tmux` and this worktree's `bkf` on a temporary task store: no model is
# called and no real session is touched.
# Usage: test-await-crew.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/../scripts/await-crew.sh
work=$(mktemp -d "${TMPDIR:-/tmp}/crew-await-test.XXXXXX")
work=$(cd "$work" && pwd -P)
trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

mkdir -p "$work/bin" "$work/repo" "$work/crew" "$work/crew2"
# The `bkf` shim runs this worktree's tooling, as the launcher's test does; the task store is temporary.
repo_root=$(git -C "$here" rev-parse --show-toplevel)
bkf_python="$(uv tool dir)/bkf-tooling/bin/python3"
cat >"$work/bin/bkf" <<SHIM
#!/usr/bin/env bash
PYTHONPATH="$repo_root/bkf/tooling" exec "$bkf_python" -m bkf_cli "\$@"
SHIM
chmod +x "$work/bin/bkf"
export BKF_TASKS_DIR="$work/tasks" PATH="$work/bin:$PATH"
# The fake tmux answers capture-pane with an unchanging pane and records which target was asked for.
cat >"$work/bin/tmux" <<'F'
#!/usr/bin/env bash
if [[ $1 == capture-pane ]]; then printf '%s\n' "${@: -1}" >>"$FAKE_TMUX_LOG"; echo 'working'; fi
F
chmod +x "$work/bin/tmux"
printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$@" >"%s/ran"\n' "$work" >"$work/open.sh"
chmod +x "$work/open.sh"

# A coordinator's card in a crew folder, working in tmux window $3: crew folder, name, window.
make_card() {
  local id
  id=$(bkf task new --repo "$work/repo" --title "crew-$2" --kind coordinator) || return 1
  bkf task start "$id" --tmux-session main --tmux-window "$3" >/dev/null || return 1
  mkdir -p "$1/cards" && printf '%s\n' "$id" >"$1/cards/$2"
}
# The crew's own card, which the waiter must ignore: it stays working.
make_crew_card() {
  local id
  id=$(bkf task new --repo "$work/repo" --title "crew" --kind crew) || return 1
  mkdir -p "$1/cards" && printf '%s\n' "$id" >"$1/cards/crew"
}
card_id() { cat "$work/crew/cards/$1" 2>/dev/null || cat "$work/crew2/cards/$1"; }

env_common=(PATH="$work/bin:$PATH" FAKE_TMUX_LOG="$work/tmux.log" AWAIT_INTERVAL=1 WATCH_INTERVAL=1
  WATCH_STILL=3600 WATCH_NOTIFY=true)

make_crew_card "$work/crew"
make_card "$work/crew" a @1
make_card "$work/crew" b @2
env "${env_common[@]}" "$script" "$work/crew" -- "$work/open.sh" B review.md \
  >"$work/out" 2>&1 &
pid=$!

sleep 3
check "runs nothing while the coordinators are working" '[ ! -e "$work/ran" ] && kill -0 $pid 2>/dev/null'
check "watches both coordinators by their tmux windows" 'grep -qx @1 "$work/tmux.log" && grep -qx @2 "$work/tmux.log"'
check "does not watch the crew card" '! grep -q "crew" "$work/tmux.log"'

bkf task ready --no-git "$(card_id a)" >/dev/null
sleep 1; : >"$work/tmux.log"; sleep 3
check "runs nothing while one coordinator is still working" '[ ! -e "$work/ran" ] && kill -0 $pid 2>/dev/null'
check "stops watching the coordinator that is ready" '! grep -qx @1 "$work/tmux.log" && grep -qx @2 "$work/tmux.log"'

bkf task done "$(card_id b)" >/dev/null
for _ in $(seq 100); do [ -e "$work/ran" ] && break; sleep 0.1; done
wait $pid; rc=$?
check "runs the command with its arguments once every card is ready or done, the crew card still working" \
  '[ "$(cat "$work/ran")" = "$(printf "B\nreview.md")" ]'
check "exits 0 and reports the command's status" '[ $rc = 0 ] && grep -q "command exited 0" "$work/out"'

# A card that cannot be read counts as not ready, and the report says so.
make_crew_card "$work/crew2"
make_card "$work/crew2" x @3
bkf task done "$(card_id x)" >/dev/null
printf 'tnotacard\n' >"$work/crew2/cards/y"
rm -f "$work/ran"
env "${env_common[@]}" "$script" "$work/crew2" -- "$work/open.sh" C \
  >"$work/out2" 2>&1 &
pid=$!
sleep 3
check "an unreadable card keeps the command from running" '[ ! -e "$work/ran" ] && kill -0 $pid 2>/dev/null'
check "the unreadable card is reported" 'grep -q "cannot read the card of y" "$work/out2"'

make_card "$work/crew2" z @4
bkf task ready --no-git "$(card_id z)" >/dev/null
cp "$work/crew2/cards/z" "$work/crew2/cards/y"
for _ in $(seq 100); do [ -e "$work/ran" ] && break; sleep 0.1; done
wait $pid
check "runs the command once the unreadable card is readable and ready" '[ "$(cat "$work/ran")" = C ]'

"$script" "$work/crew" main:crew-a >/dev/null 2>&1; rc=$?
check "refuses a call without the -- separator" '[ "$rc" = 2 ]'
mkdir -p "$work/empty"; rm -f "$work/ran"
"$script" "$work/empty" -- "$work/open.sh" >/dev/null 2>&1; rc=$?
check "refuses a crew with no coordinator cards, running nothing" '[ "$rc" = 2 ] && [ ! -e "$work/ran" ]'

exit $fail

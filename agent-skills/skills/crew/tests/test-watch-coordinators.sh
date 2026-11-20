#!/usr/bin/env bash
# Tests watch-coordinators.sh on a throwaway tmux server: no model is called and the user's tmux
# sessions are not touched.
# Usage: test-watch-coordinators.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/../scripts/watch-coordinators.sh
work=$(mktemp -d "${TMPDIR:-/tmp}/crew-watch-test.XXXXXX")
sock="crew-watch-test-$$"
trap 'tmux -L "$sock" kill-server 2>/dev/null; rm -rf "$work"' EXIT
fail=0
# macOS has no timeout(1).
timeout() { perl -e 'alarm shift; exec @ARGV' "$@"; }
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

# Make `tmux` in the script talk to the throwaway server.
mkdir -p "$work/bin"
printf '#!/usr/bin/env bash\nexec /usr/bin/env -u TMUX "%s" -L "%s" "$@"\n' "$(command -v tmux)" "$sock" >"$work/bin/tmux"
chmod +x "$work/bin/tmux"
export PATH="$work/bin:$PATH" WATCH_INTERVAL=1 WATCH_NOTIFY=true WATCH_WAITS="$work/none"

tmux new-session -d -s main -n busy 'while :; do date +%s%N; sleep 0.2; done'
tmux new-window -t main -n idle 'echo idle; sleep 300'
tmux new-window -t main -n shellbar 'echo "done · 1 shell still running"; echo "  ⏵⏵ auto mode on · 1 shell"; sleep 300'
tmux new-window -t main -n ask 'echo "Do you want to proceed? (y/n)"; sleep 300'
sleep 1

run() { WATCH_STILL=${STILL:-3} timeout 30 "$script" "$work/state-$1" "${@:2}" >"$work/out-$1" 2>&1; echo $? >"$work/rc-$1"; }

run a main:busy main:idle
check "idle pane alerts STILL, busy pane does not" 'grep -qx "STILL main:idle" "$work/out-a" && ! grep -q busy "$work/out-a"'
check "alert exits 0 without WATCHER-EXIT" '[ "$(cat "$work/rc-a")" = 0 ] && ! grep -q WATCHER-EXIT "$work/out-a"'

STILL=3600 run b main:ask
check "permission prompt alerts PROMPT at once" 'grep -qx "PROMPT main:ask" "$work/out-b"'

STILL=3 WATCH_REMIND=3600 timeout 4 "$script" "$work/state-a" main:idle >"$work/out-c" 2>&1
check "relaunch does not repeat a delivered alert" '! grep -q STILL "$work/out-c"'

STILL=3 run g main:shellbar main:idle
check "idle pane with a background shell never alerts" '! grep -q shellbar "$work/out-g"'
check "idle pane without a shell still alerts STILL beside it" 'grep -qx "STILL main:idle" "$work/out-g"'

mkdir -p "$work/waits"; export WATCH_WAITS="$work/waits"
echo $(( $(date +%s) + 3600 )) >"$work/waits/idle"
STILL=3 WATCH_GRACE=0 timeout 6 "$script" "$work/state-h" main:idle >"$work/out-h" 2>&1
check "idle pane with a quota wait still ahead stays silent" '! grep -Eq "^(STILL|OVERDUE)" "$work/out-h"'

echo $(( $(date +%s) - 10 )) >"$work/waits/idle"
STILL=3 WATCH_GRACE=0 run i main:idle
check "idle pane whose announced time passed alerts OVERDUE" 'grep -qx "OVERDUE main:idle" "$work/out-i"'

echo $(( $(date +%s) - 10 )) >"$work/waits/idle"
STILL=3 WATCH_GRACE=3600 timeout 6 "$script" "$work/state-j" main:idle >"$work/out-j" 2>&1
check "announced time inside the grace stays silent" '! grep -Eq "^(STILL|OVERDUE)" "$work/out-j"'

echo $(( $(date +%s) + 3600 )) >"$work/waits/ask"
STILL=3600 run k main:ask
check "permission prompt still alerts during a quota wait" 'grep -qx "PROMPT main:ask" "$work/out-k"'
rm -f "$work/waits"/*

run d main:nowindow
check "missing window alerts GONE" 'grep -qx "GONE main:nowindow" "$work/out-d"'

# Cards: a target written <tmux-target>=<card-id> sets the card's attention with each alert. The `bkf` shim runs
# this worktree's tooling on a temporary task store.
repo_root=$(git -C "$here" rev-parse --show-toplevel)
bkf_python="$(uv tool dir)/bkf-tooling/bin/python3"
printf '#!/usr/bin/env bash\nPYTHONPATH="%s/bkf/tooling" exec "%s" -m bkf_cli "$@"\n' "$repo_root" "$bkf_python" >"$work/bin/bkf"
chmod +x "$work/bin/bkf"
export BKF_TASKS_DIR="$work/tasks"
new_card() { bkf task new --repo "$work" --title "$1" --kind coordinator; }
attention_of() {
  bkf task show "$1" --json | python3 -c 'import json, sys; a = json.load(sys.stdin)["attention"]; print("-" if a is None else a["reason"])'
}
c_ask=$(new_card ask); c_idle=$(new_card idle); c_gone=$(new_card gone)

STILL=3600 run m main:ask="$c_ask"
check "a PROMPT alert sets the card's attention to prompt" 'grep -qx "PROMPT main:ask" "$work/out-m" && [ "$(attention_of "$c_ask")" = prompt ]'
tmux respawn-window -k -t main:ask 'echo changed; sleep 300'
sleep 1
STILL=3600 timeout 4 "$script" "$work/state-m" main:ask="$c_ask" >"$work/out-m2" 2>&1
check "the first change of the pane after an alert clears the attention" '[ "$(attention_of "$c_ask")" = - ] && ! grep -q PROMPT "$work/out-m2"'

STILL=3 run s main:idle="$c_idle"
check "a STILL alert sets the card's attention to still" 'grep -qx "STILL main:idle" "$work/out-s" && [ "$(attention_of "$c_idle")" = still ]'

echo $(( $(date +%s) - 10 )) >"$work/waits/idle"
STILL=3 WATCH_GRACE=0 run o main:idle="$c_idle"
check "an OVERDUE alert sets the card's attention to overdue" 'grep -qx "OVERDUE main:idle" "$work/out-o" && [ "$(attention_of "$c_idle")" = overdue ]'
rm -f "$work/waits"/*

# A window id target keys its quota wait by the window's name (crew-<name>): a future wake-up time stays silent.
tmux new-window -t main -n crew-x 'echo idle; sleep 300'
wid=$(tmux display-message -p -t main:crew-x '#{window_id}')
c_x=$(new_card x)
echo $(( $(date +%s) + 3600 )) >"$work/waits/crew-x"
STILL=3 WATCH_GRACE=0 timeout 6 "$script" "$work/state-x" "$wid=$c_x" >"$work/out-x" 2>&1
check "a carded window id in a quota wait stays silent and sets no attention" \
  '! grep -Eq "^(STILL|OVERDUE)" "$work/out-x" && [ "$(attention_of "$c_x")" = - ]'
rm -f "$work/waits"/*

run n main:nowindow="$c_gone"
check "a GONE alert sets the card's attention to gone" 'grep -qx "GONE main:nowindow" "$work/out-n" && [ "$(attention_of "$c_gone")" = gone ]'

tmux new-window -t main -n ask2 'echo "Do you want to proceed? (y/n)"; sleep 300'
run f main:ask2=tmissing
check "a failing bkf is reported on standard error and the watcher still alerts and exits 0" \
  'grep -qx "PROMPT main:ask2" "$work/out-f" && grep -q "bkf task attention tmissing --set prompt failed" "$work/out-f" && [ "$(cat "$work/rc-f")" = 0 ] && ! grep -q WATCHER-EXIT "$work/out-f"'

rm -f "$work/state-e"/* 2>/dev/null
WATCH_STILL=3600 "$script" "$work/state-e" main:idle >"$work/out-e" 2>&1 & pid=$!
sleep 2; kill -TERM $pid; wait $pid 2>/dev/null
check "killed watcher prints WATCHER-EXIT" 'grep -qx WATCHER-EXIT "$work/out-e"'

exit $fail

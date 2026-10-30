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
export PATH="$work/bin:$PATH" WATCH_INTERVAL=1 WATCH_NOTIFY=true

tmux new-session -d -s main -n busy 'while :; do date +%s%N; sleep 0.2; done'
tmux new-window -t main -n idle 'echo idle; sleep 300'
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

run d main:nowindow
check "missing window alerts GONE" 'grep -qx "GONE main:nowindow" "$work/out-d"'

rm -f "$work/state-e"/* 2>/dev/null
WATCH_STILL=3600 "$script" "$work/state-e" main:idle >"$work/out-e" 2>&1 & pid=$!
sleep 2; kill -TERM $pid; wait $pid 2>/dev/null
check "killed watcher prints WATCHER-EXIT" 'grep -qx WATCHER-EXIT "$work/out-e"'

exit $fail

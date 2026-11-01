#!/usr/bin/env bash
# Tests await-crew.sh with a fake `tmux`: no model is called and no real session is touched.
# Usage: test-await-crew.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/../scripts/await-crew.sh
work=$(mktemp -d "${TMPDIR:-/tmp}/crew-await-test.XXXXXX")
work=$(cd "$work" && pwd -P)
trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

mkdir -p "$work/bin" "$work/crew"
# The fake tmux answers capture-pane with an unchanging pane and records which target was asked for.
cat >"$work/bin/tmux" <<'F'
#!/usr/bin/env bash
if [[ $1 == capture-pane ]]; then printf '%s\n' "${@: -1}" >>"$FAKE_TMUX_LOG"; echo 'working'; fi
F
chmod +x "$work/bin/tmux"
printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$@" >"%s/ran"\n' "$work" >"$work/open.sh"
chmod +x "$work/open.sh"

env_common=(PATH="$work/bin:$PATH" FAKE_TMUX_LOG="$work/tmux.log" AWAIT_INTERVAL=1 WATCH_INTERVAL=1
  WATCH_STILL=3600 WATCH_NOTIFY=true)
env "${env_common[@]}" "$script" "$work/crew" main:crew-a main:crew-b -- "$work/open.sh" B review.md \
  >"$work/out" 2>&1 &
pid=$!

sleep 3
check "runs nothing while no coordinator is done" '[ ! -e "$work/ran" ] && kill -0 $pid 2>/dev/null'
check "watches both coordinators meanwhile" 'grep -qx main:crew-a "$work/tmux.log" && grep -qx main:crew-b "$work/tmux.log"'

: >"$work/crew/done/a.md"
sleep 3
check "an empty done file does not count" '[ ! -e "$work/ran" ]'

printf 'a passed review; agreed with b: shared enum\n' >"$work/crew/done/a.md"
sleep 1; : >"$work/tmux.log"; sleep 3
check "runs nothing while one is still working" '[ ! -e "$work/ran" ] && kill -0 $pid 2>/dev/null'
check "stops watching the coordinator that is done" '! grep -qx main:crew-a "$work/tmux.log" && grep -qx main:crew-b "$work/tmux.log"'

printf 'b passed review\n' >"$work/crew/done/b.md"
for _ in $(seq 100); do [ -e "$work/ran" ] && break; sleep 0.1; done
wait $pid; rc=$?
check "runs the command with its arguments once every coordinator is done" '[ "$(cat "$work/ran")" = "$(printf "B\nreview.md")" ]'
check "exits 0 and reports the command's status" '[ $rc = 0 ] && grep -q "command exited 0" "$work/out"'

"$script" "$work/crew" main:crew-a >/dev/null 2>&1
check "refuses a call without a command" '[ $? = 2 ]'

exit $fail

#!/usr/bin/env bash
# Tests launch-coordinator.sh with a fake `claude`, on a throwaway tmux server: no model is called
# and the user's tmux sessions are not touched.
# Usage: test-launch-coordinator.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/../scripts/launch-coordinator.sh
work=$(mktemp -d "${TMPDIR:-/tmp}/crew-test.XXXXXX")
work=$(cd "$work" && pwd -P)
sock="crew-test-$$"
trap 'tmux -L "$sock" kill-server 2>/dev/null; rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

mkdir -p "$work/bin" "$work/repo"
# The `bkf` shim runs this worktree's tooling, not the installed copy; the task store is a temporary one.
repo_root=$(git -C "$here" rev-parse --show-toplevel)
bkf_python="$(uv tool dir)/bkf-tooling/bin/python3"
cat >"$work/bin/bkf" <<SHIM
#!/usr/bin/env bash
PYTHONPATH="$repo_root/bkf/tooling" exec "$bkf_python" -m bkf_cli "\$@"
SHIM
chmod +x "$work/bin/bkf"
export PATH="$work/bin:$PATH" BKF_TASKS_DIR="$work/tasks"
# One field of a card: <card id> <dotted field, such as status, kind or session.tmux_window>.
card_field() {
  bkf task show "$1" --json | python3 -c '
import json, sys
value = json.load(sys.stdin)
for key in sys.argv[1].split("."):
    value = value[key]
print("" if value is None else value)' "$2"
}
# The fake Claude records its working directory and its arguments, one per line.
cat >"$work/bin/claude" <<'F'
#!/usr/bin/env bash
pwd >"$FAKE_OUT.pwd"
printf '%s\n' "$@" >"$FAKE_OUT.args"
printf '%s\n' "${BKF_DELEGATED-unset}" >"$FAKE_OUT.delegated"
F
chmod +x "$work/bin/claude"
printf 'Sub-plan B: SARP outbox.\n' >"$work/b.md"

# Runs the launcher inside a window of the throwaway server, as the orchestrator would.
# A new tmux window takes the server's environment, so the server starts with the fake on PATH.
launch() {
  PATH="$work/bin:$PATH" FAKE_OUT="$work/out" BKF_TASKS_DIR="$work/tasks" BKF_TMUX_SOCKET="$sock" \
    tmux -L "$sock" new-session -d -s main -n orchestrator \
    "'$script' $* >'$work/stdout' 2>'$work/stderr'; echo \$? >'$work/rc'; sleep 30"
  for _ in $(seq 100); do [ -s "$work/rc" ] && break; sleep 0.1; done
  [ "$(cat "$work/rc")" = 0 ] || return 0
  for _ in $(seq 100); do [ -s "$work/out.args" ] && break; sleep 0.1; done
}

launch b orch-1 "$work/repo" "$work/b.md"
check "exits 0 and prints the session name" '[ "$(cat "$work/rc")" = 0 ] && [ "$(cat "$work/stdout")" = crew-b ]'
check "opens a window named crew-b right after the caller" \
  '[ "$(tmux -L "$sock" list-windows -t main -F "#{window_name}" | paste -sd, -)" = "orchestrator,crew-b" ]'
check "leaves focus on the caller" \
  '[ "$(tmux -L "$sock" display-message -p -t main "#{window_name}")" = orchestrator ]'
check "starts claude in the working directory" '[ "$(cat "$work/out.pwd")" = "$work/repo" ]'
check "names the session crew-b" 'grep -qx -- "--name" "$work/out.args" && grep -qx crew-b "$work/out.args"'
check "marks the session as delegated" '[ "$(cat "$work/out.delegated")" = 1 ] && ! grep -qx -- "--delegated" "$work/out.args"'
check "starts the session in auto mode" 'grep -A1 -x -- "--permission-mode" "$work/out.args" | grep -qx auto'
check "first message has the brief" 'grep -q "Sub-plan B: SARP outbox." "$work/out.args"'
check "first message has the rules with names filled in" \
  'grep -q "You are \`crew-b\`" "$work/out.args" && grep -q "session \`orch-1\`" "$work/out.args" && ! grep -q "{{" "$work/out.args"'
check "first message names the brief file" 'grep -qF "\`$work/b.md\`" "$work/out.args"'
check "writes the full message next to the brief" '[ -f "$work/b.prompt.md" ]'
check "passes no model or effort when none is given" '! grep -qx -- "--model" "$work/out.args" && ! grep -qx -- "--effort" "$work/out.args"'
check "makes the crew card once, in the crew folder" \
  '[ -s "$work/cards/crew" ] && [ "$(card_field "$(cat "$work/cards/crew")" kind)" = crew ] && [ "$(card_field "$(cat "$work/cards/crew")" title)" = "crew $(basename "$work")" ]'
check "starts the crew card in the orchestrator's window" \
  '[ "$(card_field "$(cat "$work/cards/crew")" status)" = working ] && [ "$(card_field "$(cat "$work/cards/crew")" session.tmux_session)" = main ] && [ "$(card_field "$(cat "$work/cards/crew")" session.tmux_window)" = "$(tmux -L "$sock" display-message -p -t main:orchestrator "#{window_id}")" ]'
check "makes the coordinator card: kind coordinator, parent the crew card, working in its window" \
  '[ -s "$work/cards/b" ] && c=$(cat "$work/cards/b") && [ "$(card_field "$c" kind)" = coordinator ] && [ "$(card_field "$c" parent)" = "$(cat "$work/cards/crew")" ] && [ "$(card_field "$c" status)" = working ] && [ "$(card_field "$c" session.tmux_window)" = "$(tmux -L "$sock" list-windows -t main -F "#{window_id} #{window_name}" | grep " crew-b\$" | cut -d" " -f1)" ]'
check "the coordinator card is titled crew-b" \
  '[ "$(card_field "$(cat "$work/cards/b")" title)" = crew-b ]'
tmux -L "$sock" kill-server 2>/dev/null

rm -f "$work"/out.* "$work/rc"
crew_before=$(cat "$work/cards/crew")
launch c orch-1 "$work/repo" "$work/b.md" sonnet high
check "passes the model and effort it is given" \
  'grep -A1 -x -- "--model" "$work/out.args" | grep -qx sonnet && grep -A1 -x -- "--effort" "$work/out.args" | grep -qx high'
check "a second coordinator reuses the crew card, which stays the only crew card" \
  '[ "$(cat "$work/cards/crew")" = "$crew_before" ] && [ "$(bkf task list --json | python3 -c "import json,sys; print(sum(1 for t in json.load(sys.stdin)[\"tasks\"] if t[\"kind\"] == \"crew\"))")" = 1 ]'
check "the second coordinator has its own card under the crew card" \
  '[ -s "$work/cards/c" ] && [ "$(card_field "$(cat "$work/cards/c")" parent)" = "$crew_before" ] && [ "$(card_field "$(cat "$work/cards/c")" kind)" = coordinator ] && [ "$(card_field "$(cat "$work/cards/c")" status)" = working ]'
tmux -L "$sock" kill-server 2>/dev/null

rm -f "$work"/out.* "$work/rc"
launch "Bad_Name" orch-1 "$work/repo" "$work/b.md"
tmux -L "$sock" kill-server 2>/dev/null
check "refuses a name that is not lowercase-hyphen" '[ "$(cat "$work/rc")" != 0 ] && grep -q "name must be" "$work/stderr" && [ ! -e "$work/out.args" ]'

# The name crew is the crew card's file name: refused before anything is written or launched, in a crew folder of its own.
mkdir -p "$work/fresh" && cp "$work/b.md" "$work/fresh/b.md"
rm -f "$work"/out.* "$work/rc"
launch crew orch-1 "$work/repo" "$work/fresh/b.md"
tmux -L "$sock" kill-server 2>/dev/null
check "refuses the name crew with a reserved-name error" '[ "$(cat "$work/rc")" != 0 ] && grep -q "reserved for the crew card" "$work/stderr"'
check "refusing crew launches nothing and writes no cards" '[ ! -e "$work/out.args" ] && [ ! -e "$work/fresh/cards" ] && [ ! -e "$work/fresh/crew.prompt.md" ] && [ ! -e "$work/fresh/b.prompt.md" ]'

exit $fail

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
# The fake Claude records its working directory and its arguments, one per line.
cat >"$work/bin/claude" <<'F'
#!/usr/bin/env bash
pwd >"$FAKE_OUT.pwd"
printf '%s\n' "$@" >"$FAKE_OUT.args"
F
chmod +x "$work/bin/claude"
printf 'Sub-plan B: SARP outbox.\n' >"$work/b.md"

# Runs the launcher inside a window of the throwaway server, as the orchestrator would.
# A new tmux window takes the server's environment, so the server starts with the fake on PATH.
launch() {
  PATH="$work/bin:$PATH" FAKE_OUT="$work/out" tmux -L "$sock" new-session -d -s main -n orchestrator \
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
check "starts the session in auto mode" 'grep -A1 -x -- "--permission-mode" "$work/out.args" | grep -qx auto'
check "first message has the brief" 'grep -q "Sub-plan B: SARP outbox." "$work/out.args"'
check "first message has the rules with names filled in" \
  'grep -q "You are \`crew-b\`" "$work/out.args" && grep -q "session \`orch-1\`" "$work/out.args" && ! grep -q "{{" "$work/out.args"'
check "first message names the brief file" 'grep -qF "\`$work/b.md\`" "$work/out.args"'
check "writes the full message next to the brief" '[ -f "$work/b.prompt.md" ]'
check "passes no model or effort when none is given" '! grep -qx -- "--model" "$work/out.args" && ! grep -qx -- "--effort" "$work/out.args"'
tmux -L "$sock" kill-server 2>/dev/null

rm -f "$work"/out.* "$work/rc"
launch c orch-1 "$work/repo" "$work/b.md" sonnet high
check "passes the model and effort it is given" \
  'grep -A1 -x -- "--model" "$work/out.args" | grep -qx sonnet && grep -A1 -x -- "--effort" "$work/out.args" | grep -qx high'
tmux -L "$sock" kill-server 2>/dev/null

rm -f "$work"/out.* "$work/rc"
launch "Bad_Name" orch-1 "$work/repo" "$work/b.md"
check "refuses a name that is not lowercase-hyphen" '[ "$(cat "$work/rc")" != 0 ] && grep -q "name must be" "$work/stderr" && [ ! -e "$work/out.args" ]'

exit $fail

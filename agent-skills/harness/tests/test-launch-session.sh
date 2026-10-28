#!/usr/bin/env bash
# Tests launch-session.sh, and the handoff launchers that call it, with a fake `claude` and
# `codex` on a throwaway tmux server: no model is called and the user's tmux is not touched.
# Usage: test-launch-session.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/../scripts/launch-session.sh
handoff=$here/../../skills/handoff/scripts
work=$(mktemp -d "${TMPDIR:-/tmp}/session-test.XXXXXX")
work=$(cd "$work" && pwd -P)
sock="session-test-$$"
trap 'tmux -L "$sock" kill-server 2>/dev/null; rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

mkdir -p "$work/bin" "$work/repo"
# The fakes record their working directory and their arguments, one per line.
for agent in claude codex; do
  cat >"$work/bin/$agent" <<'F'
#!/usr/bin/env bash
pwd >"$FAKE_OUT.pwd"
printf '%s\n' "$@" >"$FAKE_OUT.args"
F
  chmod +x "$work/bin/$agent"
done
printf 'First line of the prompt.\nSecond line.\n' >"$work/prompt.md"

# Runs a command inside the caller window of a fresh throwaway server, as an agent would.
# A new tmux window takes the server's environment, so the server starts with the fakes on PATH.
launch() {
  tmux -L "$sock" kill-server 2>/dev/null
  rm -f "$work"/out.* "$work/rc" "$work/stderr"
  local line
  printf -v line '%q ' "$@"
  PATH="$work/bin:$PATH" FAKE_OUT="$work/out" tmux -L "$sock" new-session -d -s main -n caller \
    "$line 2>'$work/stderr'; echo \$? >'$work/rc'; sleep 30"
  for _ in $(seq 100); do [ -s "$work/rc" ] && break; sleep 0.1; done
  [ "$(cat "$work/rc")" = 0 ] || return 0
  for _ in $(seq 100); do [ -s "$work/out.args" ] && break; sleep 0.1; done
}
arg_after() { grep -A1 -x -- "$1" "$work/out.args" | sed -n 2p; }
windows() { tmux -L "$sock" list-windows -t main -F "#{window_name}" | paste -sd, -; }

launch "$script" --name crew-x --permission-mode auto --model sonnet --effort high --window crew-x \
  claude "$work/repo" "$work/prompt.md"
check "claude: exits 0" '[ "$(cat "$work/rc")" = 0 ]'
check "claude: window named after the option, right after the caller" '[ "$(windows)" = "caller,crew-x" ]'
check "claude: focus stays on the caller" '[ "$(tmux -L "$sock" display-message -p -t main "#{window_name}")" = caller ]'
check "claude: starts in the working directory" '[ "$(cat "$work/out.pwd")" = "$work/repo" ]'
check "claude: passes name, mode, model and effort" \
  '[ "$(arg_after --name)" = crew-x ] && [ "$(arg_after --permission-mode)" = auto ] && [ "$(arg_after --model)" = sonnet ] && [ "$(arg_after --effort)" = high ]'
check "claude: the whole prompt is the last argument" '[ "$(tail -2 "$work/out.args")" = "$(cat "$work/prompt.md")" ]'

launch "$script" claude "$work/repo" "$work/prompt.md"
check "claude: no options passes none" '[ "$(head -1 "$work/out.args")" = "First line of the prompt." ]'

launch "$script" --model gpt-6-luna --effort high codex "$work/repo" "$work/prompt.md"
check "codex: passes the model with -m" '[ "$(arg_after -m)" = gpt-6-luna ]'
check "codex: passes the effort as a config value" '[ "$(arg_after -c)" = "model_reasoning_effort=\"high\"" ]'
check "codex: the whole prompt is the last argument" '[ "$(tail -2 "$work/out.args")" = "$(cat "$work/prompt.md")" ]'

launch "$script" --name x codex "$work/repo" "$work/prompt.md"
check "codex: refuses --name" '[ "$(cat "$work/rc")" != 0 ] && grep -q "claude only" "$work/stderr" && [ ! -e "$work/out.args" ]'
launch "$script" --colour red claude "$work/repo" "$work/prompt.md"
check "refuses an unknown option" '[ "$(cat "$work/rc")" != 0 ] && grep -q "unknown option" "$work/stderr"'
launch "$script" claude "$work/repo" prompt.md
check "refuses a relative prompt path" '[ "$(cat "$work/rc")" != 0 ] && grep -q "absolute" "$work/stderr"'

launch "$handoff/launch-claude.sh" "$work/repo" "$work/prompt.md" opus max
check "handoff claude: passes model and effort" '[ "$(arg_after --model)" = opus ] && [ "$(arg_after --effort)" = max ]'
launch "$handoff/launch-codex.sh" "$work/repo" "$work/prompt.md"
check "handoff codex: without model or effort passes none" '[ "$(head -1 "$work/out.args")" = "First line of the prompt." ]'

# Outside tmux and Terminal.app nothing opens.
rm -f "$work/stderr"
env -u TMUX TERM_PROGRAM=other PATH="$work/bin:$PATH" "$script" claude "$work/repo" "$work/prompt.md" 2>"$work/stderr"
check "refuses outside tmux and Terminal.app" '[ $? -ne 0 ] && grep -q "run inside tmux" "$work/stderr"'

exit $fail

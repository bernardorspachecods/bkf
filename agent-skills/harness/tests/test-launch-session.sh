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
printf '%s\n' "${BKF_DELEGATED-unset}" >"$FAKE_OUT.delegated"
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

check "claude: a session without --delegated has no BKF_DELEGATED" '[ "$(cat "$work/out.delegated")" = unset ]'

launch "$script" --delegated --name crew-x claude "$work/repo" "$work/prompt.md"
check "claude: --delegated sets BKF_DELEGATED and is not passed on" \
  '[ "$(cat "$work/out.delegated")" = 1 ] && ! grep -qx -- --delegated "$work/out.args"'

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

# Placement: the new window goes right after the caller when the working directory is in the
# caller's repository, else right after the last window of its repository, else at the end.
# place <caller-dir> <target-dir> [name:dir]...: the caller window is first, the other windows follow,
# the launcher runs from the caller once every window exists; the result is the window order.
for d in a b c; do
  mkdir -p "$work/$d" && git -C "$work/$d" init -q && git -C "$work/$d" -c user.name=t -c user.email=t@t commit -q --allow-empty -m x
done
git -C "$work/a" worktree add -q "$work/a-wt" 2>/dev/null
mkdir -p "$work/plain1" "$work/plain2"
place() {
  local caller_dir=$1 target=$2 w
  shift 2
  tmux -L "$sock" kill-server 2>/dev/null
  rm -f "$work/rc" "$work/go"
  PATH="$work/bin:$PATH" FAKE_OUT="$work/out" tmux -L "$sock" new-session -d -s main -n caller -c "$caller_dir" \
    "while [ ! -e '$work/go' ]; do sleep 0.1; done; '$script' --window new claude '$target' '$work/prompt.md' 2>'$work/stderr'; echo \$? >'$work/rc'; sleep 30"
  for w in "$@"; do tmux -L "$sock" new-window -d -t main: -n "${w%%:*}" -c "${w#*:}" "sleep 30"; done
  touch "$work/go"
  for _ in $(seq 100); do [ -s "$work/rc" ] && break; sleep 0.1; done
  windows
}
check "placement: same repository goes right after the caller" \
  '[ "$(place "$work/a" "$work/a" b1:"$work/b" a2:"$work/a")" = "caller,new,b1,a2" ]'
check "placement: a worktree of the caller's repository counts as the same" \
  '[ "$(place "$work/a" "$work/a-wt" b1:"$work/b" a2:"$work/a")" = "caller,new,b1,a2" ]'
check "placement: another repository goes after the last of its windows" \
  '[ "$(place "$work/a" "$work/b" b1:"$work/b" a2:"$work/a" b2:"$work/b" a3:"$work/a")" = "caller,b1,a2,b2,new,a3" ]'
check "placement: a worktree window groups with its repository" \
  '[ "$(place "$work/b" "$work/a-wt" a1:"$work/a" b1:"$work/b" a2:"$work/a-wt" b2:"$work/b")" = "caller,a1,b1,a2,new,b2" ]'
check "placement: a repository with no window goes to the end" \
  '[ "$(place "$work/a" "$work/c" b1:"$work/b" a2:"$work/a")" = "caller,b1,a2,new" ]'
check "placement: a subdirectory belongs to its repository" \
  '[ "$(mkdir -p "$work/b/sub"; place "$work/a" "$work/b/sub" b1:"$work/b" a2:"$work/a")" = "caller,b1,new,a2" ]'
check "placement: outside git the directory itself is the key" \
  '[ "$(place "$work/plain1" "$work/plain2" p1:"$work/plain1" p2:"$work/plain2" p3:"$work/plain1")" = "caller,p1,p2,new,p3" ]'
check "placement: a plain directory of no other window goes to the end" \
  '[ "$(place "$work/plain1" "$work/plain2" p1:"$work/plain1")" = "caller,p1,new" ]'

launch "$handoff/launch-claude.sh" "$work/repo" "$work/prompt.md" opus max
check "handoff claude: passes model and effort" '[ "$(arg_after --model)" = opus ] && [ "$(arg_after --effort)" = max ]'
launch "$handoff/launch-codex.sh" "$work/repo" "$work/prompt.md"
check "handoff codex: without model or effort passes none" '[ "$(head -1 "$work/out.args")" = "First line of the prompt." ]'

# Outside tmux and Terminal.app nothing opens.
rm -f "$work/stderr"
env -u TMUX TERM_PROGRAM=other PATH="$work/bin:$PATH" "$script" claude "$work/repo" "$work/prompt.md" 2>"$work/stderr"
check "refuses outside tmux and Terminal.app" '[ $? -ne 0 ] && grep -q "run inside tmux" "$work/stderr"'

# The iTerm2 and Terminal.app paths need those apps, so only their AppleScript is checked: each
# block must compile.
awk -v dir="$work" '/<<'"'"'APPLESCRIPT'"'"'/{n++; f=dir"/as-"n".applescript"; next} /^APPLESCRIPT$/{f=""; next} f{print > f}' "$script"
check "the launcher has three AppleScript blocks" '[ "$(ls "$work"/as-*.applescript | wc -l | tr -d " ")" = 3 ]'
for f in "$work"/as-*.applescript; do
  check "AppleScript $(basename "$f") compiles" 'osacompile -o "$work/out.scpt" "$f" 2>/dev/null'
done

exit $fail

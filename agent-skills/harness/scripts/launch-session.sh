#!/usr/bin/env bash
# Open an interactive Claude or Codex session in a new tab beside the caller, with a prompt
# file as its first message. Shared by the handoff and crew skills.
# Usage: launch-session.sh [--name NAME] [--model MODEL] [--effort EFFORT]
#                          [--permission-mode MODE] [--window NAME] <claude|codex> <working-dir> <prompt-file>
# --name and --permission-mode exist for Claude only. --window names the tmux window.
# Without --model or --effort the session takes the user's defaults.
set -euo pipefail

die() { printf 'Error: %s\n' "$1" >&2; exit 1; }

name="" model="" effort="" mode="" window=""
while [[ $# -gt 0 && $1 == --* ]]; do
  [[ $# -ge 2 ]] || die "$1 needs a value"
  case $1 in
    --name) name=$2 ;;
    --model) model=$2 ;;
    --effort) effort=$2 ;;
    --permission-mode) mode=$2 ;;
    --window) window=$2 ;;
    *) die "unknown option: $1" ;;
  esac
  shift 2
done
[[ $# -eq 3 ]] || die "usage: launch-session.sh [options] <claude|codex> <working-dir> <prompt-file>"
agent=$1 dir=$2 prompt=$3

[[ $agent == claude || $agent == codex ]] || die "agent must be claude or codex: $agent"
[[ -d $dir ]] || die "not a directory: $dir"
[[ $prompt == /* ]] || die "prompt path must be absolute: $prompt"
[[ -f $prompt ]] || die "not a file: $prompt"
command -v "$agent" >/dev/null || die "$agent not found on PATH"
[[ $agent == claude || ( -z $name && -z $mode ) ]] || die "--name and --permission-mode are for claude only"

q() { printf '%q' "$1"; }
if [[ $agent == claude ]]; then
  cmd="claude"
  [[ -n $name ]] && cmd+=" --name $(q "$name")"
  [[ -n $mode ]] && cmd+=" --permission-mode $(q "$mode")"
  [[ -n $model ]] && cmd+=" --model $(q "$model")"
  [[ -n $effort ]] && cmd+=" --effort $(q "$effort")"
else
  cmd="codex"
  [[ -n $model ]] && cmd+=" -m $(q "$model")"
  [[ -n $effort ]] && cmd+=" -c $(q "model_reasoning_effort=\"$effort\"")"
fi
# The tab types only a short command; its shell expands the file into the argument,
# because a typed line of tens of KB overflows the terminal.
cmd="cd $(q "$dir") && $cmd \"\$(cat $(q "$prompt"))\""

# Inside tmux, the tab is a tmux window placed right after the caller's window without taking
# focus; under iTerm2's tmux -CC it shows as an iTerm2 tab. In Terminal.app it is a new window:
# Terminal has no command to add a tab to a given window, and a simulated cmd+T lands in
# whichever window has focus. After the agent exits, a login shell stays open in the tab.
#
# iTerm2 shows a new tmux window as a tab of its focused window, or of a new window when the
# focused one belongs to another tmux client, never of the caller's window. So when iTerm2 is
# attached (a tmux client in control mode), the caller's iTerm2 window gets focus until the tab
# appears there, and the window focused before gets it back.
iterm_focus_caller() {
  osascript - "${TMUX_PANE#%}" <<'APPLESCRIPT' || true
on run argv
  tell application "iTerm2"
    set focusedId to id of current window
    repeat with w in windows
      repeat with t in tabs of w
        if (variable of (current session of t) named "tmuxWindowPane") is (item 1 of argv) then
          set tabCount to count of tabs of w
          select w
          return (focusedId as text) & " " & (id of w) & " " & tabCount
        end if
      end repeat
    end repeat
  end tell
end run
APPLESCRIPT
}
iterm_restore_focus() { # <window focused before> <caller window> <its tab count before>
  osascript - "$@" <<'APPLESCRIPT' >/dev/null || true
on run argv
  tell application "iTerm2"
    repeat 30 times
      if (count of tabs of window id ((item 2 of argv) as integer)) > ((item 3 of argv) as integer) then exit repeat
      delay 0.1
    end repeat
    select window id ((item 1 of argv) as integer)
  end tell
end run
APPLESCRIPT
}

if [[ -n ${TMUX:-} ]]; then
  caller=$(tmux display-message -p -t "${TMUX_PANE:?TMUX set without TMUX_PANE}" '#{window_id}')
  focus=""
  if tmux list-clients -t "$(tmux display-message -p -t "$TMUX_PANE" '#{session_id}')" -F '#{client_control_mode}' | grep -qx 1; then
    focus=$(iterm_focus_caller)
  fi
  tmux new-window -d -a -t "$caller" ${window:+-n "$window"} "$cmd; exec \"\${SHELL:-/bin/zsh}\" -l"
  [[ -z $focus ]] || iterm_restore_focus $focus
elif [[ ${TERM_PROGRAM:-} == Apple_Terminal ]]; then
  # The command travels as an argument, so it needs no AppleScript escaping.
  osascript - "$cmd" >/dev/null <<'APPLESCRIPT'
on run argv
  tell application "Terminal" to do script (item 1 of argv)
end run
APPLESCRIPT
else
  die "run inside tmux or Terminal.app; TERM_PROGRAM is ${TERM_PROGRAM:-unset}"
fi

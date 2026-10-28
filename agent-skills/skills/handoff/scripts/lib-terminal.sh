#!/usr/bin/env bash
# Shared by the launch scripts: check the arguments and open a terminal tab.

# check_args <working-dir> <handoff-file> <agent-command>
check_args() {
  [[ -d "$1" ]] || { printf 'Error: not a directory: %s\n' "$1" >&2; exit 1; }
  [[ -f "$2" ]] || { printf 'Error: not a file: %s\n' "$2" >&2; exit 1; }
  [[ "$2" = /* ]] || { printf 'Error: handoff path must be absolute: %s\n' "$2" >&2; exit 1; }
  command -v "$3" >/dev/null || { printf 'Error: %s not found on PATH\n' "$3" >&2; exit 1; }
}

# open_tab <shell-command>: run the command in a new tab beside the caller.
# Inside tmux, the tab is a tmux window placed right after the caller's window
# without taking focus; under iTerm2's tmux -CC it shows as an iTerm2 tab.
# In Terminal.app it is a new window: Terminal has no command to add a tab to
# a given window, and a simulated cmd+T lands in whichever window has focus.
# After the agent exits, a login shell stays open in the tab, as in Terminal.
open_tab() {
  if [[ -n ${TMUX:-} ]]; then
    local window
    window=$(tmux display-message -p -t "${TMUX_PANE:?TMUX set without TMUX_PANE}" '#{window_id}')
    tmux new-window -d -a -t "$window" "$1; exec \"\${SHELL:-/bin/zsh}\" -l"
  elif [[ ${TERM_PROGRAM:-} = Apple_Terminal ]]; then
    # The command travels as an argument, so it needs no AppleScript escaping.
    osascript - "$1" <<'APPLESCRIPT'
on run argv
  tell application "Terminal" to do script (item 1 of argv)
end run
APPLESCRIPT
  else
    printf 'Error: run inside tmux or Terminal.app; TERM_PROGRAM is %s\n' "${TERM_PROGRAM:-unset}" >&2
    exit 1
  fi
}

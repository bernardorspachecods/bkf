#!/usr/bin/env bash
# Shared by the launch scripts: check the arguments and open a Terminal.app tab.

# check_args <working-dir> <handoff-file> <agent-command>
check_args() {
  [[ -d "$1" ]] || { printf 'Error: not a directory: %s\n' "$1" >&2; exit 1; }
  [[ -f "$2" ]] || { printf 'Error: not a file: %s\n' "$2" >&2; exit 1; }
  [[ "$2" = /* ]] || { printf 'Error: handoff path must be absolute: %s\n' "$2" >&2; exit 1; }
  command -v "$3" >/dev/null || { printf 'Error: %s not found on PATH\n' "$3" >&2; exit 1; }
}

# open_tab <shell-command>: run the command in a new Terminal.app tab.
open_tab() {
# The command travels as an argument, so it needs no AppleScript escaping.
# Opens a tab with cmd+T, which needs Accessibility permission. Terminal counts
# each tab of a tabbed window as a window, so a new tab shows as one more
# window. If none appears, falls back to a new window; running in the existing
# tab would type into the session that is open there.
osascript - "$1" <<'APPLESCRIPT'
on run argv
  set cmd to item 1 of argv
  tell application "Terminal"
    activate
    if (count of windows) is 0 then
      do script cmd
      return
    end if
    set windowsBefore to count of windows
  end tell
  try
    delay 0.2
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
  end try
  tell application "Terminal"
    if (count of windows) > windowsBefore then
      do script cmd in front window
    else
      do script cmd
    end if
  end tell
end run
APPLESCRIPT
}

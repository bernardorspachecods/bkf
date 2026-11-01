#!/usr/bin/env bash
# Wait, without the model, until every coordinator of a phase has written its done file, then run a command
# (the one that opens the next orchestrator). Meanwhile it watches the coordinators that are not done
# and notifies the user of an alert; it never wakes an orchestrator and never opens one for a partial phase.
# Usage: await-crew.sh <crew-dir> <target>... -- <command> [args...]
#   target: tmux target of a coordinator, e.g. main:crew-sarp. Its done file is <crew-dir>/done/sarp.md.
# Run it in a tmux window of its own, not as a background task of a chat: it must outlive the chat.
# Env: AWAIT_INTERVAL (seconds between checks, default 30); the WATCH_* variables of watch-coordinators.sh,
# which this script runs. WATCH_NOTIFY is used for the alerts and for the final notice.
# Exit: 0 when the command ran (its status is printed), 2 on a usage error.
set -uo pipefail

crew=${1:?crew dir}; shift
targets=()
while (( $# )) && [[ $1 != -- ]]; do targets+=("$1"); shift; done
(( $# )) && shift
(( ${#targets[@]} )) && (( $# )) || { echo 'Usage: await-crew.sh <crew-dir> <target>... -- <command> [args...]' >&2; exit 2; }
interval=${AWAIT_INTERVAL:-30}
here=$(cd "$(dirname "$0")" && pwd)
state="$crew/.await"
mkdir -p "$crew/done" "$state" || exit 2

notify() {
  if [[ -n ${WATCH_NOTIFY:-} ]]; then $WATCH_NOTIFY "$1"
  else osascript -e "display notification \"${1//\"/}\" with title \"crew\"" 2>/dev/null; fi
  return 0
}

# A coordinator is done when its done file exists and is not empty.
is_done() { local w=${1#*:}; [[ -s $crew/done/${w#crew-}.md ]]; }

child=; child_for=
stop_child() { [[ -n $child ]] && kill "$child" 2>/dev/null && wait "$child" 2>/dev/null; child=; child_for=; return 0; }
trap stop_child EXIT

while :; do
  pending=()
  for t in "${targets[@]}"; do is_done "$t" || pending+=("$t"); done
  if (( ! ${#pending[@]} )); then
    stop_child
    notify "crew: every coordinator is done"
    "$@"; rc=$?
    echo "await-crew: command exited $rc"
    exit 0
  fi
  # The watcher runs on the coordinators still working; a finished one idles and would raise STILL.
  if [[ $child_for != "${pending[*]}" ]] || ! kill -0 "$child" 2>/dev/null; then
    if [[ -n $child ]] && ! kill -0 "$child" 2>/dev/null; then
      wait "$child" 2>/dev/null; child=; child_for=
    else
      stop_child
    fi
    "$here/watch-coordinators.sh" "$state" "${pending[@]}" &
    child=$!; child_for="${pending[*]}"
  fi
  sleep "$interval"
done

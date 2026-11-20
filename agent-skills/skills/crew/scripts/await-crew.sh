#!/usr/bin/env bash
# Wait, without the model, until every coordinator of a phase is ready, then run a command (the one that
# opens the next orchestrator). A coordinator is ready when its task card (bkf task) is in review or done:
# it marks the card ready after it writes its done file. Meanwhile the script watches the coordinators that
# are not ready and notifies the user of an alert; it never wakes an orchestrator and never opens one for a
# partial phase.
# Usage: await-crew.sh <crew-dir> -- <command> [args...]
#   The coordinators are the cards in <crew-dir>/cards/: one file per coordinator, named by the coordinator,
#   holding its card id. The crew's own card (cards/crew) is not one. A card that cannot be read counts as
#   not ready. Its tmux window (session.tmux_window) is the target the watcher watches.
#   The done file <crew-dir>/done/<name>.md stays the coordinator's report, for the next orchestrator.
# Run it in a tmux window of its own, not as a background task of a chat: it must outlive the chat.
# Env: AWAIT_INTERVAL (seconds between checks, default 30); the WATCH_* variables of watch-coordinators.sh,
# which this script runs. WATCH_NOTIFY is used for the alerts and for the final notice.
# Exit: 0 when the command ran (its status is printed), 2 on a usage error or a crew with no coordinator cards.
set -uo pipefail

usage='Usage: await-crew.sh <crew-dir> -- <command> [args...]'
crew=${1:?crew dir}; shift
[[ ${1:-} == -- ]] || { echo "$usage" >&2; exit 2; }
shift
(( $# )) || { echo "$usage" >&2; exit 2; }
interval=${AWAIT_INTERVAL:-30}
here=$(cd "$(dirname "$0")" && pwd)
cards="$crew/cards"
state="$crew/.await"
mkdir -p "$crew/done" "$state" || exit 2
shopt -s nullglob

notify() {
  if [[ -n ${WATCH_NOTIFY:-} ]]; then $WATCH_NOTIFY "$1"
  else osascript -e "display notification \"${1//\"/}\" with title \"crew\"" 2>/dev/null; fi
  return 0
}

# The coordinators' names: every card in cards/ except the crew's own.
coordinators() {
  local f
  for f in "$cards"/*; do
    [[ ${f##*/} == crew ]] || printf '%s\n' "${f##*/}"
  done
}
[[ -n $(coordinators) ]] || { echo "Error: no coordinator cards in $cards" >&2; exit 2; }

# Prints "<status> <tmux window>" of the card a coordinator names ("-" when it has no window); fails when
# the card cannot be read.
card_state() {
  local id out
  id=$(<"$cards/$1") || return 1
  [[ -n $id ]] || return 1
  out=$(bkf task show "$id" --json 2>/dev/null) || return 1
  printf '%s' "$out" | python3 -c '
import json, sys
task = json.load(sys.stdin)
session = task.get("session") or {}
print(task["status"], session.get("tmux_window") or "-")' 2>/dev/null
}

child=; child_for=
stop_child() { [[ -n $child ]] && kill "$child" 2>/dev/null && wait "$child" 2>/dev/null; child=; child_for=; return 0; }
trap stop_child EXIT

while :; do
  names=$(coordinators)
  if [[ -z $names ]]; then sleep "$interval"; continue; fi
  pending=(); targets=(); unreadable=()
  for name in $names; do
    if ! st=$(card_state "$name"); then
      unreadable+=("$name"); pending+=("$name"); continue
    fi
    st_status=${st%% *}; window=${st#* }
    case $st_status in
      review|done) continue ;;
    esac
    pending+=("$name")
    [[ $window == - ]] || targets+=("$window=$(<"$cards/$name")")
  done
  for name in ${unreadable[@]+"${unreadable[@]}"}; do
    echo "await-crew: cannot read the card of $name; it counts as not ready" >&2
  done
  if (( ! ${#pending[@]} )); then
    stop_child
    notify "crew: every coordinator is done"
    "$@"; rc=$?
    echo "await-crew: command exited $rc"
    exit 0
  fi
  # The watcher runs on the coordinators still working, each with its card so that it sets their attention;
  # a finished one idles and would raise STILL.
  if (( ! ${#targets[@]} )); then
    stop_child
  elif [[ $child_for != "${targets[*]}" ]] || ! kill -0 "$child" 2>/dev/null; then
    if [[ -n $child ]] && ! kill -0 "$child" 2>/dev/null; then
      wait "$child" 2>/dev/null; child=; child_for=
    else
      stop_child
    fi
    "$here/watch-coordinators.sh" "$state" "${targets[@]}" &
    child=$!; child_for="${targets[*]}"
  fi
  sleep "$interval"
done

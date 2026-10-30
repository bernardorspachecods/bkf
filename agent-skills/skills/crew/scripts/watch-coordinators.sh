#!/usr/bin/env bash
# Watch the tmux panes of a crew's coordinators without the model, and exit when one needs attention.
# Usage: watch-coordinators.sh <state-dir> <target>...        (target: tmux target, e.g. main:crew-sarp)
# Env: WATCH_INTERVAL (seconds between checks, default 60), WATCH_STILL (seconds a pane may stay
# unchanged, default 600), WATCH_REMIND (seconds before an unchanged alert repeats, default 3600),
# WATCH_NOTIFY (command run with the alert text; default a macOS notification).
# Run it with run_in_background: every exit wakes the caller. Output is one line per alert:
#   PROMPT <target>   the pane shows a permission prompt
#   STILL <target>    the pane has not changed for WATCH_STILL seconds (prompt of any wording, stall, or wait)
#   GONE <target>     the pane cannot be captured (window or tmux server gone)
#   WATCHER-EXIT      the script stopped without alerting; nothing is being watched
# State lives in <state-dir>, so a relaunch neither repeats a delivered alert nor loses an undelivered one.
set -uo pipefail

state=${1:?state dir}; shift
(( $# )) || { echo 'Error: no targets' >&2; exit 2; }
interval=${WATCH_INTERVAL:-60}
still=${WATCH_STILL:-600}
remind=${WATCH_REMIND:-3600}
mkdir -p "$state" || exit 2

notify() {
  if [[ -n ${WATCH_NOTIFY:-} ]]; then $WATCH_NOTIFY "$1"
  else osascript -e "display notification \"${1//\"/}\" with title \"crew\"" 2>/dev/null; fi
  return 0
}

clean=0
trap '(( clean )) || { echo "WATCHER-EXIT"; notify "crew watcher stopped"; }' EXIT

prompt_re='Do you want to|\(y/n\)|❯ ?1\. Yes|Allow this|Esc to cancel|waiting for (your )?(approval|permission)'

while :; do
  alerts=(); pending_write=()
  now=$(date +%s)
  for t in "$@"; do
    f="$state/${t//[^A-Za-z0-9_-]/_}"
    if ! pane=$(tmux capture-pane -p -t "$t" 2>/dev/null); then
      alerts+=("GONE $t"); continue
    fi
    sum=$(printf '%s' "$pane" | cksum | cut -d' ' -f1)
    psum=; since=$now; alerted_sum=; alerted_at=0
    [[ -f $f ]] && read -r psum since alerted_sum alerted_at <"$f"
    [[ $alerted_sum == - ]] && alerted_sum=
    [[ $sum == "$psum" ]] || { since=$now; }
    kind=
    if printf '%s\n' "$pane" | tail -n 15 | grep -Eq "$prompt_re"; then kind=PROMPT
    elif (( now - since >= still )); then kind=STILL; fi
    if [[ -n $kind ]]; then
      if [[ $alerted_sum != "$sum" ]] || (( now - alerted_at >= remind )); then
        alerts+=("$kind $t"); alerted_sum=$sum; alerted_at=$now
      fi
    fi
    # Persisted only now; if the script dies before printing, the alert was not marked as delivered.
    pending_write+=("$f|$sum $since ${alerted_sum:--} $alerted_at")
  done
  if (( ${#alerts[@]} )); then
    printf '%s\n' "${alerts[@]}"
    for w in ${pending_write[@]+"${pending_write[@]}"}; do printf '%s\n' "${w#*|}" >"${w%%|*}"; done
    notify "crew: ${alerts[*]}"
    clean=1; exit 0
  fi
  for w in ${pending_write[@]+"${pending_write[@]}"}; do printf '%s\n' "${w#*|}" >"${w%%|*}"; done
  sleep "$interval"
done

#!/usr/bin/env bash
# Watch the tmux panes of a crew's coordinators without the model, and exit when one needs attention.
# Usage: watch-coordinators.sh <state-dir> <target>...
#   target: a tmux target, e.g. main:crew-sarp; or <tmux-target>=<card-id>, a target with its bkf task card.
#   With a card, each alert also sets the card's attention (`bkf task attention <card> --set prompt|still|
#   overdue|gone`), and the first change of the pane after an alert clears it (`--clear`). A failing bkf is
#   printed on standard error and never stops the watcher. Without a card, nothing touches bkf.
# Env: WATCH_INTERVAL (seconds between checks, default 60), WATCH_STILL (seconds a pane may stay
# unchanged, default 600), WATCH_REMIND (seconds before an unchanged alert repeats, default 3600),
# WATCH_WAITS (folder where `harness quota-wait --announce` writes the
# wake-up time of a coordinator's quota wait, default ~/.crew-waits) and WATCH_GRACE (seconds past that
# time before the wait counts as overdue, default 300), WATCH_NOTIFY (command run with the alert text; default a macOS notification).
# Run it with run_in_background: every exit wakes the caller. Output is one line per alert:
#   PROMPT <target>   the pane shows a permission prompt
#   STILL <target>    the pane has not changed for WATCH_STILL seconds and nothing runs in the background
#                     (a prompt of any wording, or a stall): nothing will wake the coordinator. A pane whose
#                     status bar shows a background shell (`· N shell`) never raises it: the shell will wake
#                     the coordinator
#   OVERDUE <target>  a quota wait announced a wake-up time that passed WATCH_GRACE seconds ago and the pane has
#                     not changed: the wait hung or the coordinator did not resume. While the announced time
#                     is still ahead, the pane raises only PROMPT.
#   GONE <target>     the pane cannot be captured (window or tmux server gone)
#   WATCHER-EXIT      the script stopped without alerting; nothing is being watched
# State lives in <state-dir>, so a relaunch neither repeats a delivered alert nor loses an undelivered one.
set -uo pipefail

state=${1:?state dir}; shift
(( $# )) || { echo 'Error: no targets' >&2; exit 2; }
interval=${WATCH_INTERVAL:-60}
still=${WATCH_STILL:-600}
remind=${WATCH_REMIND:-3600}
waits=${WATCH_WAITS:-$HOME/.crew-waits}
grace=${WATCH_GRACE:-300}
mkdir -p "$state" || exit 2

notify() {
  if [[ -n ${WATCH_NOTIFY:-} ]]; then $WATCH_NOTIFY "$1"
  else osascript -e "display notification \"${1//\"/}\" with title \"crew\"" 2>/dev/null; fi
  return 0
}

# Sets (--set REASON) or clears (--clear) a card's attention. A failure is printed on standard error only.
card_attention() {
  local out
  if ! out=$(bkf task attention "$@" 2>&1); then
    printf 'watch-coordinators: bkf task attention %s failed: %s\n' "$*" "$out" >&2
  fi
  return 0
}

clean=0
trap '(( clean )) || { echo "WATCHER-EXIT"; notify "crew watcher stopped"; }' EXIT

# The last line of the status bar names the background shells, as in `auto mode on · 1 shell`.
shell_re='· [0-9]+ shells?[[:space:]]*$'
prompt_re='Do you want to|\(y/n\)|❯ ?1\. Yes|Allow this|Esc to cancel|waiting for (your )?(approval|permission)'

while :; do
  alerts=(); attn=(); pending_write=()
  now=$(date +%s)
  for spec in "$@"; do
    t=$spec; card=
    if [[ $spec == *=* ]]; then t=${spec%=*}; card=${spec##*=}; fi
    f="$state/${t//[^A-Za-z0-9_-]/_}"
    if ! pane=$(tmux capture-pane -p -t "$t" 2>/dev/null); then
      alerts+=("GONE $t"); [[ -n $card ]] && attn+=("$card|gone"); continue
    fi
    sum=$(printf '%s' "$pane" | cksum | cut -d' ' -f1)
    psum=; since=$now; alerted_sum=; alerted_at=0
    [[ -f $f ]] && read -r psum since alerted_sum alerted_at <"$f"
    [[ $alerted_sum == - ]] && alerted_sum=
    [[ $sum == "$psum" ]] || { since=$now; }
    # The first change of the pane after an alert clears the card's attention.
    if [[ -n $card && -n $alerted_sum && $sum != "$alerted_sum" ]]; then
      card_attention "$card" --clear
      alerted_sum=
    fi
    # The quota-wait file is keyed by the session name, crew-<name>: for a window id, that is the window's name.
    key=${t#*:}
    if [[ $t == @* ]]; then key=$(tmux display-message -p -t "$t" '#{window_name}' 2>/dev/null); fi
    kind=; limit=$still; again=$remind
    if printf '%s\n' "$pane" | tail -n 15 | grep -Eq "$prompt_re"; then kind=PROMPT
    elif [[ -r $waits/$key ]] && read -r due <"$waits/$key" && [[ $due =~ ^[0-9]+$ ]]; then
      # A quota wait announced when it ends: silent until that time has passed by the grace.
      (( now >= due + grace && now - since >= still )) && kind=OVERDUE
    else
      if (( now - since >= limit )) && ! printf '%s\n' "$pane" | sed '/^[[:space:]]*$/d' | tail -n 1 | grep -Eq "$shell_re"; then kind=STILL; fi
    fi
    if [[ -n $kind ]]; then
      if [[ $alerted_sum != "$sum" ]] || (( now - alerted_at >= again )); then
        alerts+=("$kind $t")
        [[ -n $card ]] && attn+=("$card|$(printf '%s' "$kind" | tr '[:upper:]' '[:lower:]')")
        alerted_sum=$sum; alerted_at=$now
      fi
    fi
    # Persisted only now; if the script dies before printing, the alert was not marked as delivered.
    pending_write+=("$f|$sum $since ${alerted_sum:--} $alerted_at")
  done
  if (( ${#alerts[@]} )); then
    printf '%s\n' "${alerts[@]}"
    for a in ${attn[@]+"${attn[@]}"}; do card_attention "${a%%|*}" --set "${a#*|}"; done
    for w in ${pending_write[@]+"${pending_write[@]}"}; do printf '%s\n' "${w#*|}" >"${w%%|*}"; done
    notify "crew: ${alerts[*]}"
    clean=1; exit 0
  fi
  for w in ${pending_write[@]+"${pending_write[@]}"}; do printf '%s\n' "${w#*|}" >"${w%%|*}"; done
  sleep "$interval"
done

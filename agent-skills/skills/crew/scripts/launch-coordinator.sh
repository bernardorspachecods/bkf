#!/usr/bin/env bash
# Open a coordinator of a crew: a Claude session named crew-<name>, in a window beside the caller,
# whose first message is the brief followed by the crew's rules. The crew and each coordinator have a
# task card (bkf task): the crew's card is made before its first coordinator and kept in <crew>/cards/crew,
# each coordinator's card in <crew>/cards/<name>. Window placement is that of bkf launch.
# Usage: launch-coordinator.sh <name> <orchestrator-session> <working-dir> <brief-file> [model] [effort]
# Writes the full first message next to the brief as <brief>.prompt.md. Without a model or
# effort, the session takes the user's defaults.
set -euo pipefail

name=${1:?coordinator name}
orchestrator=${2:?orchestrator session name}
dir=${3:?working directory}
brief=${4:?brief file}
model=${5:-}
effort=${6:-}
[[ $name =~ ^[a-z0-9][a-z0-9-]*$ ]] || { printf 'Error: name must be lowercase letters, digits and hyphens: %s\n' "$name" >&2; exit 1; }
# The crew's own card is cards/crew; a coordinator of that name would overwrite it.
[[ $name != crew ]] || { printf 'Error: name crew is reserved for the crew card: %s\n' "$name" >&2; exit 1; }
[[ -f $brief && $brief == /* ]] || { printf 'Error: brief must be an absolute path to a file: %s\n' "$brief" >&2; exit 1; }

session="crew-$name"
prompt="${brief%.md}.prompt.md"
rules=$(<"$(dirname "$0")/coordinator-rules.md")
rules=${rules//'{{SESSION}}'/$session}
rules=${rules//'{{ORCHESTRATOR}}'/$orchestrator}
rules=${rules//'{{BRIEF}}'/$brief}
crew_dir=$(dirname "$brief")
rules=${rules//'{{DONE_FILE}}'/$crew_dir/done/$name.md}
rules=${rules//'{{DECISIONS}}'/$crew_dir/decisions.md}
rules=${rules//'{{WAIT_FILE}}'/${WATCH_WAITS:-$HOME/.crew-waits}/$session}
printf '%s\n\n---\n\n%s\n' "$(<"$brief")" "$rules" > "$prompt"

# The crew's card, once: it is the parent of every coordinator's card. Started in the orchestrator's window when it runs in tmux.
cards="$crew_dir/cards"
mkdir -p "$cards"
if [[ ! -s $cards/crew ]]; then
  crew_card=$(bkf task new --repo "$dir" --title "crew $(basename "$crew_dir")" --kind crew)
  printf '%s\n' "$crew_card" >"$cards/crew"
  if [[ -n ${TMUX:-} ]]; then
    bkf task start "$crew_card" \
      --tmux-session "$(tmux display-message -p -t "$TMUX_PANE" '#{session_name}')" \
      --tmux-window "$(tmux display-message -p -t "$TMUX_PANE" '#{window_id}')" >/dev/null
  fi
fi
crew_card=$(<"$cards/crew")

# Auto mode, like an orchestrator in auto mode: both count as prompting, so messages between them are delivered.
args=(--name "$session" --permission-mode auto --window "$session" --delegated
  --kind coordinator --parent "$crew_card" --title "$session" --json)
[[ -n $model ]] && args+=(--model "$model")
[[ -n $effort ]] && args+=(--effort "$effort")
launched=$(bkf launch claude --dir "$dir" --prompt-file "$prompt" "${args[@]}")
card=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["task"])' <<<"$launched")
printf '%s\n' "$card" >"$cards/$name"
printf '%s\n' "$session"

#!/usr/bin/env bash
# Open a coordinator of a crew: a Claude session named crew-<name>, in a tab beside the caller,
# whose first message is the brief followed by the crew's rules.
# Usage: launch-coordinator.sh <name> <orchestrator-session> <working-dir> <brief-file> [model] [effort]
# Writes the full first message next to the brief as <brief>.prompt.md. Without a model or
# effort, the session takes the user's defaults.
set -euo pipefail
source "$(dirname "$0")/../../handoff/scripts/lib-terminal.sh"

name=${1:?coordinator name}
orchestrator=${2:?orchestrator session name}
dir=${3:?working directory}
brief=${4:?brief file}
model=${5:-}
effort=${6:-}
[[ $name =~ ^[a-z0-9][a-z0-9-]*$ ]] || { printf 'Error: name must be lowercase letters, digits and hyphens: %s\n' "$name" >&2; exit 1; }
check_args "$dir" "$brief" claude

session="crew-$name"
prompt="${brief%.md}.prompt.md"
rules=$(<"$(dirname "$0")/coordinator-rules.md")
rules=${rules//'{{SESSION}}'/$session}
rules=${rules//'{{ORCHESTRATOR}}'/$orchestrator}
printf '%s\n\n---\n\n%s\n' "$(<"$brief")" "$rules" > "$prompt"

flags="--name $session"
[[ -n $model ]] && flags+=" --model $(printf '%q' "$model")"
[[ -n $effort ]] && flags+=" --effort $(printf '%q' "$effort")"
open_tab "cd $(printf '%q' "$dir") && claude $flags \"\$(cat $(printf '%q' "$prompt"))\"" "$session"
printf '%s\n' "$session"

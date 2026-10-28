#!/usr/bin/env bash
# Open a coordinator of a crew: a Claude session named crew-<name>, in a tab beside the caller,
# whose first message is the brief followed by the crew's rules.
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
[[ -f $brief && $brief == /* ]] || { printf 'Error: brief must be an absolute path to a file: %s\n' "$brief" >&2; exit 1; }

session="crew-$name"
prompt="${brief%.md}.prompt.md"
rules=$(<"$(dirname "$0")/coordinator-rules.md")
rules=${rules//'{{SESSION}}'/$session}
rules=${rules//'{{ORCHESTRATOR}}'/$orchestrator}
printf '%s\n\n---\n\n%s\n' "$(<"$brief")" "$rules" > "$prompt"

# Auto mode, like an orchestrator in auto mode: both count as prompting, so messages between them are delivered.
args=(--name "$session" --permission-mode auto --window "$session")
[[ -n $model ]] && args+=(--model "$model")
[[ -n $effort ]] && args+=(--effort "$effort")
"$(dirname "$0")/../../../harness/scripts/launch-session.sh" "${args[@]}" claude "$dir" "$prompt"
printf '%s\n' "$session"

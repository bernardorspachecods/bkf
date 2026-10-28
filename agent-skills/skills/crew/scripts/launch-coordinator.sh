#!/usr/bin/env bash
# Open a coordinator of a crew: a Claude session named crew-<name>, in a tab beside the caller,
# whose first message is the brief followed by the crew's rules.
# Usage: launch-coordinator.sh <name> <orchestrator-session> <working-dir> <brief-file>
# Writes the full first message next to the brief as <brief>.prompt.md.
set -euo pipefail
source "$(dirname "$0")/../../handoff/scripts/lib-terminal.sh"

name=${1:?coordinator name}
orchestrator=${2:?orchestrator session name}
dir=${3:?working directory}
brief=${4:?brief file}
[[ $name =~ ^[a-z0-9][a-z0-9-]*$ ]] || { printf 'Error: name must be lowercase letters, digits and hyphens: %s\n' "$name" >&2; exit 1; }
check_args "$dir" "$brief" claude

session="crew-$name"
prompt="${brief%.md}.prompt.md"
rules=$(<"$(dirname "$0")/coordinator-rules.md")
rules=${rules//'{{SESSION}}'/$session}
rules=${rules//'{{ORCHESTRATOR}}'/$orchestrator}
printf '%s\n\n---\n\n%s\n' "$(<"$brief")" "$rules" > "$prompt"

open_tab "cd $(printf '%q' "$dir") && claude --name $session \"\$(cat $(printf '%q' "$prompt"))\"" "$session"
printf '%s\n' "$session"

#!/usr/bin/env bash
# Open a new tab with a Claude session whose first message is the handoff.
# Usage: launch-claude.sh <working-dir> <handoff-file> [model] [effort]
set -euo pipefail
args=()
[[ -n ${3:-} ]] && args+=(--model "$3")
[[ -n ${4:-} ]] && args+=(--effort "$4")
exec "$(dirname "$0")/../../../harness/scripts/launch-session.sh" ${args[@]+"${args[@]}"} \
  claude "${1:?working directory}" "${2:?handoff file}"

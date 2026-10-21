#!/usr/bin/env bash
# Open a new Terminal.app tab with a Claude session whose first message is the handoff.
# Usage: launch-claude.sh <working-dir> <handoff-file>
# The tab types only a short command; the shell expands the file into the argument,
# because a typed line of tens of KB overflows the terminal.
set -euo pipefail
source "$(dirname "$0")/lib-terminal.sh"

dir=${1:?working directory}
handoff=${2:?handoff file}
check_args "$dir" "$handoff" claude

open_tab "cd $(printf '%q' "$dir") && claude \"\$(cat $(printf '%q' "$handoff"))\""

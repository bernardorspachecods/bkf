#!/usr/bin/env bash
# Open a new tab with a Codex session that reads the handoff file.
# Usage: launch-codex.sh <working-dir> <handoff-file>
set -euo pipefail
source "$(dirname "$0")/lib-terminal.sh"

dir=${1:?working directory}
handoff=${2:?handoff file}
check_args "$dir" "$handoff" codex

prompt="Read $handoff and continue the work it describes."
open_tab "cd $(printf '%q' "$dir") && codex $(printf '%q' "$prompt")"

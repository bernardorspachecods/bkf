#!/usr/bin/env bash
# Check one unit that the conversation agent implemented: gate by command, then a separate reviewer process.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
harness=$(cd "$here/../../../harness" && pwd)

exec env PYTHONPATH="$harness" python3 "$here/plan_unit.py" "$@"

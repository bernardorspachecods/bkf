#!/usr/bin/env bash
# Run the plan workflow through the Python harness engine.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
harness=$(cd "$here/../../../harness" && pwd)
workflow=$here/plan.py

exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$@"

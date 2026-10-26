#!/usr/bin/env bash
# Run the research workflow through the Python harness engine.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
harness=$(cd "$here/../harness" && pwd)
workflow=$here/../workflows/research.py

if [ "${1:-}" = finish ]; then
  shift
  delivery_only=0 keep_attempts=0 args=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --delivery-only) delivery_only=1 ;;
      --keep-attempts) keep_attempts=1 ;;
      *) args+=("$1") ;;
    esac
    shift
  done
  exec env PYTHONPATH="$harness" RESEARCH_FINISH_DELIVERY_ONLY="$delivery_only" \
    RESEARCH_FINISH_KEEP_ATTEMPTS="$keep_attempts" python3 -m harness run "$workflow" finish "${args[@]}"
fi
exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$@"

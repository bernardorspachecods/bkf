#!/usr/bin/env bash
# Run a council workflow through the Python harness engine.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
harness=$(cd "$here/../harness" && pwd)
workflow=$here/../workflows/council.py

if [ "${1:-}" = start ]; then
  sub=$1
  shift
  model=() effort=() positional=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -m|-e)
        option=$1
        [ "$#" -ge 2 ] || { echo 'council-run.sh: missing option value' >&2; exit 1; }
        value=$2
        if [ "$option" = -m ]; then model=(-m "$value"); else effort=(-e "$value"); fi
        shift 2
        ;;
      *) positional+=("$1"); shift ;;
    esac
  done
  exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$sub" \
    "${model[@]+${model[@]}}" "${effort[@]+${effort[@]}}" "${positional[@]+${positional[@]}}"
fi

exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$@"

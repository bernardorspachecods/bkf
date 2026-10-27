#!/usr/bin/env bash
# Run the review workflow through the Python harness engine.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
harness=$(cd "$here/../../../harness" && pwd)
workflow=$here/review.py

if [ "${1:-}" = start ]; then
  sub=$1
  shift
  model=() effort=() options=() positional=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -m|-e)
        option=$1
        [ "$#" -ge 2 ] || { echo 'review-run.sh: missing option value' >&2; exit 1; }
        value=$2
        if [ "$option" = -m ]; then model=(-m "$value"); else effort=(-e "$value"); fi
        shift 2
        ;;
      -2)
        options+=("$1")
        shift
        ;;
      -s|-d|-g)
        option=$1
        [ "$#" -ge 2 ] || { echo 'review-run.sh: missing option value' >&2; exit 1; }
        options+=("$option" "$2")
        shift 2
        ;;
      *)
        positional+=("$1")
        shift
        ;;
    esac
  done
  [ "${#positional[@]}" -eq 2 ] || exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$sub" "${model[@]+"${model[@]}"}" "${effort[@]+"${effort[@]}"}" "${positional[@]+"${positional[@]}"}" "${options[@]+"${options[@]}"}"
  name=${positional[0]}
  target=${positional[1]}
  exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$sub" "${model[@]+"${model[@]}"}" "${effort[@]+"${effort[@]}"}" "$name" "${options[@]+"${options[@]}"}" "$target"
fi

exec env PYTHONPATH="$harness" python3 -m harness run "$workflow" "$@"

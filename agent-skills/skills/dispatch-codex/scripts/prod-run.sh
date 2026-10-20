#!/usr/bin/env bash
# Runs one command with the Production DATABASE_URL, read from the KeePassXC vault, and only for that command.
# Usage: prod-run.sh <command> [args...]
#
# The vault holds the only copy of the Production credential; no file on disk has it. Reading it asks for the
# master password on the terminal, so a human must be present: without a terminal the script refuses, and an
# agent has no way to supply the password. Never put the master password in a file, a variable or a command.
#
# PROD_VAULT   vault file (default ~/Library/prod-secrets.kdbx)
# PROD_ENTRY   entry holding the URL in its Password field (default desmor-hub-prod-db)
set -euo pipefail

[ "$#" -gt 0 ] || { echo "usage: prod-run.sh <command> [args...]" >&2; exit 2; }
[ -t 0 ] && [ -t 2 ] || { echo "prod-run: needs a terminal to ask for the master password; refusing" >&2; exit 3; }
command -v keepassxc-cli >/dev/null || { echo "prod-run: keepassxc-cli not found" >&2; exit 4; }

vault=${PROD_VAULT:-$HOME/Library/prod-secrets.kdbx}
entry=${PROD_ENTRY:-desmor-hub-prod-db}
[ -f "$vault" ] || { echo "prod-run: vault not found: $vault" >&2; exit 4; }

printf 'prod-run: Production access requested for: %s\n' "$*" >&2
printf 'Master password: ' >&2
url=$(keepassxc-cli show -q -s -a Password "$vault" "$entry") || { echo "prod-run: could not read the vault" >&2; exit 5; }
[ -n "$url" ] || { echo "prod-run: the entry has an empty Password" >&2; exit 5; }

DATABASE_URL=$url exec "$@"

#!/bin/bash
# Read-only disk report for macOS. Measures known space hogs and prints a
# markdown table (size, risk, note). It never deletes, moves or writes anything.
# Usage: disk-report.sh [min_mb]   (default 100: hide items smaller than this)

set -u
MIN_MB="${1:-100}"
H="$HOME"

hr() { # KB -> human
  awk -v k="$1" 'BEGIN{ if(k>=1048576) printf "%.1f GB",k/1048576; else printf "%.0f MB",k/1024 }'
}

rows=""
add() { # path risk note
  local p="$1" risk="$2" note="$3" kb
  [ -e "$p" ] || return 0
  kb=$(du -sk "$p" 2>/dev/null | cut -f1); kb=${kb:-0}
  [ "$kb" -ge $((MIN_MB * 1024)) ] || return 0
  rows+="$kb|$risk|${p/#$H/~}|$note"$'\n'
}

echo "# Disk report ($(date +%F))"
echo
df -h / | awk 'NR==2{print "Free: **" $4 "** of " $2 " (volume used " $5 ")"}'
echo

# Known items: path | risk | note
# Risk: Nenhum / Baixo = regenerates itself. Médio = loses history. Teu critério /
# A confirmar = only the user can say.
add "$H/Library/Developer/Xcode/iOS DeviceSupport" "Nenhum" "Símbolos de iOS; o Xcode regenera ao ligar o iPhone"
add "$H/Library/Developer/Xcode/DerivedData" "Nenhum" "Builds do Xcode"
add "$H/Library/Developer/Xcode/Archives" "A confirmar" "Archives de apps; podem ser a única cópia de uma build"
add "$H/Library/Developer/CoreSimulator" "Baixo" "Simuladores iOS"
add "$H/.cache" "Baixo" "Caches de CLIs (codex-runtimes, uv, huggingface, watch); re-descarrega"
add "$H/.npm" "Baixo" "Cache do npm"
add "$H/Library/Caches" "Baixo" "Caches de apps (ver detalhe abaixo)"
add "$H/Library/pnpm" "Baixo" "Store do pnpm"
add "$H/.codex/sessions" "Médio" "Sessões do Codex; apagar perde o histórico para retomar"
add "$H/.codex/archived_sessions" "Baixo" "Sessões do Codex já arquivadas"
add "$H/.codex/thread_history_1.sqlite" "Médio" "Histórico do Codex; não sei se é seguro sem perder o índice"
add "$H/.codex/packages" "Baixo" "Pacotes do Codex"
add "$H/.claude/projects" "Médio" "Sessões do Claude (ver detalhe abaixo)"
add "$H/.local/share/claude" "Baixo" "Versões instaladas do Claude Code"
add "$H/Library/Android" "A confirmar" "SDK/emuladores Android; só se já não fizeres Android"
add "$H/Library/Group Containers/group.net.whatsapp.WhatsApp.shared" "Teu critério" "Media do WhatsApp; limpa-se pela app"
add "$H/Library/Containers/com.utmapp.UTM" "A confirmar" "Máquinas virtuais do UTM"
add "$H/Library/Containers/llc.turing.CrystalFetch" "A confirmar" "Imagens de macOS do CrystalFetch"
add "$H/Pictures/Photos Library.photoslibrary" "Teu critério" "Biblioteca de Fotos; não mexer daqui"
add "$H/.colima" "A confirmar" "VMs do Colima/Docker; só se já não usas containers"
add "$H/.vscode" "Baixo" "Extensões do VS Code"
add "$H/.Trash" "Baixo" "Reciclagem"
add "$H/Downloads" "Teu critério" "Downloads"

echo "## Itens conhecidos"
echo
echo "| Item | Tamanho | Risco | Notas |"
echo "|---|---|---|---|"
printf '%s' "$rows" | sort -t'|' -k1,1 -rn | while IFS='|' read -r kb risk path note; do
  [ -n "$kb" ] && echo "| \`$path\` | $(hr "$kb") | $risk | $note |"
done
echo

SKIP="/Library$"   # Library has its own sections; measuring it twice is slow
top() { # title dir count  -> top entries of a directory, unclassified
  local title="$1" dir="$2" n="${3:-8}"
  [ -d "$dir" ] || return 0
  echo "### $title"
  echo
  du -sk "$dir"/* "$dir"/.[!.]* 2>/dev/null | grep -v "$SKIP" | sort -rn | head -"$n" | while read -r kb p; do
    [ "$kb" -ge $((MIN_MB * 1024)) ] && echo "- $(hr "$kb")  \`${p/#$H/~}\`"
  done
  echo
}

echo "## Detalhe (sem classificação: decide o utilizador)"
echo
top "Sessões Claude por projeto" "$H/.claude/projects"
top "Sessões Codex por mês" "$H/.codex/sessions/$(date +%Y)"
top "Library/Caches" "$H/Library/Caches"
top "Library/Application Support" "$H/Library/Application Support"
top "Library/Containers" "$H/Library/Containers"
top "Library/Group Containers" "$H/Library/Group Containers"
top "Pastas da home" "$H" 12
echo "_Items abaixo de ${MIN_MB} MB omitidos. Nada foi apagado._"

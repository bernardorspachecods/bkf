# Shared through lib-codex.sh: add to a brief the text of the files that its role guides ask for.
# Source it; it defines functions only.
#
# A role guide asks for a file with a line of its own: <!-- inject: ../../modules/core-code-principles.md -->
# The path is relative to the guide's folder and names a Markdown file. The brief names its guides as
# "role guide: <absolute path>.md" (a path with a space in it is not found).

# Append to <prompt-file> the body (frontmatter left out) of every file its role guides ask for, once each, under a
# heading that says where it came from. Fails, leaving the prompt as it was, when a named file is not a Markdown file
# or does not exist. Running it again on the same prompt changes nothing.
inject_rules() { # <prompt-file>
  local prompt=$1 marker='<!-- rules injected by the script -->' guide dir rel file key seen="" add=""
  grep -qF "$marker" "$prompt" && return 0
  while IFS= read -r guide; do
    [ -f "$guide" ] || continue
    dir=$(dirname "$guide")
    while IFS= read -r rel; do
      file=$dir/$rel
      case $rel in
        *.md) ;;
        *) printf 'Error: %s asks to inject %s, which is not a Markdown file\n' "$guide" "$rel" >&2; return 1 ;;
      esac
      [ -f "$file" ] || { printf 'Error: %s asks to inject %s, which does not exist\n' "$guide" "$file" >&2; return 1; }
      key=$(cd "$(dirname "$file")" && pwd)/$(basename "$file")
      case "$seen" in *"|$key|"*) continue ;; esac
      seen="$seen|$key|"
      add+=$(printf '\n\n---\n## Rules from %s\nThe script added this text from %s, as the role guide asked.\n\n' "$(basename "$file" .md)" "$rel")
      add+=$'\n'
      add+=$(awk 'NR == 1 && $0 == "---" { fm = 1; next } fm && $0 == "---" { fm = 0; next } !fm' "$file")
    done < <(sed -n 's/^<!-- inject: \(.*\) -->$/\1/p' "$guide")
  done < <(sed -n 's/.*role guide: \(\/[^ ]*\.md\).*/\1/p' "$prompt" | awk '!s[$0]++')
  [ -n "$add" ] || return 0
  printf '%s\n\n%s\n' "$add" "$marker" >>"$prompt"
}

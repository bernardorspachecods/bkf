#!/usr/bin/env bash
# Tests lib-inject.sh (the text a role guide asks the script to add to a brief) and its use by codex_run, with a fake
# `codex`, in a throwaway folder: no model is called.
# Usage: test-inject.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/inject-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

. "$here/lib-codex.sh"

mkdir -p "$work/lib/modules" "$work/lib/roles" "$work/bin" "$work/agent"
printf -- '---\nbkf: document\ndescription: "A rule."\n---\n\n# Rule\n\n- Always do the thing.\n' >"$work/lib/modules/rule.md"
printf -- '---\nbkf: document\n---\n\n# Other\n\n- Other thing.\n' >"$work/lib/modules/other.md"
printf '# Plain guide\n\nNo directive here.\n' >"$work/lib/roles/plain.md"
printf '# One\n\n<!-- inject: ../modules/rule.md -->\n\nText.\n' >"$work/lib/roles/one.md"
printf '# Two\n\n<!-- inject: ../modules/rule.md -->\n<!-- inject: ../modules/other.md -->\n' >"$work/lib/roles/two.md"
printf '# Bad\n\n<!-- inject: ../modules/missing.md -->\n' >"$work/lib/roles/bad.md"

prompt() { printf '# Brief\n\nDo it.\n\n## Role\nOpen and follow the role guide: %s/%s (read-only). You are not the author.\n' "$work/lib/roles" "$1" >"$work/p.md"; }

# A guide without a directive, and a brief without a guide, are left byte for byte as they were.
prompt plain.md; cp "$work/p.md" "$work/p.orig"
inject_rules "$work/p.md"
check "no directive: the brief is unchanged" 'cmp -s "$work/p.md" "$work/p.orig"'
printf '# Brief\n\nNo guide named.\n' >"$work/p.md"; cp "$work/p.md" "$work/p.orig"
inject_rules "$work/p.md"
check "no guide in the brief: unchanged" 'cmp -s "$work/p.md" "$work/p.orig"'

# One directive adds the body of the file, without its frontmatter, after the original text.
prompt one.md; cp "$work/p.md" "$work/p.orig"
inject_rules "$work/p.md"; code=$?
check "one directive: succeeds" '[ $code -eq 0 ]'
check "one directive: the original text stays first" 'head -c "$(wc -c <"$work/p.orig")" "$work/p.md" | cmp -s - "$work/p.orig"'
check "one directive: the rule text is in the brief" 'grep -q "^- Always do the thing\.$" "$work/p.md"'
check "one directive: the frontmatter is not" '! grep -q "^description:" "$work/p.md" && ! grep -q "^bkf: document" "$work/p.md"'
check "one directive: the brief says where the text came from" 'grep -q "modules/rule.md" "$work/p.md"'

# Running it again does not add the text twice (a retried agent reuses its brief).
cp "$work/p.md" "$work/p.once"
inject_rules "$work/p.md"
check "second run: the brief is unchanged" 'cmp -s "$work/p.md" "$work/p.once"'

# Two directives add both, in order.
prompt two.md
inject_rules "$work/p.md"
check "two directives: both texts, in order" '[ "$(grep -n "Always do the thing\|Other thing" "$work/p.md" | cut -d: -f2 | tr "\n" "|")" = "- Always do the thing.|- Other thing.|" ]'

# A file that does not exist fails and leaves the brief alone.
prompt bad.md; cp "$work/p.md" "$work/p.orig"
inject_rules "$work/p.md" 2>"$work/err.txt"; code=$?
check "missing file: fails" '[ $code -ne 0 ]'
check "missing file: the message names the file" 'grep -q "missing.md" "$work/err.txt"'
check "missing file: the brief is unchanged" 'cmp -s "$work/p.md" "$work/p.orig"'

# A directive may not leave the folder tree by naming something that is not a Markdown file.
printf '# Odd\n\n<!-- inject: ../modules/rule.md.sh -->\n' >"$work/lib/roles/odd.md"
touch "$work/lib/modules/rule.md.sh"
prompt odd.md
inject_rules "$work/p.md" 2>/dev/null; code=$?
check "not a .md file: fails" '[ $code -ne 0 ]'

# codex_run injects before the agent starts: what the agent reads on stdin holds the rule.
cat >"$work/bin/codex" <<'EOF'
#!/usr/bin/env bash
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in -o) out=$2; shift 2 ;; -C|-c|-m|-s) shift 2 ;; *) shift ;; esac
done
cat >"$FAKE_STDIN"
echo done >"$out"
EOF
chmod +x "$work/bin/codex"
prompt one.md
model=m effort=e FAKE_STDIN="$work/stdin.md" PATH="$work/bin:$PATH" codex_run "$work/agent" "$work/p.md" "$work/agent/run" workspace-write
check "codex_run: the agent receives the rule text" 'grep -q "^- Always do the thing\.$" "$work/stdin.md"'
check "codex_run: the recorded brief is what the agent read" 'cmp -s "$work/p.md" "$work/stdin.md"'
prompt bad.md
model=m effort=e FAKE_STDIN="$work/stdin2.md" PATH="$work/bin:$PATH" codex_run "$work/agent" "$work/p.md" "$work/agent/run2" workspace-write 2>/dev/null; code=$?
check "codex_run: a failed injection stops the agent from starting" '[ $code -ne 0 ] && [ ! -e "$work/stdin2.md" ]'

# Every directive in the real guides names a file that exists.
bad=""
while IFS= read -r g; do
  d=$(dirname "$g")
  while IFS= read -r rel; do
    [ -f "$d/$rel" ] || bad="$bad $g -> $rel;"
  done < <(sed -n 's/^<!-- inject: \(.*\) -->$/\1/p' "$g")
done < <(find "$here/../../../library/workflow-types" -name '*.md' ! -name MAP.md)
check "real guides: every directive resolves${bad:+ (broken:$bad)}" '[ -z "$bad" ]'

# The guides that apply determinism still ask for it, so a brief for each of these roles carries the rules.
lib=$(cd "$here/../../../library/workflow-types" && pwd)
for g in plan/plan-implementation.md plan/plan-review.md code-review/code-review-axis.md; do
  printf '# Brief\n\n## Role\nOpen and follow the role guide: %s/%s (read-only).\n' "$lib" "$g" >"$work/p.md"
  inject_rules "$work/p.md"
  check "real guides: $g brings determinism into the brief" 'grep -q "^## Rules from determinism$" "$work/p.md"'
done

exit "$fail"

#!/usr/bin/env bash
# Tests the gate of plan-run.sh with a fake `codex`, in a throwaway repository: no model is called.
# Usage: test-plan-run-gate.sh        (exit 0 when every case passes)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/plan-run-gate-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }

# A fake codex. The final review of the plan ("# Final review") just writes a report. Reviews (prompt starting "# Review") answer with $FAKE_VERDICT and count themselves in
# $FAKE_STATE/reviews; implementations run $FAKE_IMPL in the checkout, with the call number in $FAKE_N.
mkdir -p "$work/bin" "$work/guides"
touch "$work/guides/plan-implementation.md" "$work/guides/plan-review.md" "$work/guides/plan-integration.md"
cat >"$work/bin/codex" <<'EOF'
#!/usr/bin/env bash
dir="" out=""
while [ "$#" -gt 0 ]; do
  case "$1" in -C) dir=$2; shift 2 ;; -o) out=$2; shift 2 ;; -c) echo "$2" >>"$FAKE_STATE/codex-config"; shift 2 ;; *) shift ;; esac
done
prompt=$(cat)
if [ "${prompt#\# Final review}" != "$prompt" ]; then
  echo "report" >"$out"
elif [ "${prompt#\# Review}" != "$prompt" ]; then
  n=$(($(cat "$FAKE_STATE/reviews" 2>/dev/null || echo 0) + 1)); echo "$n" >"$FAKE_STATE/reviews"
  printf '%s\n' "$prompt" >"$FAKE_STATE/review-prompt-$n.md"
  printf '## What I checked\n\n- one\n- two\n- three\n\n## Problems\n\nnone\n\nVERDICT: %s\n' "${FAKE_VERDICT:-pass}" >"$out"
else
  n=$(($(cat "$FAKE_STATE/impls" 2>/dev/null || echo 0) + 1)); echo "$n" >"$FAKE_STATE/impls"
  printf '%s\n' "$prompt" >"$FAKE_STATE/impl-prompt-$n.md"
  (cd "$dir" && FAKE_N=$n bash -c "$FAKE_IMPL")
  echo "handoff $n" >"$out"
  printf '%s\n' '{"type":"item.completed"}' '{"type":"item.completed"}' '{"type":"item.completed"}' '{"type":"turn.completed","usage":{"input_tokens":1234,"cached_input_tokens":1000}}'
fi
EOF
chmod +x "$work/bin/codex"
cat >"$work/bin/pnpm" <<'EOF2'
#!/usr/bin/env bash
echo "called $*" >>"$FAKE_STATE/pnpm-calls"
echo "FAKEPNPM: $*"
for a in "$@"; do [ "$a" = fail ] && exit 3; done
exit 0
EOF2
chmod +x "$work/bin/pnpm"

new_case() { # <name> <gate-block-or-empty> <impl-script>   (BRIDGE_CONFIG: the .plan-run.json of the base, or none)
  case_dir=$work/$1; mkdir -p "$case_dir/repo" "$case_dir/state" "$case_dir/plan"
  git -C "$case_dir/repo" init -q . && git -C "$case_dir/repo" config user.email t@t && git -C "$case_dir/repo" config user.name t
  echo base >"$case_dir/repo/a.txt"
  echo '{"scripts":{"db:test":"echo t","db:test:query":"echo q","db:prod:query":"echo p","db:test:x;touch pwned4":"echo weird"}}' >"$case_dir/repo/package.json"
  config=${BRIDGE_CONFIG:-'{"bridge":{"pnpmScripts":["^db:test(:[a-z0-9-]+)*$"]}}'}
  [ "$config" = none ] || printf '%s\n' "$config" >"$case_dir/repo/.plan-run.json"
  git -C "$case_dir/repo" add -A && git -C "$case_dir/repo" commit -qm init
  echo "goal" >"$case_dir/plan/goal.md"
  { printf '# Unit\n\n## Result\nx\n'; [ -n "$2" ] && printf '\n```gate\n%s\n```\n' "$2"; } >"$case_dir/plan/unit.md"
  echo "unit.md" >"$case_dir/plan/plan.txt"
  export FAKE_STATE=$case_dir/state FAKE_IMPL=$3
}
run() { # <name> [env...]  -> runs start, prints nothing; the exit code is in $code
  (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "${@:2}" \
    "$here/plan-run.sh" start -p none r "$case_dir/plan/goal.md" "$case_dir/plan/plan.txt") >"$case_dir/out.txt" 2>&1
  code=$?
}
reviews() { cat "$case_dir/state/reviews" 2>/dev/null || echo 0; }
impls() { cat "$case_dir/state/impls" 2>/dev/null || echo 0; }

# 1. No gate: reviewed as before.
new_case nogate "" 'echo change >>a.txt'
run nogate
check "no gate: the run is READY" '[ "$code" -eq 0 ] && grep -q READY "$case_dir/out.txt"'
check "no gate: one review" '[ "$(reviews)" -eq 1 ]'
check "no gate: start says the unit has no gate" 'grep -q "has no gate" "$case_dir/runs/r/status.log"'

# 2. Gate green: the reviewer is told, and it passes.
new_case green 'test -f ok' 'echo change >>a.txt; touch ok'
run green
check "gate green: ready" '[ "$code" -eq 0 ]'
check "gate green: the review prompt names the gate" 'grep -q "ran the brief" "$case_dir/state/review-prompt-1.md" && grep -q "gate.md" "$case_dir/state/review-prompt-1.md"'
check "gate green: the implementer was told about the gate" 'grep -q "The brief has a \`gate\`" "$case_dir/state/impl-prompt-1.md"'

# 3. Gate red, then fixed: the first round never reaches a reviewer, and the failure goes back to the implementer.
new_case redfix 'test -f ok' 'echo change >>a.txt; [ "$FAKE_N" -ge 2 ] && touch ok; true'
run redfix
check "gate red then fixed: ready" '[ "$code" -eq 0 ]'
check "gate red then fixed: two implementations, one review" '[ "$(impls)" -eq 2 ] && [ "$(reviews)" -eq 1 ]'
check "gate red then fixed: round 1 verdict is back, written by the script" '[ "$(cat "$case_dir/runs/r/01-unit/rounds/1/verdict")" = back ] && grep -q "FAIL \`test -f ok\`" "$case_dir/runs/r/01-unit/rounds/1/problems.md"'
check "gate red then fixed: round 2 implementer saw the failing command" 'grep -q "FAIL \`test -f ok\`" "$case_dir/state/impl-prompt-2.md"'

# 4. Gate always red: the reviewer can never pass it. The unit stops after PLAN_MAX_GATE_ROUNDS.
new_case alwaysred 'false' 'echo change >>a.txt'
FAKE_VERDICT=pass run alwaysred PLAN_MAX_GATE_ROUNDS=2
check "gate always red: stopped" '[ "$code" -ne 0 ] && grep -q "gate still fails after 2 rounds" "$case_dir/runs/r/status.log"'
check "gate always red: no reviewer was called, even one that would say pass" '[ "$(reviews)" -eq 0 ]'

# 5. A reviewer 'back' is still counted apart from gate failures.
new_case backs 'true' 'echo change >>a.txt'
FAKE_VERDICT=back run backs PLAN_MAX_ROUNDS=2
check "reviewer back: stops at the review cap" '[ "$code" -ne 0 ] && [ "$(reviews)" -eq 2 ] && grep -q "round cap 2 reached" "$case_dir/runs/r/status.log"'

# 6. A command that runs too long fails the gate.
new_case slow 'sleep 5' 'echo change >>a.txt'
run slow PLAN_GATE_TIMEOUT=1 PLAN_MAX_GATE_ROUNDS=1
check "timeout: the gate fails" '[ "$code" -ne 0 ] && grep -q "FAIL \`sleep 5\`" "$case_dir/runs/r/01-unit/rounds/1/gate.md"'

# 7. Parsing: comments, blank lines and duplicates; two blocks; a block without the tag is ignored.
printf '# U\n```gate\n# comment\n\ntrue\ntrue\n```\ntext\n```gate\nfalse\n```\n```bash\nexit 9\n```\n' >"$work/parse.md"
cmds=$(bash -c ". '$here/lib-codex.sh'; eval \"\$(sed -n '/^gate_commands() {/,/^}/p' '$here/plan-run.sh')\"; gate_commands '$work/parse.md'")
check "parsing: only gate lines, deduplicated, in order" '[ "$cmds" = "$(printf "true\nfalse")" ]'

# 8. `gates` prints the commands and flags a unit without one.
new_case gates 'echo hello' 'true'
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; printf 'unit.md\nunit2.md\n' >"$case_dir/plan/plan.txt"
gout=$("$here/plan-run.sh" gates "$case_dir/plan/plan.txt" 2>&1); gcode=$?
check "gates: lists the command" 'echo "$gout" | grep -q "\$ echo hello"'
check "gates: flags the unit with no gate and exits 1" 'echo "$gout" | grep -q "NO GATE" && [ "$gcode" -eq 1 ]'

# 9. The bridge: what the implementer may run outside the sandbox.
new_case bridge 'echo gate-ok' 'echo change >>a.txt
P=.plan-porteiro/ponte
$P pnpm db:test:query --sql "a; touch pwned" >r1.txt; echo $? >c1.txt
$P pnpm db:prod:query >r2.txt; echo $? >c2.txt
$P pnpm "db:test:query;touch pwned2" >r3.txt; echo $? >c3.txt
$P echo gate-ok >r4.txt; echo $? >c4.txt
$P echo not-gate >r5.txt; echo $? >c5.txt
$P pnpm db:test:query fail >r6.txt; echo $? >c6.txt
$P rm -rf . >r7.txt; echo $? >c7.txt'
run bridge
r=$case_dir/repo
check "bridge: the run finishes" '[ "$code" -eq 0 ]'
check "bridge: pnpm db:test:* runs, its arguments reach it untouched" 'grep -qF "FAKEPNPM: db:test:query --sql a; touch pwned" $r/r1.txt && [ "$(cat $r/c1.txt)" = 0 ]'
check "bridge: no shell: the ; inside an argument ran nothing" '[ ! -e $r/pwned ] && [ ! -e $r/pwned2 ]'
check "bridge: pnpm db:prod:* is refused and never reaches pnpm" 'grep -q refused $r/r2.txt && [ "$(cat $r/c2.txt)" = 126 ]'
check "bridge: a script name with shell syntax is refused" 'grep -q refused $r/r3.txt && [ "$(cat $r/c3.txt)" = 126 ]'
check "bridge: a gate command runs exactly as written" 'grep -q gate-ok $r/r4.txt && [ "$(cat $r/c4.txt)" = 0 ]'
check "bridge: any other command is refused" 'grep -q refused $r/r5.txt && [ "$(cat $r/c5.txt)" = 126 ] && grep -q refused $r/r7.txt && [ -e $r/a.txt ]'
check "bridge: the exit code of the command comes back" '[ "$(cat $r/c6.txt)" = 3 ]'
check "bridge: pnpm was called only for the two allowed requests" '[ "$(wc -l <$case_dir/state/pnpm-calls)" -eq 2 ]'
check "bridge: every request is in porteiro.log, refusals marked" '[ "$(grep -c REFUSED $case_dir/runs/r/porteiro.log)" -eq 4 ] && [ "$(grep -c ALLOWED $case_dir/runs/r/porteiro.log)" -eq 3 ]'
check "bridge: the folder is not in the diff and is removed afterwards" '! grep -q plan-porteiro $case_dir/runs/r/01-unit/rounds/1/diff.patch && [ ! -e $r/.plan-porteiro ]'

# 10. A db:test script changed by the implementer is refused.
new_case bridgechg '' 'echo change >>a.txt
sed -i.bak "s/echo q/echo evil/" package.json; rm -f package.json.bak
.plan-porteiro/ponte pnpm db:test:query >r1.txt; echo $? >c1.txt'
run bridgechg
check "bridge: a db:test script redefined in the unit is refused" 'grep -q "was changed" $case_dir/repo/r1.txt && [ "$(cat $case_dir/repo/c1.txt)" = 126 ]'

# 11. Metrics: one line per implementation round, and a table in status.md after finish.
new_case metrics 'true' 'echo change >>a.txt'
run metrics
check "metrics: one line per round with steps, files and tokens" 'awk -F"\t" "\$1==\"01-unit\" && \$2==1 && \$4==3 && \$5==1 && \$6==1234 {ok=1} END{exit !ok}" "$case_dir/runs/r/metrics.tsv"'
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$here/plan-run.sh" finish r) >"$case_dir/finish.txt" 2>&1
check "metrics: finish writes the table into status.md" 'grep -q "Implementation rounds" "$case_dir/repo/records/plans/r/status.md" && grep -q "| 01-unit | 1 |" "$case_dir/repo/records/plans/r/status.md"'

# 12. The service tier: fast unless PLAN_CODEX_TIER says otherwise (empty keeps the account default).
new_case tierdef '' 'echo change >>a.txt'
run tierdef
check "tier: fast by default" 'grep -qx "service_tier=\"fast\"" $case_dir/state/codex-config'
new_case tieroff '' 'echo change >>a.txt'
run tieroff PLAN_CODEX_TIER=
check "tier: empty PLAN_CODEX_TIER keeps the account default" '! grep -q service_tier $case_dir/state/codex-config'
new_case tierset '' 'echo change >>a.txt'
run tierset PLAN_CODEX_TIER=flex
check "tier: PLAN_CODEX_TIER picks another tier" 'grep -qx "service_tier=\"flex\"" $case_dir/state/codex-config'

# 13. The bridge's pnpm list comes from .plan-run.json at the base. Without that file only gate commands run.
BRIDGE_CONFIG=none new_case noconf 'echo gate-ok' 'echo change >>a.txt
.plan-porteiro/ponte pnpm db:test:query >r1.txt; echo $? >c1.txt
.plan-porteiro/ponte echo gate-ok >r2.txt; echo $? >c2.txt'
run noconf
r=$case_dir/repo
check "no config: the run finishes" '[ "$code" -eq 0 ]'
check "no config: pnpm db:test:* is refused, and the refusal names .plan-run.json" 'grep -q refused $r/r1.txt && grep -q "[.]plan-run[.]json" $r/r1.txt && [ "$(cat $r/c1.txt)" = 126 ]'
check "no config: pnpm was never called" '[ ! -e $case_dir/state/pnpm-calls ]'
check "no config: a gate command still runs through the bridge" 'grep -q gate-ok $r/r2.txt && [ "$(cat $r/c2.txt)" = 0 ]'
check "no config: start notes that there is no .plan-run.json at HEAD" 'grep -q "no .plan-run.json at HEAD" $case_dir/runs/r/status.log'

# 14. An edit to .plan-run.json in the checkout widens nothing: the base's copy is the one that counts.
new_case wtedit '' 'echo change >>a.txt
echo "{\"bridge\":{\"pnpmScripts\":[\"^db:test(:[a-z0-9-]+)*\$\",\"^db:prod(:[a-z0-9-]+)*\$\"]}}" >.plan-run.json
.plan-porteiro/ponte pnpm db:prod:query >r1.txt; echo $? >c1.txt'
run wtedit
r=$case_dir/repo
check "base config only: db:prod:query added in the checkout is refused" 'grep -q "not in the pnpm scripts" $r/r1.txt && [ "$(cat $r/c1.txt)" = 126 ]'
check "base config only: pnpm was never called for it" '[ ! -e $case_dir/state/pnpm-calls ]'

# 15. A config that does not parse allows no pnpm script, and the run still finishes.
BRIDGE_CONFIG='{not json' new_case badjson '' 'echo change >>a.txt
.plan-porteiro/ponte pnpm db:test:query >r1.txt; echo $? >c1.txt'
run badjson
r=$case_dir/repo
check "invalid config: the run finishes" '[ "$code" -eq 0 ] && grep -q READY $case_dir/out.txt'
check "invalid config: pnpm db:test:* is refused and never runs" 'grep -q refused $r/r1.txt && [ "$(cat $r/c1.txt)" = 126 ] && [ ! -e $case_dir/state/pnpm-calls ]'

# 16. The pattern must match the whole name: db:test does not allow db:test:query, and does allow db:test.
BRIDGE_CONFIG='{"bridge":{"pnpmScripts":["db:test"]}}' new_case unanch '' 'echo change >>a.txt
.plan-porteiro/ponte pnpm db:test:query >r1.txt; echo $? >c1.txt
.plan-porteiro/ponte pnpm db:test >r2.txt; echo $? >c2.txt'
run unanch
r=$case_dir/repo
check "anchoring: pattern db:test refuses pnpm db:test:query" 'grep -q "not in the pnpm scripts" $r/r1.txt && [ "$(cat $r/c1.txt)" = 126 ]'
check "anchoring: pattern db:test allows pnpm db:test, which the base defines" 'grep -qx "FAKEPNPM: db:test" $r/r2.txt && [ "$(cat $r/c2.txt)" = 0 ]'

# 17. A permissive pattern does not let shell syntax through the charset guard, defined script or not.
BRIDGE_CONFIG='{"bridge":{"pnpmScripts":[".*"]}}' new_case permissive '' 'echo change >>a.txt
.plan-porteiro/ponte pnpm "db:test:query;touch pwned3" >r1.txt; echo $? >c1.txt
.plan-porteiro/ponte pnpm "db:test:x;touch pwned4" >r2.txt; echo $? >c2.txt'
run permissive
r=$case_dir/repo
check "charset: pattern .* refuses shell syntax, and nothing named pwned3 is created" 'grep -q "characters that are not allowed" $r/r1.txt && [ "$(cat $r/c1.txt)" = 126 ] && [ ! -e $r/pwned3 ]'
check "charset: a base script whose name has shell syntax is refused before it reaches pnpm" 'grep -q "characters that are not allowed" $r/r2.txt && [ "$(cat $r/c2.txt)" = 126 ] && [ ! -e $r/pwned4 ] && [ ! -e $case_dir/state/pnpm-calls ]'

# 18. A pattern must compile on its own: x)|(.* would close the ^(?:...)$ group early and match everything. The whole config is then not usable.
BRIDGE_CONFIG='{"bridge":{"pnpmScripts":["^db:test(:[a-z0-9-]+)*$","x)|(.*"]}}' new_case breakout '' 'echo change >>a.txt
.plan-porteiro/ponte pnpm db:test:query >r1.txt; echo $? >c1.txt'
run breakout
r=$case_dir/repo
check "compile alone: a pattern that breaks the group makes the config not usable, so pnpm db:test:query is refused" 'grep -q "is not usable" $r/r1.txt && [ "$(cat $r/c1.txt)" = 126 ]'
check "compile alone: pnpm was never called" '[ ! -e $case_dir/state/pnpm-calls ]'

# 19. An untracked .plan-run.json is still in the unit's base (the base holds untracked files too): the bridge uses it, and start says it is not committed.
new_case untracked '' 'echo change >>a.txt
.plan-porteiro/ponte pnpm db:test:query >r1.txt; echo $? >c1.txt'
git -C "$case_dir/repo" rm -q --cached .plan-run.json && git -C "$case_dir/repo" commit -qm "config not committed"
run untracked
r=$case_dir/repo
check "untracked config: start says it is not committed" 'grep -q "is not committed" $case_dir/runs/r/status.log'
check "untracked config: the base copy is used, so pnpm db:test:query runs" 'grep -qx "FAKEPNPM: db:test:query" $r/r1.txt && [ "$(cat $r/c1.txt)" = 0 ]'

exit "$fail"

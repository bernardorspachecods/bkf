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
# A fake df: with FAKE_DF_BEFORE and FAKE_DF_AFTER set, the first call reports that much free space (KB) and later calls the other.
cat >"$work/bin/df" <<'EOF4'
#!/usr/bin/env bash
if [ -z "${FAKE_DF_BEFORE:-}" ]; then exec /bin/df "$@"; fi
n=$(($(cat "$FAKE_STATE/df-calls" 2>/dev/null || echo 0) + 1)); echo "$n" >"$FAKE_STATE/df-calls"
avail=$FAKE_DF_AFTER; [ "$n" -eq 1 ] && avail=$FAKE_DF_BEFORE
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/fake 9999999 1 %s 1%% /\n' "$avail"
EOF4
chmod +x "$work/bin/df"
touch "$work/guides/plan-implementation.md" "$work/guides/plan-review.md" "$work/guides/plan-integration.md"
cat >"$work/bin/codex" <<'EOF'
#!/usr/bin/env bash
dir="" out=""
while [ "$#" -gt 0 ]; do
  case "$1" in -C) dir=$2; shift 2 ;; -o) out=$2; shift 2 ;; -c) echo "$2" >>"$FAKE_STATE/codex-config"; shift 2 ;; *) shift ;; esac
done
prompt=$(cat)
stage=implement
case "$prompt" in "# Final review"*) stage=report ;; "# Review"*) stage=review ;; "# Integration of"*) stage=integrate ;; esac
if [ "${FAKE_QUOTA:-}" = "$stage" ]; then
  msg=${FAKE_QUOTA_MSG:-"You’ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/settings/usage to purchase more credits or try again at 9:43 PM."}
  printf '%s\n' '{"type":"thread.started","thread_id":"t"}' '{"type":"turn.started"}' "{\"type\":\"error\",\"message\":\"$msg\"}" "{\"type\":\"turn.failed\",\"error\":{\"message\":\"$msg\"}}"
  exit 1
fi
if [ "${FAKE_FAIL:-}" = "$stage" ]; then echo "something else broke" >&2; exit 1; fi
if [ "${prompt#\# Final review}" != "$prompt" ]; then
  echo "report" >"$out"
elif [ "${prompt#\# Review}" != "$prompt" ]; then
  n=$(($(cat "$FAKE_STATE/reviews" 2>/dev/null || echo 0) + 1)); echo "$n" >"$FAKE_STATE/reviews"
  printf '%s\n' "$prompt" >"$FAKE_STATE/review-prompt-$n.md"
  verdict=${FAKE_VERDICT:-pass}
  case "$prompt" in *"# Integration of a parallel group"*) verdict=${FAKE_INT_VERDICT:-$verdict} ;; esac
  printf '## What I checked\n\n- one\n- two\n- three\n\n## Problems\n\nnone\n\nVERDICT: %s\n' "$verdict" >"$out"
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
# Every plan-run.sh call goes through this wrapper, which kills it after PLAN_TEST_LIMIT seconds (default 120): a broken
# guard then fails its test instead of leaving the suite waiting for ever.
cat >"$work/bin/plan-run-limited" <<EOF3
#!/usr/bin/env bash
if [ -n "\${FAKE_STATE:-}" ] && [ -d "\$FAKE_STATE" ]; then printf '%s\n' "\$\$" >>"\$FAKE_STATE/plan-pids"; fi
exec perl -e 'alarm shift @ARGV; exec @ARGV' "\${PLAN_TEST_LIMIT:-120}" "$here/plan-run.sh" "\$@"
EOF3
chmod +x "$work/bin/plan-run-limited"
cat >"$work/bin/ps" <<'EOF5'
#!/usr/bin/env bash
pid=
while [ "$#" -gt 0 ]; do
  case "$1" in -p) pid=$2; shift 2 ;; *) shift ;; esac
done
if [ -n "${FAKE_STATE:-}" ] && grep -qxF "$pid" "$FAKE_STATE/plan-pids" 2>/dev/null; then
  printf 'python3 -m harness run\n'
fi
EOF5
chmod +x "$work/bin/ps"

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
    "$work/bin/plan-run-limited" start -p none r "$case_dir/plan/goal.md" "$case_dir/plan/plan.txt") >"$case_dir/out.txt" 2>&1
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
check "gate red then fixed: round 1 verdict is back, written by the script" '[ "$(cat "$case_dir/runs/r/01-unit/rounds/1/verdict")" = back ] && grep -q "### \`test -f ok\`" "$case_dir/runs/r/01-unit/rounds/1/problems.md"'
check "gate red then fixed: round 2 implementer saw the failing command" 'grep -q "### \`test -f ok\`" "$case_dir/state/impl-prompt-2.md"'

# 4. Gate always red: the reviewer can never pass it. The unit stops after PLAN_MAX_GATE_ROUNDS.
new_case alwaysred 'false' 'echo change >>a.txt'
FAKE_VERDICT=pass run alwaysred PLAN_MAX_GATE_ROUNDS=2
check "gate always red: stopped" '[ "$code" -ne 0 ] && grep -q "gate fails the same way in two rounds in a row" "$case_dir/runs/r/status.log"'
check "gate always red: no reviewer was called, even one that would say pass" '[ "$(reviews)" -eq 0 ]'

# 5. A reviewer 'back' is still counted apart from gate failures.
new_case backs 'true' 'echo change >>a.txt'
FAKE_VERDICT=back run backs PLAN_MAX_ROUNDS=2
check "reviewer back: stops at the review cap" '[ "$code" -ne 0 ] && [ "$(reviews)" -eq 2 ] && grep -q "round cap 2 reached" "$case_dir/runs/r/status.log"'

# 6. A command that runs too long fails the gate.
new_case slow 'sleep 5' 'echo change >>a.txt'
run slow PLAN_GATE_TIMEOUT=1 PLAN_MAX_GATE_ROUNDS=1
check "timeout: the gate fails with the harness timeout format" '[ "$code" -ne 0 ] && grep -q "### \`sleep 5\`" "$case_dir/runs/r/01-unit/rounds/1/gate.md" && grep -q "exit code: 124 (timed out after" "$case_dir/runs/r/01-unit/rounds/1/gate.md"'

# 7. A gate timeout kills background children as well as the command shell.
new_case child 'sleep 30 & echo $! >child.pid; wait' 'echo change >>a.txt'
run child PLAN_GATE_TIMEOUT=1 PLAN_MAX_GATE_ROUNDS=1
child_pid=$(cat "$case_dir/repo/child.pid" 2>/dev/null || echo missing)
check "timeout child: gate fails with exit code 124" '[ "$code" -ne 0 ] && grep -q "exit code: 124 (timed out after" "$case_dir/runs/r/01-unit/rounds/1/gate.md"'
check "timeout child: background sleep is gone after the gate" '[ "$child_pid" != missing ] && ! kill -0 "$child_pid" 2>/dev/null'
if [ "$child_pid" != missing ]; then kill "$child_pid" 2>/dev/null || true; fi

# 8. Parsing: comments, blank lines and duplicates; two blocks; a block without the tag is ignored.
printf '# U\n```gate\n# comment\n\ntrue\ntrue\n```\ntext\n```gate\nfalse\n```\n```bash\nexit 9\n```\n' >"$work/parse.md"
cmds=$(PYTHONPATH="$here/../harness:$here/../workflows" python3 -c 'import plan_inputs, sys; print("\n".join(plan_inputs.gate_commands([sys.argv[1]])))' "$work/parse.md")
check "parsing: only gate lines, deduplicated, in order" '[ "$cmds" = "$(printf "true\nfalse")" ]'

# 8. `gates` prints the commands and flags a unit without one.
new_case gates 'echo hello' 'true'
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; printf 'unit.md\nunit2.md\n' >"$case_dir/plan/plan.txt"
gout=$("$work/bin/plan-run-limited" gates "$case_dir/plan/plan.txt" 2>&1); gcode=$?
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
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$work/bin/plan-run-limited" finish r) >"$case_dir/finish.txt" 2>&1
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
# 20. The integration and the final review read the current briefs in 00-input/units/, not the copy the implementer got.
HDR='Brief received by the implementer (differs from the current one)'
# The fake implementer of the first unit corrects its own brief in 00-input/units/ while it works, as the coordinator would between runs.
GRPIMPL='n=$(basename "$PWD"); echo x >"f-$n.txt"'
new_case grp '' "$GRPIMPL; [ \"\$n\" = 01-unit ] && echo CURRENT-NOTE >>$work/grp/runs/r/00-input/units/01-unit.md; true"
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
run grp
rp=$case_dir/runs/r
check "current briefs: the group run is READY" '[ "$code" -eq 0 ] && grep -q READY "$case_dir/out.txt"'
check "current briefs: the unit keeps the brief its implementer received" '! grep -q CURRENT-NOTE $rp/01-unit/brief.md'
check "current briefs: the integration brief holds the current brief" 'grep -q CURRENT-NOTE $rp/S1-integration/brief.md'
check "current briefs: the integration brief also holds the received one, with the rule for weighing the two" '[ "$(grep -c "$HDR" $rp/S1-integration/brief.md)" -eq 1 ] && grep -q "The current brief defines the intent" $rp/S1-integration/brief.md'
check "current briefs: only the unit that changed gets that section" '[ "$(grep -c "$HDR" $rp/S1-integration/brief.md)" -eq 1 ]'
check "current briefs: the integration logs the difference once" '[ "$(grep -c "the brief of 01-unit differs" $rp/status.log)" -eq 1 ] && ! grep -q "brief of 02-unit2 differs" $rp/status.log'
check "current briefs: the final review reads the same, and logs nothing" 'grep -q CURRENT-NOTE $rp/report-prompt.md && [ "$(grep -c "$HDR" $rp/report-prompt.md)" -eq 1 ] && [ "$(grep -c "differs from the one" $rp/status.log)" -eq 1 ]'

# 21. A unit that did not change adds nothing to the integration brief or the report.
new_case grpsame '' "$GRPIMPL"
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
run grpsame
check "same briefs: no received-brief section and no note" '[ "$code" -eq 0 ] && ! grep -q "$HDR" $case_dir/runs/r/S1-integration/brief.md && ! grep -q "$HDR" $case_dir/runs/r/report-prompt.md && ! grep -q differs $case_dir/runs/r/status.log'

# 22. A changed gate gets the stronger note: the unit passed against another gate.
new_case grpgate 'true' "$GRPIMPL; [ \"\$n\" = 01-unit ] && sed -i.bak 's/^true\$/echo changed/' $work/grpgate/runs/r/00-input/units/01-unit.md; true"
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
run grpgate
check "changed gate: the integration notes that the unit passed against another gate" 'grep -q "gate of 01-unit was changed after it passed" $case_dir/runs/r/status.log && ! grep -q "brief of 01-unit differs" $case_dir/runs/r/status.log'
check "changed gate: the integration runs the current gate" 'grep -q "echo changed" $case_dir/runs/r/S1-integration/rounds/1/gate.md'

# 23. A current brief that is gone stops the integration with a reason, not a silent empty section.
new_case grpgone '' "$GRPIMPL; [ \"\$n\" = 02-unit2 ] && rm $work/grpgone/runs/r/00-input/units/02-unit2.md; true"
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
run grpgone
check "missing brief: the run stops and says which brief is missing" '[ "$code" -ne 0 ] && grep -q "S1-integration: 02-unit2: the current brief .* is missing or empty" $case_dir/runs/r/status.log'
check "missing brief: no reviewer saw an integration" '[ ! -e $case_dir/runs/r/S1-integration/rounds/1/diff.patch ]'
# 24. A plain step has no integration: the final review still shows the current brief and the received one, and logs nothing.
new_case single '' "echo change >>a.txt; echo CURRENT-NOTE >>$work/single/runs/r/00-input/units/01-unit.md"
run single
check "final review: a plain unit shows the current brief and the received one" 'grep -q CURRENT-NOTE $case_dir/runs/r/report-prompt.md && grep -q "$HDR" $case_dir/runs/r/report-prompt.md && ! grep -q differs $case_dir/runs/r/status.log'

# 25. The lock: <run>/.lock holds the pid of the script while it works; a second resume or a finish on that run is refused.
new_case lk '' "cat $work/lk/runs/r/.lock >$work/lk/lock-seen; sleep 6; echo change >>a.txt"
( run lk ) &
bg=$!
for _ in $(seq 1 40); do [ -s "$case_dir/lock-seen" ] && break; sleep 0.25; done
rp=$case_dir/runs/r
resume_out=$(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$work/bin/plan-run-limited" resume r 2>&1); resume_code=$?
finish_out=$(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$work/bin/plan-run-limited" finish --discard r 2>&1); finish_code=$?
check "lock: while the run works, .lock holds a pid" 'grep -qE "^[0-9]+$" "$case_dir/lock-seen"'
check "lock: a second resume is refused and says who holds it" '[ "$resume_code" -ne 0 ] && echo "$resume_out" | grep -q "already being worked on by pid $(cat "$case_dir/lock-seen")"'
check "lock: finish is refused while the run works, and the run folder is still there" '[ "$finish_code" -ne 0 ] && echo "$finish_out" | grep -q "being worked on by pid" && [ -d "$rp" ]'
wait "$bg"
check "lock: the refused commands did not disturb the run" '[ -e "$rp/.done-report" ] && grep -q READY "$case_dir/out.txt"'
check "lock: the lock is gone when the script ends" '[ ! -e "$rp/.lock" ]'

# A lock whose pid is dead, or alive but not a plan-run.sh, is stale: resume replaces it.
resume_r() { (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$work/bin/plan-run-limited" resume r) >"$case_dir/resume.txt" 2>&1; }
echo 999999 >"$rp/.lock"; resume_r; rc=$?
check "lock: a lock with a dead pid is replaced" '[ "$rc" -eq 0 ] && grep -q READY "$case_dir/resume.txt" && [ ! -e "$rp/.lock" ]'
sleep 30 & other=$!
echo "$other" >"$rp/.lock"; resume_r; rc=$?
kill "$other" 2>/dev/null
check "lock: a live pid that is not a plan-run.sh does not hold the run" '[ "$rc" -eq 0 ] && grep -q READY "$case_dir/resume.txt"'

# Shared helpers for the parallel integration cases, including when rebase cases are skipped.
grp_case() { # <name>: a parallel group of two units
  new_case "$1" '' "$GRPIMPL"
  printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
}
resume_with() { (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$work/bin/plan-run-limited" resume r) >"$case_dir/cmd.txt" 2>&1; }

# 26. rebase-integration without --paths: the base becomes the checkout minus the units' diffs, while the integrator never ran.
envrun() { (cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" "$@") >"$case_dir/cmd.txt" 2>&1; }
rbi() { envrun "$work/bin/plan-run-limited" rebase-integration r "$@"; }
owner_edits() { (cd "$case_dir/repo" && echo mine >owner.txt && git add owner.txt && git commit -qm owner && echo more >owner2.txt); }
difffiles() { grep '^diff --git' "$1" | sed -E 's#^diff --git a/(.*) b/.*#\1#'; }

grp_case rb
run rb FAKE_INT_VERDICT=escalate
rp=$case_dir/runs/r
check "rebase 1: the integration review escalated and the run stopped there" '[ "$code" -ne 0 ] && grep -q "S1-integration: the reviewer escalated" $rp/status.log && ! ls $rp/S1-integration/rounds/*/integrate.last-message.md >/dev/null 2>&1'
owner_edits
base_before=$(cat $rp/S1-integration/base)
rbi 1; rc=$?
check "rebase 1: succeeds, the base moved and the old one is kept" '[ "$rc" -eq 0 ] && [ "$(cat $rp/S1-integration/base)" != "$base_before" ] && ls $rp/S1-integration/.base.before-rebase-* >/dev/null 2>&1'
check "rebase 1: status.log says what was subtracted and at which HEAD" 'grep -q "S1-integration: base moved to the checkout minus the diffs of 01-unit 02-unit2 (HEAD " $rp/status.log'
FAKE_INT_VERDICT=pass resume_with
check "rebase 1: after resume the integration passes" 'grep -q READY $case_dir/cmd.txt'
check "rebase 1: the integration diff holds the units and not the owner's files" 'f=$(difffiles $rp/S1-integration/rounds/1/diff.patch); echo "$f" | grep -qx f-01-unit.txt && echo "$f" | grep -qx f-02-unit2.txt && ! echo "$f" | grep -q owner'
rbi 1; rc=$?
check "rebase 1: refused once the integration is closed" '[ "$rc" -ne 0 ] && grep -q "already closed" $case_dir/cmd.txt'

# The same stop and resume without the command: the owner's files stay in the diff (the case the command exists for).
grp_case rbctl
run rbctl FAKE_INT_VERDICT=escalate
owner_edits
FAKE_INT_VERDICT=pass resume_with
check "rebase 1 control: without the command the owner's files are in the integration diff" 'difffiles $case_dir/runs/r/S1-integration/rounds/1/diff.patch | grep -q owner'

# Refusals.
grp_case rbref
run rbref FAKE_INT_VERDICT=escalate
rp=$case_dir/runs/r
(cd "$case_dir/repo" && echo more >>f-01-unit.txt)
base_before=$(cat $rp/S1-integration/base)
rbi 1; rc=$?
check "rebase 1: a file of a unit's diff edited in the checkout is refused, and the git message names it" '[ "$rc" -ne 0 ] && grep -q "f-01-unit.txt" $case_dir/cmd.txt && grep -q "Nothing was changed" $case_dir/cmd.txt && [ "$(cat $rp/S1-integration/base)" = "$base_before" ]'
bash -c 'exec -a plan-run.sh sleep 30' & fakepid=$!
echo "$fakepid" >>"$FAKE_STATE/plan-pids"
echo "$fakepid" >"$rp/.lock"
rbi 1; rc=$?
kill "$fakepid" 2>/dev/null; rm -f "$rp/.lock"
check "rebase: refused while a plan-run.sh holds the run" '[ "$rc" -ne 0 ] && grep -q "being worked on by pid $fakepid" $case_dir/cmd.txt'
rbi 9; rc=$?
check "rebase: a step that does not exist is refused" '[ "$rc" -ne 0 ]'

new_case rbs '' 'echo change >>a.txt'
run rbs
rbi 1; rc=$?
check "rebase: a step that is not a group is refused" '[ "$rc" -ne 0 ] && grep -q "not a parallel group" $case_dir/cmd.txt'

# 27. Once the integrator ran, in this attempt or an earlier one, only --paths is allowed.
grp_case rbint
run rbint FAKE_INT_VERDICT=back PLAN_MAX_ROUNDS=2
rp=$case_dir/runs/r
check "rebase 1: the integrator ran in the stopped attempt" 'ls $rp/S1-integration/rounds/*/integrate.last-message.md >/dev/null 2>&1'
rbi 1; rc=$?
check "rebase 1: refused after the integrator ran, and the message names --paths" '[ "$rc" -ne 0 ] && grep -q -- "--paths" $case_dir/cmd.txt'
FAKE_INT_VERDICT=escalate resume_with
check "rebase 1: the integrator's rounds are now in an earlier attempt" '! ls $rp/S1-integration/rounds/*/integrate.last-message.md >/dev/null 2>&1 && ls $rp/S1-integration/rounds.attempt-*/*/integrate.last-message.md >/dev/null 2>&1'
rbi 1; rc=$?
check "rebase 1: still refused when the integrator's rounds are in an earlier attempt" '[ "$rc" -ne 0 ] && grep -q -- "--paths" $case_dir/cmd.txt'

# 28. rebase-integration --paths: the scenario that happened. Integration at its round cap after the integrator edited
# files, the owner commits plans/ and tests/ meanwhile: those leave the diff, the integrator's own edits stay.
grp_case rbp
run rbp FAKE_INT_VERDICT=back PLAN_MAX_ROUNDS=3
rp=$case_dir/runs/r
check "paths: the integration stopped at its round cap after two integrator rounds" '[ "$code" -ne 0 ] && grep -q "S1-integration: round cap 3 reached" $rp/status.log && [ "$(ls $rp/S1-integration/rounds/*/integrate.last-message.md | wc -l)" -eq 2 ]'
(cd "$case_dir/repo" && mkdir -p plans tests/sub && echo p >plans/a.md && git add plans && git commit -qm plans && echo t >tests/sub/x.txt)
base_before=$(cat $rp/S1-integration/base)
rbi 1 --paths f-01-unit.txt; rc=$?
check "paths: a file of a unit's diff is refused, naming the unit" '[ "$rc" -ne 0 ] && grep -q "01-unit: f-01-unit.txt" $case_dir/cmd.txt && [ "$(cat $rp/S1-integration/base)" = "$base_before" ]'
rbi 1 --paths /etc; rc1=$?; grep -q "bad path" $case_dir/cmd.txt && m1=1
rbi 1 --paths plans/../plans; rc2=$?; grep -q "bad path" $case_dir/cmd.txt && m2=1
rbi 1 --paths nothing/here; rc3=$?
check "paths: absolute and .. paths are refused as bad paths, an unchanged path as nothing to do" '[ "$rc1" -ne 0 ] && [ "${m1:-}" = 1 ] && [ "$rc2" -ne 0 ] && [ "${m2:-}" = 1 ] && [ "$rc3" -ne 0 ] && grep -q "nothing to do" $case_dir/cmd.txt && [ "$(cat $rp/S1-integration/base)" = "$base_before" ]'
rbi 1 --paths plans/ tests; rc=$?
check "paths: accepted, the files that leave the diff are listed" '[ "$rc" -eq 0 ] && grep -qx plans/a.md $case_dir/cmd.txt && grep -qx tests/sub/x.txt $case_dir/cmd.txt && grep -q "integrator, the reviewer will not see it" $case_dir/cmd.txt'
check "paths: status.log has the exact list" 'grep -q "S1-integration: base moved under plans tests; 2 file(s) no longer in the diff: plans/a.md tests/sub/x.txt" $rp/status.log'
FAKE_INT_VERDICT=pass resume_with
check "paths: after resume the integration passes" 'grep -q READY $case_dir/cmd.txt'
check "paths: the owner's plans/ and tests/ left the diff; the units' and the integrator's files stay" 'f=$(difffiles $rp/S1-integration/rounds/1/diff.patch); echo "$f" | grep -qx f-01-unit.txt && echo "$f" | grep -qx f-02-unit2.txt && echo "$f" | grep -qx f-repo.txt && ! echo "$f" | grep -qE "^(plans|tests)/"'

# 29. The integrator and the integration review also get the goal, read from 00-input/goal.md when the integration starts.
# The unit's implementer and reviewer do not. A gate block in the goal is not a gate of the integration.
GOALIMPL="$GRPIMPL; [ \"\$n\" = 01-unit ] && echo GOALCURRENT >>$work/goalc/runs/r/00-input/goal.md; true"
new_case goalc '' "$GOALIMPL"
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
printf 'GOALMARK\n\n```gate\nfalse\n```\n' >"$case_dir/plan/goal.md"
run goalc FAKE_INT_VERDICT=back PLAN_MAX_ROUNDS=2
rp=$case_dir/runs/r
check "goal: the integration brief holds the goal as it is when the integration starts" 'grep -q GOALMARK $rp/S1-integration/brief.md && grep -q GOALCURRENT $rp/S1-integration/brief.md'
check "goal: it says the goal adds no criteria to the briefs" 'grep -q "It adds no criteria to the briefs" $rp/S1-integration/brief.md'
check "goal: the integration review prompt has it" 'grep -q GOALMARK $rp/S1-integration/rounds/1/review-prompt.md'
check "goal: the integrator prompt has it" 'grep -q GOALMARK $rp/S1-integration/rounds/2/integrate-prompt.md'
check "goal: the unit implementer and reviewer do not see it" '! grep -q GOALMARK $rp/01-unit/rounds/1/implement-prompt.md && ! grep -q GOALMARK $rp/01-unit/rounds/1/review-prompt.md'
check "goal: a gate block in the goal is not run as a gate of the integration" '[ ! -e $rp/S1-integration/rounds/1/gate.md ]'

# A goal that is gone stops the integration with a reason.
new_case goalgone '' "$GRPIMPL; [ \"\$n\" = 01-unit ] && rm $work/goalgone/runs/r/00-input/goal.md; true"
printf '# U2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"; echo "unit.md unit2.md" >"$case_dir/plan/plan.txt"
run goalgone
check "goal: missing goal stops the integration and says which file" '[ "$code" -ne 0 ] && grep -q "S1-integration: the goal .*goal.md is missing or empty" $case_dir/runs/r/status.log'

# 30. accept-integration: closes a group's integration by hand, on units that passed and were applied.
acc() { envrun "$work/bin/plan-run-limited" accept-integration r "$@"; }
grp_case ac
run ac FAKE_INT_VERDICT=escalate
rp=$case_dir/runs/r
acc 1; rc=$?
check "accept: the reason is required" '[ "$rc" -ne 0 ] && grep -q -- "--why" $case_dir/cmd.txt && [ ! -e $rp/.done-S1-integration ]'
acc 1 --why " "; rc=$?
check "accept: an empty reason is refused" '[ "$rc" -ne 0 ] && [ ! -e $rp/.done-S1-integration ]'
acc 9 --why x; rc=$?
check "accept: a step that does not exist is refused" '[ "$rc" -ne 0 ]'
rm "$rp/S1-integration/.applied-01-unit"
acc 1 --why "reviewed by hand"; rc=$?
check "accept: a unit whose diff was never applied is refused, naming it" '[ "$rc" -ne 0 ] && grep -q "diff of unit 01-unit was never applied" $case_dir/cmd.txt && [ ! -e $rp/.done-S1-integration ]'
touch "$rp/S1-integration/.applied-01-unit"
bash -c 'exec -a plan-run.sh sleep 30' & fakepid=$!
echo "$fakepid" >>"$FAKE_STATE/plan-pids"
echo "$fakepid" >"$rp/.lock"
acc 1 --why "reviewed by hand"; rc=$?
kill "$fakepid" 2>/dev/null; rm -f "$rp/.lock"
check "accept: refused while a plan-run.sh holds the run" '[ "$rc" -ne 0 ] && grep -q "being worked on by pid $fakepid" $case_dir/cmd.txt && [ ! -e $rp/.done-S1-integration ]'
check "accept: the group's worktrees are still there before it succeeds" '[ -d $rp/worktrees/01-unit ]'
acc 1 --why "the owner reviewed the combined diff by hand"; rc=$?
check "accept: closes the integration: marker and status written, worktrees removed" '[ "$rc" -eq 0 ] && [ -e $rp/.done-S1-integration ] && [ "$(cat $rp/S1-integration/status)" = passed ] && [ ! -d $rp/worktrees ]'
check "accept: status.log says who, at which HEAD, why, and that nothing was reviewed" 'grep -qE "S1-integration: closed by hand by $(id -un) at HEAD [0-9a-f]+, without a review of the combined result. Reason: the owner reviewed the combined diff by hand" $rp/status.log'
acc 1 --why again; rc=$?
check "accept: refused once the integration is closed" '[ "$rc" -ne 0 ] && grep -q "already closed" $case_dir/cmd.txt'
resume_with
check "accept: resume goes on to the final review" 'grep -q READY $case_dir/cmd.txt'

grp_case acbad
run acbad FAKE_VERDICT=escalate
acc 1 --why "x"; rc=$?
check "accept: a unit that did not pass is refused, naming it" '[ "$rc" -ne 0 ] && grep -q "unit 01-unit has not passed" $case_dir/cmd.txt && [ ! -e $case_dir/runs/r/.done-S1-integration ]'

new_case acs '' 'echo change >>a.txt'
run acs
acc 1 --why x; rc=$?
check "accept: a step that is not a group is refused" '[ "$rc" -ne 0 ] && grep -q "not a parallel group" $case_dir/cmd.txt'
# 31. A usage limit is named in status.log as QUOTA: <the text as Codex wrote it>, wherever it hits; other failures keep their message.
for stage in implement review report; do
  new_case "q-$stage" '' 'echo change >>a.txt'
  run "q-$stage" FAKE_QUOTA=$stage
  rp=$case_dir/runs/r
  check "quota ($stage): the run stops and status.log has the text after 'try again at', unparsed" '[ "$code" -ne 0 ] && grep -q "QUOTA: 9:43 PM\.$" $rp/status.log'
  check "quota ($stage): the reason says usage limit, not a bare exit code" 'grep -q "usage limit reached. QUOTA: 9:43 PM." $rp/status.log && ! grep -q "exit=1" $rp/status.log'
done
  grp_case q-integrate
  run q-integrate FAKE_IMPL='echo change >>a.txt; [ "$FAKE_N" -ge 2 ] && echo more >>a.txt; true' FAKE_INT_VERDICT=back PLAN_MAX_ROUNDS=2 FAKE_QUOTA=integrate
  check "quota (integrate): named too" '[ "$code" -ne 0 ] && grep -q "S1-integration: usage limit reached. QUOTA: 9:43 PM." $case_dir/runs/r/status.log'
new_case q-other '' 'echo change >>a.txt'
run q-other FAKE_QUOTA=implement FAKE_QUOTA_MSG="You’ve hit your usage limit. Resets on Friday, 3 Nov."
check "quota: a message with no 'try again at' is kept whole, not guessed" 'grep -q "QUOTA: You’ve hit your usage limit. Resets on Friday, 3 Nov." $case_dir/runs/r/status.log'
new_case q-none '' 'echo change >>a.txt'
run q-none FAKE_FAIL=implement
check "quota: another failure keeps its exit message and no QUOTA line" '[ "$code" -ne 0 ] && grep -q "01-unit: implementer exit=1" $case_dir/runs/r/status.log && ! grep -q QUOTA $case_dir/runs/r/status.log'

# 32. Disk: the first worktree of a group measures what one takes; the group is refused when the rest cannot fit (with a margin of a quarter).
grp_case dk-ok
run dk-ok FAKE_DF_BEFORE=300000 FAKE_DF_AFTER=200000
check "disk: room for the rest (125000 KB needed, 200000 free): the group runs" '[ "$code" -eq 0 ] && grep -q "READY" $case_dir/out.txt'
check "disk: status.log says what was measured and projected" 'grep -q "S1: disk: the first worktree took 97 MB; 1 more need about 122 MB, 195 MB free" $case_dir/runs/r/status.log'

grp_case dk-no
run dk-no FAKE_DF_BEFORE=210000 FAKE_DF_AFTER=110000
rp=$case_dir/runs/r
check "disk: 100000 KB per worktree, 110000 free: the margin makes 125000 needed, so the step is refused" '[ "$code" -ne 0 ] && grep -q "not enough free disk for the parallel group of step 1: the first worktree took 97 MB, the other 1 need about 122 MB with a margin of a quarter, and 107 MB is free" $rp/status.log'
check "disk: the refusal says what the estimate leaves out" 'grep -q "temporary database clusters" $rp/status.log'
check "disk: the refusal removes the worktrees it made and leaves no ready marker" '[ ! -d $rp/worktrees ] && [ ! -e $rp/.group-ready-S1 ] && ! ls $rp/*-unit*/status >/dev/null 2>&1'
resume_with
check "disk: after the space is back, resume runs the group" 'grep -q READY $case_dir/cmd.txt'

grp_case dk-noise
run dk-noise FAKE_DF_BEFORE=1000 FAKE_DF_AFTER=2000
check "disk: a measure that shows no consumption (noise) never refuses, and is reported as 0 MB, not a negative number" '[ "$code" -eq 0 ] && grep -q "S1: disk: the first worktree took 0 MB; 1 more need about 0 MB" $case_dir/runs/r/status.log'
# 33. Progress: a green single-unit gate reports each stage in order.
new_case progress-green 'true' 'echo change >>a.txt'
run progress-green
pg_start=$(grep -nF '[plan] S1 início · unidade 01-unit' "$case_dir/out.txt" | cut -d: -f1)
pg_impl=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · implementação' "$case_dir/out.txt" | cut -d: -f1)
pg_gate=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · gate PASS' "$case_dir/out.txt" | cut -d: -f1)
pg_review=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · revisão' "$case_dir/out.txt" | cut -d: -f1)
pg_pass=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · passou' "$case_dir/out.txt" | cut -d: -f1)
pg_done=$(grep -nF '[plan] S1 concluído' "$case_dir/out.txt" | cut -d: -f1)
pg_final_review=$(grep -nF '[plan] final · revisão' "$case_dir/out.txt" | cut -d: -f1)
pg_final_done=$(grep -nF '[plan] final · concluído' "$case_dir/out.txt" | cut -d: -f1)
check "progress green: all expected lines appear in order" '[ "$code" -eq 0 ] && [ "$pg_start" -lt "$pg_impl" ] && [ "$pg_impl" -lt "$pg_gate" ] && [ "$pg_gate" -lt "$pg_review" ] && [ "$pg_review" -lt "$pg_pass" ] && [ "$pg_pass" -lt "$pg_done" ] && [ "$pg_done" -lt "$pg_final_review" ] && [ "$pg_final_review" -lt "$pg_final_done" ]'

# 34. Progress: a red gate reports the failure before the next implementation round.
new_case progress-redfix 'test -f ok' 'echo change >>a.txt; [ "$FAKE_N" -ge 2 ] && touch ok; true'
run progress-redfix
pg_fail=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · gate FAIL' "$case_dir/out.txt" | cut -d: -f1)
pg_retry=$(grep -nF '[plan] S1 unidade 01-unit · ronda 2 · implementação' "$case_dir/out.txt" | cut -d: -f1)
check "progress redfix: gate FAIL precedes round 2 implementation" '[ "$code" -eq 0 ] && [ "$pg_fail" -lt "$pg_retry" ]'

# 35. Progress: reviewer backs are reported and the round cap escalates.
new_case progress-backs 'true' 'echo change >>a.txt'
FAKE_VERDICT=back run progress-backs PLAN_MAX_ROUNDS=2
pg_back=$(grep -nF '[plan] S1 unidade 01-unit · ronda 2 · devolvida' "$case_dir/out.txt" | cut -d: -f1)
pg_escalate=$(grep -nF '[plan] S1 unidade 01-unit · ronda 2 · escalada' "$case_dir/out.txt" | cut -d: -f1)
check "progress backs: the final back is followed by escalation" '[ "$code" -ne 0 ] && [ "$pg_back" -lt "$pg_escalate" ] && grep -qF "[plan] S1 parou" "$case_dir/out.txt"'

# 36. Progress: a parallel step names the group and reports both units.
grp_case progress-group
printf '# Unit\n\n## Result\nx\n\n```gate\ntrue\n```\n' >"$case_dir/plan/unit.md"
printf '# U2\n\n## Result\nx\n\n```gate\ntrue\n```\n' >"$case_dir/plan/unit2.md"
FAKE_IMPL='printf "%s\n" "$PWD" > shared.txt' run progress-group
pg_apply=$(grep -nF '[plan] S1 integração · ronda 1 · aplicar diffs' "$case_dir/out.txt" | cut -d: -f1)
pg_integrate=$(grep -nF '[plan] S1 integração · ronda 1 · integrar' "$case_dir/out.txt" | cut -d: -f1)
pg_gate=$(grep -nF '[plan] S1 integração · ronda 1 · gate PASS' "$case_dir/out.txt" | cut -d: -f1)
pg_review=$(grep -nF '[plan] S1 integração · ronda 1 · revisão' "$case_dir/out.txt" | cut -d: -f1)
pg_pass=$(grep -nF '[plan] S1 integração · ronda 1 · passou' "$case_dir/out.txt" | cut -d: -f1)
check "progress group: names both units and reports each implementation" 'grep -qF "[plan] S1 início · paralelo · 01-unit, 02-unit2" "$case_dir/out.txt" && grep -qF "[plan] S1 unidade 01-unit · ronda 1 · implementação" "$case_dir/out.txt" && grep -qF "[plan] S1 unidade 02-unit2 · ronda 1 · implementação" "$case_dir/out.txt"'
check "progress group: integration stages are in order" '[ "$code" -eq 0 ] && [ "$pg_apply" -lt "$pg_integrate" ] && [ "$pg_integrate" -lt "$pg_gate" ] && [ "$pg_gate" -lt "$pg_review" ] && [ "$pg_review" -lt "$pg_pass" ]'
# 37. Progress: stdout keeps READY and does not receive progress lines.
new_case progress-stdout '' 'echo change >>a.txt'
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" start -p none r "$case_dir/plan/goal.md" "$case_dir/plan/plan.txt") 2>/dev/null >"$case_dir/stdout.txt"
stdout_code=$?
stdout_run=$(python3 -c 'import os, sys; print(os.path.normpath(sys.argv[1]))' "$case_dir/runs/r")
stdout_expected=$(printf 'Run folder: %s\nREADY: %s/report.md\nSee %s/status.log' "$stdout_run" "$stdout_run" "$stdout_run")
check "progress stdout: start keeps its exact output and progress does not leak to it" '[ "$stdout_code" -eq 0 ] && [ "$(cat "$case_dir/stdout.txt")" = "$stdout_expected" ] && ! grep -qF "[plan]" "$case_dir/stdout.txt"'
# 38. Progress: a gate that reaches its cap escalates and stops the step.
new_case progress-gate-cap 'false' 'echo change >>a.txt'
run progress-gate-cap PLAN_MAX_GATE_ROUNDS=1
pg_fail=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · gate FAIL' "$case_dir/out.txt" | cut -d: -f1)
pg_escalate=$(grep -nF '[plan] S1 unidade 01-unit · ronda 1 · escalada' "$case_dir/out.txt" | cut -d: -f1)
check "progress gate cap: failure is followed by escalation and step stop" '[ "$code" -ne 0 ] && [ "$pg_fail" -lt "$pg_escalate" ] && grep -qF "[plan] S1 parou" "$case_dir/out.txt"'

# 39. Progress: a checkpoint reports the pause after the completed step.
new_case progress-pause '' 'echo change >>a.txt'
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" start -p each r "$case_dir/plan/goal.md" "$case_dir/plan/plan.txt") >"$case_dir/out.txt" 2>&1
pause_code=$?
pg_done=$(grep -nF '[plan] S1 concluído' "$case_dir/out.txt" | cut -d: -f1)
pg_pause=$(grep -nF '[plan] S1 pausa' "$case_dir/out.txt" | cut -d: -f1)
check "progress pause: the completed step is followed by pause" '[ "$pause_code" -eq 3 ] && [ "$pg_done" -lt "$pg_pause" ]'

# 40. Progress: a failed final review reports its stop.
new_case progress-final-stop '' 'echo change >>a.txt'
run progress-final-stop FAKE_FAIL=report
check "progress final stop: review and stop are reported without READY" '[ "$code" -ne 0 ] && grep -qF "[plan] final · revisão" "$case_dir/out.txt" && grep -qF "[plan] final · parou" "$case_dir/out.txt" && ! grep -q "^READY:" "$case_dir/out.txt"'

# 41. A finished sequential plan's board lists every unit and the final review; `board` writes to stdout.
new_case board-sequential '' 'echo change >>a.txt'
printf '# Unit 2\n\n## Result\nx\n' >"$case_dir/plan/unit2.md"
printf 'unit.md\nunit2.md\n' >"$case_dir/plan/plan.txt"
run board-sequential
rp=$case_dir/runs/r
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" board r) >"$case_dir/board.txt" 2>"$case_dir/board.err"
board_code=$?
initial_board=$(grep -nF 'Plano r · 2 unidades' "$case_dir/out.txt" | head -1 | cut -d: -f1)
first_step=$(grep -nF '[plan] S1 início · unidade 01-unit' "$case_dir/out.txt" | head -1 | cut -d: -f1)
check "board sequential: start prints the initial board before the first step" '[ "$code" -eq 0 ] && [ -n "$initial_board" ] && [ "$initial_board" -lt "$first_step" ]'
check "board sequential: finished units and final review are passed on stdout" '[ "$board_code" -eq 0 ] && grep -qF "✓ 01-unit" "$case_dir/board.txt" && grep -qF "passou · 1 ronda" "$case_dir/board.txt" && grep -qF "✓ 02-unit2" "$case_dir/board.txt" && grep -qF "✓ Revisão final" "$case_dir/board.txt"'
echo 'Board sample from the finished sequential plan:'
cat "$case_dir/board.txt"

# 42. A parallel group gets a heading, both unit rows and its integration row.
grp_case board-group
run board-group
rp=$case_dir/runs/r
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" board r) >"$case_dir/board.txt" 2>"$case_dir/board.err"
board_head=$(grep -nF 'Passo 1 (paralelo)' "$case_dir/board.txt" | cut -d: -f1)
board_unit1=$(grep -nF '01-unit' "$case_dir/board.txt" | cut -d: -f1)
board_unit2=$(grep -nF '02-unit2' "$case_dir/board.txt" | cut -d: -f1)
board_integration=$(grep -nF 'integração' "$case_dir/board.txt" | cut -d: -f1)
check "board parallel: both units and integration appear under the parallel step" '[ "$code" -eq 0 ] && [ "$board_head" -lt "$board_unit1" ] && [ "$board_unit1" -lt "$board_unit2" ] && [ "$board_unit2" -lt "$board_integration" ] && grep -qF "✓ integração" "$case_dir/board.txt"'
# 43. A failed gate sends the unit back; the round 2 board is captured from stderr.
new_case board-gate-back 'test -f ok' 'echo change >>a.txt; [ "$FAKE_N" -ge 2 ] && touch ok; true'
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" start -p none r "$case_dir/plan/goal.md" "$case_dir/plan/plan.txt") >"$case_dir/stdout.txt" 2>"$case_dir/stderr.txt"
gate_back_code=$?
check "board gate back: round 2 shows the gate failure on stderr" '[ "$gate_back_code" -eq 0 ] && grep -qF "[plan] S1 unidade 01-unit · ronda 2 · implementação" "$case_dir/stderr.txt" && grep -qF "↩ 01-unit" "$case_dir/stderr.txt" && grep -qF "gate falhou · ronda 2 a implementar" "$case_dir/stderr.txt"'

# 44. Resume keeps the same stdout contract as start while the board stays on stderr.
new_case board-resume-stdout '' 'echo change >>a.txt'
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" start -p each r "$case_dir/plan/goal.md" "$case_dir/plan/plan.txt") >"$case_dir/start.stdout" 2>"$case_dir/start.stderr"
pause_code=$?
stdout_run=$(python3 -c 'import os, sys; print(os.path.normpath(sys.argv[1]))' "$case_dir/runs/r")
start_expected=$(printf 'Run folder: %s\nPAUSED after step 1 (01-unit). Read it in %s, then: plan-run.sh resume r\nSee %s/status.log' "$stdout_run" "$stdout_run" "$stdout_run")
(cd "$case_dir/repo" && env PATH="$work/bin:$PATH" PLAN_RUNS_DIR="$case_dir/runs" PLAN_GUIDES="$work/guides" \
  "$work/bin/plan-run-limited" resume -p none r) >"$case_dir/resume.stdout" 2>"$case_dir/resume.stderr"
resume_code=$?
resume_expected=$(printf 'Run folder: %s\nREADY: %s/report.md\nSee %s/status.log' "$stdout_run" "$stdout_run" "$stdout_run")
check "board stdout: start and resume preserve their exact stdout" '[ "$pause_code" -eq 3 ] && [ "$resume_code" -eq 0 ] && [ "$(cat "$case_dir/start.stdout")" = "$start_expected" ] && [ "$(cat "$case_dir/resume.stdout")" = "$resume_expected" ] && ! grep -qF "[plan]" "$case_dir/start.stdout" && ! grep -qF "[plan]" "$case_dir/resume.stdout"'

exit "$fail"

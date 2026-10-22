#!/usr/bin/env bash
# Run a plan with Codex: each unit is implemented by one agent and reviewed by another. The coordinator
# only writes the goal and the unit briefs, and says which units run together.
# Usage (run start, resume and finish inside the repository the plan changes):
#   plan-run.sh start   [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>
#   plan-run.sh resume  [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name>
#   plan-run.sh status  <name>
#   plan-run.sh gates   <plan.txt|name>
#   plan-run.sh finish  [--discard] <name>
#   plan-run.sh rebase-integration <name> <step> [--paths <path>...]
#   plan-run.sh accept-integration <name> <step> --why <text>
# plan.txt: one step per line, in order. A line holds the paths of unit briefs (relative to plan.txt),
# separated by spaces. One brief is a unit run in your checkout. Several on one line are a parallel group:
# each runs in its own git worktree, made from the state of your checkout when the group starts (untracked
# files included, ignored ones not), and when all have passed an integration agent applies their diffs to your checkout
# and a reviewer checks the combined result. Blank lines and lines starting with # are ignored.
# While a script works on a run it holds <run>/.lock (its pid); a second `resume` or a `finish` on that run is refused.
# State lives in ${PLAN_RUNS_DIR:-$HOME/.plan-runs}/<name>, one numbered folder per unit. It must not be
# under /tmp: the workspace-write sandbox leaves /tmp writable. A unit copies its brief from
# <run>/00-input/units/ to <run>/<unit>/brief.md when it starts, and a unit that has passed does not start again. So
# a correction in 00-input/units/ before `resume` reaches the units that still have to run, and always the integration
# of a group and the final review, which read the current briefs; the unit's own copy stays as what its implementer
# received. When the two differ, the integration brief and the final review show both and say how to weigh them; the
# integration also notes it in status.log, and more strongly when the gate differs, because the unit passed against
# another gate.
# -p sets checkpoints by step number: `each`, or numbers like `2,4`. After such a step passes the run
# pauses (exit 3, `PAUSED` in status.log) so the user can read it; `resume` goes on. On resume, -p replaces
# the list (`-p none` clears it). With no -p the run goes through every step.
# The agents never change git state. A unit's base is the checkout as the previous step left it (a git tree of
# the working files, untracked ones included); the reviewer reads the diff from it. Changes made in the checkout
# between steps, or while a unit is stopped, therefore never land in the next unit's diff. A group's integration is the
# exception: its base is taken when it starts and kept, so edits to the checkout after that appear in its diff (do not
# edit the checkout during a step; `rebase-integration` is the emergency exit). The units of a group work in worktrees made
# once, when the group starts: `resume` does not make them again.
# The gate: a brief lists commands in a fenced block tagged `gate` (one command per line; blank lines and lines
# starting with # are ignored). After each implementation round the script runs them itself, in the checkout,
# outside any agent, and only calls the reviewer when every one passes. A failing command sends the work back to
# the implementer with its output and no review; the reviewer cannot override a command, and a pass needs the
# gate green and the reviewer's pass. A brief without a gate is reviewed as before. `gates` prints the commands
# of every unit (from a plan.txt or a run), so the coordinator reads what code will run before the run starts.
# The bridge: an implementer's sandbox cannot reach the database (the host does not resolve). While an implementer
# works, the script serves `.plan-porteiro/ponte <command...>` in its checkout: the agent writes a request, the
# script (outside the sandbox) runs it if it is allowed and hands back the output and the exit code. Allowed:
# `pnpm <script>` when the script's name matches a pattern in the repository's `.plan-run.json` (read from the
# unit's base, never the working tree, so a unit cannot widen its own list; without a usable file at the base no
# pnpm script runs; the script must also be unchanged from the base), and the unit's gate commands exactly as
# written in the brief. Anything else is refused. The command is run without a shell, so the agent supplies
# arguments, never shell syntax. Every request is logged in <run>/porteiro.log. Reviewers run read-only and have
# no bridge: they receive the gate result.
# Metrics: after each implementation round the script appends a line to <run>/metrics.tsv (unit, round, minutes,
# steps the agent took, files in the diff, input tokens), and `finish` puts them in status.md, so the rule of thumb
# for the size of a unit can be checked against real runs.
# Limits: PLAN_MAX_ROUNDS (default 3) escalates a review that keeps sending work back;
# PLAN_MAX_GATE_ROUNDS (default 5) stops a unit whose gate keeps failing (both counts start again at every `resume`); PLAN_GATE_TIMEOUT (seconds, default
# 900) limits each gate command;
# PLAN_MIN_CHECKED (default 3) is the least number of lines a reviewer must give under
# "What I checked". PLAN_GUIDES points at the folder with the role guides.
# When Codex reports a usage limit the run stops and status.log gets `QUOTA: <text after "try again at">`, unparsed.
# Before a parallel group the first worktree measures its size and the group is refused if the rest will not fit (worktrees
# only, with a margin of a quarter; not what the units create while they run).
# `-p` pauses with exit 3, which is a pause and not a failure.
# PLAN_CODEX_TIER is Codex's service tier: fast unless set; PLAN_CODEX_TIER= (empty) keeps the account default.
# Progress goes to stderr as `[plan] S<k> ...` and `[plan] final · ...` lines.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
root=${PLAN_RUNS_DIR:-$HOME/.plan-runs}
guides=${PLAN_GUIDES:-$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)/agent-skills/library/workflow-types/plan}
max_rounds=${PLAN_MAX_ROUNDS:-3}
min_checked=${PLAN_MIN_CHECKED:-3}
max_gate_rounds=${PLAN_MAX_GATE_ROUNDS:-5}
gate_timeout=${PLAN_GATE_TIMEOUT:-900}
export PLAN_CODEX_TIER=${PLAN_CODEX_TIER-fast}
porteiro_timeout=${PLAN_PORTEIRO_TIMEOUT:-900}
model=gpt-6-luna effort=xhigh review_effort=
plan_step=0

# shellcheck source=lib-codex.sh
. "$here/lib-codex.sh"

note() { printf '%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$run/status.log"; }
progress() { printf '[plan] %s\n' "$*" >&2; }
valid_pause() { [[ $1 =~ ^(none|each|[0-9]+(,[0-9]+)*)$ ]]; }

# Reviewers (and the final review) may use their own reasoning effort: -r, default the implementers' effort.
review_run() { # same arguments as codex_run
  local saved=$effort code
  effort=${review_effort:-$effort}
  codex_run "$@"; code=$?
  effort=$saved
  return $code
}

load_run() { # <name>
  valid_name "$1" || die "bad run name: $1"
  run=$root/$1
  [ -d "$run" ] || die "no such run: $run"
  repo=$(cat "$run/repo")
  if [ -f "$run/settings" ]; then read -r model effort review_effort <"$run/settings"; fi
  pause=$(cat "$run/pause" 2>/dev/null || true)
}

# True when the run should pause after this step and has not yet.
pause_here() { # <step>
  [ -e "$run/.paused-S$1" ] && return 1
  case "$pause" in
    each) return 0 ;;
    ''|none) return 1 ;;
  esac
  case ",$pause," in *",$1,"*) return 0 ;; esac
  return 1
}

# ---- The lock: one script at a time works on a run ----
# <run>/.lock holds the pid of the plan-run.sh that is working on the run. A lock whose pid is gone, or now belongs to
# another program, is stale and is replaced. `resume` and `finish` (and the commands that change a stopped run) refuse
# while a live script holds it.

run_active() { # true when a live plan-run.sh holds the lock of $run
  local pid
  pid=$(cat "$run/.lock" 2>/dev/null) || return 1
  [[ $pid =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  case "$(ps -p "$pid" -o command= 2>/dev/null)" in *plan-run.sh*) return 0 ;; esac
  return 1
}

unlock_run() {
  [ "$(cat "$run/.lock" 2>/dev/null)" = "$$" ] && rm -f "$run/.lock"
  return 0
}

lock_run() {
  local i
  for i in 1 2; do
    if (set -C; echo $$ >"$run/.lock") 2>/dev/null; then trap unlock_run EXIT; return 0; fi
    run_active && die "run $(basename "$run") is already being worked on by pid $(cat "$run/.lock")"
    rm -f "$run/.lock"
  done
  die "cannot lock $run"
}

# ---- The diff of a unit: the checkout as a tree before it, against the checkout as a tree after it ----
# A snapshot is a git tree built in a throwaway index: tracked and untracked files alike (ignored ones left out),
# whatever HEAD is. So edits to files git did not track yet show up, a commit made meanwhile changes nothing,
# and nothing in the real index or the working files is touched. Runs begun with the older script keep a commit
# as base and a list of untracked files (no `base-format` file in the folder); make_patch still reads those.

snapshot_tree() { # <checkout>: prints the id of a tree holding the checkout as it is now
  local tmp t
  tmp=$(mktemp -u "${TMPDIR:-/tmp}/plan-run-index.XXXXXX") || return 1
  GIT_INDEX_FILE=$tmp git -C "$1" read-tree HEAD >/dev/null 2>&1 || { rm -f "$tmp"; return 1; }
  GIT_INDEX_FILE=$tmp git -C "$1" add -A >/dev/null 2>&1
  t=$(GIT_INDEX_FILE=$tmp git -C "$1" write-tree 2>/dev/null)
  rm -f "$tmp"
  [ -n "$t" ] || return 1
  echo "$t"
}

snapshot_commit() { # <checkout>: like snapshot_tree, as a commit, for `git worktree add`
  local t
  t=$(snapshot_tree "$1") || return 1
  GIT_AUTHOR_NAME=plan-run GIT_AUTHOR_EMAIL=plan-run@localhost GIT_COMMITTER_NAME=plan-run GIT_COMMITTER_EMAIL=plan-run@localhost \
    git -C "$1" commit-tree "$t" -p HEAD -m "plan-run snapshot"
}

snapshot_base() { # <dir> <checkout>
  local t
  t=$(snapshot_tree "$2") || die "cannot snapshot the checkout $2"
  echo "$t" >"$1/base"
  echo tree >"$1/base-format"
}

make_patch() { # <dir> <out-file> <checkout>
  local f cur
  if [ "$(cat "$1/base-format" 2>/dev/null)" = tree ]; then
    cur=$(snapshot_tree "$3") || return 1
    git -C "$3" diff --no-ext-diff "$(cat "$1/base")" "$cur" >"$2"
    return 0
  fi
  git -C "$3" diff "$(cat "$1/base")" >"$2"
  git -C "$3" ls-files --others --exclude-standard | sort >"$1/untracked-after.txt"
  comm -13 "$1/untracked-before.txt" "$1/untracked-after.txt" | while IFS= read -r f; do
    [ -f "$3/$f" ] && (cd "$3" && git diff --no-index -- /dev/null "$f") >>"$2"
  done
  return 0
}

# ---- The gate: commands in the brief that the script runs itself, outside any agent ----

gate_commands() { # <brief>...: the commands of every ```gate block, one per line, without duplicates
  awk '
    /^```gate[[:space:]]*$/ { on = 1; next }
    on && /^```[[:space:]]*$/ { on = 0; next }
    on && !/^[[:space:]]*(#|$)/ { sub(/^[[:space:]]+/, ""); sub(/[[:space:]]+$/, ""); if (!seen[$0]++) print }
  ' "$@"
}

# Runs the gate of a brief in a checkout. Writes <round>/gate.md (each command, its result, the tail of the
# output of those that failed) and gate-<n>.log; returns nonzero when any command failed.
run_gate() { # <brief> <checkout> <round-dir>
  local cmd n=0 failed=0 code start secs log out=$3/gate.md
  printf '# Gate\n\nThe script ran these commands in %s, outside any agent.\n\n' "$2" >"$out"
  while IFS= read -r cmd; do
    n=$((n + 1))
    log=$3/gate-$n.log
    start=$(date +%s)
    (cd "$2" && perl -e 'alarm shift @ARGV; exec @ARGV' "$gate_timeout" bash -c "$cmd") >"$log" 2>&1 </dev/null
    code=$?
    secs=$(($(date +%s) - start))
    if [ "$code" -eq 0 ]; then
      printf -- '- PASS `%s` (%ss)\n' "$cmd" "$secs" >>"$out"
    else
      failed=1
      [ "$code" -eq 142 ] && printf 'timed out after %ss\n' "$gate_timeout" >>"$log"
      printf -- '- FAIL `%s` exit %s (%ss)\n\n```\n%s\n```\n\n' "$cmd" "$code" "$secs" "$(tail -n 60 "$log")" >>"$out"
    fi
  done < <(gate_commands "$1")
  return "$failed"
}

# The review a failed gate produces in place of a reviewer: back, with the commands and their output.
write_gate_problems() { # <round-dir>
  {
    printf '## What I checked\n\n- The script ran the brief'"'"'s gate in the checkout; a command failed, so no reviewer ran (a failing command is not a matter of opinion).\n- The results are in gate.md of this round.\n- Each failing command below must pass.\n\n## Problems\n\n'
    cat "$1/gate.md"
    printf '\nVERDICT: back\n'
  } >"$1/problems.md"
}

# ---- The bridge: the implementer asks, the script runs what is allowed outside the sandbox ----

# The agent-side command, written into the checkout. It only writes a request and waits for the answer.
porteiro_ponte_script() {
  cat <<'PONTE'
#!/usr/bin/env bash
# Asks the runner to run an allowed command outside the sandbox. Usage: .plan-porteiro/ponte <command> [args...]
d=$(cd "$(dirname "$0")" && pwd)
[ "$#" -gt 0 ] || { echo "usage: .plan-porteiro/ponte <command> [args...]" >&2; exit 2; }
id=$(date +%s)-$$-$RANDOM
mkdir -p "$d/req" "$d/res"
printf '%s\0' "$@" >"$d/req/.$id.tmp"
mv "$d/req/.$id.tmp" "$d/req/$id"
limit=$(( ${PORTEIRO_WAIT:-1800} * 2 )); n=0
while [ ! -e "$d/res/$id.done" ]; do
  sleep 0.5; n=$((n + 1))
  [ "$n" -lt "$limit" ] || { echo "ponte: no answer from the runner" >&2; exit 124; }
done
cat "$d/res/$id.out"
code=$(cat "$d/res/$id.done")
rm -f "$d/res/$id.out" "$d/res/$id.done"
exit "$code"
PONTE
}

porteiro_setup() { # <checkout>
  local d=$1/.plan-porteiro ex
  rm -rf "$d"; mkdir -p "$d/req" "$d/res"
  porteiro_ponte_script >"$d/ponte"; chmod +x "$d/ponte"
  # kept out of every diff and snapshot without touching the repository's own ignore rules
  ex=$(git -C "$1" rev-parse --git-path info/exclude 2>/dev/null)
  case "$ex" in /*) ;; *) ex=$1/$ex ;; esac
  mkdir -p "$(dirname "$ex")"
  grep -qxF '.plan-porteiro/' "$ex" 2>/dev/null || echo '.plan-porteiro/' >>"$ex"
}

porteiro_log() { printf '%s\t%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" "$2" "$3" >>"$run/porteiro.log"; }

# Whether a pnpm script may run through the bridge: its name is plain, and a pattern of .plan-run.json at the unit's
# base matches the whole name. The file is read from the base, never the working tree. Sets $porteiro_why when refused.
porteiro_script_allowed() { # <checkout> <base> <script>
  local co=$1 base=$2 script=$3 b text verdict
  [[ $script =~ ^[A-Za-z0-9:_-]+$ ]] || { porteiro_why="$script has characters that are not allowed"; return 1; }
  b=$(cat "$base" 2>/dev/null)
  if [ -z "$b" ] || ! text=$(git -C "$co" show "$b:.plan-run.json" 2>/dev/null); then
    porteiro_why="no .plan-run.json at the unit's base: only gate commands run"; return 1
  fi
  verdict=$(printf '%s' "$text" | node -e '
    let s = "";
    process.stdin.on("data", d => s += d).on("end", () => {
      let res;
      try {
        const pats = JSON.parse(s).bridge.pnpmScripts;
        if (!Array.isArray(pats) || !pats.every(p => typeof p === "string")) throw new Error("shape");
        pats.forEach(p => new RegExp(p)); // each pattern must compile alone, so none can close the ^(?:...)$ group early
        res = pats.map(p => new RegExp("^(?:" + p + ")$"));
      } catch { process.stdout.write("invalid"); return; }
      process.stdout.write(res.some(re => re.test(process.argv[1])) ? "match" : "nomatch");
    });
  ' "$script" 2>/dev/null)
  case "$verdict" in
    match) return 0 ;;
    nomatch) porteiro_why="$script is not in the pnpm scripts that .plan-run.json allows"; return 1 ;;
    *) porteiro_why="the .plan-run.json at the unit's base is not usable: only gate commands run"; return 1 ;;
  esac
}

# Decides whether a request may run. Sets $porteiro_mode (argv|shell) or $porteiro_why. Arguments: checkout,
# base, brief, then the requested argv.
porteiro_allowed() {
  local co=$1 base=$2 brief=$3 line script now was; shift 3
  porteiro_mode="" porteiro_why=""
  [ "$#" -gt 0 ] || { porteiro_why="empty request"; return 1; }
  while IFS= read -r line; do
    [ "$line" = "$*" ] && { porteiro_mode=shell; return 0; }
  done < <(gate_commands "$brief")
  if [ "$1" = pnpm ] && [ "$#" -ge 2 ]; then
    porteiro_script_allowed "$co" "$base" "$2" || return 1
    script=$2
    now=$(node -e 'try{process.stdout.write(String(require(process.argv[1]).scripts[process.argv[2]]??""))}catch{}' "$co/package.json" "$script")
    was=$(git -C "$co" show "$(cat "$base" 2>/dev/null):package.json" 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{try{process.stdout.write(String(JSON.parse(s).scripts[process.argv[1]]??""))}catch{}})' "$script")
    [ -n "$was" ] || { porteiro_why="$script is not a script of the unit's base"; return 1; }
    [ "$now" = "$was" ] || { porteiro_why="$script was changed in this unit"; return 1; }
    porteiro_mode=argv; return 0
  fi
  porteiro_why="not allowed: only the pnpm scripts listed in .plan-run.json at the unit's base and the gate commands of the brief"
  return 1
}

# Answers one request file. The output goes to res/<id>.out and the exit code to res/<id>.done, written last.
porteiro_handle() { # <checkout> <unit> <base> <brief> <request-file>
  local co=$1 u=$2 base=$3 brief=$4 f=$5 id arg start secs code=126
  local -a argv=()
  id=$(basename "$f")
  while IFS= read -r -d '' arg; do argv+=("$arg"); done <"$f"
  local res=$co/.plan-porteiro/res
  if porteiro_allowed "$co" "$base" "$brief" ${argv[@]+"${argv[@]}"}; then
    start=$(date +%s)
    if [ "$porteiro_mode" = shell ]; then
      (cd "$co" && perl -e 'alarm shift @ARGV; exec @ARGV' "$porteiro_timeout" bash -c "${argv[*]}") </dev/null >"$res/$id.run" 2>&1
    else
      (cd "$co" && perl -e 'alarm shift @ARGV; exec @ARGV' "$porteiro_timeout" "${argv[@]}") </dev/null >"$res/$id.run" 2>&1
    fi
    code=$?
    secs=$(($(date +%s) - start))
    [ "$code" -eq 142 ] && printf 'ponte: timed out after %ss\n' "$porteiro_timeout" >>"$res/$id.run"
    tail -c 200000 "$res/$id.run" >"$res/$id.out"; rm -f "$res/$id.run"
    porteiro_log "$u" "ALLOWED exit=$code ${secs}s" "${argv[*]}"
  else
    printf 'ponte: refused (%s).\nAllowed: the pnpm scripts listed in .plan-run.json and the commands of the brief'"'"'s gate, exactly as written.\n' "$porteiro_why" >"$res/$id.out"
    porteiro_log "$u" "REFUSED ($porteiro_why)" "${argv[*]-}"
  fi
  echo "$code" >"$res/$id.done.tmp"; mv "$res/$id.done.tmp" "$res/$id.done"
}

porteiro_serve() { # <checkout> <unit> <base> <brief> <parent-pid>   (runs in the background)
  local co=$1 u=$2 base=$3 brief=$4 parent=$5 f
  while [ ! -e "$co/.plan-porteiro/.stop" ] && kill -0 "$parent" 2>/dev/null; do
    for f in "$co"/.plan-porteiro/req/*; do
      [ -f "$f" ] || continue
      case "$(basename "$f")" in .*) continue ;; esac
      porteiro_handle "$co" "$u" "$base" "$brief" "$f"
      rm -f "$f"
    done
    sleep 0.3
  done
}

porteiro_stop() { # <checkout> <pid>
  touch "$1/.plan-porteiro/.stop" 2>/dev/null
  wait "$2" 2>/dev/null
  rm -rf "$1/.plan-porteiro"
}

# One line per implementation round in <run>/metrics.tsv: how big the round was, to calibrate the size of a unit.
record_metrics() { # <unit> <round> <round-dir> <start-epoch>
  local steps files tokens
  steps=$(grep -c '"type":"item.completed"' "$3/implement.events.jsonl" 2>/dev/null); steps=${steps:-0}
  files=$(grep -c '^diff --git' "$3/diff.patch" 2>/dev/null); files=${files:-0}
  tokens=$(grep -o '"input_tokens":[0-9]*' "$3/implement.events.jsonl" 2>/dev/null | tail -1 | cut -d: -f2); tokens=${tokens:-0}
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$((($(date +%s) - $4) / 60))" "$steps" "$files" "$tokens" >>"$run/metrics.tsv"
}

# ---- The briefs the integration and the final review read: the current ones in 00-input/units/ ----
# <run>/<u>/brief.md is what the implementer received, and stays as the record of it. A unit that already passed is not
# started again, so a correction made in 00-input/units/ reaches the integration and the final review only through here.

brief_current() { # <unit>: the current brief
  echo "$run/00-input/units/$1.md"
}

check_briefs() { # <unit>...: sets $reason and fails when a current brief is missing or empty
  local u
  for u in "$@"; do
    [ -s "$(brief_current "$u")" ] || { reason="$u: the current brief $(brief_current "$u") is missing or empty"; return 1; }
  done
}

brief_differs() { # <unit>: the current brief is not the one the implementer received
  [ -f "$run/$1/brief.md" ] && ! cmp -s "$(brief_current "$1")" "$run/$1/brief.md"
}

gate_differs() { # <unit>
  brief_differs "$1" && [ "$(gate_commands "$(brief_current "$1")")" != "$(gate_commands "$run/$1/brief.md")" ]
}

# Prints the current brief; when the implementer received another, then that one, with how to weigh the two.
print_unit_brief() { # <unit> <heading-marks>
  cat "$(brief_current "$1")"
  if brief_differs "$1"; then
    printf '\n\n%s Brief received by the implementer (differs from the current one)\n\nThe current brief defines the intent. The copy below is what the implementer received. Judge against the current brief. If the unit meets the copy but not the current brief, say so: the deviation comes from the change of brief, not from the unit. If it fails both, the unit failed.\n\n' "$2"
    cat "$run/$1/brief.md"
  fi
}

# ---- Usage limit: Codex says so in its events when the account is out of quota ----
# The text after "try again at" is kept as it came (a time, another day, whatever Codex writes): it is not parsed.

quota_text() { # <events-file>: the usage-limit message, for status.log; fails when there is none
  local line
  line=$(grep -m1 'hit your usage limit' "$1" 2>/dev/null) || return 1
  case "$line" in
    *'try again at '*) printf '%s' "$line" | sed 's/.*try again at //; s/"[^"]*$//' ;;
    *) printf '%s' "$line" | sed 's/.*"message":"//; s/"[^"]*$//' ;;
  esac
}

# Sets $reason for an agent that exited with an error: the usage limit, when that is why, else the given reason.
codex_failed() { # <out-prefix> <label> <reason-when-not-quota>
  local q
  if q=$(quota_text "$1.events.jsonl"); then
    reason="$2: usage limit reached. QUOTA: $q (see $1.events.jsonl)"
    note "QUOTA: $q"
  else
    reason=$3
  fi
}

# ---- Prompts: fixed templates, so the coordinator never writes them by hand ----

implement_prompt() { # <unit-brief> <round> <resumed> <prev-problems> <prev-handoff>
  cat "$1"
  printf '\n\n---\n## Role\nOpen and follow the role guide: %s/plan-implementation.md (read-only). It says how to work inside the brief, what to verify and what the handoff holds.\n' "$guides"
  printf '\n## Rules\n- The current directory is the repository: do the work here.\n- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.\n'
  printf -- '- You cannot reach the database from here (the database host does not resolve). To run something that needs it, ask the runner: `.plan-porteiro/ponte <command> [args...]`. It runs the command outside your sandbox and prints the output and the exit code. Only the `pnpm` scripts the repository allows for the bridge (see `.plan-run.json`) and the commands of the brief'"'"'s gate, exactly as written, are accepted; anything else is refused, and every request is logged. Use it to read the data you need and to run the checks against the database.\n'
  if [ -n "$(gate_commands "$1")" ]; then
    printf -- '- The brief has a `gate`. After you finish, the script runs those commands itself and sends the work back, without a review, if any fails. Run them yourself first when you can.\n'
  fi
  if [ "$2" -eq 1 ] && [ "$3" -eq 1 ]; then
    printf '\nAn earlier attempt at this unit was stopped. The checkout may already hold its work. Judge it against the brief, keep what is right and fix the rest.\n'
  fi
  if [ -n "$4" ]; then
    printf '\nThe script'"'"'s gate or a reviewer sent your work back. The work from the earlier round is in the checkout. Fix the problems below and only those, keeping what was fine, and verify again.\n\nProblems from the gate or the review:\n\n'
    cat "$4"
    printf '\n\nYour handoff from the previous round, for you to resume from:\n\n'
    cat "$5"
    printf '\n'
  fi
}

integrate_prompt() { # <group-brief> <failed-patches-or-empty> <prev-problems> <prev-handoff>
  cat "$1"
  printf '\n\n---\n## Role\nOpen and follow the role guide: %s/plan-integration.md (read-only). It says how to bring the units of a parallel group together and what the handoff holds.\n' "$guides"
  printf '\n## Rules\n- The current directory is the repository: work here.\n- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).\n- Do not write the handoff to a file. Your final message is the handoff, and nothing else.\n'
  if [ -n "$2" ]; then
    printf '\n## What to do\nThe diffs of these units did not apply to the checkout. Bring what each one meant into the checkout, resolving the conflict, and change nothing else:\n%s\n' "$2"
  fi
  if [ -n "$3" ]; then
    printf '\nA reviewer found problems in the combined result. Fix those and only those, then verify again.\n\nProblems from the review:\n\n'
    cat "$3"
    printf '\n\nYour handoff from the previous round, for you to resume from:\n\n'
    cat "$4"
    printf '\n'
  fi
}

review_prompt() { # <brief> <patch> <previous-problems-or-empty> <attempt> <gate-file-or-empty>
  printf '# Review\n\n## The brief\n\n'
  cat "$1"
  printf '\n\n---\n## Inputs (read-only)\n- The diff, new files included: %s\n- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.\n- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.\n' "$2"
  if [ -n "${5:-}" ]; then
    printf -- '- The gate: the script ran the brief'"'"'s `gate` commands itself, outside your sandbox, and every one passed: %s. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.\n' "$5"
  fi
  printf '\n## Role\nOpen and follow the role guide: %s/plan-review.md (read-only). You are not the author of the work.\n' "$guides"
  if [ -n "$3" ]; then
    printf '\nThe problems you listed in the previous round are below. The work was corrected; check whether they are gone.\n\n'
    cat "$3"
    printf '\n'
  fi
  printf '\n---\nYour final message is the review, and nothing else. Begin it with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:\nVERDICT: pass\nVERDICT: back\nVERDICT: escalate\n'
  if [ "$4" -gt 1 ]; then
    printf 'Your previous attempt left no usable review (no "## What I checked" section, or no verdict line). Follow the form this time.\n'
  fi
}

# ---- Stages: each one writes its own folder and returns nonzero (with $reason) when it stops ----

# One review of a round. Sets $verdict; returns nonzero (with $reason) when no usable review comes out.
do_review() { # <label> <checkout> <brief> <round-dir> <prev-problems-or-empty>
  local attempt=0 checked=0 code
  while [ "$attempt" -lt 3 ]; do
    attempt=$((attempt + 1))
    rm -f "$4/review.last-message.md"
    review_prompt "$3" "$4/diff.patch" "$5" "$attempt" "$([ -s "$4/gate.md" ] && echo "$4/gate.md")" >"$4/review-prompt.md"
    review_run "$2" "$4/review-prompt.md" "$4/review" read-only
    code=$?
    [ "$code" -eq 0 ] || { codex_failed "$4/review" "$1" "$1: review exit=$code (see $4/review.stderr.log)"; return 1; }
    if [ -s "$4/review.last-message.md" ] && checked_ok "$4/review.last-message.md" && read_verdict "$4/review.last-message.md" >/dev/null; then
      checked=1; break
    fi
    note "$1: review attempt $attempt was not usable"
  done
  [ "$checked" -eq 1 ] || { reason="$1: the reviewer left no usable review after $attempt attempts (see $4/review.last-message.md)"; return 1; }
  cp "$4/review.last-message.md" "$4/problems.md"
  verdict=$(read_verdict "$4/problems.md")
  echo "$verdict" >"$4/verdict"
  note "$1: round $(basename "$4"): verdict $verdict"
}

run_unit() { # <unit-dir-name> <checkout> [<step>]
  local u=$1 co=$2 d=$run/$1 k=${3:-}
  local round=0 reviews=0 gate_fails=0 resumed=0 prev="" prevh="" rd code from="" pbridge t0
  # The base is the checkout as the previous step left it, so that whatever changed in the checkout between that
  # and the (re)start of this unit never lands in its diff. Only a plain (non-group) step has one.
  if [ -n "$k" ]; then
    if [ "$k" -gt 1 ]; then from=$run/state-after-S$((k - 1)); else from=$run/plan-base/base; fi
    if [ "$k" -eq 1 ] && [ "$(cat "$run/plan-base/base-format" 2>/dev/null)" != tree ]; then from=""; fi
    [ -f "$from" ] || from=""
  fi
  mkdir -p "$d"
  if [ -f "$d/base" ]; then
    resumed=1
    [ -d "$d/rounds" ] && mv "$d/rounds" "$d/rounds.attempt-$(date +%s)"
  fi
  if [ -n "$from" ]; then
    cp "$from" "$d/base"; echo tree >"$d/base-format"
  elif [ "$resumed" -eq 0 ]; then
    snapshot_base "$d" "$co"
  fi
  mkdir -p "$d/rounds"
  cp "$run/00-input/units/$u.md" "$d/brief.md"

  while :; do
    round=$((round + 1))
    rd=$d/rounds/$round
    mkdir -p "$rd"

    progress "S$plan_step unidade $u · ronda $round · implementação"
    echo "implementing round $round" >"$d/status"
    note "$u round $round: implement"
    implement_prompt "$d/brief.md" "$round" "$resumed" "$prev" "$prevh" >"$rd/implement-prompt.md"
    t0=$(date +%s)
    porteiro_setup "$co"
    porteiro_serve "$co" "$u" "$d/base" "$d/brief.md" "$$" &
    pbridge=$!
    codex_run "$co" "$rd/implement-prompt.md" "$rd/implement" workspace-write
    code=$?
    porteiro_stop "$co" "$pbridge"
    [ "$code" -eq 0 ] || { codex_failed "$rd/implement" "$u" "$u: implementer exit=$code (see $rd/implement.stderr.log)"; return 1; }
    [ -s "$rd/implement.last-message.md" ] || { reason="$u: implementer left no handoff"; return 1; }
    cp "$rd/implement.last-message.md" "$rd/handoff.md"
    cp "$rd/handoff.md" "$d/handoff.md"
    make_patch "$d" "$rd/diff.patch" "$co"
    record_metrics "$u" "$round" "$rd" "$t0"
    [ -s "$rd/diff.patch" ] || { reason="$u: the diff is empty after round $round, so nothing was changed"; return 1; }

    if [ -n "$(gate_commands "$d/brief.md")" ]; then
      echo "gate round $round" >"$d/status"
      note "$u round $round: gate"
      if run_gate "$d/brief.md" "$co" "$rd"; then
        progress "S$plan_step unidade $u · ronda $round · gate PASS"
        note "$u round $round: gate passed"
      else
        progress "S$plan_step unidade $u · ronda $round · gate FAIL"
        gate_fails=$((gate_fails + 1))
        write_gate_problems "$rd"; echo back >"$rd/verdict"
        note "$u: round $round: gate failed (see $rd/gate.md)"
        if [ "$gate_fails" -ge "$max_gate_rounds" ]; then
          progress "S$plan_step unidade $u · ronda $round · escalada"
          echo escalated >"$d/status"
          reason="$u: the gate still fails after $gate_fails rounds (see $rd/gate.md)"
          return 1
        fi
        prev=$rd/problems.md prevh=$rd/handoff.md
        continue
      fi
    fi

    reviews=$((reviews + 1))
    progress "S$plan_step unidade $u · ronda $round · revisão"
    echo "reviewing round $round" >"$d/status"
    note "$u round $round: review"
    do_review "$u" "$co" "$d/brief.md" "$rd" "$prev" || return 1

    case "$verdict" in
      pass) progress "S$plan_step unidade $u · ronda $round · passou"; echo passed >"$d/status"; cp "$rd/diff.patch" "$d/final.patch"; return 0 ;;
      escalate) progress "S$plan_step unidade $u · ronda $round · escalada"; echo escalated >"$d/status"; reason="$u: the reviewer escalated (see $rd/problems.md)"; return 1 ;;
      back)
        progress "S$plan_step unidade $u · ronda $round · devolvida"
        if [ "$reviews" -ge "$max_rounds" ]; then
          progress "S$plan_step unidade $u · ronda $round · escalada"
          echo escalated >"$d/status"
          reason="$u: round cap $max_rounds reached (see $rd/problems.md)"
          return 1
        fi
        prev=$rd/problems.md prevh=$rd/handoff.md ;;
    esac
  done
}

# Bring the units of a parallel group together in the checkout and review the combined result.
run_integration() { # <step> <unit-dir-name>...
  local k=$1; shift
  local idir=$run/S$k-integration name=S$k-integration u round=0 reviews=0 gate_fails=0 prev="" prevh="" rd code failed
  check_briefs "$@" || { reason="$name: $reason"; return 1; }
  [ -s "$run/00-input/goal.md" ] || { reason="$name: the goal $run/00-input/goal.md is missing or empty"; return 1; }
  for u in "$@"; do
    if gate_differs "$u"; then
      note "$name: the gate of $u was changed after it passed: it passed against another gate, and the integration runs the current one"
    elif brief_differs "$u"; then
      note "$name: the brief of $u differs from the one its implementer received"
    fi
  done
  mkdir -p "$idir"
  if [ -f "$idir/base" ]; then
    [ -d "$idir/rounds" ] && mv "$idir/rounds" "$idir/rounds.attempt-$(date +%s)"
  else
    snapshot_base "$idir" "$repo"
  fi
  mkdir -p "$idir/rounds"
  {
    printf '# Integration of a parallel group\n\nThe units below were implemented apart, each in its own copy of the repository, and their diffs were brought together in this checkout. Check the combined result against every brief and against each other: contradictions between units, a "Receives" that the other unit did not leave ready as stated, duplicated or clashing names, and each unit'"'"'s own criteria. Use the section "The integration review" of the review guide.\n'
    printf '\n## The goal of the plan\n\nThis is the goal of the whole plan, read from 00-input/goal.md when this integration started. Use it to judge how the units fit together and what is out of scope, and to read any note the coordinator left in it about how the run was carried out. It adds no criteria to the briefs.\n\n'
    sed 's/^```gate/``` gate/' "$run/00-input/goal.md"
    printf '\n'
    for u in "$@"; do printf '\n## Unit %s\n\n' "$u"; print_unit_brief "$u" '###'; printf '\n'; done
  } >"$idir/brief.md"

  while :; do
    round=$((round + 1))
    rd=$idir/rounds/$round
    mkdir -p "$rd"
    failed=""
    if [ "$round" -eq 1 ]; then
      progress "S$plan_step integração · ronda $round · aplicar diffs"
      note "$name: apply the diffs"
      for u in "$@"; do
        [ -e "$idir/.applied-$u" ] && continue
        if git -C "$repo" apply --check "$run/$u/final.patch" 2>"$rd/apply-$u.err" && git -C "$repo" apply "$run/$u/final.patch" 2>>"$rd/apply-$u.err"; then
          touch "$idir/.applied-$u"
        else
          failed="$failed- $u: $run/$u/final.patch"$'\n'
          note "$name: $u did not apply (see $rd/apply-$u.err)"
        fi
      done
    fi
    if [ -n "$failed" ] || [ "$round" -gt 1 ]; then
      progress "S$plan_step integração · ronda $round · integrar"
      echo "integrating round $round" >"$idir/status"
      note "$name round $round: integrate"
      integrate_prompt "$idir/brief.md" "$failed" "$prev" "$prevh" >"$rd/integrate-prompt.md"
      codex_run "$repo" "$rd/integrate-prompt.md" "$rd/integrate" workspace-write
      code=$?
      [ "$code" -eq 0 ] || { codex_failed "$rd/integrate" "$name" "$name: integrator exit=$code (see $rd/integrate.stderr.log)"; return 1; }
      [ -s "$rd/integrate.last-message.md" ] || { reason="$name: integrator left no handoff"; return 1; }
      cp "$rd/integrate.last-message.md" "$rd/handoff.md"
      for u in "$@"; do touch "$idir/.applied-$u"; done
    fi
    make_patch "$idir" "$rd/diff.patch" "$repo"
    [ -s "$rd/diff.patch" ] || { reason="$name: the combined diff is empty"; return 1; }

    if [ -n "$(gate_commands "$idir/brief.md")" ]; then
      echo "gate round $round" >"$idir/status"
      note "$name round $round: gate"
      if run_gate "$idir/brief.md" "$repo" "$rd"; then
        progress "S$plan_step integração · ronda $round · gate PASS"
        note "$name round $round: gate passed"
      else
        progress "S$plan_step integração · ronda $round · gate FAIL"
        gate_fails=$((gate_fails + 1))
        write_gate_problems "$rd"; echo back >"$rd/verdict"
        note "$name: round $round: gate failed (see $rd/gate.md)"
        if [ "$gate_fails" -ge "$max_gate_rounds" ]; then
          progress "S$plan_step integração · ronda $round · escalada"
          echo escalated >"$idir/status"
          reason="$name: the gate still fails after $gate_fails rounds (see $rd/gate.md)"
          return 1
        fi
        prev=$rd/problems.md prevh=$rd/handoff.md
        continue
      fi
    fi

    reviews=$((reviews + 1))
    progress "S$plan_step integração · ronda $round · revisão"
    echo "reviewing round $round" >"$idir/status"
    note "$name round $round: review"
    do_review "$name" "$repo" "$idir/brief.md" "$rd" "$prev" || return 1

    case "$verdict" in
      pass) progress "S$plan_step integração · ronda $round · passou"; echo passed >"$idir/status"; return 0 ;;
      escalate) progress "S$plan_step integração · ronda $round · escalada"; echo escalated >"$idir/status"; reason="$name: the reviewer escalated (see $rd/problems.md)"; return 1 ;;
      back)
        progress "S$plan_step integração · ronda $round · devolvida"
        if [ "$reviews" -ge "$max_rounds" ]; then
          progress "S$plan_step integração · ronda $round · escalada"
          echo escalated >"$idir/status"
          reason="$name: round cap $max_rounds reached (see $rd/problems.md)"
          return 1
        fi
        prev=$rd/problems.md prevh=$rd/handoff.md ;;
    esac
  done
}

free_kb() { df -k "$1" | awk 'NR==2 { print $4 }'; }

remove_worktrees() {
  local w
  for w in "$run"/worktrees/*; do
    [ -d "$w" ] && git -C "$repo" worktree remove --force "$w" >/dev/null 2>&1
  done
  rm -rf "$run/worktrees"
  git -C "$repo" worktree prune >/dev/null 2>&1
  return 0
}

# One step: a single unit in the checkout, or a parallel group in worktrees plus its integration.
run_step() { # <step> <unit-dir-name>...
  local k=$1; shift
  local u pids=() bad="" gb todo=0 first=1 before=0 after=0 used need joined
  if [ "$#" -eq 1 ]; then
    [ -e "$run/.done-$1" ] || run_unit "$1" "$repo" "$k" || return 1
    touch "$run/.done-$1"
    return 0
  fi
  printf -v joined '%s, ' "$@"
  progress "S$plan_step início · paralelo · ${joined%, }"
  if [ ! -e "$run/.group-ready-S$k" ]; then
    gb=$(snapshot_commit "$repo") || gb=$(git -C "$repo" rev-parse HEAD)
    mkdir -p "$run/worktrees"
    for u in "$@"; do [ -d "$run/worktrees/$u" ] || todo=$((todo + 1)); done
    for u in "$@"; do
      [ -d "$run/worktrees/$u" ] && continue
      [ "$first" -eq 1 ] && before=$(free_kb "$run")
      git -C "$repo" worktree add --detach "$run/worktrees/$u" "$gb" >"$run/$u.worktree.log" 2>&1 \
        || { reason="could not create the worktree for $u (see $run/$u.worktree.log)"; return 1; }
      if [ "$first" -eq 1 ]; then
        # The first worktree measures what each one takes; the rest are projected from it, with a margin of a quarter.
        first=0
        after=$(free_kb "$run"); used=$((before - after)); [ "$used" -gt 0 ] || used=0
        need=$(((todo - 1) * used * 5 / 4))
        if [ "$after" -lt "$need" ]; then
          remove_worktrees
          reason="not enough free disk for the parallel group of step $k: the first worktree took $((used / 1024)) MB, the other $((todo - 1)) need about $((need / 1024)) MB with a margin of a quarter, and $((after / 1024)) MB is free where the run lives ($run). Free some space, then resume. The estimate covers the worktrees only, not what the units create while they run (temporary database clusters, build output)."
          return 1
        fi
        note "S$k: disk: the first worktree took $((used / 1024)) MB; $((todo - 1)) more need about $((need / 1024)) MB, $((after / 1024)) MB free"
      fi
    done
    touch "$run/.group-ready-S$k"
  fi
  for u in "$@"; do
    [ -e "$run/.done-$u" ] && continue
    (
      mkdir -p "$run/$u"
      rm -f "$run/$u/reason"
      reason=""
      if run_unit "$u" "$run/worktrees/$u"; then touch "$run/.done-$u"; else echo "$reason" >"$run/$u/reason"; exit 1; fi
    ) &
    pids+=($!)
  done
  for u in "${pids[@]+"${pids[@]}"}"; do wait "$u" || true; done
  for u in "$@"; do
    [ -e "$run/.done-$u" ] || bad="$bad$(cat "$run/$u/reason" 2>/dev/null || echo "$u stopped"); "
  done
  [ -z "$bad" ] || { reason="$bad"; return 1; }
  [ -e "$run/.done-S$k-integration" ] || run_integration "$k" "$@" || return 1
  touch "$run/.done-S$k-integration"
  remove_worktrees
  return 0
}

# The last review: does the whole result meet the goal. A report, with no verdict loop.
run_report() {
  local code u
  check_briefs $(all_units) || return 1
  make_patch "$run/plan-base" "$run/cumulative.patch" "$repo"
  {
    printf '# Final review of the plan\n\n## The goal\n\n'
    cat "$run/00-input/goal.md"
    printf '\n\n## The unit briefs, in order\n'
    for u in $(all_units); do printf '\n### %s\n\n' "$u"; print_unit_brief "$u" '####'; printf '\n'; done
    printf '\n## Inputs (read-only)\n- The diff of the whole plan, new files included: %s\n- The reviews of each unit and of each parallel group: ' "$run/cumulative.patch"
    for u in $(all_units); do printf '%s/rounds/*/problems.md ' "$run/$u"; done
    printf '%s/S*-integration/rounds/*/problems.md' "$run"
    printf '\n- The repository is your current directory. Open it read-only. Do not change anything. Do not open the handoffs.\n'
    printf '\n## Role\nOpen and follow the role guide: %s/plan-review.md (read-only), section "The final review". You are not the author of the work.\n' "$guides"
    printf '\n---\nYour final message is the report, and nothing else.\n'
  } >"$run/report-prompt.md"
  review_run "$repo" "$run/report-prompt.md" "$run/report" read-only
  code=$?
  [ "$code" -eq 0 ] || { codex_failed "$run/report" "final review" "final review exit=$code (see $run/report.stderr.log)"; return 1; }
  [ -s "$run/report.last-message.md" ] || { reason="final review wrote no report"; return 1; }
  cp "$run/report.last-message.md" "$run/report.md"
}

all_units() { tr ' ' '\n' <"$run/00-input/order" | grep -v '^$'; }

pipeline() {
  local k=0 line
  printf 'Run folder: %s\n' "$run"
  while IFS= read -r line; do
    k=$((k + 1))
    [ -e "$run/.done-S$k" ] && continue
    plan_step=$k
    if [[ $line != *' '* ]]; then progress "S$plan_step início · unidade $line"; fi
    note "start step $k: $line ($model $effort)"
    reason=""
    # shellcheck disable=SC2086
    if run_step "$k" $line; then
      touch "$run/.done-S$k"; note "done step $k"
      progress "S$plan_step concluído"
      snapshot_tree "$repo" >"$run/state-after-S$k" 2>/dev/null || rm -f "$run/state-after-S$k"
      if pause_here "$k"; then
        touch "$run/.paused-S$k"
        note "PAUSED after step $k: read $run, then: plan-run.sh resume $(basename "$run")"
        progress "S$plan_step pausa"
        printf 'PAUSED after step %s (%s). Read it in %s, then: plan-run.sh resume %s\nSee %s/status.log\n' "$k" "$line" "$run" "$(basename "$run")" "$run"
        return 3
      fi
    else
      note "STOPPED at step $k: $reason"
      note "Read the rounds in $run, fix the cause (the briefs in $run/00-input/units/, or the checkout), then: plan-run.sh resume $(basename "$run")"
      progress "S$plan_step parou"
      printf 'STOPPED at step %s (%s): %s\nSee %s/status.log\n' "$k" "$line" "$reason" "$run"
      return 1
    fi
  done <"$run/00-input/order"
  if [ ! -e "$run/.done-report" ]; then
    note "start final review ($model $effort)"
    progress "final · revisão"
    reason=""
    if run_report; then
      touch "$run/.done-report"; note "done final review"
      progress "final · concluído"
    else
      note "STOPPED at the final review: $reason"
      progress "final · parou"
      printf 'STOPPED at the final review: %s\nSee %s/status.log\n' "$reason" "$run"
      return 1
    fi
  fi
  note "READY: report at $run/report.md"
  printf 'READY: %s/report.md\nSee %s/status.log\n' "$run" "$run"
}

# ---- Commands ----

cmd_start() {
  pause=""
  while getopts 'm:e:r:p:' o; do case $o in m) model=$OPTARG ;; e) effort=$OPTARG ;; r) review_effort=$OPTARG ;; p) pause=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 3 ] || die 'usage: start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>'
  valid_name "$1" || die "bad run name: $1"
  [ -z "$pause" ] || valid_pause "$pause" || die "bad checkpoints: $pause (use each, none, or step numbers like 2,4)"
  local name=$1 goal=$2 plan=$3 pdir line f i=0 w u order=""
  [ -s "$goal" ] || die "missing or empty goal: $goal"
  [ -s "$plan" ] || die "missing or empty plan: $plan"
  pdir=$(cd "$(dirname "$plan")" && pwd)
  command -v codex >/dev/null || die 'codex not found'
  repo=$(git rev-parse --show-toplevel 2>/dev/null) || die 'run start inside the repository the plan changes'
  [ -d "$guides" ] || die "no role guides at $guides (set PLAN_GUIDES)"
  run=$root/$name
  [ ! -e "$run" ] || die "run already exists: $run (finish it, or resume it)"

  # Validate the whole plan before creating anything
  local steps=()
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%%#*}
    # shellcheck disable=SC2086
    set -- $line
    [ "$#" -gt 0 ] || continue
    for w in "$@"; do
      f=$w; case $f in /*) ;; *) f=$pdir/$f ;; esac
      [ -s "$f" ] || die "missing or empty unit brief: $w"
      valid_name "$(basename "$f" .md)" || die "bad unit name (from the file name): $w"
    done
    steps+=("$*")
  done <"$plan"
  [ "${#steps[@]}" -gt 0 ] || die "plan.txt has no step"

  mkdir -p "$run/00-input/units"
  lock_run
  cp "$goal" "$run/00-input/goal.md"
  : >"$run/00-input/order"
  for line in "${steps[@]}"; do
    order=""
    for w in $line; do
      f=$w; case $f in /*) ;; *) f=$pdir/$f ;; esac
      i=$((i + 1))
      u=$(printf '%02d-%s' "$i" "$(basename "$f" .md)")
      cp "$f" "$run/00-input/units/$u.md"
      order="$order${order:+ }$u"
    done
    echo "$order" >>"$run/00-input/order"
  done
  echo "$repo" >"$run/repo"
  echo "$pause" >"$run/pause"
  mkdir -p "$run/plan-base"
  snapshot_base "$run/plan-base" "$repo"
  printf '%s %s %s\n' "$model" "$effort" "$review_effort" >"$run/settings"
  printf 'time\tevent\n' >"$run/status.log"
  note "start $name ($model $effort, review ${review_effort:-$effort}, max $max_rounds rounds, ${#steps[@]} step(s), $i unit(s), repo $repo)"
  for u in $(all_units); do
    [ -n "$(gate_commands "$run/00-input/units/$u.md")" ] || note "unit $u has no gate: only a reviewer checks it"
  done
  if ! git -C "$repo" cat-file -e HEAD:.plan-run.json 2>/dev/null; then
    if [ -f "$repo/.plan-run.json" ]; then
      note ".plan-run.json is not committed: commit it so changes to it are reviewed like code"
    else
      note "no .plan-run.json at HEAD: the bridge will run only gate commands unless an untracked copy is in the checkout; commit it so changes to it are reviewed like code"
    fi
  fi
  pipeline
}

cmd_resume() {
  local fm="" fe="" fr="" fp=""
  while getopts 'm:e:r:p:' o; do case $o in m) fm=$OPTARG ;; e) fe=$OPTARG ;; r) fr=$OPTARG ;; p) fp=$OPTARG ;; *) exit 1 ;; esac; done
  shift $((OPTIND - 1))
  [ "$#" -eq 1 ] || die 'usage: resume [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name>'
  load_run "$1"
  lock_run
  if [ -n "$fp" ]; then
    valid_pause "$fp" || die "bad checkpoints: $fp (use each, none, or step numbers like 2,4)"
    pause=$fp; echo "$pause" >"$run/pause"
  fi
  [ -z "$fm" ] || model=$fm
  [ -z "$fe" ] || effort=$fe
  [ -z "$fr" ] || review_effort=$fr
  [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$repo" ] || die "run resume inside the plan's repository: $repo"
  printf '%s %s %s\n' "$model" "$effort" "$review_effort" >"$run/settings"
  note "resume"
  pipeline
}

cmd_status() {
  [ "$#" -eq 1 ] || die 'usage: status <name>'
  load_run "$1"
  cat "$run/status.log"
}

# What code will run for each unit, for the coordinator to read before the run and when a unit changes. Exits 1 when a unit has no gate.
cmd_gates() { # <plan.txt | run-name>
  [ "$#" -eq 1 ] || die 'usage: gates <plan.txt|name>'
  local files=() f u w line pdir cmds missing=0
  if [ -f "$1" ]; then
    pdir=$(cd "$(dirname "$1")" && pwd)
    while IFS= read -r line || [ -n "$line" ]; do
      line=${line%%#*}
      for w in $line; do
        f=$w; case $f in /*) ;; *) f=$pdir/$f ;; esac
        [ -s "$f" ] || die "missing or empty unit brief: $w"
        files+=("$f")
      done
    done <"$1"
  else
    load_run "$1"
    for u in $(all_units); do files+=("$run/00-input/units/$u.md"); done
  fi
  [ "${#files[@]}" -gt 0 ] || die 'no unit'
  for f in "${files[@]}"; do
    printf '%s\n' "$(basename "$f" .md)"
    cmds=$(gate_commands "$f")
    if [ -n "$cmds" ]; then
      printf '%s\n' "$cmds" | sed 's/^/  $ /'
    else
      printf '  NO GATE: only a reviewer checks this unit\n'; missing=1
    fi
    printf '\n'
  done
  return "$missing"
}

# The run's history as a readable summary: per unit and per group integration, the rounds and how it ended.
write_summary() {
  local d r n last k=0 line
  {
    printf '# Plan summary\n\nRun: %s\n\n| Step | Unit | Rounds | Last verdict |\n|---|---|---|---|\n' "$(basename "$run")"
    while IFS= read -r line; do
      k=$((k + 1))
      for d in $line; do
        n=$(ls "$run/$d/rounds" 2>/dev/null | wc -l | tr -d ' ')
        last=$(ls "$run/$d/rounds" 2>/dev/null | sort -n | tail -1)
        r=$(cat "$run/$d/rounds/$last/verdict" 2>/dev/null || echo "-")
        printf '| %s | %s | %s | %s |\n' "$k" "$d" "$n" "$r"
      done
      if [ -d "$run/S$k-integration" ]; then
        n=$(ls "$run/S$k-integration/rounds" 2>/dev/null | wc -l | tr -d ' ')
        last=$(ls "$run/S$k-integration/rounds" 2>/dev/null | sort -n | tail -1)
        r=$(cat "$run/S$k-integration/rounds/$last/verdict" 2>/dev/null || echo "-")
        printf '| %s | integration | %s | %s |\n' "$k" "$n" "$r"
      fi
    done <"$run/00-input/order"
    if [ -s "$run/metrics.tsv" ]; then
      printf '\n## Implementation rounds\n\n| Unit | Round | Minutes | Steps | Files | Input tokens (k) |\n|---|---|---|---|---|---|\n'
      awk -F'\t' '{ printf "| %s | %s | %s | %s | %s | %d |\n", $1, $2, $3, $4, $5, $6 / 1000 }' "$run/metrics.tsv"
    fi
    printf '\nThe final review is in report.md.\n'
  } >"$run/status.md"
}

cmd_finish() {
  local discard=0
  [ "${1:-}" = --discard ] && { discard=1; shift; }
  [ "$#" -eq 1 ] || die 'usage: finish [--discard] <name>'
  load_run "$1"
  run_active && die "run $1 is being worked on by pid $(cat "$run/.lock"): finish it when it stops"
  remove_worktrees
  if [ "$discard" -eq 1 ]; then
    rm -rf "$run"
    printf 'Removed %s\n' "$run"
    return 0
  fi
  [ -s "$run/report.md" ] || die 'there is no final review in this run: nothing to keep'
  [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$repo" ] || die "run finish inside the plan's repository: $repo"
  local dest=$repo/records/plans/$1
  [ ! -e "$dest" ] || die "already exists: $dest"
  mkdir -p "$dest"
  write_summary
  # Keep the record (inputs, briefs, prompts, handoffs, reviews, verdicts, diffs, report); leave out the
  # script's own state and the raw Codex output.
  local skip=(--exclude '*.events.jsonl' --exclude '*.stderr.log' --exclude '*.last-message.md' \
    --exclude '.*' --exclude '*.attempt-*' --exclude 'untracked-*.txt' --exclude base --exclude plan-base \
    --exclude '*.worktree.log' --exclude repo --exclude pause --exclude settings --exclude status --exclude status.log)
  local dskip=(-x '*.events.jsonl' -x '*.stderr.log' -x '*.last-message.md' \
    -x '.*' -x '*.attempt-*' -x 'untracked-*.txt' -x base -x plan-base \
    -x '*.worktree.log' -x repo -x pause -x settings -x status -x status.log)
  rsync -a "${skip[@]}" "$run/" "$dest/" || die "copy to $dest failed; nothing deleted"
  diff -rq "${dskip[@]}" "$run" "$dest" >/dev/null || die "copy to $dest does not match; nothing deleted"
  rm -rf "$run"
  printf 'Kept in %s; removed %s\n' "$dest" "$run"
  records_note "$repo"
}

# Move the base of a group's integration, for when the checkout was edited after the integration started and those
# edits sit in its diff. Without --paths: the base becomes the checkout minus the diffs of the units already applied, which
# is only right while the integrator never ran (its own edits would be hidden too). With --paths: the base stays and the
# given paths take the checkout's current version as their base; the files that stop showing up are listed and logged.
# An emergency exit: the rule is not to edit the checkout during a step.
step_units() { sed -n "${1}p" "$run/00-input/order"; }

integrator_ran() { # <integration-dir>: in this attempt or an earlier one
  local f
  for f in "$1"/rounds*/*/integrate.last-message.md; do [ -e "$f" ] && return 0; done
  return 1
}

cmd_rebase_integration() { # <name> <step> [--paths <path>...]
  local usage='usage: rebase-integration <name> <step> [--paths <path>...]'
  [ "$#" -ge 2 ] || die "$usage"
  local name=$1 k=$2 mode=1 u p f idir old cur new tmp err hidden units head i
  local -a paths=() applied=()
  shift 2
  if [ "$#" -gt 0 ]; then
    [ "$1" = --paths ] && [ "$#" -ge 2 ] || die "$usage"
    shift; paths=("$@"); mode=2
  fi
  [[ $k =~ ^[0-9]+$ ]] || die "bad step: $k"
  load_run "$name"
  run_active && die "run $name is being worked on by pid $(cat "$run/.lock"): stop it first"
  [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$repo" ] || die "run rebase-integration inside the plan's repository: $repo"
  units=$(step_units "$k")
  # shellcheck disable=SC2086
  set -- $units
  [ "$#" -gt 1 ] || die "step $k is not a parallel group: it has no integration"
  idir=$run/S$k-integration
  [ -f "$idir/base" ] || die "the integration of step $k has not started: there is no base to move"
  [ ! -e "$run/.done-S$k-integration" ] || die "the integration of step $k is already closed"
  [ "$(cat "$idir/base-format" 2>/dev/null)" = tree ] || die "the integration of step $k keeps an old-format base: finish it as it is"
  old=$(cat "$idir/base")
  cur=$(snapshot_tree "$repo") || die "cannot snapshot the checkout $repo"
  tmp=$(mktemp -u "${TMPDIR:-/tmp}/plan-run-rebase.XXXXXX")
  head=$(git -C "$repo" rev-parse --short HEAD 2>/dev/null)

  if [ "$mode" -eq 1 ]; then
    integrator_ran "$idir" && die "the integrator already changed the checkout in step $k, so its edits would become part of the base and hide from the reviewer. Name what to leave out of the diff: rebase-integration $name $k --paths <path>..."
    for u in "$@"; do [ -e "$idir/.applied-$u" ] && applied+=("$u"); done
    [ "${#applied[@]}" -gt 0 ] || die "no unit of step $k was applied to the checkout: nothing to subtract"
    GIT_INDEX_FILE=$tmp git -C "$repo" read-tree "$cur" || { rm -f "$tmp"; die "cannot read the checkout tree"; }
    for ((i = ${#applied[@]} - 1; i >= 0; i--)); do
      u=${applied[$i]}
      if ! err=$(GIT_INDEX_FILE=$tmp git -C "$repo" apply -R --cached "$run/$u/final.patch" 2>&1); then
        rm -f "$tmp"
        die "the diff of $u cannot be taken back out of the checkout, so the checkout changed files it touches. Nothing was changed. Git says: $err"
      fi
    done
    new=$(GIT_INDEX_FILE=$tmp git -C "$repo" write-tree) || { rm -f "$tmp"; die "cannot write the new base"; }
    rm -f "$tmp"
    cp "$idir/base" "$idir/.base.before-rebase-$(date +%s)"
    echo "$new" >"$idir/base"; echo tree >"$idir/base-format"
    note "S$k-integration: base moved to the checkout minus the diffs of ${applied[*]} (HEAD $head)"
    printf 'The base of S%s-integration is now the checkout minus the diffs of %s.\n' "$k" "${applied[*]}"
    return 0
  fi

  local -a np=()
  local bad="" q
  for p in "${paths[@]}"; do
    q=${p#./}; q=${q%/}
    case "/$q/" in //*|*/../*|*/./*) die "bad path (it must be relative to the repository, with no . or ..): $p" ;; esac
    np+=("$q")
  done
  paths=("${np[@]}")
  for u in "$@"; do
    [ -f "$run/$u/final.patch" ] || continue
    while IFS= read -r f; do
      for p in "${paths[@]}"; do
        if [ "$f" = "$p" ] || [ "${f#"$p"/}" != "$f" ]; then bad="$bad  $u: $f"$'\n'; fi
      done
    done < <(grep '^diff --git a/' "$run/$u/final.patch" | sed -E 's#^diff --git a/(.*) b/(.*)$#\1\n\2#' | sort -u)
  done
  [ -z "$bad" ] || die "these paths hold files that a unit's diff changed, so leaving them out would hide that unit's work. Nothing was changed:"$'\n'"$bad"
  GIT_INDEX_FILE=$tmp git -C "$repo" read-tree "$old" || { rm -f "$tmp"; die "cannot read the base tree"; }
  for p in "${paths[@]}"; do
    GIT_INDEX_FILE=$tmp git --literal-pathspecs -C "$repo" rm --cached -r -q --ignore-unmatch -- "$p" >/dev/null 2>&1
    git --literal-pathspecs -C "$repo" ls-tree -r -z "$cur" -- "$p" | perl -0pe 's/^(\d+) \w+ (\w+)\t/$1 $2\t/' \
      | GIT_INDEX_FILE=$tmp git -C "$repo" update-index -z --index-info || { rm -f "$tmp"; die "cannot update the base under $p"; }
  done
  new=$(GIT_INDEX_FILE=$tmp git -C "$repo" write-tree) || { rm -f "$tmp"; die "cannot write the new base"; }
  rm -f "$tmp"
  hidden=$(git -C "$repo" diff --name-only "$old" "$new")
  [ -n "$hidden" ] || die "nothing under ${paths[*]} differs from the base: nothing to do"
  cp "$idir/base" "$idir/.base.before-rebase-$(date +%s)"
  echo "$new" >"$idir/base"; echo tree >"$idir/base-format"
  note "S$k-integration: base moved under ${paths[*]}; $(printf '%s\n' "$hidden" | wc -l | tr -d ' ') file(s) no longer in the diff: $(printf '%s' "$hidden" | tr '\n' ' ') (HEAD $head)"
  printf 'The diff of S%s-integration no longer shows these files (they stay in the checkout):\n%s\n' "$k" "$hidden"
  printf 'If one of them is an edit of the integrator, the reviewer will not see it either.\n'
}

# Close a group's integration by hand, when the owner has judged the combined result himself. It applies nothing and
# reviews nothing: it only records that the integration is closed, on top of units that passed and whose diffs are in
# the checkout. The reason and the commit it was closed at go to status.log.
cmd_accept_integration() { # <name> <step> --why <text>
  local usage='usage: accept-integration <name> <step> --why <text>'
  [ "$#" -eq 4 ] && [ "$3" = --why ] || die "$usage"
  local name=$1 k=$2 why=$4 u idir units head
  [ -n "${why//[[:space:]]/}" ] || die "$usage (the reason cannot be empty)"
  [[ $k =~ ^[0-9]+$ ]] || die "bad step: $k"
  load_run "$name"
  run_active && die "run $name is being worked on by pid $(cat "$run/.lock"): stop it first"
  units=$(step_units "$k")
  # shellcheck disable=SC2086
  set -- $units
  [ "$#" -gt 1 ] || die "step $k is not a parallel group: it has no integration"
  idir=$run/S$k-integration
  [ ! -e "$run/.done-S$k-integration" ] || die "the integration of step $k is already closed"
  for u in "$@"; do
    [ -e "$run/.done-$u" ] && [ "$(cat "$run/$u/status" 2>/dev/null)" = passed ] || die "unit $u has not passed: the integration cannot be closed over it"
    [ -e "$idir/.applied-$u" ] || die "the diff of unit $u was never applied to the checkout: the integration cannot be closed over it"
  done
  head=$(git -C "$repo" rev-parse --short HEAD 2>/dev/null)
  echo passed >"$idir/status"
  touch "$run/.done-S$k-integration"
  remove_worktrees
  note "S$k-integration: closed by hand by $(id -un) at HEAD $head, without a review of the combined result. Reason: $why"
  printf 'S%s-integration is closed. Continue with: plan-run.sh resume %s\n' "$k" "$name"
}

sub=${1:-}
[ "$#" -gt 0 ] && shift
case "$sub" in
  start) cmd_start "$@" ;;
  resume) cmd_resume "$@" ;;
  status) cmd_status "$@" ;;
  gates) cmd_gates "$@" ;;
  finish) cmd_finish "$@" ;;
  rebase-integration) cmd_rebase_integration "$@" ;;
  accept-integration) cmd_accept_integration "$@" ;;
  *) die 'usage: plan-run.sh start|resume|status|gates|finish|rebase-integration|accept-integration ...' ;;
esac

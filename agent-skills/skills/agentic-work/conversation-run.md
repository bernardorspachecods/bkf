# Run driven from the conversation

`--dir` is a scratch folder for each unit's evidence, not a record.

## One unit

1. **Begin:** `scripts/plan-unit.sh begin <brief> --dir <scratch>` before touching the code. Each unit's base is the state the previous one left.
2. **Implement** as the user chose: you, under the [implementation guide](roles/agentic-work-implementation.md); a Claude subagent, whose prompt is the brief followed by that guide; or an agent you launch (see below). Do not commit, stage, stash or reset.
3. **Check:** `scripts/plan-unit.sh check <brief> --dir <scratch> --review-model <model> [--review-backend codex|claude] [-r <effort>]`. Later checks resume the same reviewer.
4. **Act on the exit code.** `0` pass: next unit. `1` back: read `problems:` in the output, fix it (or send it back to the implementer) and `check` again. `2` escalate, or the reviewer says the brief is wrong: stop and tell the user; if the brief changes, `begin --restart`. `3` the check itself failed (no base, missing model, no reviewer output): fix the cause and repeat.

## When you or the user review

Run `check --gate-only`: it runs the gate and writes the diff (`patch:`), with no reviewer.

## Launching an implementer

[scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]`, one Bash call with `run_in_background: true` per agent (parallel launches are separate calls in one response). It appends the implementation guide; do not add it yourself.

- Default: Codex `gpt-6-luna`, `high`; never `gpt-6.1-sol` unless the user says. `HARNESS_BACKEND=claude` runs `claude -p` (`sonnet`, `high`).
- **Where it works.** In a run, launch with `DELEGATE_IN_PLACE=1` after `begin`, so `check` reads the agent's diff from the checkout. Without it the agent works in its own worktree `<repo>-delegate/<name>` on branch `delegate/<name>`, which first runs the committed `.plan-run.json` setup; then run `begin` and `check` inside that worktree. `DELEGATE_RERUN=1` reuses a run folder that has a `status`.
- The agent gets only the brief and its guide: forbid git commands that change state in the brief. Do not commit or merge unless the user says so.

The run folder is `~/.delegate-runs/<repo>/<name>/` (or `$DELEGATE_RUNS_DIR`): `status` (`exit=0` finished, `prepare-failed` setup stopped), `last-message.md`, `diffstat.txt`, `worktree`, `base`, logs `prepare.log` and `porteiro.log`. A silent agent is still working.

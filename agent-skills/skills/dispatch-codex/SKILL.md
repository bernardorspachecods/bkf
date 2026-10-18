---
name: dispatch-codex
description: Run work as Codex CLI tasks in the current checkout or separate git worktrees, using a script that records run results. Use when Codex should execute a brief instead of pasting prompts into a Codex window.
---

## Use

- Prepare briefs by [brief-another-agent](../../library/modules/brief-another-agent.md) and review runs by [review-work](../../library/modules/review-work.md).
- Inside a plan, follow [Execution with Codex](../../library/workflow-types/plan.md#execution-with-codex); outside a plan, show the briefs and their order to the user before launching.

## Launch

Run [scripts/run-codex.sh](scripts/run-codex.sh) once per brief: `[CODEX_IN_PLACE=1] scripts/run-codex.sh <name> <brief-file> [base-ref] [model] [effort]`.

- Write the brief to the scratchpad. `base-ref` applies in worktree mode and defaults to `HEAD`; for a sequential step, use the prior task's branch.
- Default to the user's checkout with `CODEX_IN_PLACE=1`, one task at a time. Use worktree mode only for parallel tasks, which follow [run-parallel-work](../../library/modules/run-parallel-work.md); each gets branch `codex/<name>`. Never run two tasks in one checkout.
- In place, the script snapshots tracked files in `base`; review with `git diff $(cat <run-folder>/base)` and compare `status-before.txt` with `status-after.txt` for new files. The brief must forbid git commands that change state.
- Worktree mode uses a sibling folder `<repo>-codex/<name>`.
- Defaults: model `gpt-6-luna`, effort `high`; override only when the plan names another setting.
- `gpt-6-luna` is weak on long work, and research across many sources tends to come back shallow. When it runs a brief, split the work into more and smaller briefs than you would for a stronger model; judge how far to split from the task.
- If the run folder already has a `status` file, the script stops. Set `CODEX_RERUN=1` to deliberately rerun it with the existing behavior.
- Start each run with Bash `run_in_background: true`. The script prints the run folder when done.

## Read a run

Run folders are `~/.codex-runs/<repo>/<name>/`, or under `$CODEX_RUNS_DIR` when set. Read `status` (`exit=0` means finished; otherwise read `stderr.log`), `last-message.md` (Codex's report), `diffstat.txt`, `worktree` (checkout path), and `base` (diff base). Read the actual diff; do not read `events.jsonl` unless the diff and report disagree.

## Correct a run

Send a correction with `codex exec resume` in the same checkout, or write a new brief. Do not edit Codex's work unless the user asks.

## Safety and gotchas

- Do not commit or merge unless the user says so.
- Remove stale worktrees with `git worktree remove` before reusing them.
- Runs use the `workspace-write` sandbox.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

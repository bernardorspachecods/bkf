---
name: dispatch-codex
description: Run planned work as Codex CLI tasks in separate git worktrees and review the resulting diffs. Use when the user approves a plan whose steps Codex should execute, instead of pasting prompts into a Codex window; do not use for work Claude should do itself.
---

## Core rules

- Claude plans and reviews; Codex executes. Do not watch a run while it works.
- Default to model `gpt-6-luna` at `high` effort. Use another model or effort only when the plan names one.
- Default to running in the user's checkout (`CODEX_IN_PLACE=1`), one task at a time. Use a separate worktree and branch (`codex/<name>`) only for tasks that run in parallel, one per task. Never run two tasks in one checkout at once.
- Do not commit or merge unless the user says so.

## Write the briefs

Each brief is the prompt the user would otherwise paste into Codex. It must be
self-contained: goal, files in scope, constraints, how to verify, and what to
report. Codex sees only the brief and the repository. Show the briefs and the
parallel/sequential order to the user for approval before launching.

## Launch

Run [scripts/run-codex.sh](scripts/run-codex.sh) once per brief:

`[CODEX_IN_PLACE=1] scripts/run-codex.sh <name> <brief-file> [base-ref] [model] [effort]`

- `CODEX_IN_PLACE=1`: edit the user's checkout. The script snapshots the tree first (`base` in the run folder). Review with `git diff $(cat <run-folder>/base)`, and compare `status-before.txt` with `status-after.txt` for new files. The brief must forbid git commands that change state. Without it, the script creates a worktree.
- `name`: short hyphen-case task name; it names the run folder and, in worktree mode, the branch `codex/<name>`.
- `brief-file`: path to the brief; write it to the scratchpad directory.
- `base-ref`: worktree mode only; commit to branch from, defaults to `HEAD`. For a sequential step that builds on an earlier one, pass that task's branch.
- `model`, `effort`: override the defaults only as stated above.

Start each run with Bash `run_in_background: true`, so you are notified when it
exits. Launch parallel tasks together and sequential tasks one at a time, after
the earlier one has been reviewed. The script prints the run folder when done.

## Review

When a run exits, read from its run folder (`~/.codex-runs/<repo>/<name>/`, or `$CODEX_RUNS_DIR`):

- `status`: `exit=0` means Codex finished; anything else, read `stderr.log`.
- `last-message.md`: Codex's own report.
- `diffstat.txt` and the worktree path in `worktree`: then read the actual diff.

Check the diff against the plan and the brief, and run the verification the
brief named. Do not read `events.jsonl` unless the diff and report disagree.

Then report to the user: what changed, whether it matches the plan, and what is
wrong. To fix a defect, send a correction with `codex exec resume` in the same
worktree, or write a new brief; do not edit Codex's work yourself unless the
user asks.

## Gotchas

- In worktree mode the worktree is a sibling folder `<repo>-codex/<name>`. If the branch or folder already exists, the script reuses the folder; remove stale worktrees with `git worktree remove` first.
- Runs use the `workspace-write` sandbox with no extra writable directories.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

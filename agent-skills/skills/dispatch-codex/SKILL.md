---
name: dispatch-codex
description: Run work as Codex CLI tasks in the current checkout or separate git worktrees, using a script that records run results. Use when Codex should execute a brief instead of pasting prompts into a Codex window.
---

## Use

- Prepare briefs by [brief-another-agent](../../library/modules/brief-another-agent.md) and review runs by [review-work](../../library/modules/review-work.md).
- For a whole plan, use [Plan runs](#plan-runs).
- Show the brief to the user before launching only when they ask to see it or the task was not previously defined. If the task was already defined, launch without showing the brief unless requested.

## Launch

Run [scripts/run-codex.sh](scripts/run-codex.sh) once per brief: `[CODEX_IN_PLACE=1] scripts/run-codex.sh <name> <brief-file> [base-ref] [model] [effort]`.

- Write the brief to the scratchpad. `base-ref` applies in worktree mode and defaults to `HEAD`; for a sequential step, use the prior task's branch.
- Default to the user's checkout with `CODEX_IN_PLACE=1`, one task at a time. Use worktree mode only for parallel tasks, each on branch `codex/<name>`; a plan's parallel group is handled by [Plan runs](#plan-runs). Never run two tasks in one checkout.
- In place, the script snapshots tracked files in `base`; review with `git diff $(cat <run-folder>/base)` and compare `status-before.txt` with `status-after.txt` for new files. The brief must forbid git commands that change state.
- Worktree mode uses a sibling folder `<repo>-codex/<name>`.
- Defaults: model `gpt-6-luna`, effort `xhigh`; never `gpt-6.1-sol`; override only when the plan names another setting.
- `gpt-6-luna` is weak on long work, and research across many sources tends to come back shallow. When it runs a brief, split the work into more and smaller briefs than you would for a stronger model; judge how far to split from the task.
- If the run folder already has a `status` file, the script stops. Set `CODEX_RERUN=1` to deliberately rerun it with the existing behavior.
- Start each run with Bash `run_in_background: true`. The script prints the run folder when done.

## Phase runs

For a phase where agents work in parallel and each is reviewed by another agent (research collection, digest, and similar), use [scripts/phase-codex.sh](scripts/phase-codex.sh), not `run-codex.sh`: no git, no branches, no diff. One agent is a phase with one pair.

- `phase-codex.sh start [-m model] [-e effort] [-f file] <run> <name> <agent-brief> <review-brief> [<name> <agent-brief> <review-brief>]...` creates one plain folder per agent under `~/.phase-runs/<run>/` (or `$PHASE_RUNS_DIR`), runs every agent in parallel, then its reviewer, and repeats by verdict until `pass`, `escalate` or a failure. Each agent writes one file, `output.md` unless `-f` names another. Run it with `run_in_background: true`; it prints each agent's final status. Defaults: `gpt-6-luna`, `xhigh`.
- The coordinator writes both briefs first. The script only appends the output file name, the reviewer's input and the verdict line format; everything about the phase belongs in the briefs.
- The reviewer ends `problems.md` with exactly one of `VERDICT: pass`, `VERDICT: back`, `VERDICT: escalate`; any other last line counts as a failed review. The review brief must say so or point to a guide that does, such as [the collection review](../../library/workflow-types/research/research-review-collection.md#output). `back` hands the list to the agent with its brief; `escalate` stops that agent and returns it to you; there is no round limit.
- Read the result in `<run>/log.tsv` and `<run>/<name>/rounds/<n>/problems.md` and `verdict`. A failed agent is logged in `status` and `log.tsv` and does not stop the others.
- `phase-codex.sh join <run>` concatenates the reviewed files under a heading per agent name, without reading them, and prints the path; it refuses while any agent is not `passed`. `phase-codex.sh clean <run>` deletes the run folder.
- Codex needs `--skip-git-repo-check` outside a repo, which the script passes. The sandbox confines writes to the agent's folder only outside `/tmp`, so run folders must not be under `/tmp`. Network works in the sandbox.

## Research runs

For a whole [research](../../library/workflow-types/research/research.md), use [scripts/research-run.sh](scripts/research-run.sh), which builds the briefs from fixed templates and chains the phases that need no one on top of `phase-codex.sh`.

- You write `objective.md`, `sourcemap.md` (one numbered niche per line) and `collectors.txt` (`name: 1,2,5` per line, the niches each collector covers), then run `research-run.sh start [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>` with `run_in_background: true`. It completes the source map with a cheap agent (its niches are shared out round-robin), collects with one agent per collector, joins, digests, and reviews each step. State is in `~/.research-runs/<name>/`, one numbered folder per phase.
- It stops at an `escalate` or a failure and writes `status.log` with where and why. After you fix the cause, `resume <name>` skips the finished phases and reruns the stopped one from scratch, keeping the old attempt as `<phase>.attempt-<time>`. `status <name>` prints `status.log`.
- A review is capped at `RESEARCH_MAX_ROUNDS` rounds (default 3) and must give at least `RESEARCH_MIN_CHECKED` lines (default 3) under `## What I checked`, or it is repeated and then fails. `RESEARCH_GUIDES` names the folder with the role guides.
- When it prints `READY`, write the delivery, then `deliver <name> <delivery.md>` runs the review of the delivery (exit 0 `pass`, 1 `back`, 2 `escalate`); correct the delivery and run it again for the next round.
- `finish <name>` writes `status.md`, a readable summary of the phases (model and effort, rounds, what went wrong), from the run's `status.log`, copies the run into `records/research/<name>/` of the repository you run it in (it keeps the record: inputs, outputs, briefs, prompts, problems, verdicts and logs; it leaves out the script's own state files, the Codex events, stderr and last-message files, and the reviewer snapshots), checks that the copy matches, then deletes the run. `finish --delivery-only <name>` keeps only `delivery.md`. Folders of failed or redone attempts (`<phase>.attempt-<time>`) are left out unless you pass `--keep-attempts`.

## Plan runs

For a whole [plan](../../library/workflow-types/plan/plan.md), use [scripts/plan-run.sh](scripts/plan-run.sh). Run it inside the repository the plan changes.

- You write `goal.md`, one brief per unit, and `plan.txt`: one step per line, holding the unit briefs' paths (relative to `plan.txt`). A line with one brief is a unit run in the user's checkout; several on a line are a parallel group, each in its own git worktree, whose diffs an integration agent then applies to the checkout and a reviewer checks together. Run `plan-run.sh start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>` with `run_in_background: true`. `-e` sets the implementers' reasoning effort and `-r` the reviewers' (and the final review's); without `-r` both use `-e`. `resume` takes the same options and keeps what the run already stored.
- `start` creates `~/.plan-runs/<name>/` and begins the run at once; it fails if that folder exists. Do not create the folder by hand. Keep a plan that is ready but not to be launched yet as `goal.md`, `plan.txt` and the briefs in a folder outside `~/.plan-runs` (for example `~/.plan-runs-pending/<name>/`), and run `start` from it. The script prefixes each unit name with its step number, so name the brief files without one.
- Step numbers are the lines of `plan.txt`, and the finished and paused markers (`.done-S<n>`, `.paused-S<n>`) use them. A unit may be added in `00-input/order` and `00-input/units/` only after every step already finished or in progress, so that no marker changes meaning.
- A unit's diff is taken against the checkout as the previous step left it (`state-after-S<n>` in the run folder), as a snapshot of the working files, untracked ones included and ignored ones left out. So a commit, a dependency install or another unit's changes made while a unit is stopped never land in its diff, and edits to files git did not track yet are visible to the reviewer. A run begun with an older script keeps its old bases until a step passes under the new one.
- A unit brief may hold a **gate**: a fenced block tagged `gate`, one command per line. After each implementation round the script runs these commands itself, in the checkout and outside any agent, and calls the reviewer only when all pass. A failing command sends the work back to the implementer with its output and no review, so a reviewer can never pass a red gate; a unit passes when the gate is green and the reviewer passes. `PLAN_GATE_TIMEOUT` (default 900 seconds) limits each command and `PLAN_MAX_GATE_ROUNDS` (default 5) stops a unit whose gate keeps failing. A brief with no gate is reviewed as before, and `start` notes which units have none. `plan-run.sh gates <plan.txt|name>` prints the commands of every unit (exit 1 if one has none), so the coordinator reads what code will run before `start` and whenever a unit changes. - **The bridge.** An implementer's Codex sandbox has no network, so it cannot reach a database (every `pnpm db:test:*` it ran failed on DNS). While an implementer works, the script serves `.plan-porteiro/ponte <command...>` in its checkout: the agent writes a request, the script runs it outside the sandbox and returns the output and the exit code. Only two kinds of request run: `pnpm db:test:<anything>` (each tied to `--ambiente test`, and refused if that script's definition differs from the unit's base) and the unit's gate commands exactly as written. Requests run without a shell, so an agent supplies arguments and never shell syntax; everything else is refused, and every request is logged in `<run>/porteiro.log`. The folder is kept out of diffs and removed afterwards. Reviewers run read-only and have no bridge: they receive the gate result. The commands it runs include code the agent wrote, with the user's privileges, which is also true of the gate; restricting file reads (for `.env.production`) is a further step not taken here. `PLAN_PORTEIRO_TIMEOUT` (default 900 seconds) limits each request.
`scripts/test-plan-run-gate.sh` tests the gate and the bridge with a fake `codex`, including that breaking each guard makes a test fail.
- Each unit is implemented, then reviewed by another agent (verdict `pass`, `back` or `escalate`, capped at `PLAN_MAX_ROUNDS` reviews, default 3). The run stops at an escalation or a failure and writes `status.log`; after you fix the cause, `resume <name>` continues, and a brief can be corrected in `00-input/units/` first. State is in `~/.plan-runs/<name>/`.
- `-p each` or `-p 2,4` pauses after those steps (exit 3, `PAUSED` in `status.log`) for the user to read; `resume -p none` clears it.
- When it prints `READY`, the final review is in `report.md`. `finish <name>` copies the record to `records/plans/<name>/` in the repository; `finish --discard <name>` deletes the run.

## Council runs

For a [council](../../library/workflow-types/council/council.md), use [scripts/council-run.sh](scripts/council-run.sh). `start [-m model] [-e effort] <name> <brief.md>` runs five advisors apart, anonymizes their responses into a packet with the key kept in `02-packet/key.md`, runs five reviewers apart and stops at `READY`. You then write the report and run `check <name> <report.md>` (exit 0 `pass`, 1 `back`, 2 `escalate`). `resume`, `status` and `finish` work as in plan runs; state is in `~/.council-runs/<name>/` and `finish` keeps the record in `records/councils/<name>/`.

## Review runs

For a [code review](../../library/workflow-types/code-review/code-review.md), use [scripts/review-run.sh](scripts/review-run.sh): `start [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... <name> <target>`, where the target is `working-tree` or a revision range such as `main...feature`. A Standards and a Spec agent review the pinned diff apart, a checker per axis confirms each finding, and the script writes `report.md`; `-2` adds a second reviewer per axis. State is in `~/.review-runs/<name>/`, and `finish` keeps the record in `records/reviews/<name>/`.

## Shared code

[scripts/lib-codex.sh](scripts/lib-codex.sh) holds what `phase-codex.sh` and the four run scripts share: running a Codex agent, running a set of agents in parallel, reading a verdict and checking the "What I checked" section. Source it; it defines functions only.

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

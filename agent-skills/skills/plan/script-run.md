# Plan driven by a script

Read this only when the user chose a script to drive the plan. Goal, units and briefs are written as in [SKILL.md](SKILL.md) sections 1 and 2, and the report is as in its section 3. A script builds the agent briefs from fixed templates, runs each unit and stops when a review escalates; you write only the goal, the unit briefs and their order. The script is [plan-run.sh](scripts/plan-run.sh); read [run-reference.md](run-reference.md) before the first `start`, and [run-recovery.md](run-recovery.md) only when a step has several briefs on one line or a run is stopped.

## Order and parallelism

Units run one at a time in the run's own worktree by default. Two units may run together only if they share nothing: each runs in its own copy of the repository and their diffs are brought together afterwards, which costs an integration agent and a review of the combined result. Run in series when unsure, and when the group is only two small units. Parallel pays when units are big and truly independent.

Write the order in a plan file, one step per line; units on the same line run together:

```
database.md
ui.md  ux.md      # run together
tests.md
```

## Gates and rehearsal

Before `start`, and whenever you add or change a unit, run the script's `gates` command and read the list, then rehearse before every `start` and fix unexpected failures; see [run-reference.md](run-reference.md#rehearsal). Gate commands run through `bash -c`, so shell syntax works. A check too slow for every gate (the full database suite) goes in `regression.gate` next to `plan.txt`: the script runs it at the `-p` checkpoints and before the final review. Script behavior, including lint refusals: [run-reference.md](run-reference.md#gate).

## Checkpoints and pilots

A run can pause after chosen steps (`-p`). Suggest where to pause and, when you agree the split, ask who the pauses are for: only for you to check the step (rerun what the reviewer's sandbox could not, read the diff, resume without reporting unless a fundamental decision changes), or also for the user. Write the answer in the plan and follow it. Step numbers count the lines of `plan.txt`; when you add or move a unit, recompute them before you resume.

**Pilot by kind of unit.** Pause after the first unit of each kind (moving files, changing a rule, a migration, an interface), read it, and only then release the rest of that kind.

## Delegating

Each agent gets a short brief that points to the guide for its role and never explains the method.

| Role | Does | Receives |
| --- | --- | --- |
| [Implementation](roles/plan-implementation.md) | Does the unit inside its brief, verifies, writes the handoff | The unit brief |
| [Review](roles/plan-review.md) | Checks the diff against the brief; can send the work back | The unit brief and the diff |
| [Integration](roles/plan-integration.md) | Only for a parallel group: applies the diffs, resolves conflicts, fixes what the combined review found | The briefs of the group |

```
Unit brief ─► Implement ─► Gate ─► Review ─► pass ─► next unit
                  ▲          │ red     │
                  ├──────────┘         │
                  └──────── back ──────┘   escalate ─► you

Parallel group:  unit A ─► review ─┐
                 unit B ─► review ─┴─► Integration ─► Review of the combined result ─► next step
```

- **Brief problems go to the coordinator.** When a unit signals its brief may be wrong, revisit the brief before resuming; signals: [run-reference.md](run-reference.md#brief-problems). Gate and review execution, including the gate-failure cap: [run-reference.md](run-reference.md#gate).
- **A unit that keeps coming back reaches the coordinator** (`--takeover-after`, default 2): the run stops with it in `takeover`, you apply what the reviewer listed and run `close`. See [run-reference.md](run-reference.md#takeover).
- **The handoff is a log, not evidence.** It helps the implementer resume and helps you read the run. What a unit left ready is attested by its review.
- **Each agent writes only its own files.** Two agents never touch the same file.

## Where the work lives

Before `start`, check the checkout: isolated runs cut their worktree from `HEAD`, so `start` refuses uncommitted changes. Commit or stash them, use `--from <ref>` to cut from a commit and ignore them, or use `--in-place`; see [run-reference.md](run-reference.md#the-runs-worktree).

One plan is one folder with one subfolder per unit, in order. A unit's folder holds its brief, its rounds (prompts, outputs, reviews, verdicts) and its handoff. The goal, the order and a status log sit at the top. A plan that is ready but not launched is kept as source files (goal, order, briefs) in `~/.plan-runs-pending/<repo>/<name>/`; `plan-run.sh start <name>` moves it into the run. The run's code lives in its own worktree on the branch `plan/<name>`, which the user merges at the end.

When the plan is done, the user chooses: keep the record (copied into `records/plans/` in the repository) or delete the run. Until then it stays where it is. `finish` removes the run folder and the worktree. When the plan is merged, also remove what `finish` does not: the plan's branches (unless `finish --discard` already deleted them) and any background process or temporary database the plan started.

## Run commands

Before the first `start` or `resume`, read [run-commands.md](../../modules/run-commands.md): it holds the shared commands, state folders, stop and quota handling, and the `guard` hook rule that `start` and `resume` need `run_in_background: true`.

The plan's own options and commands, and the list of its script and test files, are in [run-reference.md](run-reference.md).

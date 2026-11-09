---
name: plan
description: Use when the user has an agreed goal that needs several coordinated pieces of work, a plan split into small reviewed units that a script runs, or a stopped plan run to resume. A single task is not a plan.
---

# Plan

<!-- inject: ../../modules/coordinate-a-run.md -->
<!-- BKF:GENERATED-INJECTED -->
## Coordinate a run

The skills of the plan, code review, council and research workflows include this module, and so does the crew skill. Their guides own the phases, files and roles; this module holds what every run shares. In a workflow a script chains the phases; in a crew no script runs: the orchestrator is the coordinator, its coordinator sessions are the agents, and it chains their phases itself.

- Keep long work out of the coordinator. The coordinator keeps the conversation with the user and prepares the briefs and inputs; long work and long reviews go to agents. Small work that takes a few minutes and is quick and clear from the brief and the check (a small gap, a small fix, a short check), the coordinator does itself, on its own initiative, runs the check again and reports what it changed. A larger gap, or one that needs the agent's context, goes back to an agent.
- A run has its checkpoints, usually the start, the end and an escalation. Between them do not message the user: no progress updates or questions about small decisions. Decide within the agreed intent (`align-intent`) and continue. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.
<!-- BKF:GENERATED-INJECTED-END -->
> **Before you start**
> - A seam of up to about 15 files decided by one gate, or 1–3 sequential units repeating one pattern, goes to [`delegate-work`](../delegate-work/SKILL.md).
> - About ten files is the ceiling for a non-mechanical unit; rehearse before `start` (both in section 1).

## When to use

Use it when the user has an agreed goal that needs several pieces of work done in a coordinated way, such as a feature split into database, UI and UX. A single task is not a plan: brief it and run it. A simple, quick task, or several independent ones that need no review of each unit, goes to [delegate-work](../delegate-work/SKILL.md): you review the result at the end, which is cheap because the work is small. A plan is for units that depend on one another and need a reviewer each, with you only coordinating. To explore options before the goal is agreed, hold a discussion first.

**One plan is one goal split into units.** Each unit is small and isolated, so it can be implemented, reviewed and read on its own. The plan is the ordered list of units and what connects them.

**The format is the user's choice.** Ask whether they want a plan kept in the conversation or one that runs on a script with units, and explain the difference neutrally. A plan kept in the conversation stays there; the rest of this guide is for the plan that runs.

## How to read this

These are principles with reasons, not a procedure. Adapt to the task and keep what the reasons protect.

- **Small, isolated units.** Split a unit until a reviewer holding only its brief and its diff can judge it.
- **Code decides what code can decide.** An agent checking another agent's work is a second opinion, not evidence. A unit passes when commands that cannot be talked out of a result pass, run by the script and not by an agent. An agent judges only what no command can.

## 1. The goal and the units

Write the goal in one place and have the user confirm it. It is the intent as `align-intent` defines it: what is wanted and why, what exists when it is done, what is out of scope, what is already decided, and when to stop and ask. Do not describe the units there.

**Split the goal into units** with the user, along the seams of the work (data, interface, behaviour), not the order of effort. Test each unit:

- Can you say what exists when it is done and when it stops?
- Can a reviewer judge it from its brief and its diff, without the other units?
- If it fails review, can it be redone without redoing the others?

If a unit fails a test, split it again or merge it with the one it cannot be separated from.

Each unit costs a full review round. Make something a separate unit when it has review criteria of its own, when a dependency or worthwhile parallelism separates it, when the user wants a checkpoint there, or when merging it would overload one brief. Otherwise fold it into the unit that consumes it. Give the reason for each cut.

**How big is too big.** What slows a unit is not how many files it touches but how many new things it designs at once (a migration, fixtures and tests that depend on each other, several groups of scenarios).

- **A unit designs one new thing:** one migration, script, tool or set of tests. Repeating an already-settled pattern across many files is mechanical and can be larger.
- **About ten files is the ceiling for work that is not mechanical.** Past it, split.
- **Split on the seams the agent would otherwise cross:** a unit that reads a different group of modules for each part is several units.

Long rounds carry a larger context, which slows every step. The run records the size of each implementation round; read it after a plan and correct these limits. Measurements so far: [run-reference.md](run-reference.md#running-a-plan).

**When the split depends on something you do not yet know** (how many modules cross a boundary, what a move would break), do not write a unit for it. Run a small plan that only reads and reports, and write the real plan, with every brief, after the user has read the report. Adding units by hand to a run in progress leaves contracts unfixed and can misalign step numbers.

**Order and parallelism.** You decide which units come first and which run together, and tell the user. Units run one at a time in the run's own worktree by default. Two units may run together only if they share nothing: each runs in its own copy of the repository and their diffs are brought together afterwards, which costs an integration agent and a review of the combined result. Run in series when unsure, and when the group is only two small units. Parallel pays when units are big and truly independent. Read [run-recovery.md](run-recovery.md) only when a step has several briefs on one line or a run is stopped.

Write the order in a plan file, one step per line; units on the same line run together:

```
database.md
ui.md  ux.md      # run together
tests.md
```

**You always read the gates; the user does not have to.** Before `start`, and whenever you add or change a unit, run the script's `gates` command and read the list. Every unit has a command that fails if it is wrong, or a reason, written in the plan, why none can exist. A unit with neither is not ready. Rehearse before every `start` and fix unexpected failures; see [run-reference.md](run-reference.md#rehearsal). Gate commands run through `bash -c`, so shell syntax works.
Every unit's gate also includes the same repository-wide check command (for example `pnpm check:quick`) alongside its own tests; otherwise a defect found one unit later costs a full round. A check too slow for every gate (the full database suite) goes in `regression.gate` next to `plan.txt`: the script runs it at the `-p` checkpoints and before the final review. Script behavior, including lint refusals: [run-reference.md](run-reference.md#gate).

**Checkpoints.** A run can pause after chosen steps (`-p`). Suggest where to pause and, when you agree the split, ask who the pauses are for: only for you to check the step (rerun what the reviewer's sandbox could not, read the diff, resume without reporting unless a fundamental decision changes), or also for the user. Write the answer in the plan and follow it. Step numbers count the lines of `plan.txt`; when you add or move a unit, recompute them before you resume.

**Pilot by kind of unit.** Pause after the first unit of each kind (moving files, changing a rule, a migration, an interface), read it, and only then release the rest of that kind.

**Have the briefs read before they run.** Required when there are more than three briefs, when they are not variations of one template, or when any unit is above the size ceiling; otherwise optional (if you skip it, say so in the report). A cheap agent (a Haiku subagent is enough) reads every brief and answers only two questions: are there two sentences that cannot both be obeyed, and is there a criterion that someone holding only the diff and the gate result cannot judge? It is a probabilistic check: it adds to reading the gates, never replaces it.

**Agree the plan before anything runs.** Present the split with the reason for each cut, the order, the pauses and the model. You suggest the pauses and say what each costs; the user decides the pauses and the model. Wait for their agreement on scope, outputs, sequence and settings before the first unit starts. That agreement does not waive a checkpoint the user asked for. If a later request conflicts with the settings, stop and reconcile the plan first.

**The plan can change, with a reason on record.** A unit that shows the split was wrong is a reason to revise the units with the user, not to stretch the unit.

## 2. The unit brief

One brief per unit. It is the only thing the implementer and the reviewer share, so it must stand alone. Copy this template and fill each heading. Use a `gate` fence for commands; if no command can decide the result, state the reason under Gate.

~~~markdown
## Result
What exists when this unit is done, and when to stop.

## Receives
Concrete facts this unit can rely on from earlier units.
```premise
grep -q "photo" db/schema.sql
```

## Leaves ready
Concrete facts later units can rely on.

## Removes
`path/to/remove`

## Creates
`path/to/create`

## Out of scope
What this unit must not touch. Tests and documents made wrong by the change belong to this unit and must be adapted without weakening assertions.

## Gate
```gate
pnpm check:quick
pnpm test:unit
```

## Criteria
What the reviewer judges that no command checks.
~~~

- **Receives and leaves ready are how units touch.** Write concrete facts ("the table has `name`, `photo`, `bio`"), not "the database is done". You write every brief before the run, so the two sides of each contract are fixed: what one unit leaves ready is exactly what the next receives, and the producing unit's review checks it. A fact about the repository that the brief relies on (a file contains X, a command exists) is proved by a command in a `premise` fence, one per line. The script runs it before the unit's first round, in the checkout as earlier units left it, and stops the unit at once, with no implementer launched, if one fails. A `gate` command runs only after implementation, so it proves nothing about the start. `gates` warns when `Receives` states facts and the brief has no `premise`. Rehearsal runs the lines too, but a unit that depends on an earlier one may fail them before `start`.
- **The gate is a fenced block tagged `gate`,** one command per line (script behavior: [run-reference.md](run-reference.md#gate)). Following the `core-code-principles` module, write every criterion a command can decide as a gate line: a test, a script, a query, a comparison of behaviour before and after.
- **When the checking tool does not exist yet,** make building it a unit that comes first; the commands that use it go in a later unit.
- **Put the proof that a check can fail where the reviewer sees it:** in the diff (a test run against a broken copy) or in the gate (a line that runs the check against a case it must reject). Never in the handoff or a sentence the implementer attests: the reviewer sees only the brief, the diff and the gate result.
- **A number is a gate line, not a criterion:** a score, count or duration the reviewer would have to take from the implementer goes in the gate or out of the brief. When a gate command is slow (tens of minutes), the brief tells the implementer to measure only what it touches and leaves the full measurement to the gate.
- **Criteria are what the gate cannot decide:** whether the diff stays in scope, whether what the unit leaves ready is there as stated, whether prose is accurate, how a page looks. Say who judges each: the reviewer by reading, or the user. The reviewer does not run the gate again and does not send back or escalate because it could not run a command; it reports what it could not check.
- **Closed cases for open problems.** For a tool whose correctness has no end (a static analysis, a parser), list in the gate the cases it must get right and record its known limits. A reviewer who finds a new case reports it with a command that fails, to be added to the gate, instead of sending the unit back.
- **Out of scope is as important as the result.** Write it by exclusion (HTTP routes, migrations, other apps); do not list the only files that may change, because the radius of a change is never known beforehand. Add the clause every unit needs: tests and documents the change makes wrong belong to this unit and are adapted without weakening an assertion. A brief that forbids the one file its own required behavior breaks makes the unit loop until the cap.
- **State what each step leaves true.** A gate or criterion written with the plan's end state in mind is false half way: a command checking a rule a later unit closes cannot pass now. Check every gate line against two states, the one the unit finds and the one it leaves, and write the exceptions into the brief and into the unit that closes them. List what the unit deletes or moves under Removes and what it adds under Creates; see [run-reference.md](run-reference.md#brief-lint) for how `gates` checks them, and [run-reference.md](run-reference.md#gate) and [#rehearsal](run-reference.md#rehearsal) for the timing. Units on the same line do not see each other's changes. A tool that only bridges the transition names, in the brief of the unit that creates it, the unit that removes it and the gate that replaces it.

## 3. Delegating

Each agent gets a short brief that points to the guide for its role and never explains the method. A script builds the agent briefs from fixed templates, runs each unit and stops when a review escalates; you write only the goal, the unit briefs and their order. That script is [plan-run.sh](scripts/plan-run.sh); read [run-reference.md](run-reference.md) before the first `start`, and [run-recovery.md](run-recovery.md) only when a step has several briefs on one line or a run is stopped.

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
- **The reviewer does not see the implementer's reasoning or handoff.** The brief, the diff and the gate result are all it needs.
- **The handoff is a log, not evidence.** It helps the implementer resume and helps you read the run. What a unit left ready is attested by its review.
- **Each agent writes only its own files.** Two agents never touch the same file.
- **Agents do not touch git state:** no commit, stage, stash or reset. The run records a base before the unit starts, and the diff is read from it.

## 4. What the user receives

When the run finishes, or stops on an escalation, give:

1. **Whether the goal is met.** Yes, in part or no, in a line or two. The last review writes it, not the implementer.
2. **What each unit did.** Its result in a line, where it differs from its brief, and the verification that ran. Take this from the reviews and the diff, not from the handoffs, which are the author's optimistic account.
3. **Weak points and next step.** What is thin, what was left out, what deserves attention. What appears outside the focus is not chased midway; it goes here.

Do not restate the diff.

## 5. Where the work lives

Before `start`, check the checkout: isolated runs cut their worktree from `HEAD`, so `start` refuses uncommitted changes. Commit or stash them, use `--from <ref>` to cut from a commit and ignore them, or use `--in-place`; see [run-reference.md](run-reference.md#the-runs-worktree).

One plan is one folder with one subfolder per unit, in order. A unit's folder holds its brief, its rounds (prompts, outputs, reviews, verdicts) and its handoff. The goal, the order and a status log sit at the top. A plan that is ready but not launched is kept as source files (goal, order, briefs) in `~/.plan-runs-pending/<repo>/<name>/`; `plan-run.sh start <name>` moves it into the run. The run's code lives in its own worktree on the branch `plan/<name>`, which the user merges at the end.

When the plan is done, the user chooses: keep the record (copied into `records/plans/` in the repository) or delete the run. Until then it stays where it is. `finish` removes the run folder and the worktree. When the plan is merged, also remove what `finish` does not: the plan's branches (unless `finish --discard` already deleted them) and any background process or temporary database the plan started.

## Run commands

Before the first `start` or `resume`, read [run-commands.md](../../modules/run-commands.md): it holds the shared commands, state folders, stop and quota handling, and the `guard` hook rule that `start` and `resume` need `run_in_background: true`.

The plan's own options and commands, and the list of its script and test files, are in [run-reference.md](run-reference.md).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

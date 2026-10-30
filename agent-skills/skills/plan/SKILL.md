---
name: plan
description: Use when the user has an agreed goal that needs several coordinated pieces of work, a plan split into small reviewed units that a script runs, or a stopped plan run to resume. A single task is not a plan.
---

# Plan

<!-- inject: ../../modules/coordinate-a-run.md -->
<!-- BKF:GENERATED-INJECTED -->
## Coordinate a run

The skills of the plan, code review, council and research workflows include this module, and so does the crew skill. Their guides own the phases, files and roles; this module holds what every run shares. In a workflow a script chains the phases; in a crew no script runs: the orchestrator is the coordinator, its coordinator sessions are the agents, and it chains their phases itself.

- Stay out of the roles. The coordinator keeps the conversation with the user and prepares the briefs and inputs; it does not act as researcher, implementer, advisor or reviewer, even for a small run. A gap in an agent's work goes back to an agent, through the script or in a crew through a brief, not to the coordinator to fill.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start and judges at the end; between checkpoints do not message them: no progress updates, status summaries or questions about small decisions. Decide those within the intent agreed with the user (`align-intent`) and continue, and stop and ask only as that intent says. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked.
- An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- If the same problem returns after being sent back, or a script's cap on rounds is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.
<!-- BKF:GENERATED-INJECTED-END -->

## Navigation map

| If you need to... | See |
| --- | --- |
| Decide whether the work is a plan or a single task | [When to use](#when-to-use) |
| Understand the principles behind the stages | [How to read this](#how-to-read-this) |
| Write and confirm the goal, and split it into units | [1. The goal and the units](#1-the-goal-and-the-units) |
| Write the brief that one unit's implementer and reviewer share | [2. The unit brief](#2-the-unit-brief) |
| Brief the agents that implement and review | [3. Delegating](#3-delegating) |
| Report to the user at the end or on an escalation | [4. What the user receives](#4-what-the-user-receives) |
| Find the plan's folder and what each unit keeps | [5. Where the work lives](#5-where-the-work-lives) |

## When to use

Use this when the user has an agreed goal that needs several pieces of work
done in a coordinated way, such as a feature split into database, UI and UX. A
single task is not a plan: brief it and run it. To explore options before the
goal is agreed, hold a discussion first.

**One plan is one goal split into units.** Each unit is small and isolated, so
that it can be implemented, reviewed and read on its own. The plan is the
ordered list of units and what connects them.

**The format is the user's choice.** Do not choose it for them: ask whether they
want a plan kept in the conversation or a plan that runs on a script with units,
and explain the difference neutrally. A plan kept in the conversation stays there;
the rest of this guide is for the plan that runs.

## How to read this

These are principles with reasons, not a procedure. You can judge; what goes
wrong in long work is losing the thread, not deciding. Adapt to the task, and
keep what the reasons protect.

- **Small, isolated units.** A unit that nobody can review with attention is too
  big. Split it until a reviewer holding only its brief and its diff can judge it.
- **Code decides what code can decide.** An agent checking another agent's work
  is a second opinion, not evidence: two models agreeing is one more guess. A
  unit passes when commands that cannot be talked out of a result pass, run by
  the script and not by an agent. An agent judges only what no command can.

## 1. The goal and the units

Write the goal in one place and have the user confirm it. It is the intent as
`align-intent` defines it: what is wanted and why, what exists when it is done,
what is out of scope, what is already decided, and when to stop and ask. Do not
describe the units there.

**Split the goal into units** with the user. A good split follows the seams of
the work (data, interface, behaviour), not the order of effort. Test each unit:

- Can you say what exists when it is done and when it stops?
- Can a reviewer judge it from its brief and its diff, without the other units?
- If it fails review, can it be redone without redoing the others?

If a unit fails a test, split it again or merge it with the one it cannot be
separated from.

Each unit costs a full review round, so size units by their work and risk. Make
it a separate unit when it has review criteria of its own that a reviewer can
judge apart from its neighbours, when a dependency or worthwhile parallelism
separates it, when the user wants a checkpoint there, or when merging it would
overload one brief. Otherwise fold it into the unit that consumes it. Give the
reason for each cut.

**How big is too big.** What decides how slow a unit is, in practice, is not how many
files it touches but how many new things it designs at once: a migration, fixtures and
tests that depend on each other, or several groups of scenarios. A unit that repeats a
pattern already settled across many files is mechanical and fast. So:

- **A unit designs one new thing:** one migration, one script, one tool, one set of tests. Repeating
  a pattern already settled across many files is mechanical and can be larger.
- **About ten files is the ceiling for work that is not mechanical.** Past it, split.
- **Split on the seams the agent would otherwise cross:** a unit that makes the agent
  read a different group of modules for each part is several units.

Long rounds also carry a much larger context, which slows every step further. The run
records the size of each implementation round; read it after a plan and correct these
limits. The measurements so far are in [run-reference.md](run-reference.md#running-a-plan).

**When the split depends on something you do not yet know,** such as how many
modules cross a boundary or what a move would break, do not write a unit for
what you cannot yet describe. Run a small plan first that only reads and
reports, and write the real plan, with every brief, after the user has read the
report. Adding units by hand to a run in progress is possible but leaves the
contracts between units unfixed and can misalign step numbers; two plans keep
each one complete when it starts.

**Order and parallelism.** You decide which units come first and which run together, and tell the user.
Units run one at a time in the run's own worktree by default. Two units may run
together only if they share nothing: each then runs in its own copy of the
repository, and their diffs are brought together afterwards. That costs an
integration agent, and a review of the combined result, for the group. Run in
series when unsure, and when the group is only two small units, which is cheaper
and sees more. Parallel pays when the units are big and truly independent.

You write the order in a plan file, one step per line; units on the same line run
together:

```
database.md
ui.md  ux.md      # run together
tests.md
```

**You always read the gates; the user does not have to.** The user steers the goal
and judges at the end that what the plan reached is what they wanted. They do not
read the commands that decide each unit; you do. Before `start`, and again whenever
you add or change a unit, run the script's `gates` command and read the list. Every
unit has a command that fails if it is wrong, or a reason, written in the plan, for
why none can exist. A unit with neither is not ready to run.
The `gates` output also shows brief lint, and `start` refuses a plan whose briefs have lint
errors, and `resume` refuses a run whose current briefs have them. `plan-run.sh rehearse <plan.txt>` runs the plan's gates informally before `start`.

**Checkpoints.** A run can pause after chosen steps (`-p`). Suggest where to pause
and ask the user, when you agree the split, who the pauses are for: only for you to check the step
(rerun what the reviewer's sandbox could not, read the diff, then resume without
reporting unless a fundamental decision changes), or also for the user to read
it. Write the answer in the plan and follow it. Step numbers count the lines of
`plan.txt`; when you add or move a unit, recompute them before you resume.

**Pilot by kind of unit.** Pause after the first unit of each kind (moving files, changing a
rule, a migration, an interface), read it, and only then release the rest of that kind. A kind that
is new to the plan fails in ways the briefs cannot predict, and fails once instead of in every unit.

**Have the briefs read before they run.** A cheap agent (a Haiku subagent is enough) that reads
every brief and answers only two questions catches most contradictions: are there two sentences
that cannot both be obeyed, and is there a criterion that someone holding only the diff and the
gate result cannot judge? It is a probabilistic check, so it adds to reading the gates, never
replaces it.

**Agree the plan before anything runs.** Present the finished plan: the split with
the reason for each cut, the order, the pauses and the model. You suggest the pauses
and say what each costs; the user decides the pauses and the model. Wait for their
agreement on scope, outputs, sequence and settings before the first unit starts. That
agreement authorizes the units in scope but does not waive a checkpoint the user
asked for. If a later request conflicts with the settings, stop and reconcile the
plan first.

**The plan can change, with a reason on record.** A unit that shows the split
was wrong is a reason to revise the units with the user, not to stretch the unit.

## 2. The unit brief

You write one brief per unit. It is the only thing the implementer and the
reviewer share, so it must stand alone.

```
Unit brief
├─ Result        what exists when it is done, and when to stop
├─ Receives      what it can rely on from other units (a fact, not "look at what they did")
├─ Leaves ready  what other units may rely on from it
├─ Removes       paths it deletes or moves away, in backticks, one per line (a folder ends in `/`)
├─ Creates       paths it adds or moves to that a gate runs, in backticks, one per line
├─ Out of scope  what it must not touch
├─ Gate          the commands the script runs; the unit cannot pass if one fails
└─ Criteria      what the reviewer judges that no command checks
```

- **Receives and leaves ready are how units touch.** Write them as concrete
  facts: "the table has `name`, `photo`, `bio`", not "the database is done". You
  write every brief before the run starts, so the two sides of each contract are
  fixed then: what one unit leaves ready is exactly what the next receives. The
  producing unit's review checks that it left that ready, so a unit never starts
  on a contract that was not met.
- **The gate is a fenced block tagged `gate`,** one command per line:

  ````
  ```gate
  pnpm check:quick
  node --test scripts/audit-write-inventory.test.mjs
  ```
  ````

  After each implementation round the script runs these in the checkout, outside
  any agent and outside the reviewer's sandbox, so they can reach a database or
  write build output. A failing command sends the work back to the implementer
  with its output and no review; the reviewer cannot override it, and cannot be
  asked until it is green.
  Following the `core-code-principles` module, write every criterion that a command can
  decide as a gate line: a test, a script, a query, a comparison of the behaviour
  before and after.
- **When the checking tool does not exist yet,** make building it a unit that
  comes first, and put the commands of the unit that uses it in that later unit.
- **Put the proof that a check can fail where the reviewer sees it.** The `core-code-principles` module
  requires a check to be able to fail. The proof is in the diff (a test run against a broken copy) or in
  the gate (a line that runs the check against a case it must reject). Never in the handoff or in a
  sentence the implementer attests: the reviewer sees only the brief, the diff and the gate result. No
  criterion may depend on what the implementer reports.
- **Criteria are what the gate cannot decide:** whether the diff stays in scope,
  whether what the unit leaves ready is there as stated, whether prose is accurate,
  how a page looks. Say who judges each: the reviewer by reading, or the user.
  The reviewer does not run the gate again and does not send back or escalate
  because it could not run a command; it reports what it could not check.
- **Closed cases for open problems.** For a tool whose correctness has no end
  (a static analysis, a parser), list in the gate the cases it must get right, and
  record the limits it is known to have. A reviewer who finds a new case reports
  it with a command that fails, to be added to the gate, instead of sending the
  unit back for a case the brief never asked for.
- **Out of scope is as important as the result.** It keeps a diff small enough to review. Write it by
  exclusion: say what must not be touched (HTTP routes, migrations, other apps), and do not list
  the only files that may change, because the radius of a change is never known beforehand. Add the
  clause every unit needs: tests and documents that the change makes wrong belong to this unit and
  are adapted, without weakening an assertion. A brief that forbids the one file its own required
  behavior breaks makes the unit loop until the cap.
- **State what each step leaves true.** A gate or a criterion written with the end state of the plan
  in mind is false half way: a command that checks a rule a later unit closes cannot pass now, and a
  rule such as "this number only changes in X" is wrong when the step creates a temporary exception.
  Check every gate line against two states: the one the unit finds, for what the gate checks before
  the work, and the one the unit leaves, since the script runs the gate after the implementer
  finished. A gate that runs a file the same unit removes passes the rehearsal, which runs at the
  start state, and fails the unit. Write the exceptions into the brief and into the unit that closes
  them. List what the unit deletes or moves under Removes and what it adds under Creates: `gates`
  follows them step by step and reports as an error a gate that uses a path the plan has removed.
  Units on the same line do not see each other's changes. A tool that only bridges the transition
  names, in the brief of the unit that creates it, the unit that removes it and the gate that
  replaces it.

## 3. Delegating

Each agent gets a short brief. The method lives in the guide for its role, so
the brief points to it and never explains it. The briefs are the same shape every
time, so they are built from fixed templates: you write only the goal, the unit
briefs and their order, and a script builds the agent briefs, runs each unit and
stops when a review escalates. That script is [plan-run.sh](scripts/plan-run.sh); [run-reference.md](run-reference.md)
has its options, the gate, the repeated-failure stop, `gates` (brief lint), `rehearse`, the bridge
and the commands to repair a stopped run. Read it before the first `start`.

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

Rules that hold whatever the number of agents:

- **Brief problems go to the coordinator.** An implementer may stop with
  `BLOCKED:`, and a reviewer may return `VERDICT: brief`; both signal that the
  brief may be wrong.
- **The gate is run by the script, not by an agent,** and a review does not
  replace it. A unit passes when the gate is green and the reviewer passes.
- **The reviewer does not see the implementer's reasoning or handoff.** The brief, the diff and the gate result are
  all it needs.
- **The handoff is a log, not evidence.** It helps the implementer resume when a
  unit is sent back, and helps you read the run. What a unit left ready is attested
  by its review, not by its handoff.
- **Each agent writes only its own files.** Two agents never touch the same file.
- **A gate that keeps failing has its own cap,** larger than the cap on reviews.
  When it is reached the unit goes to you.
- **Git state is not touched by agents.** They do not commit, stage, stash or
  reset. The run records a base before the unit starts, and the diff is read from it.

## 4. What the user receives

The user judges at the end whether the plan got where it should. When the run
finishes, or stops on an escalation, you give:

1. **Whether the goal is met.** Yes, in part or no, in a line or two. The last
   review writes it, not the implementer, who tends to think so.
2. **What each unit did.** Its result in a line, where it differs from its brief,
   and the verification that ran. Take this from the reviews and the diff, not
   from the implementers' own handoffs: a handoff is the author's account and can
   be too optimistic.
3. **Weak points and next step.** What is thin, what was left out and what
   deserves attention. It is the seed of the next goal. What appears outside the
   focus is not chased midway; it goes here.

Do not restate the diff: it is the record of what changed.

## 5. Where the work lives

One plan is one folder, with one subfolder per unit in order. A unit's folder holds its
brief, its rounds (the agent prompts, the outputs, the reviews and their verdicts) and
its handoff, so the user can open one unit and see only it. The plan's goal, the order
of the units and a status log sit at the top. A plan that is ready but not yet launched
is kept as its source files (the goal, the order and the briefs) in
`~/.plan-runs-pending/<repo>/<name>/`, and `plan-run.sh start <name>` moves it into the run when
it is time. The run's code lives in its own worktree on the branch `plan/<name>`, which the
user merges at the end; [run-reference.md](run-reference.md) says how. Where the folder is, and
how it is created, is in the Run commands section below.

When the plan is done, the user chooses: keep the record, which is copied into
`records/plans/` in the repository, or delete the run. Until they choose, it stays where it is.

## Run commands

<!-- inject: ../../modules/run-commands.md -->
<!-- BKF:GENERATED-INJECTED -->
## Run commands

The scripts of the plan, research, council and code-review skills run on one engine, `agent-skills/harness`. Each takes the same commands: `<script> start ...`, `resume`, `status <name>`, `board <name>` and `finish <name>`. Start each `start` and `resume` with Bash `run_in_background: true` and stay quiet until it ends; the `guard` hook of `bkf hooks` refuses a launch in the foreground or one backgrounded by hand, including from an agent inside a run.

- **Backend.** Agents are Codex by default. `HARNESS_BACKEND=claude` runs a whole run on `claude -p`: give `-m` a Claude model such as `sonnet` and `-e` an effort from `low` to `max`. Write access is then confined to the agent's working directory, a reviewer can only read, and the quota signal is Claude's `rate_limit_event`. Set the variable on every `resume` too, or the run goes back to Codex. A run refuses to start when the backend's command is not installed.
- **State** is in `~/.<workflow>-runs/<repo>/<name>/` (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`), `<repo>` being the name of the repository's folder. A run made before that layout is still found in `~/.<workflow>-runs/<name>/`. `<WORKFLOW>_RUNS_DIR` or `HARNESS_RUNS_DIR` names the folder that holds the runs themselves, without the repository level, and `<WORKFLOW>_GUIDES` replaces the folder of role guides (by default the `roles/` folder of the skill). `start` creates the folder and fails if it exists: do not create it by hand. It is never under `/tmp`, which the sandbox leaves writable.
- **A worktree of its own.** A run whose agents read or write the repository (a plan, a code review) gets a git worktree at `<run>/tree`, so the repository's checkout stays as it is; its skill says on which branch or revision and how to opt out (`--in-place`). `finish` removes the worktree, and `finish --discard` also deletes the plan's branch.
- **Progress.** `status.log` is the event history; `status` prints it and `board` prints a board of the steps and their agents, which is also saved as `board.txt`. Progress lines go to stderr.
- **A run that stops** (an agent failed, a review escalated, the account ran out of quota) writes `STOPPED` in `status.log` with the reason. Read the rounds in the run folder, fix the cause (usually the brief or the inputs, under `00-input/`), then `resume <name>`: finished steps stay done and the unfinished one runs again. A run that was killed is detected on `resume` and continues the same way.
- **A stalled agent.** An agent that writes nothing to its events and stderr files for `HARNESS_AGENT_STALL_TIMEOUT` seconds (default 1200, 0 turns it off) is ended and the run stops with `STALLED` in `status.log`, so the script exits and the coordinator is told. An agent that keeps writing is not ended, however slow. Fix the cause (a login, the network), then `resume`.
- **Usage limit.** The run stops with the reason `usage limit reached` and `status.log` gets `QUOTA: <the text after "try again at">`, as the agent wrote it, not parsed. Wake once, a little after that time, and `resume`: run `harness quota-wait '<that text>' && <script> resume <name>` with `run_in_background: true`. `quota-wait` sleeps until the reset plus a margin (`--margin`, default 120 seconds) with no model, so the agent is woken once, when it can resume. It reads `H:MM AM|PM` and `YYYY-MM-DD HH:MM`, with an optional `UTC`; a time without `UTC` is the local time, and a clock time that passed less than 6 hours ago counts as reached. For any other text it exits 2 without waiting: work out the time yourself and set one wake-up for it plus 2 minutes, never one at the time itself or before it, and if the quota is still out when it fires, add 2 minutes more instead of guessing again.
- **Lock.** A live script holds `<run>/.lock`; a second `resume`, a `finish` or a recovery command refuses while it does. A lock whose process is gone is replaced.
- **When it prints `READY`** the result is in the run folder. `finish <name>` copies the record to `records/<plans|reviews|councils|research>/<name>/` in the repository, checks the copy and removes the run folder; `finish --discard <name>` deletes the run.
- **Limits** (environment variables): a review is capped at `<WORKFLOW>_MAX_ROUNDS` rounds (default 3), and must give at least `<WORKFLOW>_MIN_CHECKED` lines (default 3) under `## What I checked`, or it is repeated and then fails. Counts start again at every `resume`.
- **Sandbox.** Runs use the `workspace-write` sandbox. It confines writes to the agent's folder, but an agent can still read files outside the checkout, such as the login sessions of CLI tools in the home folder, and reach HTTPS, so it can use any session left open. The repository's own rules say what to keep logged out.
<!-- BKF:GENERATED-INJECTED-END -->

The plan's own options and commands, and the list of its script and test files, are in [run-reference.md](run-reference.md).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

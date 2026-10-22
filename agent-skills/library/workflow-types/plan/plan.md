---
bkf: document
description: Guides planning from goal to result, for the coordinator who works with the user. Covers when to plan, how to split a goal into isolated units, what a unit brief states, how to delegate implementation and review, and what the user receives.
tags: [planning, delegation]
---

# Plan

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

Write the goal in a few lines, in one place, and have the user confirm it. It
says what exists at the end, who uses it and what is out of scope. Do not
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
limits. The measurements so far are in the `dispatch-codex` skill.

**When the split depends on something you do not yet know,** such as how many
modules cross a boundary or what a move would break, do not write a unit for
what you cannot yet describe. Run a small plan first that only reads and
reports, and write the real plan, with every brief, after the user has read the
report. Adding units by hand to a run in progress is possible but leaves the
contracts between units unfixed and can misalign step numbers; two plans keep
each one complete when it starts.

**Order and parallelism.** You decide which units come first and which run together, and tell the user.
Units run one at a time in the user's checkout by default. Two units may run
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

**Checkpoints.** A run can pause after chosen steps (`-p`). Suggest where to pause
and ask the user, when you agree the split, who the pauses are for: only for you to check the step
(rerun what the reviewer's sandbox could not, read the diff, then resume without
reporting unless a fundamental decision changes), or also for the user to read
it. Write the answer in the plan and follow it. Step numbers count the lines of
`plan.txt`; when you add or move a unit, recompute them before you resume.

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
  Following the `determinism` module, write every criterion that a command can
  decide as a gate line: a test, a script, a query, a comparison of the behaviour
  before and after.
- **When the checking tool does not exist yet,** make building it a unit that
  comes first, and put the commands of the unit that uses it in that later unit.
- **Say how each command was shown to fail.** The `determinism` module requires a
  check to be able to fail. Write in the unit how that was shown: a test that was
  run against a broken copy, or a case that is expected to be rejected.
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
- **Out of scope is as important as the result.** It keeps a diff small enough to review.

## 3. Delegating

Each agent gets a short brief. The method lives in the guide for its role, so
the brief points to it and never explains it. The briefs are the same shape every
time, so they are built from fixed templates: you write only the goal, the unit
briefs and their order, and a script builds the agent briefs, runs each unit and
stops when a review escalates. That script is `plan-run.sh`, owned by the
`dispatch-codex` skill (`scripts/plan-run.sh`); load that skill for its usage. It runs
Codex agents, not Claude ones.

| Role | Does | Receives |
| --- | --- | --- |
| [Implementation](/plan-implementation.md) | Does the unit inside its brief, verifies, writes the handoff | The unit brief |
| [Review](/plan-review.md) | Checks the diff against the brief; can send the work back | The unit brief and the diff |
| [Integration](/plan-integration.md) | Only for a parallel group: applies the diffs, resolves conflicts, fixes what the combined review found | The briefs of the group |

```
Unit brief ─► Implement ─► Gate ─► Review ─► pass ─► next unit
                  ▲          │ red     │
                  ├──────────┘         │
                  └──────── back ──────┘   escalate ─► you

Parallel group:  unit A ─► review ─┐
                 unit B ─► review ─┴─► Integration ─► Review of the combined result ─► next step
```

Rules that hold whatever the number of agents:

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
is kept as its source files (the goal, the order and the briefs) outside the run folder,
and the run is started when it is time. Where the folder is, and how it is created, is
in the `dispatch-codex` skill.

When the plan is done, the user chooses: keep the record, which is copied into
`records/plans/` in the repository, or delete the run. Until they choose, it stays where it is.

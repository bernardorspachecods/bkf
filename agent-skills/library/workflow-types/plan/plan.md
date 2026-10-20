---
bkf: document
description: Guides planning from goal to result, for the coordinator who works with the user. Covers when to plan, how to split a goal into isolated units, what a unit brief states, how to delegate implementation and review, and what the user receives.
tags: [planning, delegation]
---

# Plan

## When to use

Use this when the user has an agreed goal that needs several pieces of work
done in a coordinated way, such as a feature split into database, UI and UX. A
single task is not a plan: brief it and run it. To explore options before the
goal is agreed, hold a discussion first.

**One plan is one goal split into units.** Each unit is small and isolated, so
that it can be implemented, reviewed and read on its own. The plan is the
ordered list of units and what connects them.

## How to read this

These are principles with reasons, not a procedure. You can judge; what goes
wrong in long work is losing the thread, not deciding. Adapt to the task, and
keep what the reasons protect.

- **Small, isolated units.** A unit that nobody can review with attention is too
  big. Split it until a reviewer holding only its brief and its diff can judge it.
- **Roles, not headcounts.** Implementation and review are roles. Nobody reviews
  what they wrote.
- **The user steers at the start and judges at the end.** The goal and the
  split into units are where the user steers; each unit then runs without them.
- **You brief, you do not do.** You keep the conversation with the user and
  prepare the briefs. You do not implement or review a unit, even a small one.
- **You are present at the start, at the end and on an escalation.** Between
  units you do not step in: the run goes on by itself.

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

**Order and parallelism.** Say which units come first and which run together.
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

**Checkpoints.** A run can pause after chosen steps (`-p`). Ask the user, when
you agree the split, who the pauses are for: only for you to check the step
(rerun what the reviewer's sandbox could not, read the diff, then resume without
reporting unless a fundamental decision changes), or also for the user to read
it. Write the answer in the plan and follow it. Step numbers count the lines of
`plan.txt`; when you add or move a unit, recompute them before you resume.

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
└─ Criteria      what the reviewer verifies, and how (a test, a command, a read)
```

- **Receives and leaves ready are how units touch.** Write them as concrete
  facts: "the table has `name`, `photo`, `bio`", not "the database is done". You
  write every brief before the run starts, so the two sides of each contract are
  fixed then: what one unit leaves ready is exactly what the next receives. The
  producing unit's review checks that it left that ready, so a unit never starts
  on a contract that was not met.
- **Criteria are checkable.** A criterion the reviewer can only agree with is
  not a criterion.
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
Unit brief ─► Implement ─► Review ─► pass ─► next unit
                  ▲           │
                  └── back ───┘   escalate ─► you

Parallel group:  unit A ─► review ─┐
                 unit B ─► review ─┴─► Integration ─► Review of the combined result ─► next step
```

Rules that hold whatever the number of agents:

- **Review is by someone other than the implementer,** and does not see the
  implementer's reasoning or handoff. The brief and the diff are all it needs.
- **The handoff is a log, not evidence.** It helps the implementer resume when a
  unit is sent back, and helps you read the run. What a unit left ready is attested
  by its review, not by its handoff.
- **Each agent writes only its own files.** Two agents never touch the same file.
- **Sending back has a cap on rounds** (three by default). If the same problem
  returns, or the cap is reached, the unit goes to you, because the brief is
  probably what is wrong. You decide whether to revise it with the user.
- **A review shows what it checked.** A review without a list of what it went
  through does not count.
- **Git state is not touched by agents.** They do not commit, stage, stash or
  reset. The run records a base before the unit starts, and the diff is read from it.
- **The choice of models is outside this document.**

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

One plan is one folder in `~/.plan-runs/<name>/`, with one subfolder per unit in
order. A unit's folder holds its brief, its rounds (the agent prompts, the
outputs, the reviews and their verdicts) and its handoff, so the user can open one
unit and see only it. The plan's goal, the order of the units and a `status.md`
sit at the top.

When the plan is done, the user chooses: keep the record, which is copied into
`records/plans/` in the repository, or delete the run. Until they choose, it stays where it is.

As soon as you create a run folder, or any file the user will read, run
`open <path>` yourself and give the full path in the same message.

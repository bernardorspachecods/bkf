---
name: agentic-work
description: "Use when work is handed to agents or needs an independent review: one unit or many, each with a brief, a gate and a review, driven from this conversation or by a script; or a stopped run to resume. Work you do yourself with no review is not agentic work; to explore options before the goal is agreed, use brainstorm."
---

# Agentic work

A run is a plan: one goal split into units, each implemented, gated and reviewed on its own (pass, back or escalate).

<!-- inject: ../../modules/agentic-roles.md -->
<!-- BKF:GENERATED-INJECTED -->
## Agentic roles

| Role | Exists to | Protects | Sees |
| --- | --- | --- | --- |
| Coordinator | Own the goal and the contracts: write the briefs and checks, decide within the agreed intent, close small gaps, write the report | That the user's intent survives the run | Everything |
| Author | Do the piece of work its brief names and nothing around it | Scope: other pieces rely on what it left alone | Its brief, and its earlier handoff on a retry |
| Reviewer | Stand in for the user on one question: does this work do what the brief asked | Independent judgment | The brief, the work and the check results; never the author's reasoning or handoff |
| Integrator | Only for parallel work: make the pieces fit without redoing them | The contracts between pieces | The pieces' briefs and the goal |

The coordinator may hold any other role, never authoring and reviewing the same piece. Every piece is reviewed; only the user can waive a review, and the report says so. A failed or escalated run is not a block: read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user.

A run's checkpoints are usually the start, the end and an escalation. At a checkpoint, stop until the user approves, and link the file instead of pasting it. Between checkpoints, decide within the agreed intent (`align-intent`) and continue without messaging the user: no progress updates or questions about small decisions.

Report an outcome as it is: what passed, what escalated, what was skipped.
<!-- BKF:GENERATED-INJECTED-END -->

You are the coordinator; a unit's author is its implementer. When you implement, work under the [implementation guide](roles/agentic-work-implementation.md).

## How the run is set

The user decides three things before the first unit, and you never choose or switch them:

| Question | Options |
| --- | --- |
| Who drives? | This conversation ([conversation-run.md](conversation-run.md)): units one after another, and the way to hand a single task to an agent. Or a script ([script-run.md](script-run.md)): parallel units, pauses, a run that goes on without you |
| Who implements? | You, an agent you launch on Codex or Claude, or the script's agents |
| Who reviews? | A reviewer on its own model and backend, you, or the user |

Read only the guide of the chosen driver.

## 1. The goal and the units

Write the goal once, as `align-intent` defines the intent, and have the user confirm it and the split.

**Split along the seams of the work** (data, interface, behaviour), not the order of effort. A unit is ready when you can say what exists when it is done, a reviewer can judge it from its brief and diff alone, and it can be redone without redoing the others. Each unit costs a review round: make one separate only when it has criteria of its own, a dependency or parallelism separates it, or the user wants a checkpoint there. About ten files that are not mechanical is the ceiling.

**When the split depends on something you do not know yet,** run a unit that only reads and reports first.

**Gates.** Every unit has a gate, or a reason in its brief why no command can decide it. Run each gate line once before the first unit, and include the repository's quick check in every gate, if it has one.

## 2. The unit brief

The brief is all the implementer and the reviewer share, so it stands alone. The tools read its `gate` and `premise` fences and its Removes and Creates sections.

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
What this unit must not touch, written by exclusion, never as the list of files that may change. Tests and documents made wrong by the change belong to this unit and are adapted without weakening assertions.

## Gate
```gate
pnpm check:quick
pnpm test:unit
```

## Criteria
What the reviewer judges that no command checks.
~~~

Receives and leaves ready are the contracts between units, the same facts on both sides. **Check each gate line against the state the unit finds and the one it leaves:** a check of a rule a later unit closes cannot pass yet.

## 3. What the user receives

When the run finishes, or stops on an escalation, give:

1. **Whether the goal is met:** yes, in part or no, and why, taken from the reviews and the diff.
2. **Weak points and next step,** including what appeared outside the focus.

Maintainers: [the package's files](files.md).

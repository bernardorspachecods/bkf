---
name: agentic-work
description: "Use when work is handed to agents or needs an independent review: one unit or many, each with a brief, a review and, where the repository has checks, a gate, driven from this conversation; or a stopped run to resume. Work you do yourself with no review is not agentic work; to explore options before the goal is agreed, use brainstorm."
---

# Agentic work

Work handed to agents is split into units, each implemented, reviewed (and gated where the repository has checks) on its own: pass, back or escalate. A unit is one change a reviewer judges in one read. **When the work is more than one unit, also read [plan.md](plan.md)** (the goal, the split, the contracts between units).

## Agentic roles

| Role | Exists to | Protects | Sees |
| --- | --- | --- | --- |
| Coordinator | Own the goal and the contracts: write the briefs and checks, decide within the agreed intent, close small gaps, integrate parallel units in a conversation run, write the report | That the user's intent survives the run | Everything |
| Author | Do the piece of work its brief names and nothing around it | Scope: other pieces rely on what it left alone | Its brief, and its earlier handoff on a retry |
| Reviewer | Stand in for the user on one question: does this work do what the brief asked | Independent judgment | The brief, the work and the check results; never the author's reasoning or handoff |
| Integrator | Only for parallel groups in the script run: make the pieces fit without redoing them | The contracts between pieces | The pieces' briefs and the goal |

You are the coordinator; a unit's author is its implementer. You may hold any other role, never authoring and reviewing the same piece. Every piece is reviewed; only the user can waive a review, and the report says so. A failed or escalated unit is not a block: read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user.

At a checkpoint (an escalation, the end, and the start of a plan), stop until the user approves, and link the file instead of pasting it. Between checkpoints, decide within the agreed intent (`align-intent`) and continue without messaging the user. When you implement, work under the [implementation guide](roles/agentic-work-implementation.md).

## One unit

1. **Brief.** Write it from the request; when the request already says what is wanted, there is no goal or split to confirm. The brief is all the implementer and the reviewer share, so it stands alone.
2. **Implementer.** A Haiku subagent, unless the user names another (a Codex agent you launch, you, another model). **The reviewer** is you, unless the user names another: run `check --gate-only` and judge the diff against the brief.
3. **Run it** as [conversation-run.md](conversation-run.md) says: begin, implement, check, act on the result.

~~~markdown
## Result
What exists when this unit is done, and when to stop.

## Start from
*Only when existing code shows the way.* The files to read first (with lines), the code to copy and the known pitfalls. A list to read, not a list of the files that may change.

## Removes
*Only when the unit deletes files.* `path/to/remove`

## Creates
*Only when the unit adds files.* `path/to/create`

## Out of scope
What this unit must not touch, written by exclusion, never as the list of files that may change. Tests and documents made wrong by the change belong to this unit and are adapted without weakening assertions.

## Gate
*Only when the repository already has a check that applies; otherwise omit the fence and say so in one line.*
```gate
pnpm test:unit
```

## Criteria
What the reviewer judges that no command checks.
~~~

The tools read the `gate` fence and the Removes and Creates sections; a section marked *only when* is left out otherwise. They do not read Start from.

Plan state and briefs never go in the scratchpad; [plan.md](plan.md) says where they live.

**Gates are optional.** Use one only where the repository clearly already has tests or checks that can decide the unit, commands you have seen (a documented script, a test suite, CI). Never invent a gate: no new harness, no ad-hoc `grep` or script, no command guessed from the stack. With nothing that applies, the reviewer alone judges the unit (so does a unit that creates the tests). **The gate runs once:** the implementer runs it last, through a tool that leaves a receipt; the check and the reviewer use the receipt and never repeat it. Any later edit, yours too, brings the gate back. Never run a unit's gate commands by hand outside the check.

A script driver exists ([script-run.md](script-run.md)); never offer it or read it unless the user asks for a script run.

## What the user receives

When the work finishes, or stops on an escalation, report the outcome as it is (what passed, what escalated, what was skipped):

1. **Whether the goal is met:** yes, in part or no, and why, taken from the reviews and the diff.
2. **Weak points and next step,** including what appeared outside the focus.

Maintainers: [the package's files](files.md).

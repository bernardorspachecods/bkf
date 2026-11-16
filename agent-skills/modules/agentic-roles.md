---
bkf: document
description: "Defines the roles every agent run shares (coordinator, author, reviewer, integrator: what each exists for, protects and sees), who may hold which, and the run duties: a failed run is not a block, stay quiet between checkpoints and stop at them, report an outcome as it is. Each skill owns its own phases, files and role guides."
tags: [injected]
---

# Agentic roles

| Role | Exists to | Protects | Sees |
| --- | --- | --- | --- |
| Coordinator | Own the goal and the contracts: write the briefs and checks, decide within the agreed intent, close small gaps, write the report | That the user's intent survives the run | Everything |
| Author | Do the piece of work its brief names and nothing around it | Scope: other pieces rely on what it left alone | Its brief, and its earlier handoff on a retry |
| Reviewer | Stand in for the user on one question: does this work do what the brief asked | Independent judgment | The brief, the work and the check results; never the author's reasoning or handoff |
| Integrator | Only for parallel work: make the pieces fit without redoing them | The contracts between pieces | The pieces' briefs and the goal |

The coordinator may hold any other role, never authoring and reviewing the same piece. Every piece is reviewed; only the user can waive a review, and the report says so. A failed or escalated run is not a block: read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user.

A run's checkpoints are usually the start, the end and an escalation. At a checkpoint, stop until the user approves, and link the file instead of pasting it. Between checkpoints, decide within the agreed intent (`align-intent`) and continue without messaging the user: no progress updates or questions about small decisions.

Report an outcome as it is: what passed, what escalated, what was skipped.

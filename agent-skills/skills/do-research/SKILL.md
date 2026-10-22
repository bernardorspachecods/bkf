---
name: do-research
description: Use when the user asks for sourced or verified findings, a comparison across sources, an audit of a conclusion, or literature work that needs multiple sources or an evidence trail.
---

# Do research

Open the files below before starting; they hold the rules for collecting evidence and concluding from it. Open each one whose description fits the task.

<!-- BKF:GENERATED-TAGGED-LIST tags: research -->
| What it is | Document |
| --- | --- |
| Guides sourced research from objective to delivery, for the coordinator who works with the user. Covers when to research, how to frame the objective, how to map where to look, how to delegate collection, review and digest, and what the user receives. A narrow lookup follows its light path. | [research.md](../../library/workflow-types/research/research.md) |
<!-- BKF:GENERATED-TAGGED-LIST-END -->

<!-- inject: ../../library/modules/coordinate-a-run.md -->
<!-- BKF:GENERATED-INJECTED -->
## Coordinate a run

The skills of the plan, code review, council and research workflows include this module. Their coordinator guides own the phases, files and roles; this module holds what every run shares.

- Stay out of the roles. The coordinator keeps the conversation with the user and prepares the briefs and inputs; it does not act as researcher, implementer, advisor or reviewer, even for a small run. A gap in an agent's work goes back to a fresh agent through the script, not to the coordinator to fill.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start and judges at the end; between checkpoints do not message them: no progress updates, status summaries or questions about small decisions. Decide those within the agreed scope and continue. Stop and ask only for a decision that changes the goal, the scope or the agreed settings, or for a requirement that cannot be met within scope, and then say it short: the decision, your recommendation and what it costs. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked.
- An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- If the same problem returns after being sent back, or the script's cap on rounds is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.
<!-- BKF:GENERATED-INJECTED-END -->

When the research has several stages or agents, also use the `work-in-stages` skill. For the written answer, also use `repo-maintenance`.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

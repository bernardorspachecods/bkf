---
name: work-in-stages
description: Use when work has several stages or roles, hands work to other agents, needs a plan, a council or a code review, or resumes a stopped run.
---

# Work in stages

Open the files below before starting; they hold the rules for planning, delegating, and reviewing multi-step work, or for handing work to other agents. Open each one whose description fits the task.

<!-- BKF:GENERATED-TAGGED-LIST tags: delegation, planning, review -->
| What it is | Document |
| --- | --- |
| Guides a code review of a branch, pull request, range or working tree, for the coordinator who works with the user. Covers when to review, how to set up the target and run its gate, how the two axes and their checkers run apart, and what the user receives. | [code-review.md](../../library/workflow-types/code-review/code-review.md) |
| Guides a council on an explicitly requested question or decision, for the coordinator who works with the user. Covers when to run one, how to write the brief, how the five advisors and five reviewers run apart, how you write the chairman's report and what the user receives. | [council.md](../../library/workflow-types/council/council.md) |
| Guides planning from goal to result, for the coordinator who works with the user. Covers when to plan, how to split a goal into isolated units, what a unit brief states, how to delegate implementation and review, and what the user receives. | [plan.md](../../library/workflow-types/plan/plan.md) |
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

For a specific kind of work, also use its own skill (for example `do-research`), and `delegate-work` for a single short task handed to one agent.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

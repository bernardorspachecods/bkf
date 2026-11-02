---
bkf: document
description: "Defines the coordinator's shared run duties: prepare briefs and inputs, fix small clear gaps after checking them, route larger or context-dependent gaps to agents, stay quiet between checkpoints, verify agent output, and escalate failures. Each workflow's coordinator guide, and the crew skill, owns its own phases and files, and points here for what every run shares."
tags: [injected]
---

# Coordinate a run

The skills of the plan, code review, council and research workflows include this module, and so does the crew skill. Their guides own the phases, files and roles; this module holds what every run shares. In a workflow a script chains the phases; in a crew no script runs: the orchestrator is the coordinator, its coordinator sessions are the agents, and it chains their phases itself.

- Stay out of the roles. The coordinator keeps the conversation with the user and prepares the briefs and inputs; it does not act as researcher, implementer, advisor or reviewer. Exception: a small gap, quick and clear from the brief and the check, the coordinator fixes itself, runs the check again and reports what it changed. A larger gap, or one that needs the agent's context, goes back to an agent.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start and judges at the end; between checkpoints do not message them: no progress updates, status summaries or questions about small decisions. Decide those within the intent agreed with the user (`align-intent`) and continue, and stop and ask only as that intent says. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked.
- An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- If the same problem returns after being sent back, or a script's cap on rounds is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.

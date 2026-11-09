---
bkf: document
description: "Defines the coordinator's shared run duties: prepare briefs and inputs, fix small clear gaps after checking them, route larger or context-dependent gaps to agents, stay quiet between checkpoints, verify agent output, and escalate failures. Each workflow's coordinator guide, and the crew skill, owns its own phases and files, and points here for what every run shares."
tags: [injected]
---

# Coordinate a run

The skills of the plan, code review, council and research workflows include this module, and so does the crew skill. Their guides own the phases, files and roles; this module holds what every run shares. In a workflow a script chains the phases; in a crew no script runs: the orchestrator is the coordinator, its coordinator sessions are the agents, and it chains their phases itself.

- Keep long work out of the coordinator. The coordinator keeps the conversation with the user and prepares the briefs and inputs; long work and long reviews go to agents. Small work that takes a few minutes and is quick and clear from the brief and the check (a small gap, a small fix, a short check), the coordinator does itself, on its own initiative, runs the check again and reports what it changed. A larger gap, or one that needs the agent's context, goes back to an agent.
- A run has its checkpoints, usually the start, the end and an escalation. Between them do not message the user: no progress updates or questions about small decisions. Decide within the agreed intent (`align-intent`) and continue. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.

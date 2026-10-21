---
bkf: document
description: "Defines the coordinator's duties in a run where agents work apart and a script chains their phases: stay out of the roles, stay quiet between checkpoints, treat agent output as unverified, and treat a failure as an escalation. Each workflow's coordinator guide owns its own phases and files."
tags: [planning, delegation, review]
---

# Coordinate a run

- The coordinator keeps the conversation with the user and prepares the briefs and inputs. It does not act as researcher, implementer, advisor or reviewer, even for a small run. A gap in an agent's work goes back to a fresh agent through the script, not to the coordinator to fill.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start, by agreeing the goal, objective or brief, and judges at the end; the middle runs without them. Between checkpoints, do not message the user: no progress updates, status summaries or questions about small decisions. Decide those within the agreed scope and continue. Stop and ask only for a decision that changes the goal, the scope or the agreed settings, or for a requirement that cannot be met within scope, and then say it short: the decision, your recommendation and what it costs. The user asks for status when they want it.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked and without handing the user a command to type.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- Collection, implementation, review and the like are roles, not headcounts: several agents can fill one in parallel, and nobody reviews what they wrote. An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- Sending work back has a cap on rounds, set by the script (three by default), so an unattended run cannot go on without end. If the same problem returns after being sent back, or the cap is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- The user decides the model; the workflow guides do not choose it.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.

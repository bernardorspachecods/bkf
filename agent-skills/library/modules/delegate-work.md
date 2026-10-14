---
bkf: document
description: "Defines how to assign work to agents and reconcile handoffs, including independence, write boundaries, and completion reports. Workflow sequencing and user checkpoints are covered by coordinate-a-workflow."
tags: [delegation]
---

# Delegate work

- Advice is lightweight: send only the context needed to answer, return the answer with its uncertainty, and create no packet or artifact unless the work itself needs one.
- Use one agent for cohesive work. Use several only when their outputs and write boundaries are independent and parallel work materially helps; ask the user about agent count only when it would materially change the assignment. Give each agent non-overlapping files, keep shared files under one writer or have agents return proposed changes, use the smallest isolation that prevents conflicting edits, and do not let implementation and review change the same target at once.
- For a significant design decision, have several agents work independently on radically different options, each under a different constraint and with its own brief, then compare them and give your own recommendation, proposing a hybrid if elements combine well.
- Delegating or handing over work does not create a new identity for it. The incoming agent continues the same task and scope, receiving the current state, unresolved points, next action, and existing IDs; changing the executor does not make provisional work complete.
- A delegated implementer does only the named work and edits only its assigned files. It does not certify its own work: it reports where and why it deviated from the brief and leaves judging to a review. When revising after feedback it keeps the earlier version retrievable. It may resolve minor issues within scope; on a blocking ambiguity it pauses the affected work, asks the coordinator, and continues independent work that is still in scope.
- If a stage cannot be done as assigned, for example because delegation or an independent reviewer is unavailable, say so; do not imply it was done.
- Have each delegated agent report what it changed or found, the verification performed and its results, remaining uncertainty, and any unmet completion condition.
- The primary agent checks each handoff against the assignment, the agreed scope, the criteria, the gates, and the evidence, using the submitted artifacts and without copying, editing, or rewriting what agents wrote: out-of-scope changes, missed requirements, relevant verification, unsupported conclusions, and lost uncertainty or disagreement. It reconciles within the authorized scope and reports unresolved conflicts, unsupported claims, and incomplete work plainly. With several reviewers, it integrates their assessments.
- Do not report delegated work complete while an agent is still running; otherwise completion follows the output availability rule in coordinate-a-workflow.md.
- Treat silence from a running agent as pending; stop it only for an explicit error, timeout, blocked state, or user instruction.
- A standalone request to delegate authorizes that assignment without a durable plan. Return a standalone review in the conversation unless persistent output is requested; if it is requested without a destination, settle the destination with the user first. Do not create a plan just to give a review an ID or location.
- Add coordination material only when independent work, a long handoff, or several contributors require it. Keep it a concise temporary brief, and delete it once the handoff is reconciled and no decision is pending, unless the user asks to keep it.
- Give each agent the exact path to its assignment, tell it to read only the files named there and write only in its designated place, and have it return a brief completion confirmation instead of copying its output into the handoff. These boundaries are instructions; do not describe them as enforced.

---
bkf: document
description: "Defines how to assign work to agents outside a run script and reconcile their handoffs, including independence, write boundaries, and completion reports. Coordination across a run is covered by coordinate-a-run."
tags: [delegation]
---

# Delegate work

- Advice is lightweight: send only the context needed to answer, return the answer with its uncertainty, and create no packet or artifact unless the work itself needs one.
- Use one agent for cohesive work. Use several only when their outputs and write boundaries are independent and parallel work materially helps; ask the user about agent count only when it would materially change the assignment. Give each agent non-overlapping files, keep shared files under one writer or have agents return proposed changes, use the smallest isolation that prevents conflicting edits, and do not let implementation and review change the same target at once.
- Delegating or handing over work does not create a new identity for it. The incoming agent continues the same task and scope, receiving the current state, unresolved points, next action, and existing IDs; changing the executor does not make provisional work complete.
- A delegated implementer reports where and why it deviated from the brief. When revising after feedback it keeps the earlier version retrievable. It may resolve minor issues within scope; on a blocking ambiguity it pauses the affected work, asks the coordinator, and continues independent work that is still in scope.
- Have each delegated agent report what it changed or found, the verification performed and its results, remaining uncertainty, and any unmet completion condition. The primary agent checks each handoff against the assignment, the agreed scope, the criteria, the gates, and the evidence, using the submitted artifacts and without copying, editing, or rewriting what agents wrote: out-of-scope changes, missed requirements, relevant verification, unsupported conclusions, and lost uncertainty or disagreement. It reconciles within the authorized scope and reports unresolved conflicts, unsupported claims, and incomplete work plainly. With several reviewers, it integrates their assessments.
- Treat silence from a running agent as pending; stop it only for an explicit error, timeout, blocked state, or user instruction.
- A standalone request to delegate authorizes that assignment without a durable plan. Return a standalone review in the conversation unless persistent output is requested; if it is requested without a destination, settle the destination with the user first. Do not create a plan just to give a review an ID or location.

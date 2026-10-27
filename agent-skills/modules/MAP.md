---
bkf_version: "0.1"
description: Owns the shared rule modules whose text the workflow and work skills inject into their bodies; the skills themselves live outside this bundle.
---

# Modules map

A module is a rule written once and shared. A skill that needs it names it in
an `<!-- inject: ... -->` line, and `bkf skills --write` copies the module's
text into the skill's body, because a harness always loads a triggered skill's
body but may skip a link.

Every module carries the tag `injected`: no skill selects a module by tag.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Defines the coordinator's duties in a run where agents work apart and a script chains their phases: stay out of the roles, stay quiet between checkpoints, treat agent output as unverified, and treat a failure as an escalation. Each workflow's coordinator guide owns its own phases and files, and points here for what every run shares. | [coordinate-a-run.md](/coordinate-a-run.md) |
| Sets the principles for work with code: test first, growing in layers, long-term decisions, reuse and code smells; and how it is verified: let code decide what code can decide, make every check able to fail. Covers any work with code, including work handed to other agents; the gate a script runs for a plan or a review is owned by the gate module. | [core-code-principles.md](/core-code-principles.md) |
| States the contract of the gate, the commands a script runs outside any agent to decide what code can decide: how they run, what they record, and what an agent that receives the result does with it. | [gate.md](/gate.md) |
| Sets how an agent settles intent with the user before work that is more than a small change, so it can then work alone: what is wanted and why, when it is done, what is out of scope and decided, when to stop and ask, and how a change of intent is recorded. Long or delegated work keeps the intent in a goal file; small work restates it in the conversation. | [intent.md](/intent.md) |
| States how the run scripts of the plan, research, council and code-review skills behave in common: the commands they share, where a run keeps its state, how a stopped run resumes, the backend, the usage limit, the lock, the limits and what finishing keeps. Each skill's own section adds the options of its script. | [run-commands.md](/run-commands.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

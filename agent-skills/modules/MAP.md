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
| Defines the roles every agent run shares (coordinator, author, reviewer, integrator: what each exists for, protects and sees), who may hold which, and the run duties: a failed run is not a block, stay quiet between checkpoints and stop at them, report an outcome as it is. Each skill owns its own phases, files and role guides. | [agentic-roles.md](/agentic-roles.md) |
| Sets the principles for work with code: test first, small steps with long-term decisions, reuse and code smells; and how it is verified: code decides what code can decide, every check can fail, what code cannot decide is reported as unverified. Covers any work with code, whoever does it. | [core-code-principles.md](/core-code-principles.md) |
| Sets how an agent settles intent with the user before work that is more than a small change, so it can then work alone: what is wanted and why, when it is done, what is out of scope and decided, when to stop and ask, and how a change of intent is recorded. Long or delegated work keeps the intent in a goal file; small work restates it in the conversation. | [intent.md](/intent.md) |
| States how the run scripts of the agentic-work, research and council skills behave in common: the commands they share, where a run keeps its state, how a stopped run resumes, the backend, the usage limit, the lock, the limits and what finishing keeps. Each skill's own section adds the options of its script. | [run-commands.md](/run-commands.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

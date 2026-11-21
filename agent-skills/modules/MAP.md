---
bkf_version: "0.1"
description: Owns the shared rule modules whose text the workflow and work skills inject into their bodies; the skills themselves live outside this bundle.
---

# Modules map

A module is a rule written once and shared by more than one skill. A skill
whose every run needs it names it in an `<!-- inject: ... -->` line, and
`bkf skills --write` copies the module's text into the skill's body, because a
harness always loads a triggered skill's body but may skip a link. A skill that
needs it only for some uses links it with the condition for reading it.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Defines the roles every agent run shares (coordinator, author, reviewer, integrator: what each exists for, protects and sees), who may hold which, and the run duties: a failed run is not a block, stay quiet between checkpoints and stop at them, report an outcome as it is. Each skill owns its own phases, files and role guides. | [agentic-roles.md](/agentic-roles.md) |
| States how the run scripts of the agentic-work and research skills behave in common: the commands they share, where a run keeps its state, how a stopped run resumes, the backend, the usage limit, the lock, the limits and what finishing keeps. Each skill's own section adds the options of its script. | [run-commands.md](/run-commands.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

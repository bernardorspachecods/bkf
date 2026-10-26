---
description: Owns the request-matching skills, their generated catalog, and the shared rule modules; it does not index individual skill packages.
---

# Agent skills map

The inventory routes to the shared modules bundle. Catalog output and the
scripts that build and check it are linked as artifact references because the
skill packages are selected by their own metadata.

After adding or editing a skill, or changing a module a skill injects, run [`bkf skills`](/bkf/tooling/commands.md#bkf-skills) to check or
refresh the injected text and catalog.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| States what the agent harness is for, its layers, the decisions taken about it and what is still to build, in order. It is the working plan of the harness; the code and each skill own their own behavior. | [harness-goal.md](/agent-skills/harness-goal.md) |
| Owns the shared rule modules whose text the workflow and work skills inject into their bodies; the skills themselves live outside this bundle. | [MAP.md](/agent-skills/modules/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

## Artifact references

- [Generated skill catalog](/agent-skills/SKILL-ARCHITECTURE.md) — read the catalog when you need to inspect the skill collection as a whole.

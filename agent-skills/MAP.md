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
| Documents the harness engine's commands, exit codes and environment variables, and how to run its tests; read it when you change how agents, gates, injection or workflow definitions run. | [harness.md](/agent-skills/harness/harness.md) |
| Owns the shared rule modules whose text the workflow and work skills inject into their bodies; the skills themselves live outside this bundle. | [MAP.md](/agent-skills/modules/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

## Artifact references

- [Generated skill catalog](/agent-skills/skill-architecture.md) — it opens with a table of every skill, when to use it, and whether it runs only when the user asks; read it when you need to know which skills exist or to inspect the collection as a whole.

---
description: Owns the request-matching entry skills, their generated catalog, and the shared rule library; it does not index individual skill packages.
---

# Agent skills map

The inventory routes to the shared library bundle. Catalog output and the
scripts that build and check it are linked as artifact references because the
entry skill packages are selected by their own metadata.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Owns the shared rule modules and workflow types selected by entry skills; request-matching skills and their generated lists live outside this bundle. | [MAP.md](/agent-skills/library/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

## Artifact references

- [Generated skill catalog](/agent-skills/SKILL-ARCHITECTURE.md) — read the catalog when you need to inspect the skill collection as a whole.
- [Catalog generator](/agent-skills/scripts/generate_skill_catalog.py) — regenerate the catalog after skill changes; skill folders that git ignores are left out.
- [Catalog validator](/agent-skills/scripts/validate_skill_catalog.py) — check skill metadata and generated catalog consistency.

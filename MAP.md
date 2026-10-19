---
bkf_version: "0.1"
description: Routes repository-wide agent guidance and the BKF and agent-skill areas; local navigation belongs to each area's map.
---

# BKF repository map

Start from the map for the area you are working in: [BKF](/bkf/MAP.md) or
[agent skills](/agent-skills/MAP.md). Each area map owns its task routes and
implementation references. To learn what BKF is and how its layers fit
together, read [what BKF is](/bkf/manual/what-is-bkf.md) first.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Sets the repository entry rule for agents: use the root map to find the active area map, then follow that area's instructions. | [AGENTS.md](/AGENTS.md) |
| Owns the request-matching entry skills, their generated catalog, and the shared rule library; it does not index individual skill packages. | [MAP.md](/agent-skills/MAP.md) |
| Defines the BKF document, map, and bundle format and provides tooling to generate inventories and check conformance. | [MAP.md](/bkf/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

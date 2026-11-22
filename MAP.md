---
bkf_version: "0.2"
description: "Routes the common tasks of this repository to their owner document; local navigation belongs to each area's map. Holds no rules or details."
---

# BKF repository map

Why the repository is built this way is in
[what BKF is](/bkf/manual/what-is-bkf.md). Local navigation belongs to each
area's map: [BKF](/bkf/MAP.md) or [agent skills](/agent-skills/MAP.md).

## Common tasks

| Task | Start here |
| --- | --- |
| Organize a new repository under BKF, or revamp an outdated one | [Build a repo's organization](/bkf/manual/build-repo-organization.md) |
| Decide whether BKF fits a repository | [Why BKF](/bkf/manual/why-bkf.md) |
| Change a document in this or any BKF repository | [`repo-maintenance` skill](/agent-skills/skills/repo-maintenance/SKILL.md) |
| Add or change a skill | [`skill-authoring` skill](/agent-skills/skills/skill-authoring/SKILL.md), then `bkf skills --write` |
| Add or change a hook or a `bkf` command | [Tooling map](/bkf/tooling/MAP.md): the files to change and the commands to run |
| Change how workflows run | [Harness engine](/agent-skills/harness/harness.md) |
| Change the format | [Specification](/bkf/format/format-specification.md) |
| Install on a new machine, or after pulling new commands | [Install guide](/INSTALL.md) |

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Sets the repository entry rule for agents: open the map of the area you will change, then follow its instructions. | [AGENTS.md](/AGENTS.md) |
| Owns the request-matching skills and their generated catalog; it does not index individual skill packages. | [MAP.md](/agent-skills/MAP.md) |
| Defines the BKF document, map, and bundle format and provides tooling to generate inventories and check conformance. | [MAP.md](/bkf/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

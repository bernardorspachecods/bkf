---
bkf_version: "0.1"
description: "Lists every piece this repository provides, where it lives, when it is used and which document owns it, and routes the common tasks to their start; local navigation belongs to each area's map. Holds no rules or details: each row links to its owner."
---

# BKF repository map

Everything the repository has, to know before you work in it or apply it to
another repository. Each row names the owner document; open it only for the
piece your task touches. Why the pieces are built this way is in
[what BKF is](/bkf/manual/what-is-bkf.md). Local navigation belongs to each
area's map: [BKF](/bkf/MAP.md) or [agent skills](/agent-skills/MAP.md).

## Common tasks

| Task | Start here |
| --- | --- |
| Organize a new repository under BKF, or revamp an outdated one | [Build a repo's organization](/bkf/manual/build-repo-organization.md) |
| Decide whether BKF fits a repository | [Why BKF](/bkf/manual/why-bkf.md) |
| Change how workflows run | [Harness engine](/agent-skills/harness/harness.md) |
| Change the format | [Specification](/bkf/format/format-specification.md) |

## Pieces

| Piece | Where | When it is used | Owner |
| --- | --- | --- | --- |
| Format: what a valid document, map and bundle are | `bkf/format/` | Writing or checking any document, map or frontmatter | [Specification](/bkf/format/format-specification.md), [frontmatter profiles](/bkf/format/frontmatter-profiles.md), [glossary](/bkf/format/glossary.md) |
| `bkf` command: `validate`, `inventory`, `skills`, `orient`, `search`, `sources`, `log`, `updates`, `hooks`, `task`, `merge`, `launch`, `help` | `bkf/tooling/` | After editing documents, at session start, to look up rules and manage researched sources, to install hooks; skills and the Agentic app call `task`, `merge` and `launch` to open agent sessions, record their state and land their branches through the merge queue | [Command reference](/bkf/tooling/commands.md); `bkf help`. To add or change a hook or a `bkf` command: [tooling map](/bkf/tooling/MAP.md), the files to change and the commands to run |
| Hooks: behavior that must run in every session, including the prompt prefixes such as `t:` and `i:` | Code in `bkf/tooling/`, installed under `~/.agent-hooks/` | Every session, once installed on the machine | [`bkf hooks`](/bkf/tooling/commands.md#bkf-hooks) |
| Personal rules printed at every session start | `~/.agent-hooks/rules.md`, seeded from `bkf/tooling/default_rules.txt` | Every session, with the `rules` hook | [`bkf hooks`](/bkf/tooling/commands.md#bkf-hooks) |
| Skills: one per situation, picked by the harness from their descriptions | `agent-skills/skills/` | When a request matches a skill's description, or the user names it | [Skill catalog](/agent-skills/skill-architecture.md): a generated table of every skill and when to use it. To add or change a skill: [`skill-authoring` skill](/agent-skills/skills/skill-authoring/SKILL.md), then `bkf skills --write` |
| Workflow: `agentic-work`, run by a script with agents in reviewed roles | Each skill's `scripts/` and `roles/` | Work that spans several agents | Each workflow's skill; shared run commands in [run-commands](/agent-skills/skills/agentic-work/run-commands.md) |
| Harness: the engine the workflow scripts, the agent launcher of `agentic-work` calls | `agent-skills/harness/` | Changing how agents, gates, injection or workflow definitions run | [Harness engine](/agent-skills/harness/harness.md) |
| Repo library: a repository's own procedures and modules | `repo-library/` in each repository that needs one | A procedure repeats in that repository | [`repo-library` skill](/agent-skills/skills/repo-library/SKILL.md) |
| Upkeep rules for every document change | The `repo-maintenance` skill | Every change that touches a BKF repository's documents | [`repo-maintenance` skill](/agent-skills/skills/repo-maintenance/SKILL.md) |
| Feedback and ideas logs | `bkf/feedback.md`, `bkf/ideas.md` | Recording a problem or an idea for later review, never read during ordinary work | [BKF agent instructions](/bkf/AGENTS.md) |
| Records of past runs | `records/` | Only when the user points to a past run | [Agent instructions](/AGENTS.md) |
| Installation on a machine | `INSTALL.md` | A new machine, or after pulling new commands | [Install guide](/INSTALL.md) |

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Sets the repository entry rule for agents: open the map of the area you will change, then follow its instructions. | [AGENTS.md](/AGENTS.md) |
| Owns the request-matching skills and their generated catalog; it does not index individual skill packages. | [MAP.md](/agent-skills/MAP.md) |
| Defines the BKF document, map, and bundle format and provides tooling to generate inventories and check conformance. | [MAP.md](/bkf/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

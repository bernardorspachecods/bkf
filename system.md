---
bkf: document
description: "Lists every piece this repository provides (format, bkf command, hooks, modules, skills, workflows, harness, repo library, logs) with where it lives, when it is used and which document owns it, and routes the common tasks to their start. Holds no rules or details: each row links to its owner."
tags: [navigation, overview]
---

# What this repository provides

Read this first to know everything the repository has before you work in it or
apply it to another repository. Each row names the owner document; open it only
for the piece your task touches. Why the pieces are built this way is in
[what BKF is](/bkf/manual/what-is-bkf.md).

## Pieces

| Piece | Where | When it is used | Owner |
| --- | --- | --- | --- |
| Format: what a valid document, map and bundle are | `bkf/format/` | Writing or checking any document, map or frontmatter | [Specification](/bkf/format/format-specification.md), [frontmatter profiles](/bkf/format/frontmatter-profiles.md), [glossary](/bkf/format/glossary.md) |
| `bkf` command: `validate`, `inventory`, `skills`, `orient`, `search`, `log`, `updates`, `hooks`, `help` | `bkf/tooling/` | After editing documents, at session start, to look up where a rule lives, to install hooks | [Command reference](/bkf/tooling/commands.md); `bkf help` |
| Hooks: behavior that must run in every session, including the prompt prefixes such as `t:` and `i:` | Code in `bkf/tooling/`, installed under `~/.agent-hooks/` | Every session, once installed on the machine | [`bkf hooks`](/bkf/tooling/commands.md#bkf-hooks) |
| Personal rules printed at every session start | `~/.agent-hooks/rules.md`, seeded from `bkf/tooling/default_rules.txt` | Every session, with the `rules` hook | [`bkf hooks`](/bkf/tooling/commands.md#bkf-hooks) |
| Modules: rules written once and injected into skills | `agent-skills/modules/` | Never read on their own; their text arrives inside the skills | [Modules map](/agent-skills/modules/MAP.md) |
| Skills: one per situation, picked by the harness from their descriptions | `agent-skills/skills/` | When a request matches a skill's description, or the user names it | [Skill catalog](/agent-skills/SKILL-ARCHITECTURE.md): a generated table of every skill and when to use it |
| Workflows: `plan`, `research`, `council`, `code-review`, run by a script with agents in reviewed roles | Each skill's `scripts/` and `roles/` | Work that spans several agents | Each workflow's skill; shared run commands in [run-commands](/agent-skills/modules/run-commands.md) |
| Harness: the engine the workflow scripts, `delegate-work`, `handoff` and `crew` call | `agent-skills/harness/` | Changing how agents, gates, injection or workflow definitions run | [Harness README](/agent-skills/harness/README.md); goals and decisions in [harness goal](/agent-skills/harness-goal.md) |
| Repo library: a repository's own procedures and modules | `repo-library/` in each repository that needs one | A procedure repeats in that repository | [`repo-library` skill](/agent-skills/skills/repo-library/SKILL.md) |
| Upkeep rules for every document change | The `repo-maintenance` skill | Every change that touches a BKF repository's documents | [`repo-maintenance` skill](/agent-skills/skills/repo-maintenance/SKILL.md) |
| Feedback and ideas logs | `bkf/feedback.md`, `bkf/ideas.md` | Recording a problem or an idea for later review, never read during ordinary work | [BKF agent instructions](/bkf/AGENTS.md) |
| Records of past runs | `records/` | Only when the user points to a past run | [Agent instructions](/AGENTS.md) |
| Installation on a machine | `INSTALL.md` | A new machine, or after pulling new commands | [Install guide](/INSTALL.md) |

## Common tasks

| Task | Start here |
| --- | --- |
| Organize a new repository under BKF, or revamp an outdated one | [Build a repo's organization](/bkf/manual/build-repo-organization.md) |
| Decide whether BKF fits a repository | [Why BKF](/bkf/manual/why-bkf.md) |
| Change a document in this or any BKF repository | [`repo-maintenance` skill](/agent-skills/skills/repo-maintenance/SKILL.md) |
| Add or change a skill | [`skill-authoring` skill](/agent-skills/skills/skill-authoring/SKILL.md), then `bkf skills --write` |
| Add or change a module | [Modules map](/agent-skills/modules/MAP.md), then `bkf skills --write` |
| Add or change a hook or a `bkf` command | [Tooling map](/bkf/tooling/MAP.md): the files to change and the commands to run |
| Change how workflows run | [Harness README](/agent-skills/harness/README.md) |
| Change the format | [Specification](/bkf/format/format-specification.md) |

---
name: skill-authoring
description: Create and maintain agent skills.
---

# Skill mechanics

This skill owns skill packaging, invocation, and resource boundaries.

### Invocation

- **Model-invoked:** set neither marker. The description is always available for automatic selection, and the user can still invoke the skill by name.
- **User-invoked:** set both `disable-model-invocation: true` in `SKILL.md` (Claude Code: the skill runs only through `/name`) and `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (Codex). Use this when the workflow should run only when the human explicitly asks for it.
- **Exception:** a skill that a hook or another skill tells an agent to follow stays model-invoked, so it sets only the Codex marker. Add it to `AGENT_INVOKED_SKILLS` in `bkf/tooling/skill_catalog_common.py` with the reference that makes it agent-invoked; `bkf skills --check` enforces the pairing.

### Frontmatter and description

Every skill needs a lowercase hyphen-case `name` matching its directory and a concise `description`. The description should state:

- the capability the skill provides;
- the situations that should trigger it;
- an important boundary when similar tasks should not trigger it.

Keep routing information in the description and execution instructions in the body. Do not use the description as a miniature manual.

### Splitting and routing

Choose the file structure from the work the skill must guide:

- Keep everything in `SKILL.md` when the skill has one compact workflow and
  most of its guidance applies to every invocation. A single file is easier to
  follow when there is no useful branch-specific reading to avoid.
- Add reference files when the skill has substantial guidance for distinct
  branches, stages, or artifact types, and an agent can load only the guidance
  needed for the current task. Do not split only to shorten `SKILL.md` or sort
  related topics into separate files.

### Skills that share a module

A rule that several skills need lives once in `agent-skills/modules/`. A module that every run of the skill needs, and that is short, is better injected than linked: an agent that is only told to read a file may not. Write `<!-- inject: ../../modules/name.md -->` on a line of its own where the text belongs; [`bkf skills`](../../../bkf/tooling/commands.md#bkf-skills) reports the block stale when the module changes and `bkf skills --write` fills it (frontmatter left out, headings one level lower) and regenerates the skill catalog. Link a module instead when only some uses of the skill need it, or when it is long. A role guide inside a skill (`roles/`) injects with the same line, with the path relative to the guide.

### Bundled scripts

When a skill bundles scripts that generate files or folders, the script is the
source of truth: do not copy its templates or full output into `SKILL.md`.
Document how to run it, a brief map of its output, and what the agent does
afterward. Read [Script-backed skills](references/script-backed-skills.md)
when authoring or reviewing a skill that includes scripts, before drafting the
instructions that describe them.

### Before publishing

Verify that `bkf skills` passes.

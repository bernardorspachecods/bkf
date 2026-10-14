---
name: skill-authoring
description: Create and maintain agent skills.
---

# Skill mechanics

Use [Writing principles](../../library/modules/writing-principles.md) when selecting content,
drafting, and reviewing skill instructions and references. This skill owns
skill packaging, invocation, and resource boundaries.

### Invocation

- **Model-invoked:** omit `disable-model-invocation`. The description is a context pointer that is always available for automatic selection, and the user can still invoke the skill by name.
- **User-invoked:** set `policy.allowimplicitinvocation: false` in `agents/openai.yaml`. Use this when the workflow should run only when the human explicitly asks for it.

Keep automatic skills' descriptions narrow enough to avoid competing with similar skills.

Keep invocation policy in `agents/openai.yaml`; do not add unsupported invocation fields to `SKILL.md` frontmatter.

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

When a skill has references, `SKILL.md` remains its complete entry point and
workflow owner. It states the skill's purpose and boundaries, gives the shared
rules and overall sequence, explains how to choose the applicable path, and
directs the agent to the additional instructions needed to complete it. Do not
leave a required decision, shared rule, or workflow transition implicit in a
reference that an agent may not load.

Organize references around coherent work paths, such as a lifecycle stage or a
specialized artifact. Keep shared rules in one canonical location and avoid
repeating them across files. Link every authored package file from `SKILL.md`,
with a clear condition for reading it and the point in the workflow when it is
needed.

### Bundled scripts

When a skill bundles scripts that generate files or folders, the script is the
source of truth: do not copy its templates or full output into `SKILL.md`.
Document how to run it, a brief map of its output, and what the agent does
afterward. Read [Script-backed skills](references/script-backed-skills.md)
when authoring or reviewing a skill that includes scripts, before drafting the
instructions that describe them.

### Final checks

Before publishing, verify that:

- frontmatter parses and the name matches the directory;
- the description is specific and routes the intended cases;
- every relative reference exists;
- every authored package file is linked from `SKILL.md`; package validation
  must check that all files are reachable through those links;
- invocation policy matches the intended human/agent ownership;
- the skill does not duplicate a stronger source of truth or impose process on unrelated work.
- instructions for bundled scripts do not restate output the scripts already define.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

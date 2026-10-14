---
bkf: document
description: Specifies the bkf sync preview and write contract for first-time scaffolding and reconciling later declaration changes, including file matching, path renames, and orphan reporting. It also covers the declaration parser and ID allocator it uses.
tags: [bkf, tooling, workflows, synchronization]
---

# Workflow Synchronizer

## Responsibility

Bring workflow files in line with the declaration, including the first time,
when the workflow has not yet been scaffolded. The
[workflow foundation](/format/agent-workflow-foundation.md#syncing-after-the-declaration-changes)
owns why and when; this brief owns what the command does.

- Match files to declaration entries by the `stage_id`, `stage_ids`, or
  `work_unit_id` in frontmatter, not by name, so a drifted or renamed file is
  still found.
- Create missing files for new entries with newly allocated IDs.
- On the first run, create the workflow folder, named from the allocated
  workflow ID and the parent's top-level heading, move the parent into it, and
  generate the ordered work-unit folders, optional `WORK-UNIT.md` files, stage
  files, and shared files with their workflow profiles. Names follow the
  [workflow foundation](/format/agent-workflow-foundation.md#composition-ordering-and-identity),
  which owns the naming rules.
- Recompute each file and folder name from the declaration (order prefix,
  title slug) and rename drifted paths, in two phases to avoid collisions.
- When a stage joins an existing shared file, update its `stage_ids` and tell
  the agent to add the section.
- Report orphans: files whose IDs are not in the declaration.
- Never delete a file and never edit a shared-file body.

## Interface

Before planning anything, sync runs the shared declaration checks (see the
[shared modules](#shared-modules)) and changes nothing if
they fail. Run `bkf sync <parent-file>` to preview; the preview is the default.
For an unscaffolded parent, the plan includes the workflow folder, moving the
parent into it, assigning IDs, and creating generated files. Add `--write` to
apply the plan.

When a rename is planned while a work unit is `in_progress`, sync warns and
requires `--confirm-in-progress` with `--write`. A plan that only adds files
needs no confirmation. It prints the changed paths and leaves references to
renamed paths for the agent to update.

## Shared modules

Sync, scaffold, and the validator share two internal modules; neither is a
command.

- **Declaration parser.** `workflow_declaration.py` parses exactly one fenced
  `bkf-workflow` YAML block from a workflow parent, allocates missing IDs in
  declared order, and resolves `key` references in `reviews` and `after` to
  IDs. It preserves round-trip YAML comments and formatting as far as ruamel
  supports it and leaves the rest of the Markdown intact.
  `workflow_declaration_checks.py` holds the declaration-only checks (structure,
  keys, `reviews`, `after`) shared by the validator and sync, so the rules have
  one implementation and the same messages. Syntax and conformance criteria are
  owned by the workflow foundation.
- **ID allocator.** `workflow_ids.py` allocates `W`, `WU`, and `ST`
  identifiers without a ledger: it scans every bundle Markdown member for
  mentions of the requested kind and allocates the next number within the
  parent's scope. An identifier may be reused after its last mention
  disappears, and a segment above 99 is an error. Workflow folder creation
  reserves its candidate atomically; on collision the scaffold retries with the
  next available workflow ID.

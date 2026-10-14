---
description: Defines the BKF command interfaces and implements tools that generate inventories, validate bundles, and synchronize workflows.
---

# BKF Tooling Map

Start with `commands.md` for the installed CLI; the synchronizer brief covers
`bkf sync`, and the implementation files are linked below.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Explains how to install the central bkf command and what bkf validate, bkf inventory, bkf orient, bkf search, bkf log, and bkf hooks do: invocation, options, and exit status. The rules they apply are owned by the specification and profiles; bkf sync is in workflow-synchronizer.md. | [commands.md](/tooling/commands.md) |
| Specifies the bkf sync preview and write contract for first-time scaffolding and reconciling later declaration changes, including file matching, path renames, and orphan reporting. It also covers the declaration parser and ID allocator it uses. | [workflow-synchronizer.md](/tooling/workflow-synchronizer.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

## Artifact references

- [generate_inventory.py](/tooling/generate_inventory.py) — Implements preview, check, and write modes for BKF member inventories.
- [bkf_common.py](/tooling/bkf_common.py) — Shares frontmatter parsing and map-scope logic across BKF tools.
- [validate_bundle.py](/tooling/validate_bundle.py) — Checks BKF bundle structure, metadata, maps, and links.
- [workflow_ids.py](/tooling/workflow_ids.py) — Allocates workflow, work-unit, and stage IDs by scanning bundle Markdown mentions.
- [workflow_declaration_checks.py](/tooling/workflow_declaration_checks.py) — Applies the declaration-only checks shared by the validator and sync.
- [workflow_declaration.py](/tooling/workflow_declaration.py) — Parses workflow declarations, assigns IDs, and resolves keyed references.
- [workflow_files.py](/tooling/workflow_files.py) — Builds generated workflow paths and frontmatter for scaffold and sync.
- [workflow_scaffold.py](/tooling/workflow_scaffold.py) — Creates workflow folders and files from a parent declaration.
- [workflow_sync.py](/tooling/workflow_sync.py) — Previews or applies declaration-driven workflow file synchronization.
- [workflow_validation.py](/tooling/workflow_validation.py) — Applies the workflow foundation's validation checks.
- [hook_events.py](/tooling/hook_events.py) — Records the files a session edits and checks their bundles when it stops.
- [bkf_hooks.py](/tooling/bkf_hooks.py) — Previews, installs, and reports the agent prefix-mode and orientation hooks for Claude Code and Codex.
- [agent_modes.py](/tooling/agent_modes.py) — Implements the `w:` and `t:` prompt-prefix hook, copied to the user's home on install.
- [bkf_cli.py](/tooling/bkf_cli.py) — Dispatches the installed `bkf` command to the focused tooling modules.
- [pyproject.toml](/tooling/pyproject.toml) — Declares the installable BKF tooling package, dependencies, and `bkf` command entry point.
- [orient.py](/tooling/orient.py) — Prints the map chain and validation health for session-start orientation.
- [search.py](/tooling/search.py) — Searches indexed BKF document sections with an in-memory FTS5 index.
- [log_entry.py](/tooling/log_entry.py) — Appends user ideas and feedback to the selected bundle's ideas or feedback file.
- [requirements.txt](/tooling/requirements.txt) — Declares YAML and Markdown parser dependencies for BKF tooling.

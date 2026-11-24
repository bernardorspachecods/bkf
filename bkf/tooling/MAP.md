---
description: Defines the BKF command interfaces and implements tools that generate inventories, and validate bundles.
---

# BKF Tooling Map

Start with `bkf help` for the command list and `commands.md` for the installed
CLI. The implementation files are linked below.

To run the tests, use the commands below from the repository root; they assume
`bkf` is installed per `INSTALL.md`. The tooling tests need the dependencies in
the installed tool's environment, so plain `python3` does not run them. The
installed tool imports the checkout it was installed from: in another checkout
or a linked worktree, set `PYTHONPATH=bkf/tooling` so the tests run this code.

```sh
PYTHONPATH=bkf/tooling "$(uv tool dir)/bkf-tooling/bin/python3" -m unittest discover -s bkf/tooling/tests
```

To add or change a hook:

1. Register it in `registrations()` in [bkf_hooks.py](/bkf/tooling/bkf_hooks.py); a new group also goes in `HOOK_NAMES`, which sets the `--only` choices. Add a probe case in `_probe_command` if the hook needs special probe input, because `install --write` and `status` run every registered command with probe input.
2. Handle its `bkf hooks run <event>` in [hook_events.py](/bkf/tooling/hook_events.py), as every event but `rules` is: the event name in `EVENTS`, a branch in `main`, and a case in `_probe`, which rejects an event it does not know. Put a substantial handler in its own module.
3. Add a new module to `py-modules` in [pyproject.toml](/bkf/tooling/pyproject.toml) and to the artifact references below; the installed command fails with `ModuleNotFoundError` until it is reinstalled with `--reinstall`.
4. Add tests in `tests/test_hooks.py` and `tests/test_hook_events.py`.
5. Describe the behavior in the [`bkf hooks` section](/bkf/tooling/commands.md#bkf-hooks), its only owner, including the group list in its usage line.
6. Run the tests, reinstall, then `bkf hooks install` to preview, `bkf hooks install --write` and `bkf hooks status`.

To add a command, give it an entry in `COMMANDS` in [bkf_cli.py](/bkf/tooling/bkf_cli.py), which also feeds `bkf help`, and a section and a navigation-map row in [commands.md](/bkf/tooling/commands.md); steps 3, 4 and the tests of step 6 apply as for a hook.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Explains how to install the central bkf command and documents each subcommand's invocation, options, and exit status. The command list is `bkf help`; the rules they apply are owned by the specification and profiles. | [commands.md](/bkf/tooling/commands.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

## Artifact references

- [generate_inventory.py](/bkf/tooling/generate_inventory.py) — Implements preview, check, and write modes for BKF member inventories.
- [skills.py](/bkf/tooling/skills.py) — Combines inventory, injected-text, and skill-catalog checks and writes for `bkf skills`.
- [skill_catalog_common.py](/bkf/tooling/skill_catalog_common.py) — Validates skill packages and generates the skill catalog.
- [relink.py](/bkf/tooling/relink.py) — Shares the link rewriting for `bkf mv` and `bkf relink`: Markdown and HTML link rules, bundle file discovery, and the move application.
- [bkf_mv.py](/bkf/tooling/bkf_mv.py) — Implements `bkf mv`: validates the move, runs `git mv`, rewrites links, and refreshes inventories.
- [bkf_upgrade.py](/bkf/tooling/bkf_upgrade.py) — Implements `bkf upgrade`: migrates bundles to format 0.2 by prefixing nested bundles' links with their path from the outermost root and setting `bkf_version`.
- [bkf_relink.py](/bkf/tooling/bkf_relink.py) — Implements `bkf relink`: finds moves by git rename detection, applies `--map` moves, reports unresolved links, and sets its exit statuses.
- [generate_skill_catalog.py](/bkf/tooling/generate_skill_catalog.py) — Writes or prints the generated skill catalog.
- [validate_skill_catalog.py](/bkf/tooling/validate_skill_catalog.py) — Validates skill metadata and catalog consistency.
- [bkf_common.py](/bkf/tooling/bkf_common.py) — Shares frontmatter parsing and map-scope logic across BKF tools.
- [navigation_map.py](/bkf/tooling/navigation_map.py) — Parses a document's `## Navigation map` table and checks it against the document's headings; shared by `bkf validate` and the guard hook.
- [validate_bundle.py](/bkf/tooling/validate_bundle.py) — Checks BKF bundle structure, metadata, maps, and links.
- [updates.py](/bkf/tooling/updates.py) — Prints the format update documents needed by one or more BKF bundles.
- [hook_events.py](/bkf/tooling/hook_events.py) — Handles the `bkf hooks run` events: snapshots and records session edits, checks their bundles when the session stops, gives the agent the resulting warnings with its next prompt, and dispatches the `log`, `guard`, `audit`, and `sources` hooks.
- [session_number.py](/bkf/tooling/session_number.py) — Chooses the `<repo><N>` name (`bkf1`, `bkf2`) that the `tabname` hook gives an interactive Claude session on its first prompt.
- [task_session.py](/bkf/tooling/task_session.py) — Links interactive Claude sessions to cards in the task store: creates and owns implicit session cards, safely backfills an explicit task's missing current UUID, and names implicit cards from their first prompt.
- [bkf_hooks.py](/bkf/tooling/bkf_hooks.py) — Previews, installs, and reports the eleven hook groups (modes, orient, check, log, rules, task, guard, audit, tabname, sources, context) for Claude Code and Codex.
- [context_hook.py](/bkf/tooling/context_hook.py) — Warns before context compaction and restores the session continuation note after compaction.
- [default_rules.txt](/bkf/tooling/default_rules.txt) — Holds the default standing rules that `bkf hooks install --write` copies to `~/.agent-hooks/rules.md` when that file is missing.
- [agent_modes.py](/bkf/tooling/agent_modes.py) — Implements the `w:`, `t:` and `g:` prompt-prefix hook and the `git stash` block, copied to the user's home on install.
- [bkf_cli.py](/bkf/tooling/bkf_cli.py) — Dispatches the installed `bkf` command to the focused tooling modules.
- [pyproject.toml](/bkf/tooling/pyproject.toml) — Declares the installable BKF tooling package, dependencies, and `bkf` command entry point.
- [orient.py](/bkf/tooling/orient.py) — Prints the map chain and validation health for session-start orientation.
- [search.py](/bkf/tooling/search.py) — Searches indexed BKF document sections with an in-memory FTS5 index.
- [search_attached.py](/bkf/tooling/search_attached.py) — Loads attached-text search configuration and cuts sidecars into located passages.
- [bkf_sources.py](/bkf/tooling/bkf_sources.py) — Handles the sources command arguments and exit statuses.
- [source_hooks.py](/bkf/tooling/source_hooks.py) — Looks up and captures sources during Claude Code web tool calls.
- [source_page.py](/bkf/tooling/source_page.py) — Fetches HTML and extracts source metadata and readable text.
- [source_record.py](/bkf/tooling/source_record.py) — Defines source record ids, metadata, and claim validation.
- [source_store.py](/bkf/tooling/source_store.py) — Provides the store API, catalog updates, and Git commits.
- [bkf_launch.py](/bkf/tooling/bkf_launch.py) — Opens an interactive Claude or Codex session in tmux with its task card, worktree and prompt copy.
- [bkf_task.py](/bkf/tooling/bkf_task.py) — Handles the task command arguments and the exit statuses.
- [task_store.py](/bkf/tooling/task_store.py) — Owns the machine-wide store of agent tasks: one folder per task, atomic locked writes, the task transitions, and the one-time migration of the legacy statuses.
- [merge_store.py](/bkf/tooling/merge_store.py) — Holds the merge queue of a repository: its schema 1 file, the turn rules, and the recovery of a stale turn or a dormant waiter; changes no git state or card.
- [merge_git.py](/bkf/tooling/merge_git.py) — Reads the git state the merge queue checks (heads, cleanliness, ancestry, the target branch) and fast-forwards the target on land.
- [bkf_merge.py](/bkf/tooling/bkf_merge.py) — Implements `bkf merge`: the queue commands, their exit statuses, and the status JSON the app reads.
- [task_tmux.py](/bkf/tooling/task_tmux.py) — Opens a window for a task's shell command in tmux, iTerm2 or Terminal.app, grouped by repository, and names each repository's tmux session.
- [task_worktree.py](/bkf/tooling/task_worktree.py) — Creates or reuses the git worktree of a task under the main checkout's `.claude/worktrees` and records it on the task.
- [audit.py](/bkf/tooling/audit.py) — Builds the whole-repository report of git changes and bundle health that the `bkf:` prompt prefix returns.
- [read_guard.py](/bkf/tooling/read_guard.py) — Denies the first whole-file read of a large Markdown document with a navigation map and returns the map's section links.
- [log_entry.py](/bkf/tooling/log_entry.py) — Appends user ideas and feedback to the selected bundle's ideas or feedback file.
- [requirements.txt](/bkf/tooling/requirements.txt) — Declares YAML and Markdown parser dependencies for BKF tooling.

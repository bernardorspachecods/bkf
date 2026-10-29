---
description: Defines the BKF command interfaces and implements tools that generate inventories, and validate bundles.
---

# BKF Tooling Map

Start with `bkf help` for the command list and `commands.md` for the installed
CLI. The implementation files are linked below.

To run the tests, use the commands below from the repository root; they assume
`bkf` is installed per `INSTALL.md`. The tooling tests need the dependencies in
the installed tool's environment, so plain `python3` does not run them.

```sh
"$(uv tool dir)/bkf-tooling/bin/python3" -m unittest discover -s bkf/tooling/tests
```

To add or change a hook:

1. Register it in `registrations()` in [bkf_hooks.py](/tooling/bkf_hooks.py); a new group also goes in `HOOK_NAMES`, which sets the `--only` choices. Add a probe case in `_probe_command` if the hook needs special probe input, because `install --write` and `status` run every registered command with probe input.
2. Handle its `bkf hooks run <event>` in [hook_events.py](/tooling/hook_events.py), as every event but `rules` is: the event name in `EVENTS`, a branch in `main`, and a case in `_probe`, which rejects an event it does not know. Put a substantial handler in its own module.
3. Add a new module to `py-modules` in [pyproject.toml](/tooling/pyproject.toml) and to the artifact references below; the installed command fails with `ModuleNotFoundError` until it is reinstalled with `--reinstall`.
4. Add tests in `tests/test_hooks.py` and `tests/test_hook_events.py`.
5. Describe the behavior in the [`bkf hooks` section](/tooling/commands.md#bkf-hooks), its only owner, including the group list in its usage line.
6. Run the tests, reinstall, then `bkf hooks install` to preview, `bkf hooks install --write` and `bkf hooks status`.

To add a command, give it an entry in `COMMANDS` in [bkf_cli.py](/tooling/bkf_cli.py), which also feeds `bkf help`, and a section and a navigation-map row in [commands.md](/tooling/commands.md); steps 3, 4 and the tests of step 6 apply as for a hook.

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Explains how to install the central bkf command and documents each subcommand's invocation, options, and exit status. The command list is `bkf help`; the rules they apply are owned by the specification and profiles. | [commands.md](/tooling/commands.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

## Artifact references

- [generate_inventory.py](/tooling/generate_inventory.py) — Implements preview, check, and write modes for BKF member inventories.
- [skills.py](/tooling/skills.py) — Combines inventory, injected-text, and skill-catalog checks and writes for `bkf skills`.
- [skill_catalog_common.py](/tooling/skill_catalog_common.py) — Validates skill packages and generates the skill catalog.
- [generate_skill_catalog.py](/tooling/generate_skill_catalog.py) — Writes or prints the generated skill catalog.
- [validate_skill_catalog.py](/tooling/validate_skill_catalog.py) — Validates skill metadata and catalog consistency.
- [bkf_common.py](/tooling/bkf_common.py) — Shares frontmatter parsing and map-scope logic across BKF tools.
- [navigation_map.py](/tooling/navigation_map.py) — Parses a document's `## Navigation map` table and checks it against the document's headings; shared by `bkf validate` and the guard hook.
- [validate_bundle.py](/tooling/validate_bundle.py) — Checks BKF bundle structure, metadata, maps, and links.
- [updates.py](/tooling/updates.py) — Prints the format update documents needed by one or more BKF bundles.
- [hook_events.py](/tooling/hook_events.py) — Handles the `bkf hooks run` events: snapshots and records session edits, checks their bundles when the session stops, gives the agent the resulting warnings with its next prompt, and dispatches the `log`, `guard`, and `audit` hooks.
- [bkf_hooks.py](/tooling/bkf_hooks.py) — Previews, installs, and reports the seven hook groups (modes, orient, check, log, rules, guard, audit) for Claude Code and Codex.
- [default_rules.txt](/tooling/default_rules.txt) — Holds the default standing rules that `bkf hooks install --write` copies to `~/.agent-hooks/rules.md` when that file is missing.
- [agent_modes.py](/tooling/agent_modes.py) — Implements the `w:` and `t:` prompt-prefix hook and the `git stash` block, copied to the user's home on install.
- [bkf_cli.py](/tooling/bkf_cli.py) — Dispatches the installed `bkf` command to the focused tooling modules.
- [pyproject.toml](/tooling/pyproject.toml) — Declares the installable BKF tooling package, dependencies, and `bkf` command entry point.
- [orient.py](/tooling/orient.py) — Prints the map chain and validation health for session-start orientation.
- [search.py](/tooling/search.py) — Searches indexed BKF document sections with an in-memory FTS5 index.
- [audit.py](/tooling/audit.py) — Builds the whole-repository report of git changes and bundle health that the `bkf:` prompt prefix returns.
- [read_guard.py](/tooling/read_guard.py) — Denies the first whole-file read of a large Markdown document with a navigation map and returns the map's section links.
- [log_entry.py](/tooling/log_entry.py) — Appends user ideas and feedback to the selected bundle's ideas or feedback file.
- [requirements.txt](/tooling/requirements.txt) — Declares YAML and Markdown parser dependencies for BKF tooling.

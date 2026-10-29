# Install

Run core setup from the repository root. Requirements are `uv` and Python 3.10 or later.

## Core install

1. Install the editable command:

   ```sh
   uv tool install --editable ./bkf/tooling
   ```

   Expected result: `bkf` is installed from this checkout, with its executable under `~/.local/bin`. If `bkf` is not found, run `uv tool update-shell` and reopen the shell. If the checkout moves, reinstall from its new location. After pulling a checkout that adds commands or dependencies, run the same install command with `--reinstall` so the new command is picked up.

2. Check whether the skill-link paths already exist before creating them. An existing real folder must be merged or moved first; do not overwrite it. From the repository root, use absolute targets. Choose the pair for your agent:

   Claude Code:

   ```sh
   ln -s "$PWD/agent-skills/skills" ~/.claude/skills
   ln -s "$PWD/agent-skills/modules" ~/.claude/modules
   ```

   Codex:

   ```sh
   ln -s "$PWD/agent-skills/skills" ~/.agents/skills
   ln -s "$PWD/agent-skills/modules" ~/.agents/modules
   ```

   Expected result: the two skill paths point to `agent-skills/skills` and `agent-skills/modules`; the skills' `../../modules/` links resolve through the modules link.

3. Check the repository from its root:

   ```sh
   bkf validate .
   bkf inventory . --check
   ```

   Expected result: both checks succeed.

## Optional: hooks

4. Preview hook installation:

   ```sh
   bkf hooks install
   ```

   Expected result: a preview reports each hook script and registration as `ok`, `missing`, or `differs`; it makes no changes.

5. Apply the installation when the preview is as intended:

   ```sh
   bkf hooks install --write
   ```

   Expected result: hooks are registered in `~/.claude/settings.json` and `~/.codex/hooks.json` where those tools are present, and hook files are placed under `~/.agent-hooks/`. Installation creates `~/.agent-hooks/rules.md` from BKF's default rules only when the file is missing, and never overwrites it; after that the file is yours to edit. The `--only modes|orient|check|log|rules|guard|audit` option limits installation to selected groups, and `--home PATH` targets another home directory.

   What each hook group does is in the [`bkf hooks` reference](bkf/tooling/commands.md#bkf-hooks). Edit `~/.agent-hooks/rules.md` to hold your own standing instructions; the `rules` hook prints it at every session start and cuts a long file, so keep it short.

6. Report hook status:

   ```sh
   bkf hooks status
   ```

   Expected result: status and probe results are reported for installed hooks. `status` returns 1 when a hook script or registration is not `ok`. The `rules` file entry reports `missing` only when you have deleted `~/.agent-hooks/rules.md`; that does not change the exit status. After the first install, Codex asks for a one-time review; run `/hooks` in Codex.

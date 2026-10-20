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
   ln -s "$PWD/agent-skills/library" ~/.claude/library
   ```

   Codex:

   ```sh
   ln -s "$PWD/agent-skills/skills" ~/.agents/skills
   ln -s "$PWD/agent-skills/library" ~/.agents/library
   ```

   Expected result: the two skill paths point to `agent-skills/skills` and `agent-skills/library`; the skills' `../../library/` links resolve through the library link.

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

   The seven groups are:

   - `modes` sets per-session talk or work mode from prompt prefixes. In talk mode (`t:`), the hook denies file edits and any shell command it cannot show to be read-only.
   - `orient` adds bundle orientation at session start.
   - `check` validates changed bundles and checks their inventories when a session stops. A failing check blocks the stop and gives the agent the output; it blocks at most twice per session. Warnings never block: the group also registers a `UserPromptSubmit` hook that gives the agent the warnings about files it changed, once, with the next prompt.
   - `log` records idea and feedback entries from prompt prefixes, and saves the agent's last message so an entry can quote it.
   - `guard` denies the first whole-file read of a large Markdown document that has a `## Navigation map`, and returns the map's section links instead. A second whole-file read in the same session is allowed.
   - `audit` answers a prompt that starts with `bkf:` with a structure audit of the whole repository: git changes (staged, modified, deleted, untracked) grouped by bundle, plus validation and inventory status for every bundle. The agent sees a short summary and the path of the full report in `~/.agent-hooks/reports/`; the prompt itself still reaches the agent.
   - `rules` prints your `~/.agent-hooks/rules.md` at every session start, so the agent sees your standing instructions before the first prompt. BKF ships default rules (`bkf/tooling/default_rules.txt`) that installation copies the first time; replace or trim them as you like. Long files are cut at a line boundary, so keep it short; the [limit](bkf/tooling/commands.md#bkf-hooks) is set by the hook.

6. Report hook status:

   ```sh
   bkf hooks status
   ```

   Expected result: status and probe results are reported for installed hooks. `status` returns 1 when a hook script or registration is not `ok`. The `rules` file entry reports `missing` only when you have deleted `~/.agent-hooks/rules.md`; that does not change the exit status. After the first install, Codex asks for a one-time review; run `/hooks` in Codex.

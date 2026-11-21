---
bkf: document
description: "Explains how to install the central bkf command and documents each subcommand's invocation, options, and exit status. The command list is `bkf help`; the rules they apply are owned by the specification and profiles."
tags: [bkf, tooling, installation, validation, map-inventory]
---

# The bkf command

## Navigation map

| If you need to... | See |
| --- | --- |
| Install the command or list its subcommands | [Install](#install) and [bkf help](#bkf-help) |
| Check a bundle against the format | [bkf validate](#bkf-validate) |
| Refresh a map's member inventory | [bkf inventory](#bkf-inventory) |
| Check or write the skill catalog | [bkf skills](#bkf-skills) |
| Record an idea or feedback entry | [bkf log](#bkf-log) |
| Print the format update documents a bundle needs | [bkf updates](#bkf-updates) |
| Orient an agent at session start | [bkf orient](#bkf-orient) |
| Install, check, or understand the hooks | [bkf hooks](#bkf-hooks) |
| Search the documents | [bkf search](#bkf-search) |
| Register, reopen, close, or check researched sources | [bkf sources](#bkf-sources) |
| Record, read, or change agent tasks | [bkf task](#bkf-task) |
| Read the text of a task's tmux window | [bkf task output](#bkf-task) |
| Send text to a task's tmux window | [bkf task send](#bkf-task) |
| Open an agent session in tmux with its task card | [bkf launch](#bkf-launch) |
| Queue a session's branch to land on the target, one at a time | [bkf merge](#bkf-merge) |

## Install

The package is maintained in this directory. Install it in editable mode so
the `bkf` command uses this checkout and its declared dependencies; bundle
repositories need no copies of the scripts. From the BKF source repository:

```sh
uv tool install --editable ./bkf/tooling
```

The executable is installed under `~/.local/bin`. If `bkf` is not found, run
`uv tool update-shell` and reopen the shell, or call `~/.local/bin/bkf`. In a
checkout without the installed command, use `bkf/tooling/.venv/bin/bkf`. If the
checkout moves, reinstall from the new path.

The editable install records the `py-modules` list in `pyproject.toml` when it
is created. After adding or renaming a module there, a command fails with
`ModuleNotFoundError` until each install is refreshed: rerun the command above
with `--reinstall`, and for a checkout's `.venv` run
`uv pip install --python bkf/tooling/.venv/bin/python -e bkf/tooling`.

Skills are installed through the symlink `~/.claude/skills`. Create it on a new
machine.

## bkf help

`bkf help` lists commands, summaries, and usage guidance grouped by situation:
after editing documents, session start and lookup, install, and called by
skills and the app. The `help` command appears at the end. `bkf help <command>` shows
that command's options. Both exit with `0`; an unknown command or `help` target
exits with `2`. `COMMANDS` in [bkf_cli.py](/tooling/bkf_cli.py) owns the list,
group assignments, summaries, and `use:` lines. `HELP_GROUPS` in the same file
owns the known groups and their display order; use `bkf help` for the current
list instead of repeating it here.

## bkf validate

`bkf validate <bundle-root>` checks the bundle against its declared BKF version
and prints findings with severity, code, path, and explanation. The rules are
in the [specification](/format/format-specification.md#6-conformance) and the
[frontmatter profiles](/format/frontmatter-profiles.md). It does not check body quality or style, fragment targets
(except the links of a `## Navigation map`), linked artifact contents, or remote URLs (URL syntax only).

- Exit `0`: conformant with the supported version. `1`: non-conformant. `2`: the
  bundle path was invalid, or the declared version is unsupported and
  best-effort checks could not establish conformance.
- An older declared version gets best-effort validation, and its finding MUST
  tell the agent to run `bkf updates <bundle-root>` on that bundle. An
  unrecognized version gets best-effort validation, and the finding says
  whether to update the validator or move the bundle to a supported version.
- Nested bundles (see [nested bundles](/format/format-specification.md#33-nested-bundles))
  are validated from their own roots with findings grouped by bundle; the exit
  status is the highest. `--this-bundle` skips them.
- A tracked description containing `open when` or `use when` is a warning, as
  is a document over 350 body lines or 2,000 words without a `## Navigation
  map` table (`NAVIGATION_MAP_REVIEW`). A document with that table gets
  `NAVIGATION_MAP_STALE` for a link to a heading that does not exist, a level 2
  section no row reaches, or a table without rows, whatever its size
  ([specification §4](/format/format-specification.md#4-bkf-documents-and-profiles)).
  The `feedback` and `ideas` logs are exempt from the navigation map warnings.
  When any navigation map warning is printed, one paragraph on writing the map
  ends the findings.
- A `MAP.md` that is neither the bundle root nor a nested bundle root gets
  `MAP_TOO_SMALL` when it covers 4 or fewer items: its tracked documents and
  child maps in scope, plus its artifact references and `## Task routes` rows.
  The finding asks the agent to delete the map when its parent can list the
  contents, or to ask the user when that is not obvious. It is a warning, and
  the stop hook gives it to the agent for changed `MAP.md` files.
- A bundle with a `tag-vocabulary.yaml` gets `TAG_VOCABULARY_INVALID` for an
  unusable file and `TAG_UNKNOWN` for each tag that is not a canonical tag
  ([frontmatter profiles](/format/frontmatter-profiles.md#tag-vocabulary)).
- A [notes file](/format/format-specification.md#35-notes-files) with a `bkf`
  field is `NOTES_TRACKED`, and a link to one from a document or a map is
  `NOTES_LINKED`; both are errors. The validator reads only a notes file's
  frontmatter, and frontmatter it cannot parse is not a finding.
- `REPO_LIBRARY_ENTRY_UNLINKED` warns when no enclosing-bundle document outside
  `repo-library/` links to a Markdown entry.
- `AGENT_INSTRUCTIONS_LONG` warns when an `AGENTS.md` or `CLAUDE.md` anywhere in
  the bundle has a body over 250 words (frontmatter not counted), because agent
  harnesses load these files into every session. The finding says to move rules
  a hook or script can check into that hook or script, and detail into the
  document that owns it, leaving a pointer.

## bkf updates

`bkf updates [PATH]...` finds every bundle under each path, including a bundle
at the path itself and nested bundles, using the same bundle discovery as
`bkf validate`. With no paths, it uses `.`. It reports every found bundle in
one run. For each bundle, it prints the bundle path, its declared version, the
version supported by the installed `bkf`, and one status:

- `current`: say the bundle is up to date.
- `behind`: print the applicable update documents, oldest target version
  first. Read and print their contents from the installed checkout's
  `bkf/updates/`, placing each under a header that names its target version.
  If no update document exists for the supported version, report a repository
  defect as an error.
- `ahead`: say the installed `bkf` is older than the bundle and the checkout
  should be updated. Do not print update documents.

Applicable update documents have target versions greater than the bundle's
declared version and no greater than the installed `bkf` version. The update
file rules are in the
[format specification](/format/format-specification.md#31-map-files-and-inventories).

Exit `0` means every bundle is `current`. Exit `1` means at least one bundle
is `behind` or `ahead`, or a behind bundle has no update document for the
supported version, or no BKF bundles were found under the searched paths.
Exit `2` means the command was invoked with invalid usage.

## bkf inventory

`bkf inventory <bundle-root>` previews a unified diff for every stale map
inventory. `--write` updates the maps; `--check` fails when any is stale. The
root must contain its `MAP.md`; nested maps and nested bundles are processed in
the same run, and `--this-bundle` limits it to the selected bundle.

It validates every map and in-scope tracked member before writing anything, and
follows the table, ordering, marker, and line-ending rules of the
[specification](/format/format-specification.md#31-map-files-and-inventories).
For child-map rows, it reads the map's `description`. A missing, empty, or
non-string description stops generation with an error naming the map; the
validator reports the same condition as an error. The required map fields are
owned by the [map specification](/format/format-specification.md#31-map-files-and-inventories).

`--skills <skills-dir>` also expands the inject directives of the `SKILL.md` files in that directory. From the repository root, `bkf inventory agent-skills/modules --skills agent-skills/skills --write` refreshes them; use the same invocation with `--check` to verify.

With `--skills`, a line `<!-- inject: path -->` in a skill (the path is relative to the
skill file and names a Markdown file) is followed by a generated block, between
`<!-- BKF:GENERATED-INJECTED -->` and `<!-- BKF:GENERATED-INJECTED-END -->`, holding the
file's text without its frontmatter, with headings one level lower and relative links
rebased to the skill. A bundle-root link (`/...`) in the file stops generation with an error,
because it would not resolve from the skill. The block is replaced when the source changes, and
`--check` reports the skill stale.

## bkf skills

`bkf skills [REPOSITORY-ROOT] [--check|--write]` checks or regenerates the
agent-skills inventories, injected module text, and skill catalog. The root
defaults to the current directory and must contain `agent-skills/skills`; the modules
check runs only when `agent-skills/modules` exists.

`--check` is the default and never writes. It checks the modules map
inventories and the injected text in skills, then validates skill metadata and links,
runtime metadata, and whether `agent-skills/skill-architecture.md` is current.
It prints both check results and exits non-zero if either check fails.
A `SKILL.md` or `openai.yaml` value without quotes that YAML would reject (it
contains `: `, ends with `:` or starts with `@`, a backtick, `%`, `&`, `*` or
`!`) is a `FRONTMATTER_INVALID` error: quote the value.
A user-invoked skill sets both `disable-model-invocation: true` in `SKILL.md`
(Claude Code) and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`
(Codex). Setting one without the other is an `INVOCATION_MARKERS_MISMATCH` error.
The skills in `AGENT_INVOKED_SKILLS` (`bkf/tooling/skill_catalog_common.py`) are
exempt: a hook or another skill tells an agent to follow them, so they keep the
Codex marker alone. An exempt skill that does not have that pair is an
`INVOCATION_EXEMPTION_STALE` error.

`--write` refreshes the modules map inventory and the injected text, then writes the
generated skill catalog. Use it after changing a skill or a module a skill injects.

## bkf log

`bkf log idea|feedback TEXT [--cwd PATH] [--context TEXT]` inserts one entry
at the top of the selected bundle's `ideas.md` or `feedback.md`, below its
introduction. `--cwd` defaults to the
process directory. `--context` is optional and holds the agent's last message;
the full message is quoted as an excerpt up to 5,000 characters. Longer messages
keep the end, starting at a whitespace boundary, with a first quote line such as
`> [message truncated: 123 earlier characters omitted]` reporting the exact
number omitted.

The target is the nearest enclosing bundle root that contains the selected
file. If none exists above the working directory, the only matching file in a
bundle below it is used. With no target file or several matches, nothing is
written and the command explains why.

An entry includes the date, a heading, the user's working folder, and the
original text when the heading is shortened or spans multiple lines. Inside a
git repository, the working folder is shown as the repository folder followed
by `/` and the relative path (or just the repository folder at its root);
outside git it is the absolute path, with the home directory shortened to `~`.

```md
## 2026-10-13: Add a quick search

Raised by the user, working in my-repo/bkf/tooling.
```

Exit `0` means the entry was written. Exit `1` reports a write or target
selection failure or invalid command arguments.

## bkf orient

`bkf orient [--cwd PATH] [--debug]` prints a short orientation
block for the selected directory. `--cwd` defaults to the process working
directory. The output starts with `orientation (from PATH)`, followed by the
map chain from the outermost bundle root through
the nearest map at or above the directory. Each map path is followed by its
member inventory rows. Output is capped at 6,000 characters; omitted rows are
reported with a `read <map-path>` marker. It does not run validation: the `check`
and `warnings` hooks report findings for the files the session changes (see
[bkf hooks](#bkf-hooks)).

If the
directory is outside a bundle, the command prints nothing. An unexpected failure prints a JSON `systemMessage`
for the user and returns success; `--debug` prints the failure to stderr and
returns 1.

Claude Code can inject the plain stdout from a `SessionStart` command hook as
context. The hook runs on every session source, so orientation survives
`/clear`. Add a hook like this to `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "bkf orient" }
        ]
      }
    ]
  }
}
```

Codex also adds plain stdout from a `SessionStart` hook as developer context.
Its `additionalContext` field is capped at about 2,500 tokens by default; see
the [Codex hooks documentation](https://learn.chatgpt.com/docs/hooks).

## bkf hooks

`bkf hooks install [--write] [--only modes|orient|check|log|rules|task|guard|audit|tabname|sources] [--home PATH]` and
`bkf hooks status [--only modes|orient|check|log|rules|task|guard|audit|tabname|sources] [--home PATH]`
manage ten hook groups. Registration targets Claude Code
(`~/.claude/settings.json`) and Codex (`~/.codex/hooks.json`). The `sources`
group targets Claude Code only. A tool whose folder is missing is skipped.

- **modes** registers `UserPromptSubmit` and `PreToolUse` hooks that run a copy
  of `agent_modes.py` placed at `~/.agent-hooks/mode.py`. A prompt starting with
  `w:` tells the agent to implement right away. A prompt starting with `g:`
  tells the agent to do its work in a separate git worktree before any edit,
  created with `git worktree add -b` from the local `HEAD` (never from origin,
  which the `EnterWorktree` tool's `name` option uses by default) and entered
  with `EnterWorktree` by `path`; it blocks
  nothing and does not choose between implementing and discussing. A prompt starting with `t:` puts
  the agent in talk mode: it is told to discuss only, and the hook denies
  `Edit`, `Write`, `NotebookEdit`, `apply_patch`, and any `Bash` command it
  cannot show to be read-only. `psql` counts as read-only only when every `-c`
  is a single `SELECT`, `SHOW`, `TABLE`, `VALUES`, `EXPLAIN` (without `ANALYZE`) or a
  `\d`-style meta-command, with no `INTO`, `;`-chained statement, file option or
  stdin. The Bash guard recognizes separators and
  redirects outside quotes and checks command substitutions recursively. A
  prompt without a prefix is free and clears the mode. The mode is kept per
  session in `~/.agent-hooks/state/`. In every mode, including no mode, the hook
  also denies a `Bash` command that runs `git stash` other than `git stash list`
  or `git stash show`, because the checkout is shared and a stash moves other
  agents' uncommitted changes. The user can still run it with `!`.
- **orient** registers a `SessionStart` hook that runs `bkf orient`, described
  above, using the absolute path of the installed `bkf` command.
- **rules** registers a `SessionStart` hook that prints
  `~/.agent-hooks/rules.md` at every session start. Output is capped at 4,000
  characters and cut at a line boundary; a longer file ends with
  `... rules.md truncated`. A line that starts with `[interactive] ` is for a
  chat with the user: it is printed without the prefix, and left out when the
  environment variable `BKF_DELEGATED` is set, which the harness sets for every
  agent it starts. The hook never fails a session and `bkf hooks install --write`
  copies `default_rules.txt` to that path only when it does not exist, and never
  overwrites or edits an existing file.
- **task** registers, for Claude Code and Codex, a `SessionStart`, a
  `UserPromptSubmit`, a `Stop`, a `PostToolUse` and a `PreToolUse` hook (all
  tools); for Claude Code also a `PermissionRequest`, a `StopFailure` and a
  `SessionEnd` hook. All run `bkf hooks run task`. With `BKF_TASK` set, it
  reads the task from the [task store](#bkf-task). On `SessionStart` it prints
  this text, and nothing on the other events:

  > This session works on task <id> (<kind>): <title>. When the owner moves
  > this card to "to be merged", you will get a message: follow the
  > git-merge-queue skill. `bkf task ready` and `bkf task done` no longer exist;
  > the card leaves the board with `bkf task close` once its branch has landed.

  It prints nothing when the task cannot be read or when its kind is `unit`
  (a script owns those cards). Unknown events and unreadable input print the
  text as `SessionStart` does. The mark events and `SessionEnd` never print,
  since their standard output would go to the agent's context.

  On `PostToolUse` and `Stop` the hook also renews the lease of the merge turn
  when the task holds it and the lease is more than a minute old (see
  [bkf merge](#bkf-merge)). Nothing else changes with those events.

  The hook keeps its own mark on the card: attention reason `prompt` with one of
  four notes. It applies only to a card that is `working` and of kind `task` or
  `handoff`; other cards are left alone.

  | Event | Effect on the card |
  | --- | --- |
  | `Stop`, with `background_tasks` and `session_crons` both empty or absent | set `waiting for your reply` |
  | `Stop`, with either list non-empty | clear the hook's own mark; set nothing |
  | `PermissionRequest` | set `waiting for your approval` |
  | `PreToolUse` with `tool_name` `AskUserQuestion` | set `waiting for your answer` |
  | `PreToolUse` with any other tool, `PostToolUse` (any tool), `UserPromptSubmit` | clear the hook's own mark |
  | `StopFailure` (the turn ended on an API error) | set `stopped on an error` |

  Setting replaces the hook's own mark when its note differs, and does nothing
  to any other attention: a `prompt` with another note, or another reason. Clearing
  touches only the hook's own mark. So a session that ends its turn to wait for
  background work never shows as waiting, and a session that resumes clears its
  mark when its first tool call starts. The hook changes the card through the store's
  locked helpers, as `bkf task attention` does; an event that changes nothing
  does not take the lock. Empty or invalid input is treated as
  `SessionStart`. With `BKF_HOOK_DEBUG_FILE` set, the hook also appends each raw
  input to that file as one line, to read a real payload; nothing sets it by
  default. The hook always exits 0; errors are swallowed. The agents that
  the harness starts never see `BKF_TASK`.

  **Session cards.** With `BKF_TASK` unset, an interactive Claude session in tmux
  (`CLAUDE_CODE_ENTRYPOINT` is `cli` and `TMUX_PANE` is set) has a card of its
  own: kind `task`, source `session`, session agent `claude`. Any other session,
  such as `claude -p`, one outside tmux, or one with `BKF_TASK` set, returns
  before it reads its input, and a `BKF_TASK` session never touches the session
  links. The session's `session_id` is its link to the card, kept in the store
  as described under [bkf task](#bkf-task):

  - `SessionStart` with no card for the `session_id`, in a git repository (the
    input's `cwd`): creates the card, `working`. Its repository is the one that
    holds `cwd`, its title is the tmux window's name (else the repository
    folder's name), and its session records `tmux_session` and `tmux_window`
    (the window id) of `TMUX_PANE`. Outside a git repository nothing is read or
    written. A link whose card is missing is replaced by a new card.
  - `SessionStart` with a card (`resume`, `compact`): reuses it and points its
    session at the pane's window again.
  - `UserPromptSubmit`: while the card's title is still the one it was created
    with, the first prompt with text names it: its first line that has words,
    without leading `#` marks, with runs of spaces collapsed, and cut to 80
    characters ending in `…`. The window name gives the title the same way.
    Later prompts never rename it, and a title someone else set is kept.
  - `SessionEnd`: the card is deleted, unless it is `to-merge` or has the
    `merge-failed` attention: those wait for the owner (the merge queue, or the
    failed merge), so they stay. The link stays either way; a resume whose card
    is gone gets a new card, and a link is replaced only when its card is gone.
  - The mark events act on a session card as on a launched one. A link whose
    card is missing does nothing on these events.
- **check** registers a `SessionStart` hook that records a git snapshot,
  a `PostToolUse` hook that records files written by editing tool calls
  (`Edit`, `Write`, `NotebookEdit`, `MultiEdit`, `apply_patch`), and a `Stop`
  hook that validates the bundles they identify. The hooks run `bkf hooks run
  snapshot`, `bkf hooks run record`, and `bkf hooks run stop`; each reads the
  hook's JSON from stdin and is not meant to be run by hand. The snapshot keeps
  the repository's `HEAD` and hashes for its dirty paths at session start. At
  `Stop`, the recorder paths are combined with paths that became dirty, changed,
  were cleaned, or were committed since the snapshot. Each path is mapped to its
  nearest enclosing bundle (a folder whose map declares `bkf_version`), and
  that bundle alone is checked with `bkf validate --this-bundle` and `bkf
  inventory --check`. A failing check blocks the stop and gives the agent the
  output, including the `bkf inventory --write` fix for a stale inventory; a
  warning or an incomplete validation does not block. When the check does not
  block, the warnings that name a file changed in the session are saved for the
  session; `bkf hooks run warnings`, a `UserPromptSubmit` hook of this group,
  gives them to the agent once as context with the next prompt, and shows the
  same warnings to the user as a `systemMessage` (without the map guidance). The recorder ignores edits made by subagents (payloads with `agent_id`), and the check ignores
  recorded paths that belong to another worktree than the session's working directory. The hook blocks at most
  once per session so an error the agent cannot fix cannot trap it, and a
  passing or abandoned check clears the record and refreshes the snapshot. The
  recorder remains a fallback when git comparison is unavailable. A snapshot
  requires a git repository; more than 2000 dirty paths skips it. Two sessions
  in the same repository at the same moment are not told apart by the git
  snapshot. Records are kept per session in `~/.agent-hooks/state/` and pruned
  after 14 days.
- **log** registers a `UserPromptSubmit` hook and a `Stop` hook. New entries go
  at the top of the file, below its introduction. A prompt
  starting with `i:` is logged as an idea, and one starting with `f:` as
  feedback; neither reaches the model. The `i-:` and `f-:` forms log the
  same way without the agent-message excerpt, for entries unrelated to the
  last answer. Pasted-text wrapper tags (`<pasted_content …>`) are removed
  from the logged text. The excerpt uses the full agent message through 5,000 characters;
  longer messages keep the end at a whitespace boundary and begin with a quoted
  `[message truncated: N earlier characters omitted]` line. The working-folder
  text includes the git repository's folder name and the relative path (or only
  the repository name at its root); outside git it uses an absolute path with
  the home directory shortened to `~`. The excerpt comes from the agent's last
  message saved by the `Stop` hook; Claude Code's transcript is the fallback.
  Nothing is written when no single target file can be found. Every hook
  failure is reported to the user through `systemMessage` and does not block
  the session; a failed `i:` or `f:` entry still stops the prompt so the entry
  is not lost.
- **guard** registers a `PreToolUse` hook for `Read` and `Bash`. On the first
  whole-file read or single-file `cat` of a Markdown file with a `## Navigation
  map` whose body (after the frontmatter) exceeds 350 lines or 2,000 words, the
  same size test and the same `## Navigation map` table that `bkf validate`
  checks, it denies the read and returns the map's
  section links with line ranges, showing a row's label and heading as one when
  the label only repeats the heading. A second whole-file read of that resolved
  path is allowed in the same session. Partial `Read` calls and other shell
  commands are allowed. Refusals are stored per session in
  `~/.agent-hooks/state/` and pruned after 14 days.
  The same hook also denies a `Bash` call that starts a long-run launcher in the
  foreground: `plan-run.sh` with
  `start` or `resume`, `delegate-run.sh`, or `codex exec`, whether
  called by path, behind `cd`, an environment assignment, `bash`, `env` or `nohup`. It is
  allowed only when the tool input has `run_in_background: true`; a launcher backgrounded by
  hand is denied even then, because the session cannot show its state: `nohup`, a
  trailing `&`, a subshell or `bash -c` ending in `&`, a `for`/`while` loop, `xargs`
  or `parallel`, and a call that starts more than one launcher (one Bash call per run).
  Compound openers (`do`, `then`, `{`, `(`) are looked through, and `bash -c`/`eval`
  strings are judged as if written out. Commands that only mention a name (`grep`, `cat`, `echo`) and the read-only
  subcommands (`status`, `board`, `gates`, `finish`) are allowed.
  [launch_guard.py](/tooling/launch_guard.py) owns the check.
  The same hook asks the user (`permissionDecision: ask`) before a `git` command that
  discards work: `branch -D` (or `-d -f`), `worktree remove --force`, `clean`, `reset --hard`
  and a forced `push`. Approving is the user's request to discard; `branch -d` and
  `worktree remove` without force pass, because git refuses what is not merged or is dirty.
  [git_guard.py](/tooling/git_guard.py) owns the check.
- **audit** registers a `UserPromptSubmit` hook, `bkf hooks run audit`, with a
  60-second timeout. A prompt starting with `bkf:` (any case) triggers an audit
  of the git repository that contains the working directory; any other prompt
  is left alone. Unlike `log`, the prompt still reaches the agent. The audit
  lists the git changes as staged, modified, deleted, and untracked, grouped by
  the deepest bundle that holds each path, and for every bundle runs the
  validator and `inventory --check`. The agent receives a summary of at most
  3,000 characters: counts, the first 15 untracked paths, and the first five
  errors of each bundle. The full report is written to
  `~/.agent-hooks/reports/bkf-audit-<timestamp>.md`, and the 20 newest reports
  are kept. The audit changes nothing in the repository. Outside a git
  repository it says so and stops.
- **tabname** registers `bkf hooks run tabname` on `SessionStart`,
  `UserPromptSubmit` and `Stop`. Inside tmux it renames the session's tmux
  window (the tab under iTerm2's `tmux -CC`) to the session's name: the last
  `/rename` title, else the generated title, read from the session transcript
  and cut at 80 characters. The session is the source: renaming the tab by hand
  does not rename the session, and the next event renames the tab again. It
  does nothing outside tmux or while the session has no title yet.
  On the first prompt of an interactive session whose name is still the one
  Claude Code derived (`bkf-1a`), it also names the session `<repo><N>` (`bkf1`,
  `bkf2`): the repository's folder name (the main checkout's, from a worktree)
  and the lowest number no other live session holds, so sessions message each
  other by a short name. It sets the name through the hook's `sessionTitle` and
  renames the tmux window at once. A name chosen with `/rename` or `--name`, or
  already of that form, is kept; a number is free again when its session ends.
  [session_number.py](/tooling/session_number.py) owns the choice.
- **sources** looks up and captures web research in the initialized
  [sources store](#bkf-sources).
  - Before `WebFetch`, an unregistered URL passes silently. A registered
    URL or alias with a missing or blank snapshot can be fetched outside a
    completion window. During a window the hook uses the one-call grant
    described in [Complete](#bkf-sources). A denial gives the id and absolute
    paths to the snapshot and record. It gives the command to reopen the
    source, except while another call holds the grant: then it states that the
    grant is reserved until `HH:MM` (local time) by a call that has not
    reported back, and the command comes back with the normal denial once
    the window expires. After a used grant it says the grant was already used
    and when it would have expired. The hook strips the URL and
    percent-encodes `|`, `{`, `}`, `^`, backtick, space, `<`, `>`, and `"`
    after the host before it compares or stores it, so a URL a browser would
    fetch is captured once.
  - After a successful `WebFetch`, the hook fetches the raw page for the
    snapshot and metadata. A new record starts pending and carries its creating
    `session_id` and, for a subagent, `agent_id`. Its `via` comes from the latest
    search by that session and agent, or `direct fetch`. The context gives the
    `finish` commands with optional `--id NEW`, the warning when a URL
    redirects to another page, and snapshot instructions when there is no
    text. Raw capture and refresh use the same [fetch rules](#bkf-sources).
    A refresh keeps the record's identity and records today's consultation
    once. For the same page, it fills recoverable `unknown` metadata. For an
    unrelated destination under the same URL comparison as `add`, it records
    `ext.redirected_to`, keeps the cited page's metadata, and reports the
    redirect in the hook context and on stderr. A refresh that lands on the
    same page clears `ext.redirected_to` and any alias that held that
    destination, unless the fetch failed. A refresh that ends at another page
    never replaces a snapshot that has text, with or without Key claims; it
    saves the destination's text only when the record had none. Otherwise a
    readable candidate replaces the snapshot only if every existing claim
    matches in its section. A replacement marks the snapshot as `web` and clears its manual
    note. If the candidate fails the claim checks, the hook keeps the saved
    text and provenance and lists the failed claims in its context and on
    stderr. A fetch without readable text also preserves the saved text.
  - Before `WebSearch`, BKF search suggests up to five distinct registered
    sources with their id, status, description, and absolute record path.
    The hook also shows the latest identical query's time, session, URL
    count, and first ten result URLs. Query matching folds case and
    whitespace. A matching record without `ext.id` or `ext.status` is skipped
    with a warning naming its path; the others are still suggested. A search with neither match passes silently. After the
    search, the hook appends its time, session, agent when present, query,
    and URLs from the tool response's result entries to
    `searches/YYYY-MM-DD.jsonl` and commits it with the same Git lock retries
    as `add`.
  - At `Stop` the hook asks the session to close any pending records it
    created. At `SubagentStop` it asks only for records owned by that subagent.
    The reason gives the `finish` syntax with optional `--id NEW` for each id
    and snapshot instructions for records without text.
    A stop retry with `stop_hook_active` passes.
  - The group does nothing without an initialized store. Internal errors go
    to stderr and allow the tool call or stop to proceed. Codex has no
    `WebFetch` or `WebSearch` hook points. In Codex, use `bkf search` and
    `bkf sources` directly.

`install` previews by default and prints one line per script and registration
as `ok`, `missing`, or `differs`; `--write` applies it. Other settings and
hooks in the files are kept, an entry that is already current is left alone,
and an unreadable file stops the command before anything is written. After
`install --write`, each registered command is run with harmless probe input;
any failed probe is printed as `broken` and makes the command return 1. `status`
runs the same probes for existing entries. A probe checks the installed command
itself, so a stale copy that cannot answer is reported as `broken` with a
reason. `--only` limits the registrations that are installed or probed. The
script is copied rather than linked so the hooks survive a moved checkout;
`status` reports `differs` when the installed copy or a command no longer
matches this checkout, and returns 1 unless everything is `ok`. Hook failures
exit 0. Groups other than `sources` also print a JSON `systemMessage` for
the user. There is no uninstall: remove the entries by hand. Codex asks for a
one-time review of new hooks, so run `/hooks` in Codex after the first install.

## bkf search

`bkf search QUERY... [--cwd PATH] [--limit N] [--path PATH] [--heading TEXT]
[--tag TAG]... [--debug]` searches sections in
the outermost bundle containing the selected directory, including nested
bundles. `--cwd` defaults to the current directory; `--limit` defaults to 5.
The index is rebuilt in memory for each call.

The index includes tracked BKF documents and every `AGENTS.md`. It excludes
`MAP.md`, feedback and ideas profiles, untracked files, the bundle-root
`readme.md` and notes files, and files inside hidden folders. Membership and
document metadata follow the
[membership rules](/format/format-specification.md#12-discovery-membership-and-composition) and
[frontmatter profiles](/format/frontmatter-profiles.md).

Tags are indexed for every section of a document, so a query word that is a
tag ranks that document's sections. Queries that match no tag rank as they would
without tags. When a bundle has a
[`tag-vocabulary.yaml`](/format/frontmatter-profiles.md#tag-vocabulary) and the
query contains a canonical tag or any of its synonyms (case-insensitive; a
multi-word synonym matches a contiguous run of words, stopwords included), the
canonical tag and all its synonyms are added to the query as phrases. Each bundle
searched contributes its own vocabulary. A vocabulary that is invalid makes the
search fail with exit `1`.

Filters narrow the sections searched and combine with AND:

- `--path PATH` keeps documents under that directory, or that file. It is
  resolved against `--cwd` (or the current directory when `--cwd` is absent). A
  path outside the bundle exits `2`.
- `--heading TEXT` keeps sections whose own heading, the last element of the
  heading trail, equals the text, case-insensitive.
- `--tag TAG` keeps documents carrying that tag, case-insensitive. A synonym
  resolves to its canonical tag through the vocabulary of the document's bundle.
  Repeat the option to require several tags.

Results show the `/`-rooted path, section heading, and a whitespace-collapsed
preview of up to 200 characters. When the query matches the section body, the
preview is the matching passage, with `…` where text is cut and no highlight
markers. When the hit came only from the heading, description or tags, the
preview is the start of the body. Output is capped at 4,000 characters.

Agents should search before writing or moving a rule to see where it already
lives. Exit `0` means results or no matches; `2` means the query has no
searchable words or `--path` is outside the bundle; `1` reports a search failure. `--debug` adds a traceback to
failures.

## bkf sources

The sources store is a machine-wide BKF bundle with its own Git repository.
It holds metadata, claim anchors, and local snapshots. A consuming bundle
keeps its citations and the reasons a source matters there. Every
subcommand accepts `--dir PATH`, which overrides `BKF_SOURCES_DIR` and the
default `~/sources`.

```sh
bkf sources init [--dir PATH]
bkf sources add URL [--via TEXT] [--kind KIND] [--dir PATH]
bkf sources add --manual --title T [--author A] [--published YYYY-MM-DD] [--url URL|unknown] [--kind KIND] [--via TEXT] [--dir PATH]
bkf sources snapshot ID --from FILE --note TEXT [--dir PATH]
bkf sources complete ID --why TEXT [--dir PATH]
bkf sources finish ID --status used|discarded --description TEXT [--reason REASON] [--kind KIND] [--id NEW] [--dir PATH]
bkf sources check [ID...] [--dir PATH]
```

**Init.** Create the bundle, schema, source catalog, and first Git commit.
On an existing store, `init` compares each built-in field definition with
the current schema, updates missing or changed definitions, and commits
`ext-schema.yaml`. Store-defined fields are preserved. A non-empty directory
without a sources store is refused.

**Add.** Prints the id on stdout. Exit `3` means the same canonical URL or
alias is already registered. It prints the existing id and leaves the record
as it was. URL comparison folds scheme and host case, treats HTTP and HTTPS
as equivalent, drops `www.` and trailing slashes outside the root, and sorts
the query after removing `utm_*`, `fbclid`, `gclid`, and `mc_*`. It keeps
`ref` because it can select a version. It keeps client-side route fragments
starting with `#/` or `#!/` and drops other fragments. `add`, URL lookup, and
the hooks first strip the URL and percent-encode `|`, `{`, `}`, `^`, backtick,
space, `<`, `>`, and `"` after the host, as a browser does, so
`https://fonts.example.org/css?family=Roboto|Open+Sans` is stored as
`...Roboto%7COpen+Sans` and has the same identity typed either way. `check` and
the schema stay strict: a stored URL must already be encoded.

Web registration and hook refresh connect directly to public HTTP(S)
addresses. The fetcher resolves each destination, refuses hosts with any
non-public address, and connects to a checked IP address. It excludes private,
loopback, link-local, multicast, reserved, and unspecified addresses in IPv4
and IPv6, including IPv4-mapped addresses. The fetch has one 20-second
deadline across DNS, connections, and redirects, and streams at most 5 MB
per HTML response. An address refusal or exceeded limit gives a fetch
failure with the reason on stderr.

The fetcher follows up to five HTTP redirects in total and at most one
client-side redirect. It recognizes `<meta http-equiv="refresh" content="N; url=...">`
and standalone inline scripts of the form `location.replace('...')`,
`location.href = '...'`, or `window.location = '...'`, with either quote style.
It resolves the target against the page URL without executing JavaScript.

If the requested URL matches the final URL or its same-site canonical link
after normalization, `add` stores the same-site canonical URL when available
and otherwise stores the final URL. A canonical URL or alias must preserve
the requested `ref` and client-side route. Site detection uses common domain suffixes
and hosting domains. If neither matches, `add` stores the requested URL in
`ext.url` and the final URL in `ext.redirected_to`. It warns on stderr to
check whether the cited page is gone and close a pending record as `discarded`
with reason `dead` if it is. Only equivalent URL variants are aliases and
deduplication keys. Two cited pages that redirect to the same destination
stay separate, and the destination can be registered independently.

Metadata and snapshot text come from the fetched page. The fetcher decodes
HTML using the byte-order mark, HTTP charset, or HTML charset declaration in
that order, with UTF-8 as a fallback. Charset labels such as `iso-8859-1`,
`latin1`, and `ascii` select Windows-1252. Lossy decoding is reported on
stderr. See the [WHATWG Encoding Standard](https://encoding.spec.whatwg.org/#names-and-labels)
for the label mapping.

Metadata extraction tries JSON-LD, then meta tags.
Title falls back to the HTML title. The record keeps all names in the selected
byline, joined by commas. With no named author, a GitHub or GitLab
repository uses its URL owner. Other pages use the publisher or site name
as written, such as JSON-LD `publisher.name` or `og:site_name`, then the
domain label. The first valid date in the following order becomes `published`.

1. JSON-LD `datePublished`.
2. `article:published_time`, then citation date meta tags.
3. A `<time datetime>` with a class token equal to `published`, as in
   `class="entry-date published"`, or `itemprop="datePublished"`.
4. A valid `<time datetime>` inside an element marked as a byline or article
   metadata, such as `class="article-meta"`. The fallback skips times marked
   as updates or event boundaries and classes such as `unpublished`.
5. A `/YYYY/MM/DD/` date in the same-site canonical URL's path when available,
   otherwise in the final URL's path. The record marks this fallback with
   `ext.published_from: url`.

Dates use `YYYY-MM-DD`. The `updated` field uses JSON-LD and meta tags.
Missing values are `unknown`. The record starts `pending`, records today's
consultation date, and sets `via` to `user` unless supplied. Use `--kind` to
override the inferred `docs`, `article`, `talk`, `package`, `standard`, `repo`,
`paper`, or `thread`.
A 404 or 410 is recorded as `discarded` with reason `dead`. Other failed
fetches and non-HTML pages create pending records, derive the author from
the URL, and warn that there is no snapshot. If you read the source another
way, such as in a rendered browser or a package registry, save that text with
`bkf sources snapshot ID --from FILE --note TEXT` before marking it as used.

In manual mode provide a title and any metadata you know. The default URL
is `unknown`, which permits multiple records without a URL. A supplied URL
uses the same duplicate check. Records added in manual mode start with
`snapshot: none`.

The id combines an author's surname, organization, or site label with up to
four significant title words in ASCII kebab-case. A standalone generic label
such as `ai`, `www`, `docs`, `github`, or `gitlab` is replaced by a more
specific label when available. An unknown or generic title uses the last
meaningful URL path segment when available. Title words that repeat the
label are dropped, and `unknown` is omitted. For a list of named authors, the
id uses only the first author. In a single byline string, comma-separated
parts with two or more words each are treated as full names. A single personal
name can use `Surname, Given`.
Collisions get a numeric suffix starting at `-2`. Search existing records with
`bkf search QUERY --cwd PATH`, using the store path as `PATH`.

**Snapshot.** Save the UTF-8 text you read to `records/ID/ID.txt`. Use
`--from -` to read from stdin. Give a non-empty note naming where you got
the text, such as “npm registry README of eslint-seatbelt.” The command
requires non-empty text and records `ext.snapshot: manual` and
`ext.snapshot_note`. It works on pending and finished records and preserves
their citations. Fetched HTML headings and manual Markdown ATX headings
(`#` through `######`) are saved as `## <heading>` lines with normalized
whitespace and no zero-width characters. Every new manual snapshot starts
with `<!-- BKF:SNAPSHOT:1 -->`, so reading it back never parses Markdown
again; fetched snapshots carry the marker only when they need escapes. A backslash prefixes each
literal line that starts with `## ` or a backslash, and a literal first line
that equals the marker. Claim matching removes the marker and one leading
backslash from each escaped line. Text in manual code fences remains part of
the enclosing section. Older snapshots keep their original interpretation
of `## ` headings and manual code fences. The command records
today's consultation once. If any claim fails against the candidate, the
command keeps the saved text and provenance, lists the failed claims on
stderr, and exits `1`. Use a web fetch to replace a `web` snapshot.
The note is required for `manual` and absent for `web` and `none`.

**Complete.** Give a reason to reopen a source. The command appends today's
date and the reason to `ext.completions` and opens a 30-minute grant for one
Claude Code `WebFetch` of the record's URL or aliases. The first admitted
`PreToolUse` reserves it for that session, agent, and tool use id. A matching
`PostToolUse` consumes the grant and refreshes the record. Other calls are
denied during the reservation and after consumption. A matching
`PostToolUseFailure` releases the reservation immediately for another call
within the window. If neither event arrives, the grant stays reserved until
expiry. An admitted call may finish after expiry if its reservation is still
recorded.
The window is local state inside the store's `.git` directory. `complete`
refuses to replace a live reservation, and its error states the expiry time
(`HH:MM`, local) and that the reserving call has not reported back, as the
hook's denial does. Once the call settles or the window
expires, running `complete` again appends another reason and starts a new window.

**Finish.** To close a source as `used`, open `records/ID/ID.md` and use
this format for each Key claim. The command runs the full record check before
writing either closed status. If the record has `snapshot: none`, save the text with
`bkf sources snapshot` first.

## bkf task

The task store is machine-wide and holds the state of agent tasks: one folder
per task under the state directory. `BKF_TASKS_DIR` overrides the folder;
otherwise `$XDG_STATE_HOME/bkf/tasks`, else `~/.local/state/bkf/tasks`.
Skills, `bkf launch`, `bkf merge`, and the Agentic app call these subcommands. An
agent in a task's window runs `bkf task close` itself once its branch has landed.

```sh
bkf task new --repo DIR --title T [--body-file F|-] [--source S] [--kind K] [--parent ID | --no-parent] [--json]
bkf task list [--repo DIR] [--status S]... [--kind K] [--parent ID] [--json]
bkf task show [ID] [--json]
bkf task output [ID] [--lines N]
bkf task send [ID] (--text T | --message-file F|-) [--no-enter]
bkf task start ID [--agent A] [--model M] [--effort E] [--reviewer R] [--tmux-session S] [--tmux-window W] [--worktree PATH] [--branch B] [--run-dir D]
bkf task worktree ID [--base REV] [--json]
bkf task fail [ID] [--exit N] [--note T]
bkf task close [ID]
bkf task attention [ID] (--set REASON [--note T] | --clear)
bkf task delete ID
```

**Layout.** Each task is `<store>/<id>/task.json`, and a task may also have
`prompt.md`. The store holds `generation`, a counter that rises on every
write, and `.lock`, which serializes writes. `<store>/.sessions/<session_id>.json`
links a Claude session to its card: `{"task": <id>, "default_title": <title or null>}`,
where `default_title` is kept until the first prompt names the card. The folder
name starts with a dot, so `bkf task list` does not read it as a task. An id is `t` followed by the
local time, a dash, and four hex digits, such as `t20261120-143005-a1b2`.
Writes replace files atomically.

**Legacy statuses.** The first read or write of a store that predates the four
statuses below migrates it once, under the lock: `done` cards are deleted,
`review` cards become `working`, and the file `.migrated-statuses` records that
it ran. The merge queue's files live under `<store>/.merge/` (see
[bkf merge](#bkf-merge)).

**task.json.** Every file has `"schema": 1` and these keys:

| Key | Holds |
| --- | --- |
| `id` | the folder name |
| `kind` | `task`, `handoff`, or `unit` |
| `parent` | the parent task's id, or null |
| `repo` | the repository's identity: the folder holding its git common directory |
| `title` | one line |
| `body` | the text from `--body-file` |
| `source` | where the task came from, or null |
| `status` | one of the statuses below |
| `attention` | `{reason, since, note}` when a person is needed, else null |
| `session` | `{agent, model, effort, reviewer, tmux_session, tmux_window}`, else null |
| `worktree` | `{path, branch, head}`, else null |
| `run_dir` | the run folder, or null |
| `exit` | the exit status of a failed run, or null |
| `note` | free text, or null |
| `created`, `updated` | UTC timestamps, `YYYY-MM-DDTHH:MM:SSZ` |

**Statuses and transitions.** `todo` starts at `new`. The statuses are `todo`,
`working`, `to-merge` (in the merge queue; see [bkf merge](#bkf-merge)), and
`failed`. `start` moves `todo`, `working`, `failed` or `to-merge` to `working` and
clears `attention` and `exit`; a `working` card that starts again is a rerun, and
the start clears its attention. `bkf merge enter` moves `todo`, `working`, `failed`
or `to-merge` to `to-merge` and clears `attention`. The merge queue moves a card
to `working` with the `merge-failed` attention when it leaves the queue with a
reason (`bkf merge fail`, or recovery), and to `working` without attention when
the session or the owner takes it out, or when an interim land (`bkf merge land
--continue`) finishes. `fail` moves `working` or `to-merge` to `failed`.
`attention` is allowed in `todo`, `working`, `to-merge`, and `failed` (a failed
card is one that needs its owner); `--clear` is always allowed. `close` and
`delete` remove the folder whatever its status. A transition that is not
allowed is refused.

The attention reasons are `prompt`, `quota`, `launch-failed`, `escalated`,
`paused` and `merge-failed`. A plan run sets `escalated` on a unit
or run that needs its coordinator (blocked, escalated, takeover or stopped; the
note says which) and `paused` on a run that waits for its owner at a checkpoint,
such as a finished run's report or a delegate's finished work. The merge queue
sets `merge-failed` with the reason as the note.

**New.** Prints the id, or the task JSON with `--json`. `--repo` is turned into
the repository identity, so linked worktrees share one. `--body-file -` reads
standard input. `--parent` defaults to `$BKF_TASK` when that is set;
`--no-parent` makes the task without a parent.

**Start.** An option object is recorded only when at least one of its options
is given, and its other keys stay null. A `working` card may start again (a
rerun). A `to-merge` card may start too, but only as a safety net for a card a
session left in `to-merge` after a plain land: `bkf task start` refuses it while
it still holds an entry in the merge queue, and the card then stays `to-merge`.
The transition table allows the move; the queue check is in `bkf task start`.

**Close.** Deletes the card, whatever its status: a session runs it after its
branch has landed, and a plan run's passed unit is closed the same way. It
prints nothing, and an unknown id is refused like the other commands.

**List.** Filters combine with AND, and `--status` may repeat. `--repo DIR`
keeps tasks whose repository identity is that of `DIR`. Without `--json`, one
line per task: id, status, kind, and title, separated by two spaces; one line
per unreadable folder goes to standard error. With `--json`, standard output
holds one object:

```json
{"schema": 1, "store": "<absolute store path>", "generation": 12, "tasks": [<task JSON>], "unreadable": ["<id>"]}
```

Tasks are in creation order, then id. The app reads `list --json` each time
`generation` changes, so the command imports only the standard library.

**Worktree.** Creates the git worktree of a task, or reuses it, and records it on
the card as `worktree: {path, branch, head: null}`. The status does not change;
the task must be `todo`, `working` or `failed`, and any other status is refused
before git runs. A failed card's worktree is reused or created like any other. The repository is the task's `repo`, the main checkout. The path is
`<repo>/.claude/worktrees/<slug>` and the branch is `task/<slug>`. The slug folds
the title to Unicode NFKD without combining marks, lowercase, runs of characters
outside `a-z0-9` as one `-`, at most 30 characters with no trailing `-`, and
`task` when nothing is left; then `-` and the last four characters of the id.
`--base REV` is resolved in the repository, and defaults to its `HEAD`. The
base applies only when a new branch is made. Rules, in order:

- The path exists: reused (`created: false`) only when it is a worktree of this
  repository with the branch checked out. Otherwise refused, naming the path.
- The branch exists without a worktree: `git worktree add <path> <branch>`.
- Neither exists: `git worktree add -b <branch> <path> <base>`.
- Unless `git check-ignore` already ignores `.claude/worktrees/<slug>` in the
  main checkout, the line `/.claude/worktrees/` is appended once to
  `<git-common-dir>/info/exclude`.

Output is the path on the first line and the branch on the second, or with
`--json` one object `{"path", "branch", "created"}`. A worktree already created is
never removed on a later failure.

**Show.** Without `--json`, `key: value` lines: id, title, status, kind, repo,
parent, worktree, branch, tmux window, attention, and note. A missing value is
`-`.

**Output.** Prints the text of the task's tmux window, so a session can see what
another shows. The target is always the card's recorded `tmux_session` and
`tmux_window`, never an argument. It runs `tmux capture-pane -p -S -N -t
<session>:<window>`: the visible screen and `N` lines of history above it.
`--lines` defaults to 200 and is at most 5000; any other value is refused. Output
goes to standard output unchanged. A session or window name with a leading dash,
a colon, a space or a line break is refused before tmux runs. Refused, with a
reason on standard error, when the card has no window, when the window is closed
(no such window, or no tmux server running), or when tmux is not installed. It
never changes the card.

**Send.** Types a message into the task's tmux window as if the user had typed
it, so one agent can answer a prompt in another agent's window. The target is
the card's recorded `tmux_session` and `tmux_window`, never an argument, and the
refusals are those of `output`. Exactly one of `--text T` and `--message-file F|-`
is required; `-` reads standard input. Each line is typed as literal characters,
with an Enter key between lines, and one more Enter follows the last line unless
`--no-enter` is given. Nothing runs a shell: the characters arrive as typed, and
a message that starts with a dash needs the `--text=-...` form. A message is
refused when it is empty, longer than 10000 characters, or holds a control
character other than tab or line feed. Standard output stays empty on success,
and the command never changes the card.

**Exit status.** `0` is success. `1` is a refusal: an unknown or corrupt task,
a transition not allowed, a dirty tree, or a missing id. A refusal prints one
line on standard error starting with `bkf task: `, and nothing on standard
output. `2` is a usage error from argument parsing.

## bkf merge

The merge queue lands the finished branches of one repository on its target
branch, one session at a time, so each session merges the target as it is at
its turn and tests that result. The steps a session runs are in the
`git-merge-queue` skill (`agent-skills/skills/git-merge-queue/SKILL.md`); this
section owns the queue's rules and exit statuses. The queue of a repository is
`<store>/.merge/<repo-key>/queue.json` (the task store, and a slug of the
repository identity with a hash). Each change runs under the store's lock and
raises the store generation, which the app watches.

```sh
bkf merge enter [--task ID] [--worktree PATH] [--target BRANCH]
bkf merge wait [--task ID] [--timeout S] [--worktree PATH] [--target BRANCH]
bkf merge verify [--task ID] [--target BRANCH]
bkf merge land [--continue] [--task ID] [--target BRANCH]
bkf merge fail --reason TEXT [--task ID] [--target BRANCH]
bkf merge leave [--task ID] [--target BRANCH]
bkf merge status [--repo DIR] [--task ID] [--json]
```

**Target.** `--target`, else the queue's target when the queue exists, else the
branch that `origin/HEAD` names, else `main`, else `master`. A `--target` that
differs from an existing queue's target is refused.

**Task.** `--task` defaults to `$BKF_TASK`. The card names the repository, so
the queue is the card's.

**Worktree.** `enter`, and `wait` when it joins the queue, take the worktree from
`--worktree`, else from the card's recorded path, else from the current work
tree. The branch is the one checked out there. A detached head, or the target
branch itself, is refused.

**Entry and turn.** `enter` adds the task at the back, moves its card to
`to-merge` and clears its attention. When nobody holds the turn, the new entry
takes it at once. `wait` joins the queue first when the task is not in it. The
entry at the head whose state is `turn` is the lock: only it verifies and lands.
When it leaves (by landing, failing, leaving or recovery), the next entry takes
the turn in the same locked change.

**Verify and land.** `verify` refuses a dirty work tree, then records the
branch's head and the target's head, and sets phase `testing`. `land` refuses
unless the target's head is unchanged since verify, the branch head is unchanged
since verify, and the target is an ancestor of the branch head. It refuses when
the target's checkout has uncommitted changes. Before it moves the target it
writes phase `landing` to disk, then fast-forwards the target only: `git merge
--ff-only <branch>` in the target's checkout, or a compare-and-swap of the ref
when no worktree has the target checked out. On success the entry is removed,
and the card stays `to-merge` until the session runs `bkf task close`.

**Interim land.** `land --continue` lands the same way, with the same checks and
the same fast-forward, for a session that keeps working on its branch after the
land. Afterwards the entry is removed, the next entry takes the turn, and the
card moves to `working` without attention, so the session can go on; the
event is `landed` with a reason that starts `interim:`. The output names no
cleanup and says what to do next: the session may keep working on the branch,
and before its next land it runs `bkf merge enter` again. Each land needs its
own `verify`, and the checks the repository names must pass on that result. The
ancestry check is unchanged: after an interim land the target is an ancestor of
the branch, so while the target has not moved, a land after new commits is a
fast-forward of what was verified. Once another session has landed, the target
has moved and is not an ancestor of the branch's new commits, so `land` refuses
with exit 3 until the branch merges the target again and is verified again. The
last land of a branch is the plain `land`, which keeps the card in `to-merge`
and points to cleanup. Between two lands the card is `working`, so a session
that ends in that gap loses its card at `SessionEnd` like any working card; the
branch stays, and a resumed session gets a new card.

**Fail and leave.** `fail --reason TEXT` removes the entry, moves the card to
`working` with the attention `merge-failed` and the reason as its note, and
gives the turn to the next entry. `leave` removes the entry and moves the card
to `working` without attention. Neither runs during a land. A take-out by the
owner is a `leave` (the app runs it and types the owner's message into the
session); see the take-out rule below.

**Take-out.** When the entry is gone while a session is in the merge flow (its
`wait` exits 2, or its `verify` or `land` exits 5 with "not in the merge queue"),
the output names the cause from the task's last queue event:

- A `left` event (the owner's take-out, or the session's own `leave`): the
  session stops the merge flow, does not run `land` and does not re-enter the
  queue on its own, and goes on with its work or waits for the owner. It
  re-enters on its own only after its own `bkf merge fail`: the card then has
  `merge-failed` with the reason the session wrote, and the session fixes the
  branch first. Otherwise it re-enters only when the owner asks again.
- A `landed` event: the branch already landed, so there is nothing to land and
  the session does not enter again.
- A recovery event (`lock-recovered`, `dropped-dormant`, `failed`; see below),
  or no event: the queue removed the entry, not the owner. The output gives the
  reason and says the session may run `bkf merge enter` again, which joins the
  back of the queue.

The re-entry after `land --continue` is the session's planned step, not a
take-out.

**Recovery.** Every mutating command, and every poll of `wait`, first settles
the queue under the lock; `status` only reports what recovery would do.

- The holder loses the turn when its card is gone, when its recorded tmux window
  is gone (a card that records no window is not checked for one), or when its
  lease has run out. The lease is 60 minutes from the last sign of life, and
  `BKF_MERGE_LEASE_MINUTES` sets its length in minutes. Any `bkf merge` call by
  the holder renews it, and so does the task hook on `PostToolUse` and `Stop`, at
  most once a minute. A single tool call longer than the lease ends the turn.
- A waiting entry is dropped when its card is gone, or when it has not been
  polled for three minutes. `wait` polls every second and refreshes the entry at
  most every ten seconds, so the store does not write on each poll.
- A dropped holder or waiter returns its card to `working` with the attention
  `merge-failed` and the note `lost its place in the merge queue: <why>`.
- A holder in phase `landing` when the queue is read again means its land died
  before it wrote the result. The branch decides: an ancestor of the target is
  recorded as landed; anything else is dropped as failed, with the card marked.

Each recovery is an event in the queue: `lock-recovered`, `dropped-dormant`,
`landed` or `failed`. `main-moved` records a land that found the target moved.

**Exit status.**

| Exit | Meaning |
| --- | --- |
| `0` | Done: entered, your turn, verified, landed (an interim land included), failed or left. |
| `1` | Refused, with the reason on standard error: no task, a dirty work tree, no branch, the target branch, a land in progress. |
| `2` | `wait`: the entry left the queue (a take-out, a land or a recovery). The output says why and whether the session may re-enter on its own; see the take-out rule. |
| `3` | `land`: not verified, the branch changed since verify, the target moved (recorded as `main-moved`), or the branch does not contain the target. The entry keeps the turn. |
| `4` | `land`: the target's checkout has uncommitted changes, or the fast-forward was refused. The entry keeps the turn. |
| `5` | Not your turn, or the task is not in the queue (`verify`, `land`, `fail`): a take-out or recovery, so the session stops the merge flow as the take-out rule says. |
| `75` | `wait`: the timeout passed (default 540 seconds, `--timeout S`); run it again. |

**Status.** Read-only: it never changes the queue. The one-time store migration
can run on its first read, as for every store read. `--repo DIR` picks a
repository's queue; `--task ID` adds the task's place. With `--json` it prints
one object, which the Agentic app reads (the field names are its contract):

```json
{"schema": 1, "store": "<abs>", "generation": 12,
 "queues": [{"repo": "<abs>", "target": "main", "target_head": "<sha>",
   "lock": {"task": "<id>", "since": "<utc>", "lease_until": "<utc>", "phase": "testing|landing|null", "stale": false} | null,
   "entries": [{"position": 1, "task": "<id>", "branch": "<name>", "worktree": "<abs>|null", "state": "turn|waiting",
     "entered": "<utc>", "turn_since": "<utc>|null", "stale": false}],
   "events": [{"at": "<utc>", "task": "<id>", "event": "<name>", "reason": "<text>|null"}]}],
 "task": {"in_queue": true, "position": 1, "state": "turn", "queue_ahead": 0}}
```

`stale` is true when recovery would drop the entry, even when no command has run
it. `task` appears only with `--task`; its `queue_ahead` counts the entries
before it and is `null` when it is not queued. `events` keeps the last 50. The
file's top-level `lock` is reserved and stays `null` in schema 1; the lock is the
head entry whose state is `turn`.

**Settings.** `BKF_MERGE_LEASE_MINUTES` sets the lease (default 60).

## bkf launch

`bkf launch` opens an interactive Claude or Codex session for the skills and the
Agentic app, and is the one way they start one. It composes the task store
(`bkf task`), the task worktree and the tmux layer. It writes no prompt text: it
receives one. Not used by hand.

```sh
bkf launch <claude|codex> --dir D [--prompt-file F|-] [--model M] [--effort E] [--reviewer R] [--name N] [--permission-mode P] [--window W] [--delegated] [--task ID | --no-task | [--title T] [--kind K] [--parent ID | --no-parent] [--body-file F]] [--worktree auto|none] [--size COLSxROWS] [--no-attach] [--json]
bkf launch --session-name --dir D
```

**Request.** Checked before anything is written. The agent must be `claude` or
`codex` and on `PATH`. `--name` and `--permission-mode` are claude only. `--dir`
is a folder, and `--prompt-file` exists when it is a path. `--task` names a task
whose status is `todo` or `failed`. `--name`, `--permission-mode` with codex, and
the card options with `--task` or `--no-task` are usage errors, as is `--worktree
auto` with `--no-task`.

**Card.** `--task ID` launches on that card. `--no-task` makes none. Otherwise a
new card is created: its repository is the identity of `--dir`, its kind is
`--kind` (default `handoff`), its parent is `--parent` (default `$BKF_TASK`;
`--no-parent` for none), its body is `--body-file`, and its title is the first
of `--title`, `--window`, `--name`, the first non-empty line of the prompt cut to
80 characters, or `session`.

**Worktree.** `--worktree` defaults to `auto` when the card's kind is `task`, and
to `none` otherwise and without a card. `auto` calls `bkf task worktree` through
`task_worktree.prepare`. A repository that is not a git repository falls back to
`none` silently. A failed card is prepared like any other card, and it is reused
through `prepare`, which reuses it on its branch or creates it. The session works in the
worktree, or in `--dir`.

**Prompt.** With a card, the prompt is saved as the card's `prompt.md`, and the
window reads that copy. Without a card, a path is used as an absolute path, and
standard input is saved to a new temporary file that is kept. Without
`--prompt-file` the session starts with no first message.

**Command.** Claude: `claude [--name N] [--permission-mode P] [--model M] [--effort E] "$(cat '<prompt>')"`.
Codex: `codex [-m M] [-c 'model_reasoning_effort="E"'] "$(cat '<prompt>')"`. Each
value is shell-quoted. The prompt is expanded by the window's shell, because a
typed line of tens of KB overflows the terminal.

**Window.** `task_tmux.open_window`, named by `--window` (else the card's title),
with `BKF_TASK=<id>` for a card, `BKF_TASKS_DIR` when the caller has it set, and
`BKF_DELEGATED=1` with `--delegated`. `--size` sizes a new session. The placement
rules are those of `task_tmux.py`: inside tmux, the window goes into the caller's
session, grouped with the windows of the same repository (right after the caller's
window when the working directory is in its repository, else right after the last
window of that repository, else at the end). Outside tmux, the window goes right
after the last window of the repository in the session that already holds such
windows (a worktree of the repository counts; the session with the most attached
clients wins, then the first by name, and only sessions with names tmux accepts
as targets count). With no such window, the repository's session
(`repo_session_name`) is used, created when missing. A terminal attaches to the
session: iTerm2 gets `tmux -CC attach`, Terminal.app `tmux attach`. Elsewhere, or with `--no-attach`, the output says how to attach.
`BKF_TMUX_SOCKET` makes every tmux call use a named server: the tests use it and
never touch the user's server.

**Start.** With a card, `task_store.start` records the session (agent, model,
effort, reviewer, tmux session and window id) and the worktree, and the card
becomes `working`.

**Output.** Plain: the card id on the first line (with a card), then
`<session>:<window id>`, then `attach with: tmux attach -t =<session>` when no
terminal shows the session. With `--json`, one object: `{"task", "session",
"window", "worktree", "branch", "needs_attach"}`, where `task`, `worktree`, and
`branch` are null when absent.

**Session name.** `--session-name --dir D` prints the tmux session that the
placement above uses for `D` (the session holding the repository's windows, else
its repository session) and launches nothing. The Agentic app uses it to bring
that session's iTerm2 window forward before a launch.

**Failure.** After the card exists, a failing step (worktree, window, start)
leaves the card in its status, sets `attention` `launch-failed` with the error as
its note, and exits 1 with one `bkf launch: ` line on standard error. This holds
for a failed card too. A worktree already created is kept. With no
card, the same failure only exits 1. A refusal before the card exists also exits
1; usage errors exit 2.

```md
## Key claims

- c1 (sec. Page heading): The claim in your words — "short verbatim anchor"

## Notes
```

Use the heading from `records/ID/ID.txt`, where headings appear as
`## <heading>`. Supply a one-line description for the catalog. To close a
source as `discarded`, give a reason of `dead`, `paywall`, `copy-of:<id>`,
`marketing`, or `outdated`. Use `--id NEW` to rename a pending record as
part of closing it. Choose an unused id of lowercase letters and digits
separated by single hyphens. The folder, record, any snapshot, and `ext.id`
move together, and the catalog is refreshed in the same commit. The command
prints the final id. After `finish`, the id is permanent. Record
project-specific relevance in the consuming bundle.

**Check.** Check the store schema and the selected records. An outdated
`ext-schema.yaml` is an error and names `bkf sources init` as the fix.
With no ids, check every record directory, including directories
missing their `ID.md` file. Reports malformed frontmatter with the file
path, missing or invalid metadata, impossible calendar dates, malformed
HTTP(S) URLs, a discarded record without a reason, and a used record
without Key claims. `check` and the schema reject raw whitespace, control
characters, `<`, `>`, `"`, `{`, `}`, `|`, `\`, `^`, and the backtick in `url`,
`aliases`, and `redirected_to`. An anchor passes within the named
`## <heading>` section from its heading line to the next section or the end
of the snapshot.
The check normalizes whitespace and typographic quotes, and removes
U+200B, U+200C, U+200D, U+2060, and U+FEFF when comparing headings and
locators. A used record without snapshot text gets one missing-evidence
error with recovery instructions. Pending records produce warnings. Exit `1`
means there was an error. URL lookup, web capture, catalog updates, and hook
search suggestions skip records whose frontmatter cannot be loaded and
report their paths on stderr. This includes value construction errors such
as an impossible unquoted date. `check` reports them as record errors and
continues through the selected records.

Exit `0` means success, `1` reports an operation error, and `2` reports
invalid command syntax. `add`, `snapshot`, `complete`, and `finish` commit
their record and any catalog or schema change, retrying Git lock conflicts.
If the commit fails, the files remain on disk and the command warns on
stderr and exits `0`. Git ignores
`*.txt` snapshots, so they are local to the machine that saved them.

Code can import `resolve_store_path`, `normalize_url`, `lookup_url`, `add`,
and `rename` from `source_store`. The low-level `rename(directory, old_id, new_id)`
API accepts pending records only. A URL lookup returns the id, record path, and
`has_snapshot` flag, or `None` for a miss. `add` returns the id for either a
new or existing record. Tests can pass `fetch=` with a function that takes
the requested URL and returns a `source_page.FetchedPage` with the final URL
and HTML, or raises a fetch error. `add` calls it again if it follows a
client-side redirect.

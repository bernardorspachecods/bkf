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
with `--force`, and for a checkout's `.venv` run
`uv pip install --python bkf/tooling/.venv/bin/python -e bkf/tooling`.

Skills are installed through the symlink `~/.claude/skills`. Their relative
links to `../../library/` resolve through a second symlink,
`~/.claude/library`, pointing to `agent-skills/library`. Create both on a new
machine.

## bkf help

`bkf help` lists commands, summaries, and usage guidance grouped by situation:
after editing documents, session start and lookup, and install.
The `help` command appears at the end. `bkf help <command>` shows
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

`--skills <skills-dir>` also processes tagged lists in entry skills. A list is
delimited by `<!-- BKF:GENERATED-TAGGED-LIST tags: t1, t2 -->` and
`<!-- BKF:GENERATED-TAGGED-LIST-END -->` and holds the same two-column table
for the library files with matching tags, grouped `modules/` then
`workflow-types/` and sorted by filename. Files without markers are unchanged.
From the repository root, `bkf inventory agent-skills/library --skills agent-skills/skills --write` refreshes these lists; use the same invocation with `--check` to verify them.

## bkf skills

`bkf skills [REPOSITORY-ROOT] [--check|--write]` checks or regenerates the
agent-skills inventories, generated tagged lists, and skill catalog. The root
defaults to the current directory and must contain `agent-skills/library` and
`agent-skills/skills`.

`--check` is the default and never writes. It checks the library map
inventories and skill tagged lists, then validates skill metadata and links,
runtime metadata, and whether `agent-skills/SKILL-ARCHITECTURE.md` is current.
It prints both check results and exits non-zero if either check fails.

`--write` refreshes library map inventories and tagged lists, then writes the
generated skill catalog. Use it after changing a skill or a library module
listed by a skill.

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

`bkf orient [--cwd PATH] [--no-validate] [--debug]` prints a short orientation
block for the selected directory. `--cwd` defaults to the process working
directory. The output starts with `orientation (from PATH)`, followed by a
validation health line and the map chain from the outermost bundle root through
the nearest map at or above the directory. Each map path is followed by its
member inventory rows. Output is capped at 6,000 characters; omitted rows are
reported with a `read <map-path>` marker. `--no-validate` omits the health line.

Validation runs in-process with a five-second limit. The health line reports
`ok`, the number of errors, or a timeout. When validation finds warnings, a
second line gives their count and up to 10 of them follow, each as a code and
path. When any is a navigation map warning, one paragraph of guidance on writing
the map follows, the same one `bkf validate` ends its findings with. If the
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

`bkf hooks install [--write] [--only modes|orient|check|log|rules|guard|audit] [--home PATH]` and
`bkf hooks status [--only modes|orient|check|log|rules|guard|audit] [--home PATH]` manage seven hook groups that
must run every time, which a skill cannot guarantee. They are registered for
both Claude Code (`~/.claude/settings.json`) and Codex (`~/.codex/hooks.json`);
a tool whose folder is missing is skipped.

- **modes** registers `UserPromptSubmit` and `PreToolUse` hooks that run a copy
  of `agent_modes.py` placed at `~/.agent-hooks/mode.py`. A prompt starting with
  `w:` tells the agent to implement right away. A prompt starting with `t:` puts
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
  `... rules.md truncated`. The hook never fails a session and `bkf hooks install --write`
  copies `default_rules.txt` to that path only when it does not exist, and never
  overwrites or edits an existing file.
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
  same warnings to the user as a `systemMessage` (without the map guidance). The hook blocks at most
  twice per session so an error the agent cannot fix cannot trap it, and a
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
print a JSON `systemMessage` for the user and exit 0 so they never block the
session. There is no uninstall: remove the entries by hand. Codex asks for a
one-time review of new hooks, so run `/hooks` in Codex after the first install.

## bkf search

`bkf search QUERY... [--cwd PATH] [--limit N] [--debug]` searches sections in
the outermost bundle containing the selected directory, including nested
bundles. `--cwd` defaults to the current directory; `--limit` defaults to 5.
The index is rebuilt in memory for each call.

The index includes tracked BKF documents and every `AGENTS.md`. It excludes
`MAP.md`, feedback and ideas profiles, untracked files, and files inside hidden
folders. Membership and document metadata follow the
[tracking rules](/format/format-specification.md#32-tracking) and
[frontmatter profiles](/format/frontmatter-profiles.md).

Results show the `/`-rooted path, section heading, and a whitespace-collapsed
preview of up to 200 characters. Output is capped at 4,000 characters.

Agents should search before writing or moving a rule to see where it already
lives. Exit `0` means results or no matches; `2` means the query has no
searchable words; `1` reports a search failure. `--debug` adds a traceback to
failures.

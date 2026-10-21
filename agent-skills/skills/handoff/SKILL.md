---
name: handoff
description: Write a handoff for the task in progress and open a fresh Claude or Codex session on it in a new Terminal tab, so the work continues without the old chat's context. Use only when the user asks to continue in a new chat; do not use to summarize a conversation or to record knowledge that outlives the task.
---

# Handoff

A handoff carries work in flight into a new session that does not
inherit the old chat. Its value is what it leaves out. Facts that stay true
after the task belong in the repository's documents, placed by
[organize-documents](../../library/modules/organize-documents.md), not here.

## Write

1. Take the purpose of the next session from the user. If they did not state it, ask. It decides what stays.
2. Write the handoff to the scratchpad as `handoff-<short-name>.md`, following the isolated-handoff rules in [brief-another-agent](../../library/modules/brief-another-agent.md). Then apply these:
   - Keep an item only if the new agent would err or have to ask without it. Drop context that only served the earlier task.
   - Point to specs, issues, diffs and files by path or URL. Do not copy them.
   - State settled decisions with their reason, and what was tried and ruled out.
   - State the working directory, the branch, and where uncommitted changes stand.
   - Mark each claim as verified (say how) or as an assumption. The new agent will not re-check a claim written as fact, so re-check cheap ones now and downgrade the rest, especially "X is done" and "Y is not built".
   - Leave out keys, tokens and passwords.
3. Re-read the file as the new agent would, without this chat, and fix what you could not act on. Then launch without showing it to the user, unless they asked to see it first.

## Launch

Each script takes `<working-dir> <absolute-handoff-path>`, opens a new Terminal.app tab in that directory and starts the agent there. The current chat is untouched. Use Claude unless the user asks for Codex.

- [scripts/launch-claude.sh](scripts/launch-claude.sh) starts `claude` with the whole handoff as its first message, so the user sees it in full.
- [scripts/launch-codex.sh](scripts/launch-codex.sh) starts `codex` with a short prompt that points to the file, which Codex reads itself. The file sits in this session's scratchpad, outside its workspace, and may prompt for read permission.
- Run them only when `$TERM_PROGRAM` is `Apple_Terminal`. In another terminal, give the user the path and the command to run themselves.
- The tab comes from a simulated cmd+T, which needs Accessibility permission for Terminal. Without it, or if the keystroke is lost, the script opens a new window instead. Read [scripts/lib-terminal.sh](scripts/lib-terminal.sh), which both scripts share, only to change how the tab opens.

Afterward, tell the user the handoff path and that the new session is open.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

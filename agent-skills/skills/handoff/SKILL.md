---
name: handoff
description: Write a handoff for the task in progress and open a fresh Claude or Codex session on it in a new terminal tab, so the work continues without the old chat's context. Use only when the user asks to continue in a new chat; do not use to summarize a conversation or to record knowledge that outlives the task.
---

# Handoff

A handoff carries work in flight into a new session that does not
inherit the old chat. Its value is what it leaves out. Facts that stay true
after the task belong in the repository's documents, placed by
[repo-maintenance](../repo-maintenance/SKILL.md), not here.

## Write

1. Take the purpose of the next session from the user. If they did not state it, ask. It decides what stays.
2. Write the handoff to the scratchpad as `handoff-<short-name>.md`, following these rules:
   - Keep an item only if the new agent would err or have to ask without it. Drop context that only served the earlier task.
   - Point to specs, issues, diffs and files by path or URL. Do not copy them.
   - State settled decisions with their reason, and what was tried and ruled out.
   - State the working directory, the branch, and where uncommitted changes stand.
   - Mark each claim as verified (say how) or as an assumption. The new agent will not re-check a claim written as fact, so re-check cheap ones now and downgrade the rest, especially "X is done" and "Y is not built".
   - Leave out keys, tokens and passwords.
   - Sources: give each one's path and what it is authoritative for, and what wins when they disagree (by default the plan on intent and scope, the code on current behavior). Say what not to read, whether examples are binding or only shape references, and whether history is current truth or background.
   - Name what the new agent can access (repo, tools, files) and what it lacks. Put the essential context in the file, stating anything settled in this chat, instead of pointing to guidance the new agent cannot reach.
   - Delimit pasted or retrieved material (logs, documents, code) from the instructions and say what it is.
   - Use only the sections that a source does not already cover, in this order with the immediate request last, in one or two sentences: objective (only when the request alone would lose the purpose), context the new agent lacks, sources, rules (hard constraints, each with its reason), preferences and what to do when they conflict, examples (only when a format or tone is hard to describe), history, ask-before and stop conditions, process (only when order matters or the default approach would be wrong), verify-by, output format.
   - Autonomous work tends to fail by silent scope growth and by guessing past ambiguity: default to stopping when scope must change or a decision needs clarifying, and let the user's standing guardrails take precedence.
   - If the user wants a prompt to paste themselves instead of a launched session, give it in one fenced block ready to paste, and after it at most a few lines on the assumptions made and what was left out because a source covers it. Do not walk through the structure.
3. Re-read the file as the new agent would, without this chat, and fix what you could not act on. Then launch without showing it to the user, unless they asked to see it first.

## Launch

Each script takes `<working-dir> <absolute-handoff-path>`, opens a new tab in that directory and starts the agent there. The current chat is untouched. Use Claude unless the user asks for Codex.

- [scripts/launch-claude.sh](scripts/launch-claude.sh) starts `claude` with the whole handoff as its first message, so the user sees it in full.
- [scripts/launch-codex.sh](scripts/launch-codex.sh) starts `codex` with a short prompt that points to the file, which Codex reads itself. The file sits in this session's scratchpad, outside its workspace, and may prompt for read permission.
- Run them only when `$TMUX` is set or `$TERM_PROGRAM` is `Apple_Terminal`. In another terminal, give the user the path and the command to run themselves.
- Inside tmux, the tab is a tmux window placed right after the caller's window, without taking focus; under iTerm2's `tmux -CC` it shows as an iTerm2 tab. In Terminal.app it is a new window, because Terminal cannot add a tab to a chosen window. Read [scripts/lib-terminal.sh](scripts/lib-terminal.sh), which both scripts share, only to change how the tab opens.

Afterward, tell the user the handoff path and that the new session is open.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

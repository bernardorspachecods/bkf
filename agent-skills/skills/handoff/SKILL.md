---
name: handoff
description: Write a handoff for the task in progress and open a fresh Claude or Codex session on it in a new terminal tab, so the work continues without the old chat's context. Use only when the user asks to continue in a new chat; do not use to summarize a conversation or to record knowledge that outlives the task.
---

# Handoff
## Write

1. Take the purpose of the next session from the user. If they did not state it, ask. It decides what stays.
2. Write the handoff to the scratchpad as `handoff-<short-name>.md`, following these rules:
   - Drop context that only served the earlier task.
   - Point to specs, issues, diffs and files by path or URL. Do not copy them.
   - State settled decisions with their reason, and what was tried and ruled out.
   - Mark each claim as verified (say how) or as an assumption.
   - Leave out whatever a new session already loads on its own at start (standing instructions, memory, repository documents, hooks). 
   - If the user wants a prompt to paste themselves instead of a launched session, give it in one fenced block ready to paste, and after it at most a few lines on the assumptions made and what was left out because a source covers it. Do not walk through the structure.
3. Re-read the file as the new agent would, without this chat, and fix what you could not act on. Then launch without showing it to the user.

## Launch

Run `bkf launch claude --dir <working-dir> --prompt-file <absolute-handoff-path> --title "<one-line name of the task>" [--model M] [--effort E]`, with `codex` in place of `claude` only when the user asked for Codex. The working directory may be any directory, not only the caller's. The new session's first message is the whole handoff file, so the user sees it in full, and the current chat is untouched. Give a model or effort only when the user chose one; without them the session takes the user's defaults.

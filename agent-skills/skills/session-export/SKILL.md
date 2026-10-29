---
name: session-export
description: Export chosen Claude Code or Codex sessions to readable files with what the chat itself does not show (tokens per turn, models, what woke each turn, messages between sessions), to analyze how skills and instructions behave. Use only when the user asks to export or analyze specific sessions; do not use to summarize a conversation or to export sessions on your own initiative.
---

# Session export

A session's own record on disk holds more than any chat export: per-turn token usage, model and effort, timestamps, the full text of messages between sessions, and what woke each turn. This skill turns the sessions the user names into files they can read and compare. It has no script: the record's format belongs to the tool's version and changes, so you write a throwaway query for the version in front of you and run it.

## Find the sessions

The user names them: this session, a name, or a crew. If the match is not one clear session, list the candidates (title, first message, folder, date) and let the user choose before exporting.

- **Claude Code:** `~/.claude/projects/<working folder, with / replaced by ->/<session id>.jsonl`. Sessions of a crew are named `crew-<name>`; the orchestrator is the session that opened them.
- **Codex:** `~/.codex/sessions/<year>/<month>/<day>/rollout-<time>-<id>.jsonl`.

## Read the record without loading it

Never read a session file whole into the conversation: it is megabytes. Count its record types and read one example of each (`python3 -I`), write a query for what you need, run it, and read only its output. A file given to you as the export of a chat (plain text) has none of these fields; say so and export what it has.

## What to produce

One folder per session, `~/.session-exports/<repo>/<date>-<session name>/`, with:

- `transcript.md`: user and assistant messages verbatim, in order, each with its time and the cause that woke it (the user, a background task finishing, a scheduled task, a message from another session). Tool use as one line each: the command, the file, the search, the agent started. Messages sent to other sessions in full, with sender and receiver. Drop tool output.
- `stats.md`: one row per turn (time, duration, model, effort, new input, cache read, cache write, output, thinking tokens), then totals by model and counts of turns by cause. In Codex the token events may be cumulative: check before summing.

Every number comes from the command, never from your reading or adding. In Claude Code a single reply is written as several records with the same `requestId` and the same usage: count each request once, or every total doubles. A turn starts at a message the user typed or a background notification: a slash command is written as three records, and text a tool injects mid-turn (a loaded skill) is not a new turn. Check that the rows add up to the totals and that the message counts match what the transcript lists. Say what the query could not read (unknown record types or fields) at the top of `stats.md`; a gap you do not state looks like a zero.

Tokens are what the tool recorded. Do not convert them to money.

## Rules

- A session holds whatever passed through it, secrets included. The folder is outside every repository and never goes into git, and its content is never pasted into the chat or sent elsewhere.
- Do not change or delete the source sessions.
- When the files are written, run `open` on the folder and give its full path. Do not summarize the sessions unless the user asks.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

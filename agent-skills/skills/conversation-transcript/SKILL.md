---
name: conversation-transcript
description: Clean exported Codex session files into a user-assistant transcript, optionally retaining a compact activity trail. Use when asked to remove session artifacts or preserve an audit trail; do not use to summarize or rewrite the conversation.
---

# Conversation transcript

Keep user and assistant messages verbatim and in their original order. Remove activity artifacts unless the user selects the activity mode.

Choose a mode from the request. If the user has not specified one, ask: “Which mode should I use: `messages-only` or `messages-and-activity`?” Wait for the answer before editing.

- **`messages-only`**: keep only user and assistant messages with speaker headings. Remove activity logs, tool calls, command output, and other artifacts.
- **`messages-and-activity`**: keep the messages and a concise activity trail showing files read or searched, relevant commands, exact web search queries, and agents started. Keep completion or interruption status when recorded. Drop bulky outputs that do not help identify the work.

Run the [transcript cleaner](scripts/clean_transcript.py) with the selected mode. In `messages-and-activity`, merge consecutive activity sections into one `## Activity` block. Add category headings such as `### Commands and file reads` or `### Web searches` only when that category appears, in the order its events occur. Start a new activity block after each user or assistant message.

The cleaner preserves only information present in the session. It keeps commands and web queries in their recorded form, marks searches whose query is missing, and preserves agent start, completion, or interruption events. It drops command output and other artifacts.

Run `python3 scripts/clean_transcript.py INPUT --mode MODE`. The cleaner produces one Markdown transcript; without a destination option, it writes the transcript to stdout.

- Use `--output PATH` to write a separate file. Its parent directory must already exist, and `PATH` must differ from the source path.
- Use `--in-place` only when the user wants the source replaced.
- Use `--rename` only when the user wants the source renamed. It writes a sibling file named `codex-trancript-{number}.md`, then deletes the source. It chooses the lowest unused positive number starting at `1`.
- Use `--rename-number N` only with `--rename`; `N` must be positive, and the target file must not already exist. A collision fails without replacing the target.

After writing to a file, check the resulting transcript and report its path.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

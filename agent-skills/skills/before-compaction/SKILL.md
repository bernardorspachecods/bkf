---
name: before-compaction
description: Suggest the message for compacting the current chat and make the agent check, after the compaction, that the documents hold everything it needs to continue. Use only when the user is about to compact; do not use to hand work to a new chat (use handoff).
---

# Before compaction

Compaction keeps a summary of the chat, not the chat. What the work still needs
must live in documents.

1. Suggest one compaction message for the user to paste after `/compact`. It
   states the task in progress, the next step, and the paths of the documents
   that carry the rest (plan, specs, notes, changed files). It points to them
   instead of copying them.
2. End that message with this instruction: after compaction, open those
   documents and check that they hold everything needed to continue. Name what
   is missing and ask the user for it instead of guessing.

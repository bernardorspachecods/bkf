---
name: before-compaction
description: Before the user compacts the chat, make sure everything the work needs is written in documents and suggest the compaction message. Use only when the user is about to compact; do not use to hand work to a new chat (use handoff).
---

# Before compaction

1. Check that everything needed to continue is written in documents, and write
   what is missing.
2. Suggest one compaction message for the user to paste after `/compact`. It
   states the task in progress, the next step, and the paths of the documents
   that carry the rest (plan, specs, notes, changed files). It points to them
   instead of copying them.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

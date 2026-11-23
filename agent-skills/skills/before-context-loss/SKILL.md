---
name: before-context-loss
description: Before the user compacts the chat or ends the session, make sure everything the work needs is written in documents and suggest the message that carries the work on. Use only when the user is about to compact or end the session; do not use to hand work to a new chat (use handoff).
disable-model-invocation: true
---

# Before context loss

1. Check that everything needed to continue is written in documents, and write
   what is missing.
2. Suggest one message for the user to paste. It states the task in progress,
   the next step, and the paths of the documents that carry the rest (plan,
   specs, notes, changed files). It points to them instead of copying them.
   - Compaction: the message goes after `/compact`.
   - End of session: the message opens the next session on this work.

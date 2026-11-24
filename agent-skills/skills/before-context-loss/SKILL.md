---
name: before-context-loss
description: Prepare the documents and continuation message needed to resume work after context loss. Use when the user is about to compact or end a session, or a hook announces automatic compaction and gives a continuation file; do not use to hand work to a new chat (use handoff).
disable-model-invocation: true
---

# Before context loss

Choose the mode from the trigger:

- **Automatic:** A hook says the session will be compacted automatically and
  names a continuation file. Check that everything needed to continue is
  written in documents, and write what is missing. Then write one standalone
  post-summary continuation message to the named file, overwriting it. State
  the task in progress, the next step, and the paths of the documents that
  carry the rest (plan, specs, notes, changed files). Point to those documents
  instead of copying them. Do not ask the user to compact; carry on with the task.
- **Manual:** The user is about to compact the chat or end the session. Check
  that everything needed to continue is written in documents, and write what
  is missing. Suggest one message for the user to paste. It states the task in
  progress, the next step, and the paths of the documents that carry the rest
  (plan, specs, notes, changed files). It points to them instead of copying
  them. For compaction, the message goes after `/compact`; for an end of
  session, it opens the next session on this work.

---
name: repo-read-audit
description: Report what repository material an agent inspected during a task, what it contributed, and where retrieval was inefficient. Use only when the user explicitly asks for a read or retrieval audit; do not add reports to ordinary task responses.
---

# Repository Read Audit

Use this skill only when the user explicitly asks for a report on an agent's
repository reading or information retrieval. Audit the current task or the
specific run the user identifies. The purpose is to help assess whether the
repository made the needed information discoverable and whether the agent
retrieved it efficiently.

## Evidence and scope

1. Establish the task the agent was trying to complete and, when available,
   what information the user expected it to find. Use the request and the
   session context; ask a focused question only if the audit's target cannot
   otherwise be identified.
2. Reconstruct the read trail from the available conversation, tool trace,
   shell history, or user-provided run log. Include only sources you can
   actually inspect. For each part of the trail, identify its evidence source:
   directly visible tool trace, a run log or agent-provided account, or your
   own reconstruction. Do not describe an agent-provided account as a visible
   tool trace. Labelling the source and limiting conclusions to the supported
   portion follow [writing-principles](../../library/modules/writing-principles.md).
3. Distinguish content reads from discovery actions:
   - Opening or printing a file is a content read; state whether the full file,
     a section, or a small excerpt was inspected when known.
   - Listing paths or searching names discovers files, but does not mean their
     contents were read.
   - Search results and command output expose only the returned matches or
     lines. Do not describe the rest of those files as read.
   - Context inherited from the user, an earlier agent, or a conversation
     summary is not a file read by the current agent. Label it as inherited
     context when it materially shaped the work.
4. Do not reopen files just to reconstruct the history. Do not claim exact
   counts of lines, bytes, tokens, or time unless the available trace supports
   them. Never infer a complete read history from the final answer alone.

## Judge the retrieval

Evaluate the trail against the task, not against a preferred fixed number of
files. For each meaningful content read, explain what was inspected and what
it contributed in plain language. Keep a separate row for each file so the
user can see which sources were read; repeated reads of the same file may
share a row if their actions and contribution are clear. Record path listings,
searches, and other discovery actions separately from content reads.

Classify reads as:

- **Directly useful:** supplied a requirement, authoritative answer, or
  implementation evidence needed for the task.
- **Supporting:** helped resolve ambiguity, establish context, or verify a
  conclusion.
- **Low-value or avoidable:** duplicated already available guidance, followed
  an unnecessarily broad path, repeated a read without a clear purpose,
  inspected unrelated material, or otherwise added little to the task.

Call a read unnecessary only when you can explain why it did not materially
help and what simpler source or route would have sufficed. For each
inefficiency, name the observed read or discovery action, explain why it added
little, and label the simpler route as an inference when it was not directly
tested. Do not turn an agent's failure to mention a file's contribution into
proof that the read was useless. A failed search, wrong turn, or unproductive
read may still be reasonable exploration if the result exposed a real
ambiguity. State uncertainty instead of guessing intent.

Assess repository organization only as far as this task's trail supports.
Consider whether the agent found an entry point, followed clear links to the
authoritative source, encountered conflicting or duplicated guidance, had to
guess where information lived, or missed information the task clearly
required. Treat one task as a sample, not proof of overall repository quality.

## Report

Keep the report concise and specific. Use this structure, omitting sections
that have no evidence:

1. **Scope:** task audited and limits of the available trace.
2. **Content reads:** a compact table with one row per file, the inspected
   extent when known, what it contributed, and its assessment (directly
   useful, supporting, or low-value/avoidable). Keep repeated reads of one
   file together only when clear. Do not combine different files into one row.
3. **Discovery actions:** list relevant path listings, searches, or other
   actions that exposed names or excerpts without reading whole files.
4. **Inefficiencies:** for each low-value or avoidable read or discovery
   action, identify the evidence, explain why it added little, and give a
   simpler route when supportable. Mark proposed alternatives as inference
   when they were not tested. Say “none observed” when supported; do not
   invent a criticism to fill the section.
5. **Retrieval result:** whether the needed information was found, how the
   repository's entry points and authority cues helped or hindered, and any
   likely gap. Separate observed facts from interpretation.
6. **Confidence:** note material gaps in the trace or expected-answer criteria.

Do not turn the audit into a general repository review or recommend
restructuring unless the observed retrieval provides concrete evidence for it.

## Runtime metadata

This skill's invocation and display metadata is in
[agents/openai.yaml](agents/openai.yaml).

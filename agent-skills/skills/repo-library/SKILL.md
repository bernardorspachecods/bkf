---
name: repo-library
description: Use at the start of any task in a repository, and whenever a repo-specific procedure or rule may apply, to find the repository's own procedures and modules in its repo-library.
---

# Repo library

A repository can define its own procedures and guidelines for how work is done in it. The general guidance cannot know them, and following them is what makes your work fit this repository.

1. Look for `repo-library/MAP.md` at the repository root. If it is missing, continue with the task and do not mention it.
2. Read the map. Open each entry whose description fits the task.
3. Follow the entries you opened together with the general guidance; they add to it and do not replace it. In the rare case a repo entry contradicts the general guidance, follow the repo entry and tell the user about the conflict.
4. When the same procedure or rules recur in the repository, or the user says "we always do X here", open the file below and propose a new entry.
5. When you hand work to another agent, put the path to `repo-library/MAP.md` in the assignment.

<!-- BKF:GENERATED-TAGGED-LIST tags: repo-library -->
| What it is | Document |
| --- | --- |
| Defines how to identify, propose, write, and validate reusable procedures in a repository's repo-library, or in the general library when the rule applies to any repository, including when it comes from an external source. Day-to-day document organization is covered by organize-documents. | [grow-libraries.md](../../library/modules/grow-libraries.md) |
<!-- BKF:GENERATED-TAGGED-LIST-END -->

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

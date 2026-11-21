---
name: repo-library
description: "Use when adding or reviewing an entry of a repository's repo-library: a procedure or rule set that the repository applies repeatedly."
---

# Repo library

Nothing sends an agent to `repo-library/` by default. An entry is used only when the documents of the task lead to it, so an entry that nothing links to is never read.

- Propose a candidate; do not write it first. Name the activity, the rules or stages it would hold, and whether it is a module or a workflow; name the two or three closest existing entries and what each owns, so the user can correct the overlap check. Then wait for the answer.
- A candidate is a procedure or rule set the work has applied more than once, or one the user says always applies here, scoped to an activity (for example, editing the database). Prose about how the repository works, with no activity to act on, is not a candidate.  Keep a candidate only if a capable agent would not follow it unprompted, it records a local preference, or it prevents a failure agents credibly show.
- **Make the entry reachable, in the same change.** Link it from where someone doing the task will look: the document that owns where the activity starts (for example, the release protocol linking the entries for the platforms it deploys to) or a task route in the nearest map. The link must point from the task to the entry: an entry that only links out to the task documents is not reached by anyone doing the task. An entry with no link from outside `repo-library/`, apart from the root map's listing of the library, is incomplete. Say which links you added.

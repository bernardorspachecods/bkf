---
name: repo-library
description: "Use when adding or reviewing an entry of a repository's repo-library: a procedure or rule set that the repository applies repeatedly."
---

# Repo library

A repository keeps its own procedures in `repo-library/` at its root, a BKF bundle: `modules/` for one rule set about one activity, `workflow-types/` for a procedure with stages (a release, a migration), and a `MAP.md` with the generated member inventory. An entry's `description` follows the Descriptions section of `bkf/format/frontmatter-profiles.md`. If the folder does not exist yet, create it with the root `MAP.md`.

Nothing sends an agent to `repo-library/` by default. An entry is used only when the documents of the task lead to it, so an entry that nothing links to is never read.

- A candidate is a procedure or rule set the work has applied more than once, or one the user says always applies here, scoped to an activity (for example, editing the database). Prose about how the repository works, with no activity to act on, is not a candidate. An external source (a page, document or file) the user wants turned into a rule is a candidate only when it holds a rule or procedure scoped to an activity; if it holds only information, say so and stop. An entry derived from a source names it (URL or path, and the date collected), and each claim is located in the source exactly as written. Keep a candidate only if a capable agent would not follow it unprompted, it records a local preference, or it prevents a failure agents credibly show.
- Propose a candidate; do not write it first. Name the activity, the rules or stages it would hold, and whether it is a module or a workflow; name the two or three closest existing entries and what each owns, so the user can correct the overlap check. Then wait for the answer.
- Before writing, check the map for an entry with the same activity and extend it when it fits. Have a fresh agent who did not draft the proposal independently find where the rule already lives, in the repo-library and the general library; give it only that job, have it report only the overlap locations and make no edits. Do not duplicate a rule the general library owns; the repo entry holds only what is specific to the repository.
- **Make the entry reachable, in the same change.** Link it from where someone doing the task will look: the document that owns where the activity starts (for example, the release protocol linking the entries for the platforms it deploys to) or a task route in the nearest map. The link must point from the task to the entry: an entry that only links out to the task documents is not reached by anyone doing the task. An entry with no link from outside `repo-library/`, apart from the root map's listing of the library, is incomplete. Say which links you added.
- After writing, run `bkf inventory --write` and `bkf validate` on `repo-library/` and on the places you linked from, and say what was added. If the `bkf` command is not installed, do not write the map by hand: tell the user the tool is missing.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

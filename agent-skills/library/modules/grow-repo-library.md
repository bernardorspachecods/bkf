---
bkf: document
description: "Defines how to identify, propose, write, and validate reusable procedures in a repository's repo-library. Day-to-day document organization is covered by organize-documents."
tags: [repo-library]
---

# Grow the repo library

- A repository's own procedures live in `repo-library/` at the repository root, which is a BKF bundle in the same shape as this library: modules for rules in `modules/`, workflows for staged procedures in `workflow-types/`, and a `MAP.md` with the generated member inventory. An entry's frontmatter `description` states what it is or covers, in one sentence with no "open when" or "use when" phrase. If the folder does not exist yet, create it with the root `MAP.md`.
- A candidate is a procedure or rule set the work has applied more than once, or one the user says always applies here, and that is scoped to an activity (for example, editing the database). Prose about how the repository works, with no activity to act on, is not a candidate.
- Propose a candidate; do not write it first. Name the activity, the rules or stages it would hold, and whether it is a module or a workflow; also name the two or three closest existing entries and what each owns, so the user can inspect and correct the overlap check. Then wait for the user's answer.
- Write a module for one rule set about one activity. Write a workflow only when the procedure has stages, such as a release or a migration.
- Before writing, check the map for an entry with the same activity and extend it when it fits. Have a fresh agent who did not draft the proposal independently find where the proposed rule already lives; give it only that job, have it report only the overlap locations, and have it make no edits. Use the review rules in [review-work](/modules/review-work.md). Do not duplicate a rule the general library already owns; the repo entry holds only what is specific to the repository.
- After writing, run `bkf inventory --write` and `bkf validate` on `repo-library/`, and say what was added. If the `bkf` command is not installed, do not write the map by hand: tell the user the tool is missing.

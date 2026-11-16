---
bkf: document
description: "Lists what is still open after the 2026-10-26 audit of the skills against harness-goal.md and the refactor that moved the harness out of skills/: the choices that are the owner's and the small gaps left. Delete an item when it is settled."
tags: [harness, skills]
---

# Skills audit against harness-goal

What is still open after the audit of 2026-10-26 and the changes it led to (the harness moved out of `skills/`, the briefs became templates, runs and pending plans per repository, a worktree per run). What was settled is in git and in [harness-goal.md](/agent-skills/harness-goal.md). **Not read in the audit:** `brainstorm`, `prototype`, `evaluate-relevance`, `watch`, `retrieval-chat-audit`, `skill-authoring` (only the packaging parts), `git-worktree-cleanup`, `code-work` and `align-intent`. On 2026-10-27 they were searched for stale references to the harness, its paths and its scripts, and none was found.

## Decided by the owner on 2026-10-27

- The plan-only capabilities (`bridge`, `group`, `integration`, `diffbase`, `loop`, `metrics`) stay in the engine.
- `agent-skills/harness` is not a BKF bundle: it is code with a README, linked from the map of `agent-skills`.

## Open

| # | Where | What |
| --- | --- | --- |
| 4 | `agentic-work/scripts/plan_inputs.py` | The briefs of council and research are now templates in each skill's `briefs/` (filled by `harness.template`). The plan's six prompt builders are not: they are assembled from conditional parts (resumed unit, previous problems, gate file, attempt number, a brief that differs from the one received), so a faithful move needs about a dozen fragments and would spread each prompt over several files. I recommend leaving them in code unless you edit those prompts often. |
| 6 | Existing runs and pending plans | Those already in `~/.plan-runs`, `~/.research-runs` and `~/.plan-runs-pending` are not moved into the `<repo>/` layout; runs are still found where they are, pending plans are not (move them to `~/.plan-runs-pending/<repo>/` by hand). Do it after the plan run in progress ends. |
| 7 | `isolation` branch | The change lives on the branch `isolation` of `bkf`, in the worktree `~/bkf-isolation`. It is merged into `main` only when no run is using the code of `main` (`schemas-sarp-c1` was running when it was written). |

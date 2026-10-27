---
bkf: document
description: "Lists what is still open after the 2026-10-26 audit of the skills against harness-goal.md and the refactor that moved the harness out of skills/: the choices that are the owner's and the small gaps left. Delete an item when it is settled."
tags: [harness, skills]
---

# Skills audit against harness-goal

Audit of 2026-10-26, followed by the refactor in [harness-refactor-plan.md](/agent-skills/harness-refactor-plan.md). Read in full: `delegate-work`, `dispatch-agents` (since removed), `handoff`, `run-to-completion`, the modules, and the relevant parts of `plan`, `research`, `council` and `code-review`. **Not read:** `brainstorm`, `prototype`, `evaluate-relevance`, `watch`, `retrieval-chat-audit`, `skill-authoring` (only the packaging parts), `git-worktree-cleanup`, `conversation-transcript`, `code-work`, `align-intent` (header only for some), so they may hold drift not listed here.

## Settled by the refactor

Fixed false or stale text (`plan` saying Codex only, the missing `work-in-stages` and "Safety and gotchas", the empty metadata section, the `<WORKFLOW>_GUIDES` wording). The `dispatch-agents` skill is gone: its common text became the module `run-commands`, injected into the four workflow skills, and each skill now documents its own script (the plan's long section is [plan/run-reference.md](/agent-skills/skills/plan/run-reference.md)). The workflow skills now say the Claude backend exists, research says where web access applies, and the early stop, `gates` and `rehearse` are in the plan reference. The `guard` hook rule is in the module.

## Decided by the owner on 2026-10-27

- The plan-only capabilities (`bridge`, `group`, `integration`, `diffbase`, `loop`, `metrics`) stay in the engine.
- `agent-skills/harness` is not a BKF bundle: it is code with a README, linked from the map of `agent-skills`.

## Open

| # | Where | What |
| --- | --- | --- |
| 1 | `delegate-work` | It does not mention the goal file or the `intent` module (decision: long or delegated work has a goal file with those sections). Add one line pointing to the module, or leave it because a brief for one short task carries its own intent. |
| 2 | `run-to-completion` | It does not name `plan-run.sh gates` and `rehearse` as part of the last alignment. |
| 3 | `plan/SKILL.md` §3 | The early stop and the lint are only in `run-reference.md`; §3 says "a gate has its own cap". Decide whether the stop rule belongs in the rules of §3. |
| 4 | `plan/scripts/plan_inputs.py` | The briefs of council, code review and research are now templates in each skill's `briefs/` (filled by `harness.template`). The plan's six prompt builders are not: they are assembled from conditional parts (resumed unit, previous problems, gate file, attempt number, a brief that differs from the one received), so a faithful move needs about a dozen fragments and would spread each prompt over several files. I recommend leaving them in code unless you edit those prompts often. |
| 5 | `delegate-work` | The old text named `codex exec resume` to send a correction to Codex in the same checkout; the new text says only to write a new brief or resume the agent. Decide whether to name a command, since `delegate-run.sh` has none for resuming. |
| 6 | Existing runs and pending plans | Those already in `~/.plan-runs`, `~/.research-runs` and `~/.plan-runs-pending` are not moved into the `<repo>/` layout; runs are still found where they are, pending plans are not (move them to `~/.plan-runs-pending/<repo>/` by hand). Do it after the plan run in progress ends. |
| 7 | `isolation` branch | The change lives on the branch `isolation` of `bkf`, in the worktree `~/bkf-isolation`. It is merged into `main` only when no run is using the code of `main` (`schemas-sarp-c1` was running when it was written). |

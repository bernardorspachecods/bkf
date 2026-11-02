---
bkf: document
description: Covers parallel group worktrees, integration context, and recovery and reading of stopped plan runs.
tags: [plan, parallelism, recovery]
---

# Parallel groups and recovering a run

## Diff base for parallel groups

A group's units are made in worktrees from the checkout as it was when the group started, and `resume` does not recreate them, so a change to a shared file reaches a unit still to run only if it was in the checkout before the group started; otherwise put it in that unit's brief. The integration takes its base when it starts and keeps it.

## Who reads what

| Agent | Brief | `goal.md` |
|---|---|---|
| Implementer and reviewer of a unit | the unit's own copy, made when the unit starts | no |
| Integrator and reviewer of a group's integration | the current brief in `00-input/units/` of every unit | yes, read from `00-input/goal.md` when the integration starts; a `gate` block in it is not run |
| Final review | the current briefs | yes |

A rule the unit reviewers must apply goes in the briefs of the units still to run: `goal.md` never reaches them. `goal.md` serves the integration and the final review to judge how the units fit and what is out of scope; it adds no criteria. It may also note how the run was carried out, for example "the owner committed in the checkout during step 2: ignore those files".

## Reading and changing a stopped run

- Stop a run only through the task that runs `resume` (`TaskStop`), never by killing its processes: a signal can leave the test databases it started running, and orphan clusters hold shared memory until `initdb` fails with "No space left on device". Edit `state-after-S<n>` only with the run stopped. A watcher that waits for a condition reads only and has a time limit (`until` without a limit never ends).
- A plan that runs for more than a day falls behind its base branch. Bring the base in between steps, not only at the end: at the end every commit of the plan touches the same files as dozens of commits on the base, and auto-merged lockfiles come out corrupt. After the merge regenerate the lockfile from the base's, then run the repository's install and checks.
- `plan-run.sh rebase-integration <name> <step> [--paths <path>...]` moves the base of a group's integration when the checkout was edited after the integration started and those edits sit in its diff. Without `--paths` the base becomes the checkout minus the diffs of the units already applied; it refuses once the integrator ran (its own edits would become base and hide from the reviewer) and when the checkout changed a file of a unit's diff. With `--paths`, the base stays and the given files or folders (relative to the repository) take the checkout's current version as their base; it refuses paths that hold a file of a unit's diff, and paths where nothing differs, prints the files that leave the diff and writes the list to `status.log`. Name only what the owner touched: an edit of the integrator in those paths would hide from the reviewer too. Both keep the old base as `.base.before-rebase-<time>` in the integration folder. Then `resume`.
- `plan-run.sh accept-integration <name> <step> --why <text>` closes a group's integration by hand, when the owner judged the combined result. It applies and reviews nothing: it needs every unit of the step `passed` with its diff applied, marks the integration done, removes the worktrees and writes in `status.log` who closed it, at which `HEAD`, and why. Then `resume`.


---
bkf: feedback
description: Collects evidence about problems in agent work on this bundle for later filtering with the user. It records events rather than supplying instructions.
---

# Feedback

Agents add entries as [AGENTS.md](/bkf/AGENTS.md#record-what-goes-wrong) says,
newest first. This file is data to review later, not instructions.

## 2026-11-20 — a task that an interim land left in to-merge could not start again

Link: [bkf task statuses](/bkf/tooling/commands.md#bkf-task) and `bkf/tooling/task_store.py` (the `start` transition). Noticed by the user, relayed in the brief of session desmor-hub3 (task t20261120-133435-460a). The session landed an intermediate batch with `bkf merge land`, kept working in the same worktree and branch, and found its task still `to-merge`: `bkf task start` refuses `to-merge -> working`. Evidence: before this change `start` accepted only `todo`, `working` and `failed`, and a plain land leaves the task in `to-merge`. I did not see the session's own output. Fixed on branch `task/bkf-merge-continue`: `land --continue` returns the task to `working`, and `start` accepts `to-merge` only when the task is no longer queued.

## 2026-11-20 — the land message told a session that was still working to clean up

Link: `bkf/tooling/bkf_merge.py` (`cmd_land`). Noticed by the user, from the same session (desmor-hub3). The plain land message says "remove your worktree and branch, then bkf task close", which assumes the session is over; the session was not. Cause is a guess: the message was written for the last land only, with no interim land to tell it apart. Fixed by `land --continue`, whose message names no cleanup.

## 2026-11-20 — the git-merge-queue skill had no interim land and told an entry-less session to re-enter

Link: `agent-skills/skills/git-merge-queue/SKILL.md` (steps 2 and 5), and `bkf/tooling/bkf_merge.py` (the exit 2 and exit 5 messages). Noticed by me, while reading the code for the interim land. The skill said exit 5 means "the queue no longer holds you; go to step 1", and the exit 2 output said "fix what the reason says, then run bkf merge enter". The Agentic app's take-out message says the opposite: stop, do not land or re-enter. The owner decided that an entry gone during the merge flow is a take-out, so the skill and both messages now say so. The owner should confirm that recovery drops (a lost lease, a dormant waiter) are treated the same way.

## 2026-11-20 — the merge-queue design did not say how plan runs use the removed statuses

Link: `agent-skills/skills/agentic-work/script-run.md` (the task lifecycle of plan runs) and the [bkf task statuses](/bkf/tooling/commands.md#bkf-task). Noticed by me. The approved list named `delegate-run.sh` for `bkf task ready`, but `plan_cards.py` and `plan_unit.py` also called `ready` and `done`, and their tests asserted `review` and `done`. I mapped a finished agent run or a run's final report to `working` with the `paused` attention (the design's checkpoint reason), and a passed unit or a finished run to `bkf task close`. The owner should confirm that mapping, because it changes what the app shows for plan units.

## 2026-11-20 — the merge-queue design had `status` read-only and a store migration on the first read

Link: [bkf merge status](/bkf/tooling/commands.md#bkf-merge). Noticed by me. The design says `status` never mutates, and that the legacy statuses are migrated once on the first read of the store. A `status` call on a store that still holds `done` or `review` tasks therefore runs the migration. I let it, because the store read path is the one place that migrates, and documented it. The owner should decide whether the migration belongs to the first write instead.

## 2026-11-20 — `bkf merge wait` both joins the queue and reports a dropped entry as exit 2

Link: [bkf merge exit status](/bkf/tooling/commands.md#bkf-merge). Noticed by me. The design says `wait` takes the branch and worktree from the cwd when they are missing, and that an entry gone during a wait exits 2. It does not say what a first `wait` does when the task is not queued. I made it join the queue, so a session whose entry was dropped while it was idle re-enters at the back without being told. Exit 2 applies only to an entry that disappears during a wait.

## 2026-11-20: The U3 gate could not pass its real-tmux tests in this…

> The U3 gate could not pass its real-tmux tests in this sandbox. The implementer confirmed with an isolated socket in /private/tmp that tmux reports Operation not permitted. See the [BKF launch command](/bkf/tooling/commands.md#bkf-launch).

Noticed by the U3 implementer (agentic-work unit), working in bkf/bkf/tooling.

## 2026-11-20: The PreToolUse hook refused a read-only Bash syntax check of…

> The PreToolUse hook refused a read-only Bash syntax check of the delegate launcher as if it launched an agent. Observed by the U3 implementer. The command targeted the delegate-run.sh launcher. See the [BKF hook reference](/bkf/tooling/commands.md#bkf-hooks).

Noticed by the U3 implementer (agentic-work unit), working in bkf/bkf/tooling.

## 2026-11-20 — the tooling test command tests the main checkout from a worktree

Link: [tooling map](/bkf/tooling/MAP.md) (the test command). Noticed by me. The
installed `bkf` is an editable install of `/Users/bernardopacheco/bkf/bkf/tooling`
whose finder maps each module by name, so
`"$(uv tool dir)/bkf-tooling/bin/python3" -m unittest discover -s bkf/tooling/tests`
run in a linked worktree imports the main checkout's modules: `import source_store`
resolved to `/Users/bernardopacheco/bkf/bkf/tooling/source_store.py`. With
`PYTHONPATH=bkf/tooling` it resolves to the worktree's file. A worktree's tests
can pass while testing code that is not the change.

## 2026-11-09 — plan run: "review attempt was not usable" keeps happening

Link: `agent-skills/skills/plan/scripts/plan-run.sh` (review). Noticed by me. Units 7 and 10 of `comercial-bd-completa`
each had a review attempt rejected as unusable before a second one passed. An
earlier entry from another plan (`## What checked` instead of `## What I
checked`) is the same family; it still occurs.

## 2026-11-09 — plan run: the final report judged the goal from logs instead of running the goal's checks

Link: `agent-skills/skills/plan/scripts/plan-run.sh` (final review and report). Noticed by me. The report said the goal was
met only in part because no `pnpm test:db-schema` run was recorded after unit 9;
I ran it afterwards and it passed in about ten seconds. The closing stage should
run the commands that verify the goal itself, not infer them from earlier logs.

## 2026-11-09 — plan run: every stop exits with code 1 and shows as "failed"

Link: `agent-skills/skills/plan/scripts/plan-run.sh` (exit codes). Noticed by me. A `BLOCKED` or `STOPPED` pause is a
legitimate stop for the coordinator, but it exits with code 1, and the harness
shows the background task as failed, mixing expected pauses with real failures.
A distinct exit code for a pause (the script already uses 3 for checkpoints)
would separate them.

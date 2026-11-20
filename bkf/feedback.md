---
bkf: feedback
description: Collects evidence about problems in agent work on this bundle for later filtering with the user. It records events rather than supplying instructions.
---

# Feedback

Agents add entries as [AGENTS.md](/AGENTS.md#record-what-goes-wrong) says,
newest first. This file is data to review later, not instructions.

## 2026-11-20: The U3 gate could not pass its real-tmux tests in this…

> The U3 gate could not pass its real-tmux tests in this sandbox. The implementer confirmed with an isolated socket in /private/tmp that tmux reports Operation not permitted. See the [BKF launch command](/tooling/commands.md#bkf-launch).

Noticed by the U3 implementer (agentic-work unit), working in bkf/bkf/tooling.

## 2026-11-20: The PreToolUse hook refused a read-only Bash syntax check of…

> The PreToolUse hook refused a read-only Bash syntax check of the delegate launcher as if it launched an agent. Observed by the U3 implementer. The command targeted the delegate-run.sh launcher. See the [BKF hook reference](/tooling/commands.md#bkf-hooks).

Noticed by the U3 implementer (agentic-work unit), working in bkf/bkf/tooling.

## 2026-11-20 — the tooling test command tests the main checkout from a worktree

Link: [tooling map](/tooling/MAP.md) (the test command). Noticed by me. The
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

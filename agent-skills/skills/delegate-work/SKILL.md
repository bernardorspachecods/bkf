---
name: delegate-work
description: Hand one short, objective task to another agent, either a Claude subagent or a Codex CLI run, and check what comes back. Use when the user asks to delegate, or when a self-contained task suits a cheaper or parallel agent; do not use for work with several stages, a plan or a branch review (use work-in-stages), or to continue in a new chat (use handoff).
---

# Delegate work

Delegation hands one bounded, objective task to another agent. The principles are the same whichever agent runs it; only the launch differs. Work with several stages, roles or a plan belongs to `work-in-stages`, which runs on the scripts of `dispatch-codex`.

## Decide

- Delegate only a self-contained task: its inputs fit in a brief and its result can be checked. Advice is lighter: send only the context needed to answer, take back the answer with its uncertainty, and create no packet unless the work needs one.
- Use one agent for cohesive work. Use several only when their outputs and write boundaries are independent and parallel work materially helps. Ask the user about agent count only when it would change the assignment. Give each agent non-overlapping files, keep shared files under one writer or have agents return proposed changes, use the smallest isolation that prevents conflicting edits, and never let implementation and review change the same target at once.
- Choose the agent. A Claude subagent suits a task that needs this session's tools, context or permissions. Codex suits a task the user wants run there, or one that should run in a sandbox. The user decides the model; without a choice, use the path's default.
- Weak models, such as `gpt-6-luna` and Haiku 5.5, are weak on long work, and research across many sources comes back shallow. Split the work into more and smaller briefs than you would for a stronger model, and judge how far from the task.

## Brief

- Give the smallest brief that lets the agent complete and verify the work: the objective and expected output, the inputs and relevant decisions, the files or components it owns and its write boundaries, constraints, completion conditions, and the verification required. Write it by the rules of `handoff` for sources, what the agent can access and delimiting pasted material.
- Name the check that decides: a test or script. The agent runs it and reports; you run it again when the work comes back (see Reconcile). For code, follow [determinism](../../library/modules/determinism.md). Do not accept "it works" from a report.
- When an authoritative plan already holds the objective, context, process and output, use its unit as the brief: do not create a second plan or copy the parent plan. Keep only that source, a few high-stakes stop conditions, the immediate request, and a verify-by only if the plan's definition of done is vague.
- Keep established facts, constraints and sourced context in the context section. Add a separate section for assumptions and unresolved context only for material uncertainties not already stated; write "None identified" when there are none.
- A brief no stage file holds is transient: write it to the scratchpad or a temporary folder, not into the repository's documents or tooling folders, and save it in the repository only when the user asks.
- Show the brief to the user before launching only when they ask to see it or the task was not previously defined.

## Launch

### Claude subagent

Use the Agent tool with the brief as the prompt, and set `model` only when the user chose one. For agents that write in parallel, use `isolation: "worktree"`. Run it in the background and carry on; the report arrives as a notification. The agent's report is not shown to the user, so relay what matters.

### Codex

Run [scripts/run-codex.sh](scripts/run-codex.sh) once per brief: `[CODEX_IN_PLACE=1] scripts/run-codex.sh <name> <brief-file> [base-ref] [model] [effort]`. Start each run with Bash `run_in_background: true`; the script prints the run folder when done.

- `base-ref` applies in worktree mode and defaults to `HEAD`; for a sequential step, use the prior task's branch.
- Default to the user's checkout with `CODEX_IN_PLACE=1`, one task at a time. Use worktree mode (a sibling folder `<repo>-codex/<name>`, branch `codex/<name>`) only for parallel tasks. Never run two tasks in one checkout.
- In place, the script snapshots tracked files in `base`; review with `git diff $(cat <run-folder>/base)` and compare `status-before.txt` with `status-after.txt` for new files. The brief must forbid git commands that change state.
- Defaults: model `gpt-6-luna`, effort `xhigh`; never `gpt-6.1-sol`; override only when the user or the plan names another setting.
- If the run folder already has a `status` file, the script stops. Set `CODEX_RERUN=1` to deliberately rerun it.
- Run folders are `~/.codex-runs/<repo>/<name>/`, or under `$CODEX_RUNS_DIR`. Read `status` (`exit=0` means finished; otherwise read `stderr.log`), `last-message.md` (Codex's report), `diffstat.txt`, `worktree` and `base`. Read the actual diff; open `events.jsonl` only if the diff and the report disagree.
- Send a correction with `codex exec resume` in the same checkout, or write a new brief. Do not edit Codex's work unless the user asks.
- Do not commit or merge unless the user says so. Remove stale worktrees with `git worktree remove` before reusing them. The sandbox notes in `dispatch-codex` ("Safety and gotchas") apply here too.

## Reconcile

- Each agent reports what it changed or found, the verification it ran and its results, remaining uncertainty, and any unmet completion condition. An implementer also reports where and why it deviated from the brief, keeps the earlier version retrievable when it revises after feedback, resolves minor issues within scope, and on a blocking ambiguity pauses the affected work and asks.
- Check each handoff against the assignment, the agreed scope, the criteria and the evidence, using the submitted artifacts and without rewriting what the agent wrote: out-of-scope changes, missed requirements, relevant verification, unsupported conclusions, and lost uncertainty or disagreement. Reconcile within the authorized scope and report unresolved conflicts, unsupported claims and incomplete work plainly. With several reviewers, integrate their assessments.
- Run the check you named yourself, in the checkout the agent worked in, and judge by its result, not by the agent's account of its own run: a report is a reading. You can use the [harness gate in dispatch-codex](../dispatch-codex/SKILL.md#shared-code) to record it instead of running it by hand. If you cannot run it (a database out of reach, say), say so and report the work as unverified, not as passed.
- Treat silence from a running agent as pending; stop it only for an explicit error, timeout, blocked state or user instruction.
- Handing work over does not create a new identity for it. The incoming agent continues the same task and scope, receiving the current state, unresolved points, next action and existing IDs; changing the executor does not make provisional work complete.
- A standalone request to delegate authorizes that assignment without a durable plan. Return a standalone review in the conversation unless persistent output is requested; if it is requested without a destination, settle the destination with the user first. Do not create a plan just to give a review an ID or location.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

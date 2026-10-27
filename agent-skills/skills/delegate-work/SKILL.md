---
name: delegate-work
description: Hand one short, objective task to another agent, either a Claude subagent or a run of the harness on Codex or Claude, and check what comes back. Use when the user asks to delegate, or when a self-contained task suits a cheaper or parallel agent; do not use for work with several stages, a plan or a branch review (use plan, research, council or code-review), or to continue in a new chat (use handoff).
---

# Delegate work

One bounded, objective task goes to another agent; its result is checked by you, not by its own report.

## Decide

- Delegate only a task whose inputs fit in a brief and whose result a command can check. Advice needs only the context to answer it.
- One agent for cohesive work. Several only when their files and outputs are independent; give each its own files, and never let implementation and review change the same target.
- A weak model (`gpt-6-luna`, Haiku) fails on long work and goes shallow on research across many sources: make more and smaller briefs.

## Brief

- Write it by the rules of [handoff](../handoff/SKILL.md) for sources, access and pasted material. Give the objective, the files the agent owns, what it must not touch, and the check that decides: a test or script.
- When an authoritative plan already holds these, use its unit as the brief.
- A transient brief goes in the scratchpad, not in the repository; save it there only if the user asks.

## Launch

- **Claude subagent:** the Agent tool with the brief as the prompt; set `model` only when the user chose one, and `isolation: "worktree"` for agents that write in parallel. The report is not shown to the user: relay what matters.
- **Harness agent:** [scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]`, started with `run_in_background: true`. Codex by default (`gpt-6-luna`, `xhigh`; never `gpt-6.1-sol` unless the user says); `HARNESS_BACKEND=claude` runs it on `claude -p` (`sonnet`, `high`). It works in the checkout with `DELEGATE_IN_PLACE=1`, one task at a time, or in a sibling worktree `<repo>-delegate/<name>` on branch `delegate/<name>`, the only way to run tasks in parallel. The brief must forbid git commands that change state. `DELEGATE_RERUN=1` reuses a run folder that already has a `status` file.
- It prints the run folder, `~/.delegate-runs/<repo>/<name>/` (or under `$DELEGATE_RUNS_DIR`): `status` (`exit=0` means finished; otherwise `stderr.log`), `last-message.md` (the agent's report), `diffstat.txt`, `worktree` and `base`. In place, read the diff with `git diff $(cat <run-folder>/base)` and compare `status-before.txt` with `status-after.txt` for new files.
- To correct the work, write a new brief or resume the agent in the same checkout. Do not edit its work unless the user asks, and do not commit or merge unless the user says so.

## Reconcile

- Run the named check yourself, in the checkout the agent worked in, and judge by its result: a report is a reading. If you cannot run it, say the work is unverified.
- Read the actual diff against the brief: out-of-scope changes, missed requirements, conclusions without evidence. Report unresolved conflicts and incomplete work plainly.
- Treat a silent running agent as pending; stop it only for an error, a timeout, a block or an instruction from the user.
- Tests of the launcher are in [tests/](tests/test-delegate-run.sh).

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

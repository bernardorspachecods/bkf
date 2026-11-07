---
name: delegate-work
description: "Hand one short, objective task to another agent, either a Claude subagent or a run of the harness on Codex or Claude, and check what comes back. Use before you start any self-contained task that would take you more than a few minutes or touch more than a few files, and whenever the user asks to delegate: such work is not done by the main agent and never goes to a fork of it. Do not use for work with several stages, a plan or a branch review (use plan, research, council or code-review), or to continue in a new chat (use handoff)."
---

# Delegate work

One bounded, objective task goes to another agent; its result is checked by you, not by its own report.

## Decide

- Prefer this to a plan when the work is simple and quick: the cheaper agent does it and you review it at the end, which costs little because it is small. If the work has units that depend on one another and each needs its own reviewer, it is a plan.
- Delegate only a task whose inputs fit in a brief and whose result a command can check. Advice needs only the context to answer it.
- One agent for cohesive work. Several only when their files and outputs are independent; give each its own files, and never let implementation and review change the same target.
- Delegating is the default, not an exception: if you are about to spend more than a few minutes on a task that fits a brief, write the brief instead. The agent is always a weaker model, never a fork or a copy of yourself. The default path is the harness agent on Codex (`gpt-6-luna`); use a Claude subagent (`haiku`) only when the user asks for it or the harness cannot run the task.
- A weak model (`gpt-6-luna`, Haiku) fails on long work and goes shallow on research across many sources: make more and smaller briefs.

## Brief

- Write it by the rules of [handoff](../handoff/SKILL.md) for sources, access and pasted material. Give the objective, the files the agent owns, what it must not touch, and the check that decides: a test or script.
- When an authoritative plan already holds these, use its unit as the brief.
- A transient brief goes in the scratchpad, not in the repository; save it there only if the user asks.

## Launch

- **Claude subagent:** the Agent tool with the brief as the prompt. Always set `model: "haiku"` unless the user chose another: without `model` the subagent inherits your own expensive model. Never use `subagent_type: "fork"`, which is your own model by definition. Set `isolation: "worktree"` for agents that write in parallel. The report is not shown to the user: relay what matters.
- **Harness agent:** [scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]`, started with `run_in_background: true`. Codex by default (`gpt-6-luna`, `high`; never `gpt-6.1-sol` unless the user says); `HARNESS_BACKEND=claude` runs it on `claude -p` (`sonnet`, `high`). By default it uses a sibling worktree `<repo>-delegate/<name>` on branch `delegate/<name>`; a newly created worktree runs the committed `.plan-run.json` setup before the agent starts. `DELEGATE_IN_PLACE=1` uses the checkout instead. A bridge object in that base config lets the agent run listed, unchanged pnpm scripts outside the sandbox with `.plan-porteiro/ponte pnpm <script> [args...]`; the delegated brief explains its limits. The brief must forbid git commands that change state. `DELEGATE_RERUN=1` reuses a run folder that already has a `status` file and does not prepare a reused worktree.
- **One Bash call per task, each with `run_in_background: true`.** That is the only way the user sees each task in the footer of their shell and is notified when it ends. Never launch with `nohup`, `&`, `disown`, `setsid`, `tmux`, a `for` loop or a subshell, and never put several tasks in one call: the harness cannot track them, so they run invisibly. For parallel tasks, send the Bash calls in the same response. After launching, check that each task shows as a background task; if one does not, stop it and relaunch it correctly.
- It prints the run folder, `~/.delegate-runs/<repo>/<name>/` (or under `$DELEGATE_RUNS_DIR`): `status` (`exit=0` means finished; `prepare-failed` means worktree setup stopped before launch), `last-message.md` (the agent's report), `diffstat.txt`, `worktree` and `base`. Worktree setup output is in `prepare.log`; bridge requests are logged in `porteiro.log`. In place, read the diff with `git diff $(cat <run-folder>/base)` and compare `status-before.txt` with `status-after.txt` for new files.
- Close a small gap yourself: when the work is mostly right and what is missing is quick, simple and clear from the brief and the check (a missed case, a wrong name, a failing line), fix it directly in the checkout. Sending it back costs a new brief, a run and a second review, which is more than the fix. Then run the check again and say what you changed.
- Send it back only when the gap is large, needs the agent's context, or shows the brief was wrong (write a new brief or resume the agent in the same checkout). Do not rewrite the agent's work wholesale in its place.
- Do not commit or merge unless the user says so.

## Reconcile

- Run the named check yourself, in the checkout the agent worked in, and judge by its result: a report is a reading. If you cannot run it, say the work is unverified.
- Read the actual diff against the brief: out-of-scope changes, missed requirements, conclusions without evidence. Report unresolved conflicts and incomplete work plainly.
- Treat a silent running agent as pending; stop it only for an error, a timeout, a block or an instruction from the user.
- Tests of the launcher are in [tests/](tests/test-delegate-run.sh).

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

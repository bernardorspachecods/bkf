---
name: delegate-work
description: "Hand one short, objective task to another agent, either a Claude subagent or a run of the harness on Codex or Claude, and check what comes back. Use when the user asks to delegate, or chooses delegation when you ask how a self-contained task that would take you more than a few minutes or touch more than a few files should be done. Do not use for work with several stages, a plan or a branch review (use plan, research, council or code-review), or to continue in a new chat (use handoff)."
---

# Delegate work

## Decide

- Delegate only if input fits a brief and a command checks the result; advice needs only context. Use one agent for cohesive work, several only for independent files and outputs. Never let implementation and review change the same target.
- If a brief-sized task takes more than a few minutes, ask whether to delegate or do it yourself, without stating a time estimate; brief only if they choose. Agents are weaker: default to the Codex harness (`gpt-6-luna`); use a Claude subagent (`haiku`) only if requested or the harness cannot run the task. Split long work or multi-source research into smaller briefs for weak models.

## Brief

- Follow [handoff](../handoff/SKILL.md) for sources, access and pasted material. Include objective, owned/excluded files and a deciding test or script; use an authoritative plan's unit if it has these.
- Keep transient briefs in the scratchpad, not the repository; save only if asked.

## Launch

- **Claude subagent:** use the Agent tool with the brief as prompt. Always set `model: "haiku"` unless the user chose another, or it inherits your expensive model. Set `isolation: "worktree"` for parallel writers. Relay relevant findings; the report is not shown to the user.
- **Harness agent:** run [scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]` with `run_in_background: true`. Default: Codex `gpt-6-luna`, `high`; never `gpt-6.1-sol` unless user says. `HARNESS_BACKEND=claude` runs `claude -p` (`sonnet`, `high`). Default sibling worktree `<repo>-delegate/<name>` uses branch `delegate/<name>`; a new worktree runs committed `.plan-run.json` setup before launch. `DELEGATE_IN_PLACE=1` uses the checkout. Base-config bridge: listed, unchanged pnpm scripts run outside sandbox via `.plan-porteiro/ponte pnpm <script> [args...]`; the delegated brief explains its limits. Forbid git state-changing commands. `DELEGATE_RERUN=1` reuses a run folder with `status`, without worktree setup.
- **Launch restrictions:** one Bash call per task, each with `run_in_background: true`; this alone shows the task in the user's shell footer and sends a completion notification. Never launch with `nohup`, `&`, `disown`, `setsid`, `tmux`, a `for` loop or subshell, or put several tasks in one call (the harness cannot track them). For parallel tasks, send Bash calls in the same response. Check each launch shows as a background task; if not, stop and relaunch it correctly.
- Run folder `~/.delegate-runs/<repo>/<name>/` (or `$DELEGATE_RUNS_DIR`) has `status` (`exit=0` finished; `prepare-failed` setup stopped), `last-message.md`, `diffstat.txt`, `worktree`, `base`; setup log: `prepare.log`; bridge log: `porteiro.log`. In place, read `git diff $(cat <run-folder>/base)` and compare `status-before.txt`/`status-after.txt` for new files.
- If the work is mostly right and the gap is quick and clear from the brief and check, fix it in the checkout, rerun the check and say what changed. Return large gaps, ones needing agent context, or a wrong brief; write a new brief or resume the agent in the same checkout. Never rewrite its work wholesale.
- Do not commit or merge unless the user says so.

## Reconcile

- Run the named check in the agent's checkout; trust its result, not report. If it cannot run, say unverified.
- Check diff against brief for scope, missed requirements and unsupported conclusions; report conflicts or gaps.
- A silent agent is pending; stop only for an error, timeout, block or user instruction.
- Launcher tests: [tests/](tests/test-delegate-run.sh).

## Runtime metadata

Invocation/display metadata: [agents/openai.yaml](agents/openai.yaml).

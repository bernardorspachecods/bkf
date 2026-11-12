# One Codex agent outside a plan

Read this only for the rare case of a single self-contained task the user wants
run on Codex, with no units or reviews. Anything sequential, with several
stages or needing a review is a plan: write the units and drive it with
[conversation-run.md](conversation-run.md) or [script-run.md](script-run.md).
Do not use this to avoid writing a plan.

The brief, the check and the reconciliation follow the plan's rules: write it
as a unit brief ([SKILL.md](SKILL.md) section 2, with a `gate`), keep it in the
scratchpad, and run the gate in the agent's checkout instead of trusting its
report.

## Launch

[scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]`, one Bash call with `run_in_background: true` per task (the launch guard refuses `nohup`, `&`, loops and several tasks in one call; parallel tasks are separate calls in the same response).

- Default: Codex `gpt-6-luna`, `high`; never `gpt-6.1-sol` unless the user says. `HARNESS_BACKEND=claude` runs `claude -p` (`sonnet`, `high`).
- Worktree `<repo>-delegate/<name>` on branch `delegate/<name>`; a new worktree runs the committed `.plan-run.json` setup first. `DELEGATE_IN_PLACE=1` uses the checkout; `DELEGATE_RERUN=1` reuses a run folder that has a `status`.
- The base-config bridge lets the agent run listed, unchanged pnpm scripts through `.plan-porteiro/ponte pnpm <script> [args...]`; the brief explains its limits.
- Forbid git state-changing commands in the brief. Do not commit or merge unless the user says so.

## Result

Run folder `~/.delegate-runs/<repo>/<name>/` (or `$DELEGATE_RUNS_DIR`): `status` (`exit=0` finished, `prepare-failed` setup stopped), `last-message.md`, `diffstat.txt`, `worktree`, `base`, logs `prepare.log` and `porteiro.log`. In place, read `git diff $(cat <run-folder>/base)` and compare `status-before.txt` with `status-after.txt` for new files. A silent agent is pending.

A small, clear gap you fix in the checkout, rerun the gate and say what changed; a large one, or one needing the agent's context, goes back with a new brief. Never rewrite its work wholesale. Launcher tests: [tests/test-delegate-run.sh](tests/test-delegate-run.sh).

# Run driven from the conversation

`--dir` is a scratch folder for each unit's evidence, not a record.

## One unit

1. **Begin:** `scripts/plan-unit.sh begin <brief> --dir <scratch>` before touching the code. Each unit's base is the state the previous one left.
2. **Implement** as the user chose: you, under the [implementation guide](roles/agentic-work-implementation.md); a Claude subagent, whose prompt is the brief followed by that guide; or an agent you launch (see below). Do not commit, stage, stash or reset. **The implementer leaves the gate receipt as its last step:** `scripts/plan-unit.sh gate <brief> --dir <scratch>` (a Claude agent in its own shell; tell it the exact command), or `.plan-porteiro/ponte gate` for an agent launched with `DELEGATE_UNIT_DIR` (below). Do not run the gate commands yourself.
3. **Check:** `scripts/plan-unit.sh check <brief> --dir <scratch> --review-model <model> [--review-backend codex|claude] [-r <effort>]`. `check` accepts a green receipt for the same tree and gate commands and does not run the gate again (`gate: pass (receipt, …)`); with no receipt, or a stale one, it runs the gate. Later checks resume the same reviewer.
4. **Act on the exit code.** `0` pass: next unit. `1` back: read `problems:` in the output, fix it (or send it back to the implementer) and `check` again. `2` escalate, or the reviewer says the brief is wrong: stop and tell the user; if the brief changes, `begin --restart`. `3` the check itself failed (no base, missing model, no reviewer output): fix the cause and repeat. On pass or escalate, `check` closes the unit's task card.

## When you or the user review

Run `check --gate-only`: it uses the receipt or runs the gate, and writes the diff (`patch:`), with no reviewer. After review, close the card with `scripts/plan-unit.sh close <brief> --dir <scratch> --as done|failed`: `done` deletes the card, `failed` leaves it failed. To record why it failed, pass `--note TEXT`.

## Launching an implementer

A Claude implementer is always a subagent, never launched through a shell. The launcher below is only for a Codex implementer, whose sandbox cannot reach what the gate needs.

[scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]`, one Bash call with `run_in_background: true` per agent (parallel launches are separate calls in one response). It appends the implementation guide; do not add it yourself.

- **Do not wait with a Monitor or by polling.** The background Bash call notifies you when the agent exits, and `check` reports each unit's end; a Monitor on a gate or an agent adds nothing and expires unseen.
- Default: Codex `gpt-6-luna`, `high`; never `gpt-6.1-sol` unless the user says.
- **Where it works.** In a run, launch with `DELEGATE_IN_PLACE=1` after `begin`, so `check` reads the agent's diff from the checkout. Without it the agent works in the worktree of its task card, `<repo>/.claude/worktrees/<slug>` on branch `task/<slug>` (`bkf task show` names both), which first runs the committed `.plan-run.json` setup; then run `begin` and `check` inside that worktree.
- **Back rounds.** Relaunch under the same name with `DELEGATE_RERUN=1` to reuse the unit's card. Keep that name for every round.
- **The receipt and card.** Set `DELEGATE_UNIT_DIR=<scratch>/<unit>` (the folder `begin` made) so `check` can find the card. For a brief with a gate, the launcher tells the agent to run `.plan-porteiro/ponte gate`, which runs the gate outside its sandbox and writes the receipt there.
- The agent gets only the brief and its guide: forbid git commands that change state in the brief. Do not commit or merge unless the user says so.

The run folder is `~/.delegate-runs/<repo>/<name>/` (or `$DELEGATE_RUNS_DIR`): `task` (the id of the unit's card), `last-message.md`, `diffstat.txt`, `worktree`, `base`, logs `prepare.log` and `porteiro.log`. The state is the card: `bkf task show "$(cat <run>/task)"` shows `working` with the `paused` attention and the file count in its note when the agent finished and waits for you, `failed` (see `exit` or its note), or no card once a passed unit's card is closed. A silent agent is still working.

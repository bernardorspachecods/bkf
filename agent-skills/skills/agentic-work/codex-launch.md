# Launching a Codex implementer

Read this page only when a Codex agent implements.

[scripts/delegate-run.sh](scripts/delegate-run.sh) `<name> <brief-file> [base-ref] [model] [effort]`, one Bash call with `run_in_background: true` per agent (parallel launches are separate calls in one response). It appends the implementation guide; do not add it yourself.

- **Do not wait with a Monitor or by polling.** The background Bash call notifies you when the agent exits, and `check` reports each unit's end; a Monitor on a gate or an agent adds nothing and expires unseen.
- Default: Codex `gpt-6-luna`, `high`; never a Sol model (`gpt-6.2-sol`) unless the user says.
- **Where it works.** In a sequential run, launch with `DELEGATE_IN_PLACE=1` after `begin`, so `check` reads the agent's diff from the checkout. Without it the agent works in its own worktree, `<run>/worktree` on a new branch `delegate/<name>` made from the base, which first runs the committed `.plan-run.json` setup; then run `begin` and `check` inside that worktree. For a wave, run the launcher from inside the unit's worktree (`cd` to the path `worktree` printed) with `DELEGATE_IN_PLACE=1` and `DELEGATE_UNIT_DIR=<run>/units/<unit>`, so it works in that worktree and leaves the receipt in the unit folder.
- **Back rounds.** Relaunch under the same name with `DELEGATE_RERUN=1` to reuse the run folder and its worktree. Keep that name for every round.
- **The receipt.** Set `DELEGATE_UNIT_DIR=<run>/units/<unit>` (the unit folder) so the agent's receipt lands there. For a brief with a gate, the launcher tells the agent to run `.plan-porteiro/ponte gate`, which runs the gate outside its sandbox and writes the receipt there.
- The agent gets only the brief and its guide: forbid git commands that change state in the brief. Do not commit or merge unless the user says so.

The run folder is `~/.delegate-runs/<repo>/<name>/` (or `$DELEGATE_RUNS_DIR`): `base`, `worktree` (not made with `DELEGATE_IN_PLACE=1`), `last-message.md`, `diffstat.txt`, `exit` (the agent's exit status, written when it ends), logs `worktree.log`, `prepare.log` and `porteiro.log`. The state is the run folder: no `exit` yet means the agent is still working, and `exit` with `0` means it finished and `diffstat.txt` lists its changes. A silent agent is still working.

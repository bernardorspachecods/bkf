# Run driven from the conversation

`--dir` is the plan folder's `units/` directory (`~/.plan-runs/<repo>/<name>/units`; see [plan.md](plan.md)). A single unit outside a plan uses the same layout under a name for the task.

## One unit

1. **Begin:** From the main checkout, run `scripts/plan-unit.sh begin <brief> --dir <run>/units` before touching the code. Each unit's base is the state the previous one left.
2. **Implement** as the user chose: you, under the [implementation guide](roles/agentic-work-implementation.md); a Claude subagent, whose prompt is the brief followed by that guide; or a Codex agent (see [codex-launch.md](codex-launch.md)). Do not commit, stage, stash or reset. **The implementer leaves the gate receipt as its last step:** `scripts/plan-unit.sh gate <brief> --dir <run>/units` (a Claude agent in its own shell; tell it the exact command), or `.plan-porteiro/ponte gate` for a Codex agent.
3. **Check:** `scripts/plan-unit.sh check <brief> --dir <run>/units --review-model <model> [--review-backend codex|claude] [-r <effort>]`. `check` accepts a green receipt for the same tree and gate commands and does not run the gate again (`gate: pass (receipt, …)`); with no receipt, or a stale one, it runs the gate. Later checks resume the same reviewer.
4. **Act on the exit code.** `0` pass: next unit. `1` back: read `problems:` in the output, fix it (or send it back to the implementer) and `check` again. `2` escalate, or the reviewer says the brief is wrong: stop and tell the user; if the brief changes, `begin --restart`. `3` the check itself failed (no base, missing model, no reviewer output): fix the cause and repeat.

## When you or the user review

Run `check <brief> --dir <run>/units --gate-only`: it uses the receipt or runs the gate, and writes the diff (`patch:`), with no reviewer. Then decide on the diff yourself.

## A wave of parallel units

1. **Prepare:** For each unit of the wave, run `scripts/plan-unit.sh worktree <brief> --dir <units-dir> [--unit NAME] [--restart]` from the main checkout, with `<units-dir>` set to `<run>/units`. It snapshots the main checkout's current state, including uncommitted and untracked files, creates a detached worktree at `<units-dir>/<unit>/worktree`, applies the repository's `.plan-run.json` setup, and begins the unit with that state as its base; do not run `begin` for it. `--restart` starts the unit over. The command prints `worktree: <path>`.
2. **Launch:** Launch every implementer in one response. A Claude subagent's prompt is the brief, then the [implementation guide](roles/agentic-work-implementation.md), then the worktree path printed by the command with "work only in this folder" and its exact gate command: `<skill>/scripts/plan-unit.sh gate <brief> --dir <run>/units`. Use absolute paths for `<skill>` (the `agent-skills/skills/agentic-work` directory in this checkout) and `<run>/units`. A Codex agent: see [codex-launch.md](codex-launch.md).
3. **Check:** A unit's `gate` and `check` work on its worktree from any directory. Use the absolute script path `<skill>/scripts/plan-unit.sh` from outside the checkout. Check each unit as in [One unit](#one-unit): run `<skill>/scripts/plan-unit.sh check <brief> --dir <run>/units [--unit NAME] --review-model <model> [--review-backend codex|claude] [-r <effort>]`, or `<skill>/scripts/plan-unit.sh check <brief> --dir <run>/units [--unit NAME] --gate-only` when you review. Act on the same exit codes. Back rounds go to the same worktree.
4. **Integrate.** When every unit of the wave passed, write a wave brief with `## Result` listing the units integrated and `## Gate` containing the union of the units' gate lines. Run `scripts/plan-unit.sh begin <wave brief> --dir <run>/units` in the main checkout. Integrate one unit at a time with `scripts/plan-unit.sh integrate <brief> --dir <units-dir> [--unit NAME]` from the main checkout, with `<units-dir>` set to `<run>/units`. The command three-way merges the unit's changes into the main checkout's current state, writes the prior tree id to `<units-dir>/<unit>/pre-integration`, and never stages or commits.
   - Exit 0 means the integration is clean (`integrated: <n> file(s)`). Insertions at the same place are joined automatically and their paths appear after `joined:` and in `<units-dir>/<unit>/joined.txt`, even if the integration also leaves conflicts. Read the joined sections in the wave's diff.
   - Exit 1 means conflicts remain. The paths appear after `conflicts:` and in `<units-dir>/<unit>/conflicts.txt`. Before editing the marked files, keep copies of them. Resolve the markers while keeping what both briefs ask, then integrate the next unit. Send only the manual resolution diff, between the copies and the resolved files, to a reviewer to judge against both briefs. Never review your own resolution.
   - Exit 3 means the command failed and the checkout was left as it was. The command refuses to integrate a unit again or to write a file that still contains conflict markers.

   Run `scripts/plan-unit.sh check <wave brief> --dir <run>/units --gate-only` after all integrations. The wave gate runs once on the integrated checkout, and `patch:` is the whole wave's diff.
5. **Finish:** Run `scripts/plan-unit.sh discard <brief> --dir <units-dir> [--unit NAME]` for each unit to remove its worktree while keeping its unit folder. Update the plan file's unit states and Resume instructions.

A Claude implementer is always a subagent: in the main checkout for a sequential unit, and in its worktree for a wave. A Codex implementer is launched as [codex-launch.md](codex-launch.md) says.

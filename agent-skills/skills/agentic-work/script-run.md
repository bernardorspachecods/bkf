# Run driven by a script

You write `goal.md`, one brief per unit and `plan.txt`; [plan-run.sh](scripts/plan-run.sh) runs the units and stops when one needs you. Before the first `start` or `resume`, read [run-commands.md](run-commands.md).

## Starting

`plan-run.sh start [-m model] [-e effort] [-r review-effort] [--review-model model] [--review-backend codex|claude] [--takeover-after N] [--takeover-review reviewer|none] [-p checkpoints] [--in-place] [--from <ref>] <name> [<goal.md> <plan.txt>]`. `-e` is the implementers' effort, `-r` the reviewers' (default `-e`). `--review-model` and `--review-backend` put the reviewers on another model or backend; another backend needs its own `--review-model`. `resume` takes the same options and keeps what the run stored. Codex runs in the `fast` service tier; `PLAN_CODEX_TIER=` (empty) keeps the account default.

`plan.txt` holds one step per line, as brief paths relative to it; briefs on the same line run as a parallel group:

```
database.md
ui.md  ux.md      # run together
tests.md
```

- **Pending plans.** A plan ready but not launched lives in `~/.plan-runs-pending/<repo>/<name>/` (`goal.md`, `plan.txt`, briefs). `plan-run.sh pending` lists them; `start <name>` moves one into the run. The script numbers the units, so name the briefs without a number.
- **The run's worktree.** A run works in `<run>/tree` on a new branch `plan/<name>` and commits each passed unit there. With `--in-place`, do not edit the checkout during a step.
- **Task cards.** Each run and each unit has a card in the task store (`bkf task`), its unit cards under the run's: `<run>/task` and `<run>/<unit>/task` name them, and `bkf task show` or the Agentic app shows their state. A run waits at its final report as `working` with the `paused` attention; a passed unit's card is closed (deleted) and a failed one stays `failed`; `finish` closes the run's card.
- **Worktree setup.** The committed `.plan-run.json` sets the worktree up before the first unit, outside any agent: `{"worktree": {"copy": [".env.test"], "prepare": ["pnpm install --frozen-lockfile"]}}`. Never copy a secret: agents read everything in the worktree. `PLAN_PREPARE_TIMEOUT` (default 1800 s).

## Before every start: gates, lint, rehearsal

Run `plan-run.sh gates <plan.txt|run-name>` and read every unit's commands; it also lints the briefs, and `start` refuses on a lint error (`PLAN_ALLOW_LINT_ERRORS=1` only for a lint that is wrong). Then `plan-run.sh rehearse <plan.txt|run-name|pending-name>` runs every gate command once; fix the unexpected failures. Gate commands run through `bash -c`.

A check too slow for every gate (the full database suite) goes in `regression.gate` next to `plan.txt`, one command per line. The script runs it at each `-p` pause and before the final review; a failure stops the run: repair it and `resume`.

## Checkpoints and pilots

`-p each` or `-p 2,4` pauses after those steps (exit 3, `PAUSED`; a pause, not a failure); `resume -p none` clears it. Suggest where to pause and ask who the pauses are for: only you (read the diff, rerun what the reviewer's sandbox could not, resume) or also the user. Write the answer in the plan. **Pilot by kind:** pause after the first unit of each kind (moving files, a rule, a migration, an interface) before releasing the rest. Step numbers are the lines of `plan.txt`; add a unit only after every step already finished or running.

## While units run

- **Do not set up a Monitor or poll to wait.** The script stops when a unit finishes, pauses or needs you, and a run started with `run_in_background: true` notifies you when it exits. A Monitor on a gate or a unit adds nothing and expires unseen.
- `PLAN_GATE_TIMEOUT` (default 900 s per command), `PLAN_MAX_GATE_ROUNDS` (default 5).
- A false premise stops the unit before its first round: correct the brief or the checkout and `resume`.
- **Brief problems come to you.** An implementer's `BLOCKED: ...` or a reviewer's `VERDICT: brief` stops the unit: the brief may be wrong. Correct briefs in `00-input/units/` before `resume`; units not yet started, integrations and the final review read the current briefs.
- **Agents keep their conversation** across rounds and `resume`. Answer a `BLOCKED`, or say what you changed in the checkout, with `resume --say "<text>"` (or `--say-file`): without it the agent resumes knowing the problems but not your answer.
- **A rule the unit reviewers must apply goes in the briefs still to run:** `goal.md` reaches only the integration and the final review.

## Parallel groups

Run in series when unsure or when the group is two small units; parallel pays only for big, truly independent units, and costs an integration and a review of the combined result. A group's units are made in worktrees cut when the group starts, so a change to a shared file reaches a unit still to run only if it was in the checkout before; otherwise put it in that unit's brief.

## The bridge

While an implementer works, `.plan-porteiro/ponte gate` runs the unit's whole gate outside its sandbox and writes the gate receipt in the unit's folder; the loop accepts a green receipt for the same tree and gate commands and goes straight to the review, so the gate runs once. `.plan-porteiro/ponte <command...>` runs outside its sandbox the unit's gate commands and the `pnpm` scripts allowed by `bridge.pnpmScripts` in `.plan-run.json`. It reads that file from the unit's base, so change the list with the run stopped, and say in the final review that it grew. A measurement longer than about 30 minutes goes in the gate, not through the bridge.

## Takeover

With `--takeover-after N` (default 2) the N-th review that sends a unit back stops the run with the unit in `takeover`. Apply every problem the reviewer listed in the checkout the message names, then `plan-run.sh close <name>`; with `--takeover-review reviewer` (default) the same reviewer checks your delta, with `none` only the gate does, and you say so in the report. `--takeover-after 0` keeps only the review cap (`PLAN_MAX_ROUNDS`). `escalate`, `brief`, `BLOCKED` and a gate failing the same way twice are not takeovers: they point to the design or the brief.

## A stopped run

- Stop a run only through the task that runs `resume` (`TaskStop`), never by killing its processes: a killed run leaves running what it started, such as test databases.
- A run longer than a day falls behind its base branch: bring the base in between steps, not only at the end.
- A group's integration whose diff picked up your own edits: `plan-run.sh rebase-integration <name> <step> [--paths <path>...]`. One the user judged by hand: `plan-run.sh accept-integration <name> <step> --why <text>`. Then `resume`.

## Finishing

The user chooses `finish` or `finish --discard`. After the merge also remove what `finish` does not: the plan's branches and any background process or temporary database the run started.

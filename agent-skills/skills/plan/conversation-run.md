# Plan driven from the conversation

Read this only when the user chose to drive the plan from this conversation. Goal, units and briefs are written as in [SKILL.md](SKILL.md) sections 1 and 2; nothing goes to a run folder. The commands below write each unit's files (diffs, gate logs, reviews) into a scratch folder you choose, such as `$SCRATCH/units`: evidence for you, not a record.

Here this conversation does the work it was asked to do, so the first rule of "Coordinate a run" ("keep long work out of the coordinator") does not apply; the rest of that module does.

## One unit

```
begin ─► implement ─► check ─► pass ─► next unit
             ▲          │ back
             └──────────┘      escalate / brief ─► stop and ask the user
```

1. **Begin:** `scripts/plan-unit.sh begin <brief> --dir <scratch>` before touching the code. It saves the checkout as the unit's base (each unit begins from the state the previous one left) and copies the brief.
2. **Implement** as the user chose: you, or an agent you delegate to ([delegate-work](../delegate-work/SKILL.md)). Do not commit, stage, stash or reset.
3. **Check:** `scripts/plan-unit.sh check <brief> --dir <scratch> --review-model <model> [--review-backend codex|claude] [-r <effort>]`. It runs the brief's `gate` commands; a failing gate exits 1 with no reviewer. If they pass, the unit's reviewer (one conversation per unit, read-only, on that model and backend) reads the brief and the diff and answers. Later checks resume the same reviewer, which sees what changed and its own earlier problems.
4. **Act on the exit code.** `0` pass: next unit. `1` back: read `problems:` in the output, fix it (or send it back to the implementer) and `check` again. `2` escalate, or the reviewer says the brief is wrong: stop and tell the user; if the brief changes, `begin --restart`. `3` the check itself failed (no base, missing model, no reviewer output): fix the cause and repeat.

Fix the code, never the gate, to make a unit pass.

## When this conversation reviews

Run `check --gate-only`: it runs the gate and writes the diff (`patch:`), with no reviewer. Read the brief and that diff, and nothing the implementer wrote about its own work. You cannot have implemented that unit.

## What the user receives

As in [SKILL.md](SKILL.md) section 4, from verdicts and diffs and not from the implementer's account: which units passed in which round, what each gate and review checked, what stayed unverified.

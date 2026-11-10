# Plan driven from the conversation

Read this only when the user chose to drive the plan from this conversation. The goal, the units and the briefs are written as in [SKILL.md](SKILL.md) sections 1 and 2; nothing is written to a run folder, and the plan stays in the conversation. The commands below write the files of each unit (diffs, gate logs, reviews) into a scratch folder you choose, such as `$SCRATCH/units`; they are evidence for you, not a record.

This guide replaces the first rule of "Coordinate a run" ("keep long work out of the coordinator") for this driver, because here this conversation does the work it was asked to do. The checkpoints, the report and the rest of that module still apply.

## One unit

```
begin ─► implement ─► check ─► pass ─► next unit
             ▲          │ back
             └──────────┘      escalate / brief ─► stop and ask the user
```

1. **Begin.** Run `scripts/plan-unit.sh begin <brief> --dir <scratch>` before touching the code. It saves the checkout as the unit's base and copies the brief. Every unit begins from the state the previous one left, so the diff holds only this unit.
2. **Implement.** Whoever the user chose: you, or an agent you delegate to ([delegate-work](../delegate-work/SKILL.md)). Do not commit, stage, stash or reset.
3. **Check.** Run `scripts/plan-unit.sh check <brief> --dir <scratch> --review-model <model> [--review-backend codex|claude] [-r <effort>]`. It runs the brief's `gate` commands itself. If one fails it writes the problems and exits 1 without starting a reviewer. If they pass it starts a new reviewer process, read-only, on that model and backend, that reads the brief and the diff and nothing else.
4. **Act on the exit code.**

| Exit | Meaning | You |
| --- | --- | --- |
| 0 | pass | Next unit |
| 1 | back | Read `problems:` in the output. Fix it, or send it back to the implementer, then `check` again. A new round is a new reviewer process that sees the previous problems |
| 2 | escalate, or the reviewer says the brief is wrong | Stop and tell the user. If the brief changes, `begin --restart` |
| 3 | the check itself failed (no base, missing model, no reviewer output) | Fix the cause and run `check` again |

The gate stops being the same gate if you change it to make a unit pass: fix the code, not the gate.

## When this conversation reviews

If the user chose that you review, run `check --gate-only` instead. It runs the gate and writes the diff (`patch:` in the output) and no reviewer. Read the brief and that diff, and nothing the implementer wrote about its own work. The implementer must not be you in this case: a unit you wrote is reviewed by a reviewer process, not by you.

## What the user receives

As in [SKILL.md](SKILL.md) section 4, from the verdicts and the diffs, not from the implementer's account. Say which units passed in which round, what each gate and review checked, and what stayed unverified.

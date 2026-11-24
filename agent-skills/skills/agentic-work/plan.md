# Plan: more than one unit

Read this when the work is more than one unit. Everything in [SKILL.md](SKILL.md) still holds; this page adds the goal, the split and the contracts between units.

## How the run is set

**Ask one question, and no other about the way:** implement with a Haiku subagent, or with a Codex agent you launch? Both run in this conversation. Offer only those two; the user names anything else (you, another model, another reviewer) if they want it. You never choose or switch it yourself.

The run's checkpoints are the start (the goal and the split), the end and an escalation.

## 1. The goal and the units

Write the goal once, as `align-intent` defines the intent, and have the user confirm it and the split.

**Split along the seams of the work** (data, interface, behaviour), not the order of effort.

**Keep units small.** A unit is one change a reviewer can judge in one read. When its Result needs an "and", split it in two. Make mechanical changes (moves, renames, the same edit across many files) units of their own, apart from non-mechanical work. About four non-mechanical files is the ceiling. Units that run in parallel cost tokens, not time.

**When the split depends on something you do not know yet,** run a unit that only reads and reports first.

**Gates** follow the rules in SKILL.md. Run each gate line once before the first unit, and include the repository's quick check, if it has one.

**Review the briefs before the start checkpoint.** An agent other than the coordinator, with fresh context, reads the plan and briefs. It answers whether the plan serves the goal, any brief is incomplete, any unit is too large, independent units remain in sequence, and an implementer can build each unit on the first attempt from its brief. Put its findings in the plan.

## 2. The full brief

A unit of a plan adds to the minimal brief of SKILL.md the sections that carry facts between units. A section marked *only when* is left out otherwise.

~~~markdown
## Receives
*Only when an earlier unit leaves something this one needs.* Concrete facts this unit can rely on from earlier units.
```premise
grep -q "photo" db/schema.sql
```

## Leaves ready
*Only when a later unit needs something from this one.* Concrete facts later units can rely on.
~~~

Receives and leaves ready are the contracts between units, the same facts on both sides; the tools read the `premise` fence. **Check each gate line against the state the unit finds and the one it leaves:** a check of a rule a later unit closes cannot pass yet.

**Run independent units in waves.** Units with no dependency form a wave and run in parallel by default, each in its own worktree; units in one wave may change the same files. Run units in sequence only when one receives what another leaves ready. In a conversation run, the coordinator integrates the wave: a clean integration needs only the wave's gate. Send a hand-resolved conflict to a reviewer as the resolution diff, judged against both briefs. The integrator agent and its guide are for the script run only. See [conversation-run.md](conversation-run.md) for mechanics.

## 3. Plan state

Keep the plan in one folder, never in the scratchpad: `~/.plan-runs-pending/<repo>/<name>/` until the user approves the start checkpoint, then move it to `~/.plan-runs/<repo>/<name>/`. Store `plan.md`, `briefs/`, and `units/` there; `units/` holds every unit's `--dir`. In `plan.md`, keep the goal and done condition, an appended decision log (one dated line per decision, what and why), waves and unit states, gate lines, and one `Resume` section. Rewrite `Resume` at each checkpoint with the run's place and next step. Record every mid-plan decision before anyone acts on it. When a decision changes a brief, edit that brief; units not yet started read its current version.

When the repository has a plans folder, keep its entry for this plan to the idea and one line: `Running in ~/.plan-runs/<repo>/<name>/ since <date>, session <name>`. Write it at the start and remove it at the end; other sessions ask the owning session. At the end, move lasting decisions to their owner documents and remove the line. Copy the plan folder to `records/plans/<name>/` only when it is worth reviewing against the code later; otherwise delete it.

**Hand off with a complete plan.** At the start checkpoint, hand the plan to a fresh session of the same model when planning used much of the context. Between waves, hand off when more than half the context is used. Otherwise continue in the same conversation. Write the plan file so a fresh coordinator can read only it.

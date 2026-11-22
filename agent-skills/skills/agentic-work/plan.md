# Plan: more than one unit

Read this when the work is more than one unit. Everything in [SKILL.md](SKILL.md) still holds; this page adds the goal, the split and the contracts between units.

## How the run is set

**Ask one question, and no other about the way:** implement with a Haiku subagent, or with a Codex agent you launch? Both run in this conversation. Offer only those two; the user names anything else (you, another model, another reviewer) if they want it. You never choose or switch it yourself.

The run's checkpoints are the start (the goal and the split), the end and an escalation.

## 1. The goal and the units

Write the goal once, as `align-intent` defines the intent, and have the user confirm it and the split.

**Split along the seams of the work** (data, interface, behaviour), not the order of effort. A unit is ready when you can say what exists when it is done, a reviewer can judge it from its brief and diff alone, and it can be redone without redoing the others. Each unit costs a review round: make one separate only when it has criteria of its own, a dependency or parallelism separates it, or the user wants a checkpoint there. About ten files that are not mechanical is the ceiling.

**When the split depends on something you do not know yet,** run a unit that only reads and reports first.

**Gates** follow the rules in SKILL.md. Run each gate line once before the first unit, and include the repository's quick check, if it has one.

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

Units run one after another, each from the state the previous one left ([conversation-run.md](conversation-run.md)). Parallel work needs an integrator ([integration guide](roles/agentic-work-integration.md)).

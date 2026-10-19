---
bkf: document
description: Guides the integration role in a plan - how an agent brings the units of a parallel group together in the checkout, resolves conflicts and fixes what the combined review found. Read it when a brief points you here.
tags: [role-guide]
---

# Plan integration

You were given the briefs of a parallel group: units that were implemented apart,
each in its own copy of the repository, and passed their own reviews. Their diffs
are being brought together in the checkout you are in. Your job is to make that
combination hold, not to redo the units. Another agent reviews the combined
result, and it sees only the briefs and the combined diff.

These are principles with reasons, not a procedure. Adapt to the task, and keep
what the reasons protect.

## Two cases

- **A diff did not apply.** The brief lists which. Bring what that unit meant into
  the checkout: read its brief to know what it was for, and its diff to see what it
  did, then make the change where the code now stands. Resolve the conflict in
  favour of what both briefs ask for. If they ask for incompatible things, do not
  choose: stop and say so.
- **The combined review sent problems back.** Fix those and only those. They are
  contradictions between units, a "Receives" that another unit did not leave ready
  as stated, or clashes the units could not see in each other.

## Stay inside the briefs

- **Do not redo or improve a unit.** Each passed its own review against its own
  brief. Change only what the conflict or the problem forces.
- **Respect each unit's out of scope.** The briefs still bind what you may touch.
- **Do not touch git state.** No commit, stage, stash, reset or clean. The run
  records a base before integration and reads the combined diff from it.

## Verify before you hand over

Run the checks that the criteria of the units in the group name, for the places
you touched. A combination that was not run is not known to work.

## When to stop midway

Stop when the briefs cannot both hold: they contradict each other, or a unit left
something its neighbour relied on missing. Say which and why, with what you found.
The contract between the units was probably wrong, and the coordinator decides
whether to revise the briefs with the user.

## Output

The work itself, in the checkout, and your final message as the handoff:

- What you changed and why, per conflict or problem.
- The verification you ran and its results.
- Anything the units left in a state you did not resolve.

The handoff is your log. What proves the group holds is the review of the
combined diff.

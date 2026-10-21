---
bkf: document
description: Guides the implementation role in a plan - how an agent does one unit inside its brief, verifies it, records what it left ready and when to stop. Read it when a brief points you here.
tags: [role-guide]
---

# Plan implementation

You were given a unit brief with a result, what you can rely on, what you must
leave ready, what is out of scope and the criteria a reviewer will check. Your
job is to do that unit and nothing around it. Another agent reviews your work,
and it sees only the brief and your diff.

These are principles with reasons, not a procedure. Adapt to the task, and keep
what the reasons protect.

## Stay inside the brief

- **Do the result, stop at the stop.** The brief says when you are done. Extra
  work makes the diff harder to review and can break a unit that depends on
  what you left alone.
- **Respect out of scope.** If the result seems to need a change outside the unit,
  do not make it. Say so in the handoff. Files you did not make are not yours to
  change.
- **Rely only on what the brief says you receive.** If it is not true, or
  something else is needed, that is a reason to stop (see below), not to guess.
- **Leave ready what the brief says,** in the form it says. Other units rely on it.

## Verify before you hand over

Run the checks the criteria name, and any others that tell you the unit works.
Report what you ran and what came out, including failures. A unit that is not
verified is not done, and a reviewer cannot tell it from one that is.

When the brief has a `gate`, the script runs those commands itself after you finish
and sends the work back, with their output and no review, if one fails. Run them
yourself before you hand over, when you can. A command you cannot run from where you
work (a database that is out of reach, say) is named in the handoff, not skipped.
If the brief or the run gives you a way to run a command your sandbox cannot (a
database that is out of reach, say), use it only for what it allows. If a command is
refused, do not look for a way around it: say in the handoff what you needed.
Do not weaken a test or a check that already exists to make the gate pass.

**Show every new check failing once.** A test or script you write can pass without
checking anything. Run it against a wrong input, or a throwaway copy of the code with
the defect put back, and see it fail; then say in the handoff which check you broke,
how, and what failed. A check that has never failed is not yet evidence.

## When to stop midway

Work inside the brief. The one reason to stop is that the brief no longer holds:
what you were told you receive is missing or false, or the result cannot exist as
described. Then stop and tell the coordinator why, with what you found.

If you notice something outside the brief, write one line under "outside the
focus" in your handoff and do not pursue it.

## If the unit comes back

A review sends back a list of problems. Fix those and only those, then verify
again. Do not rewrite what the review accepted. If you think a problem is wrong,
say why in the handoff instead of ignoring it.

## Output

The work itself, in the checkout, and one handoff file at the place the brief names:

- The verification you ran and its results.
- Where the result differs from the brief, and why.
- What you left ready, as concrete facts another unit can rely on.
- The lines outside the focus, if any.

The handoff does not retell what you did: the diff is that record. It is your
log, and what you or the coordinator read to resume. It is not what proves the
unit is done: the review checks that against the diff.

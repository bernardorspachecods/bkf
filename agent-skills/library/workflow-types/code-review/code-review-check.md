---
bkf: document
description: Guides the checker in a code review - how an agent confirms each finding of one axis against the diff and the criteria, without redoing the review. Read it when a brief points you here.
tags: [role-guide]
---

# Code review checker

You were given a diff, the gate results, the criteria of one axis, and the
findings of the reviewer (or reviewers) of that axis. You are not the author of any of
them. Your job is narrow: for each finding, confirm that it is real. You do not review
the diff again, you do not add findings, and you do not judge whether the criteria are
right.

These are principles with reasons, not a procedure. Adapt to the task, and keep
what the reasons protect.

## What to confirm, per finding

- **The hunk exists.** The quoted hunk is in the diff, at the place the finding
  says, and was changed by it.
- **The criterion exists.** The rule or spec line is in the criteria you were given,
  and the quotation is accurate.
- **They connect.** The hunk does break the rule, or the spec line is unmet. This is
  the part to read carefully: a finding can quote a real hunk and a real rule and
  still be wrong about their relation. You may open the repository, read-only, to
  see the code around the hunk. Where a run can settle the question, run it instead
  of reading: the test the finding names, or a command that shows the behavior. Mark
  by what the run showed, not by how the code reads.

## Mark each finding

- **Confirmed.** All three hold. Say in a line where you saw it, or which run showed it.
- **Unconfirmed.** One does not, or you could not tell. Say which and why in a line,
  with the run if you made one. Do not drop it: the report shows it as unconfirmed,
  because you can be wrong too.

If two reviewers reported the same problem, merge them into one finding and keep
the better-supported wording.

## Do not add and do not soften

Do not add findings you notice. Write them in one line under "outside the findings"
and do not mark them. Do not change a finding's wording to make it more or less
severe; confirm it or not.

## Output

Write `checked.md` in your own folder: the findings in the reviewers' order, each
with its mark and the line or run that supports it, then the "outside the findings"
line if any. State at the top how many were confirmed and how many were not.

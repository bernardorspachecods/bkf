---
bkf: document
description: Guides the completeness check of a council report - how a reviewer checks that the chairman left nothing out of the report that the advice and the reviews hold and that matters to the question. Read it when a brief points you here.
tags: [role-guide]
---

# Council completeness check

You were given a question, the five responses with the key that identifies them,
the five reviews, and the chairman's report. You are not the author of any of them.

Your job is narrow: check that the chairman did not cut what mattered. The report
chooses what goes in front, and a choice like that can drop a view or a warning.
You are not here to judge the question, the advisors or the conclusion. Those are
settled.

These are principles with reasons, not a procedure. Adapt to the task, and keep
what the reasons protect.

## What to check

Go through the responses and the reviews and, for each part, find where it went in
the report:

- **Each advisor's position** is in the report, including the ones that disagree
  with the rest, in a form that advisor would recognize.
- **Each advisor's strongest counterargument and key risk** that bear on the
  question are in the report, or dropped with a stated reason.
- **What the reviewers raised** that survived is in the report: the strongest
  points, the weak points they found and what all the responses missed.
- **Disagreement is not smoothed.** Where the advisors split, the report shows
  the split and does not present the majority as the answer.

Material the chairman left out on purpose, with a line saying why, is not a cut.
Something that matters to the question and is missing without a word is.

## Show what you checked

A verdict with no evidence cannot be told apart from a skim. Before the list of
cuts, write what you went through:

- **For every response and every review you went through, one line:** the point,
  and where it is in the report (front, dropped with a reason, or not found).
- **A pass is this same list with no cuts under it.** It is never a single
  sentence saying nothing was left out.
- **If you did not open part of the input, say which part.**

## Output

Write `## What I checked`, then the list of what was left out or cut, each pointing
to where it is in the source. If nothing was, say so. The last line is the verdict,
exactly one of `VERDICT: pass`, `VERDICT: back` or `VERDICT: escalate`, with nothing
after it. A script reads that line, so any other form counts as a failed review.

The list goes back to the chairman, up to the cap of rounds the run sets. If the
same cut returns after being sent back, escalate: the report or the brief is
probably what is wrong.

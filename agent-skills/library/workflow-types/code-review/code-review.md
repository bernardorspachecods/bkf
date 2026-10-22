---
bkf: document
description: Guides a code review of a branch, pull request, range or working tree, for the coordinator who works with the user. Covers when to review, how to set up the target and run its gate, how the two axes and their checkers run apart, and what the user receives.
tags: [review, code]
---

# Code review

## When to use

Use this when the user wants a branch, a pull request, a range of commits or the
working tree reviewed. The review has two axes and reports them side by side:
**Standards** (does the code follow the repository's documented standards?) and
**Spec** (does it do what the originating issue or spec asked?). Fixing what the
review finds is a separate task; nothing is sent back from here.

## How to read this

These are principles with reasons, not a procedure. Adapt to the task, and keep
what the reasons protect.

- **Two axes, never merged.** A merged list or a single verdict hides which kind
  of problem the change has. The report never picks a winner across axes.
- **Reviewers are not the author,** and each axis has its own agent, which does not
  see the other axis' criteria.
- **A review is a claim to be checked.** A checker confirms each finding against
  the diff, because a reviewer on a small model invents findings.

## 1. The target

Before anything runs, settle with the user:

- **What is reviewed.** A range such as `main...feature` (three dots, so the
  comparison is against the merge-base), or the working tree. Commits come with a
  range. You pass the range to the script as it is.
- **The spec.** Look for it in this order: an issue reference in the commit
  messages, a path the user gave, a spec file named for the branch or the feature.
  If none exists, ask once. If there is none, the Spec axis is skipped and the
  report says "no spec available".
- **The standards.** The repository documents give them: pass each file that holds
  the coding standards, and the code-smell module if the repository has one. If
  there are none, the Standards axis is skipped and the report says so.

An axis with no criteria is not run. Fewer than two axes is a smaller review, not
a different workflow, and the report names what was skipped.

## 2. Gate

Before the axis reviewers start, the repository's own deterministic checks run on
the target: its tests, type check, lint and any other gate the repository defines.
You find the commands in the repository's documents or scripts, such as the README,
the package scripts or the CI configuration, and pass each to the script with `-g`.
The script runs them itself, outside the agents, records each command and its result
in `00-input`, and gives them to both reviewers as evidence.
Following the `core-code-principles` module, these checks, not a reviewer's reading, are
the evidence of what a run can show.

- **A red result is a finding.** Say so to the user at once. The review goes on, but
  no reviewer can override a red result: it stands in the report as a finding of its own.
- **No check is a gap.** The `core-code-principles` module says a missing check is a gap,
  not a pass: if the repository has no check for the changed behavior, report that
  absence as a gap.

## 3. The roles

A script builds the briefs from fixed templates, pins the diff, runs the agents and
builds the report. You write only the target and name the criteria.

| Role | Does | Receives |
| --- | --- | --- |
| [Axis reviewer](/code-review-axis.md) (Standards, Spec) | Finds where the diff breaks its criteria | The diff, the commit list, the gate results and its own criteria |
| [Checker](/code-review-check.md) (one per axis) | Confirms each finding against the diff | The diff, the gate results, the criteria of that axis and its reviewers' findings |

```
Setup ─► Gate ─► Standards reviewer ─► Standards checker ─┐
                         Spec reviewer      ─► Spec checker      ─┴─► Report ─► You add the summary ─► User
```

Rules that hold whatever the models:

- **Each agent works in its own folder and writes one file.** The sandbox stops
  writes outside the folder but not reads, so a brief tells each agent to open only
  its own folder and the repository. Isolation between the axes is an instruction,
  not a barrier.
- **A second reviewer per axis is an option,** for a change that matters. The
  checker's job is precision: it removes false findings, not misses. A second
  independent reviewer per axis is the only remedy for misses, and the findings are
  merged before the check.

## 4. What the user receives

The script writes the report, with the two axes under their own headings and each
finding marked confirmed or unconfirmed. You add at the top: the gate results
(each command and its result), the number of findings per axis and the worst one in
each. Do not restate the findings.

State in the report, plainly, that a clean axis is not a clean diff: the checkers
confirm what was found, not what was missed. Also state what the review could not
verify by code, such as how a change looks on screen or matters of opinion.

## 5. Where the work lives

One review is one folder in `~/.review-runs/<name>/`: `00-input` (the pinned diff,
the commits, the criteria, the gate results), `01-review`, `02-check` and
`report.md` at the top. A review is usually read and dropped. When it is done, the user chooses: keep the
record, copied into `records/reviews/` in the repository, or delete the run.

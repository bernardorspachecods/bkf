---
name: code-review
description: Use when the user asks for a code review of a branch, pull request, revision range or working tree run by separate agents, or a stopped review run to resume. Looking over your own change while you work is part of code-work.
---

# Code review

<!-- inject: ../../modules/coordinate-a-run.md -->
<!-- BKF:GENERATED-INJECTED -->
## Coordinate a run

The skills of the plan, code review, council and research workflows include this module. Their coordinator guides own the phases, files and roles; this module holds what every run shares.

- Stay out of the roles. The coordinator keeps the conversation with the user and prepares the briefs and inputs; it does not act as researcher, implementer, advisor or reviewer, even for a small run. A gap in an agent's work goes back to a fresh agent through the script, not to the coordinator to fill.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start and judges at the end; between checkpoints do not message them: no progress updates, status summaries or questions about small decisions. Decide those within the intent agreed with the user (`align-intent`) and continue, and stop and ask only as that intent says. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked.
- An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- If the same problem returns after being sent back, or the script's cap on rounds is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.
<!-- BKF:GENERATED-INJECTED-END -->

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
| [Axis reviewer](roles/code-review-axis.md) (Standards, Spec) | Finds where the diff breaks its criteria | The diff, the commit list, the gate results and its own criteria |
| [Checker](roles/code-review-check.md) (one per axis) | Confirms each finding against the diff | The diff, the gate results, the criteria of that axis and its reviewers' findings |

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

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

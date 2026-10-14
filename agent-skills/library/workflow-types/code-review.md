---
bkf: document
description: Defines a two-axis review workflow that checks a pinned change against repository standards and its originating specification, then reports each axis separately. Correcting review findings is a separate task.
tags: [review, code]
---

# Code review

**Use when** the user wants to review a branch, a pull request, or
work-in-progress changes. The review runs on two axes and
reports them side by side: Standards (does the code follow the repository's
documented coding standards?) and Spec (does the code do what the originating
issue or spec asked?). It may be run in a reduced form; see "Required core and optional stages".

## Declaration

```bkf-workflow
steps:
  - work_unit:
      title: "Review setup"
      steps:
        - stage:
            key: setup
            title: "Review setup — pin the diff and find the spec and the standards sources"

  - work_unit:
      title: "Two-axis review"
      steps:
        - parallel:
            - stage: {title: "Standards axis — check the diff against the documented standards and the common code smells"}
            - stage: {title: "Spec axis — check the diff against the originating spec"}
        - stage:
            title: "Final report — both axes side by side"
```

## Required core and optional stages

- **Required core:** each axis that has criteria is checked by its own agent, which is not the author of the change, against its own criteria, and the axes are reported separately. The spec axis is skipped when there is no spec (see "Going back and limits"), and the report says so.
- **Optional stages:** setup may be done by the coordinator inline for a small, already-pinned target, provided the diff is confirmed non-empty and the spec and standards sources are named. The report is the two axis reports under their headings, verbatim or lightly cleaned, with no separate synthesis agent.
- Fewer than two axes, a merged list, or a single overall verdict is not a reduced form of this workflow type. A light run is one pinned diff, one agent per axis, and one report with both axes under their headings; one agent in two passes is only the fallback when delegation is unavailable.

## Stage notes

| Stage | Receives | Does not receive | Output |
| --- | --- | --- | --- |
| Setup | What the user wants reviewed (a branch, a pull request, a range, or the working tree), the repository | | The diff command for it (for a branch or range, three-dot so the comparison is against the merge-base) and the commit list if there is one, with any ref confirmed to resolve and the diff confirmed non-empty, so a bad ref or empty diff fails here and not inside two agents. The spec source, looked for in order: issue references in the commit messages, a path the user passed, a spec file named for the branch or feature, or ask. The standards sources the repository documents. |
| Standards | The diff command and commit list, the standards files and the common code smells in full | The spec | Each place the diff breaks a documented standard (cites the file and rule) and each code smell it spots (names it and quotes the hunk). Under 400 words. |
| Spec | The diff command and commit list, the spec | The standards | Requirements missing or partial, behavior in the diff that was not asked for (scope creep), and requirements that look implemented but wrong, quoting the spec line for each. Under 400 words. |
| Report | Both axis reports | | The two reports under their own headings, and a one-line summary: findings per axis and the worst issue within each axis. It never picks a winner across axes. |

Each finding names the exact file, line, and symbol. A finding that involves security, architecture, or onboarding gets a full explanation.

## Going back and limits

- No spec found and none exists: the Spec stage is skipped and the report says "no spec available".
- Fixing what the review found is a separate task; the workflow type sets no rounds.

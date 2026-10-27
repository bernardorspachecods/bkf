# Brief: check of the {{title}} findings

## Inputs (read-only, in the current directory)
- diff.patch: the diff under review
{{criteria_input}}- gate.md: the repository's own checks, run by the script before the review
- reports/: the findings of the reviewer(s) of this axis

## The repository
It is at {{repo}}. Open it read-only to see the code around a hunk. Change nothing in it.

## Role
Open and follow the role guide: {{guides}}/code-review-check.md (read-only). You are not the author of the findings.

## Rules
- Write your result to checked.md in the current directory. Write nothing else.
- Open only files in the current directory, the repository and the role guide.
- Do not run git commands that change state.

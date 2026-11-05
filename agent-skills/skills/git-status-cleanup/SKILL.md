---
name: git-status-cleanup
description: Commit the uncommitted changes of the current worktree, either only what this session changed (default) or everything. Do not use to delete merged branches or worktrees (use git-worktree-cleanup).
---

# Git status cleanup

Commits uncommitted changes of the current worktree. One argument picks the scope.

## Scope

| Argument | Commits | Leaves |
|---|---|---|
| `mine` (default) | only the changes this session made | everything else, untouched |
| `all` | every non-ignored change, including work this session did not do | nothing |

## Rules

- Ignored files are out of scope.
- One commit for the chosen scope, with a concise message that describes it. Without a better description, use `chore(worktree): snapshot existing changes`.
- `mine`: identify the session's changes from what you edited and created, not from `git status` alone. Stage by path (or by hunk when a file mixes your changes with others'). If you cannot separate your changes from someone else's in the same file, stop and ask; do not guess.
- Never use `--force`, `reset`, `clean` or `stash`, and never revert or discard changes you did not make.
- If the worktree is clean, report that no commit was necessary.
- Report the commit message and, for `mine`, what was left behind.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

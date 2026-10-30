---
name: git-worktree-cleanup
description: Delete the local branches already merged into the default branch, and the linked worktrees checked out on them, then report what was left and why. Use only when the user asks to clean up worktrees or branches; do not use to commit changes (use git-status-cleanup).
---

# Git worktree cleanup

Deletes what is certainly finished and lists the rest. It works on local branches and linked worktrees of the current repository. It never touches remote branches, the default branch, the current branch or the worktree you stand in.

## Core rules

- Delete without asking only a branch that is merged (see below) and, for a worktree, only one that is clean. Everything else is reported, not deleted.
- Run `git fetch --prune origin` first, so the default branch is current: a branch merged on the remote must not look unmerged.
- A worktree is clean when `git -C <path> status --porcelain` prints nothing. A worktree with changes, or whose branch has commits outside the default branch, belongs to another agent: leave it.
- Never use `--force`, `reset`, `clean` or `stash`. If git refuses to delete something, leave it and report the refusal.
- Removing a worktree deletes its ignored files (`.env`, `node_modules`). Say in the report when a removed worktree had any (`git -C <path> status --ignored --short`, before removing it).

## Merged

A branch is merged when its tip is an ancestor of the default branch (`git merge-base --is-ancestor`); delete it with `git branch -d`.

A branch merged by squash or rebase is not an ancestor. Treat it as merged only when `gh pr list --state merged --head <branch> --json headRefOid` returns a pull request whose `headRefOid` equals the local branch tip, so nothing was added after the merge; only then use `git branch -D`, and say in the report that it was a squash merge. Without `gh`, or without a match, leave the branch.

## Report

What was deleted (branch, worktree path), what was left with the reason, and the commands to delete the ones left if the user wants them gone.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

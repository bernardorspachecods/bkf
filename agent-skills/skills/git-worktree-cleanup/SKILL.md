---
name: git-worktree-cleanup
description: Delete the local branches already merged into the default branch, and the linked worktrees checked out on them, then report what was left and why. In integrate mode, first merge or open a pull request for the finished worktrees. Use only when the user asks to clean up worktrees or branches; do not use to commit changes (use git-status-cleanup).
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

## Integrate mode

Only when the user asks for it (`git-worktree-cleanup integrate`). Before the cleanup, it brings finished work into the default branch, so the cleanup can then delete it. The default mode never merges or opens pull requests. This mode overrides, for the steps below only, the rule that a clean worktree with commits outside the default branch is left alone, and the limit to local operations (it may push the branch it opens a pull request for).

- Applies to a clean linked worktree whose branch has commits outside the default branch. A worktree with changes belongs to another agent: leave it and report it.
- Choose by the size and risk of the changes in each worktree. Simple changes without conflicts are merged into the default branch locally, with `--ff-only` or a plain merge after updating the branch. Larger or riskier changes get a pull request (`git push` of that branch, then `gh pr create`), and the worktree stays until the pull request is merged.
- Resolve a merge conflict yourself when the right result is clear from both sides. When it is not, abort that merge, leave the branch untouched and ask the user about that conflict; continue with the other worktrees.
- Run the repository's own check, as its instructions name it, before a merge. If it fails or none is named, open a pull request instead of merging.
- Never force-push, never push the default branch, and never rewrite history. Without `gh`, leave the branch and report it.
- Say in the report, per worktree, which path was taken (merged, pull request, asked, left) and why.

## Report

What was deleted (branch, worktree path), what was left with the reason, and the commands to delete the ones left if the user wants them gone.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

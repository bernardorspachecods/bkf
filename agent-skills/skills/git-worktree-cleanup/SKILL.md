---
name: git-worktree-cleanup
description: Delete the local branches already merged into the default branch, and the linked worktrees checked out on them, then report what was left and why. Use only when the user asks to clean up worktrees or branches; do not use to commit changes (use git-status-cleanup).
---

# Git worktree cleanup

Deletes what is certainly finished and lists the rest for the user. It works on local branches and linked worktrees of the current repository. It never touches remote branches, the default branch, the current branch or the worktree you stand in.

## Core rules

- Delete without asking only a branch whose work is already in the default branch (see "Merged"), and only a worktree that is clean. Everything else is reported, not deleted.
- Never use `--force`, `git branch -D` outside the squash case below, `git reset`, `git clean` or `git stash`. A refusal from git is an answer: report it and leave the item.
- Do not choose by branch name, age or how the branch looks abandoned.
- Other agents may be working in other worktrees. A worktree with changes, or whose branch has commits that are not in the default branch, is theirs: leave it.

## Steps

1. Find the default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`, usually `origin/main`) and run `git fetch --prune origin` so it is current. Read `git worktree list --porcelain` and `git branch --format='%(refname:short) %(objectname)'`.
2. Classify each local branch except the default branch and the current one.
3. For every merged branch with a linked worktree, check the worktree is clean (`git -C <path> status --porcelain` prints nothing) and is not the directory you are in. Remove it with `git worktree remove <path>`, then delete the branch with `git branch -d <branch>`.
4. For every merged branch without a worktree, delete it with `git branch -d <branch>`.
5. Run `git worktree prune` for worktree folders that no longer exist.
6. Report, as a table: what was deleted (branch, worktree path); what was left, each with the reason; the commands to delete the left ones if the user wants them gone.

## Merged

A branch is merged when its tip is an ancestor of the default branch: `git merge-base --is-ancestor <branch> origin/main`. `git branch -d` then deletes it.

A branch merged by squash or rebase is not an ancestor. Treat it as merged only when `gh pr list --state merged --head <branch> --json headRefOid` returns a pull request whose `headRefOid` equals the local branch tip, so nothing was added after the merge. Delete that one with `git branch -D` and say in the report that it was a squash merge. Without `gh`, or without a match, leave the branch.

## Left in place, with the reason

- Commits not in the default branch (give how many), or a squash match whose tip differs.
- A worktree with changes (give the output of `status --porcelain` in a line) or detached HEAD.
- The current branch, the default branch, the branch of the worktree you stand in, and branches checked out in the main worktree.
- A worktree git refuses to remove.

Ignored files in a removed worktree (build output, `.env` files) are deleted with it. Mention in the report that the worktree had any, with `git -C <path> status --ignored --short` before removing it, so the user can tell.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

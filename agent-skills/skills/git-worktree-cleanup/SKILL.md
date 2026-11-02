---
name: git-worktree-cleanup
description: Delete the local branches already merged into the default branch, and the linked worktrees checked out on them, then report what was left and why, offering to delete merged remote branches after confirmation. In integrate mode, first merge the finished worktrees into the default branch (or open pull requests when the user asks for them). Use only when the user asks to clean up worktrees or branches; do not use to commit changes (use git-status-cleanup).
---

# Git worktree cleanup

Deletes what is certainly finished and lists the rest. It works on local branches and linked worktrees of the current repository. It never deletes the default branch, the current branch or the worktree you stand in, and it deletes a remote branch only after the user confirms (see Remote branches).

## Core rules

- Delete without asking only a branch that is merged (see below) and, for a worktree, only one that is clean. Everything else is reported, not deleted.
- Run `git fetch --prune origin` first, so the default branch is current: a branch merged on the remote must not look unmerged.
- A worktree is clean when `git -C <path> status --porcelain` prints nothing. A worktree with changes, or whose branch has commits outside the default branch, belongs to another agent: leave it.
- A worktree can be referenced from outside git. Each harness run (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`, at `<repo>/<name>/`) stores the path of the checkout it was launched from in its `repo` file, and `finish` runs git there. A detached, clean worktree already at the default branch may be such a launch worktree; removing it breaks `finish`. Before removing a detached worktree, search those `repo` files for its path; if one names it, leave it and report which run.
- Never use `--force`, `reset`, `clean` or `stash`. If git refuses to delete something, leave it and report the refusal.
- Removing a worktree deletes its ignored files (`.env`, `node_modules`). Say in the report when a removed worktree had any (`git -C <path> status --ignored --short`, before removing it).

## Merged

A branch is merged when its tip is an ancestor of the default branch (`git merge-base --is-ancestor`); delete it with `git branch -d`.

A branch merged by squash or rebase is not an ancestor. Treat it as merged only when `gh pr list --state merged --head <branch> --json headRefOid` returns a pull request whose `headRefOid` equals the local branch tip, so nothing was added after the merge; only then use `git branch -D`, and say in the report that it was a squash merge. Without `gh`, or without a match, leave the branch.

## Integrate mode

Only when the user asks for it (`git-worktree-cleanup integrate`). Before the cleanup, it brings finished work into the default branch, so the cleanup can then delete it. The default mode never merges or opens pull requests. This mode overrides, for the steps below only, the rule that a clean worktree with commits outside the default branch is left alone.

By default it merges locally and never opens a pull request: the user is usually the only person on the project. It opens pull requests only when the user asks (`git-worktree-cleanup integrate pr`); then it may push the branch it opens a pull request for, and overrides the limit to local operations for that.

- Applies to a clean linked worktree whose branch has commits outside the default branch. A worktree with changes belongs to another agent: leave it and report it.
- Merge into the default branch locally, with `--ff-only` or a plain merge after updating the branch, whatever the size of the changes.
- Run the repository's own check, as its instructions name it, before a merge. If it fails or none is named, do not merge and do not open a pull request: leave the branch and report why.
- Resolve a merge conflict yourself when the right result is clear from both sides. When it is not, abort that merge, leave the branch untouched and ask the user about that conflict; continue with the other worktrees.
- With `integrate pr`, every finished worktree gets a pull request (`git push` of that branch, then `gh pr create`) instead of a local merge, and the worktree stays until the pull request is merged. Without `gh`, leave the branch and report it.
- Never force-push, never push the default branch, and never rewrite history.
- Say in the report, per worktree, which path was taken (merged, pull request, asked, left) and why.

## Remote branches

The only exception to "no remote action": a pull request merged on GitHub leaves its `origin/*` branch behind, and no local branch points at it, so the steps above never see it. Report these, and delete them only when the user confirms.

- Candidate: an `origin/*` branch (not the default branch, not `origin/HEAD`) with no local branch of the same name, that is merged: its tip is an ancestor of `origin/<default>`, or `gh pr list --state merged --head <branch> --json headRefOid` returns a pull request whose `headRefOid` equals the tip (say it was a squash merge).
- List the candidates in the report with the command `git push origin --delete <branch>` for each. Run it only after the user confirms, for the branches they confirm. A remote deletion is hard to undo and an agent or a preview deployment may still use the branch; say so when you ask.
- A branch that is not merged, or has no match, is not a candidate: do not list a command for it.

## Report

What was deleted (branch, worktree path), what was left with the reason, the remote candidates awaiting confirmation, and the commands to delete the ones left if the user wants them gone.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

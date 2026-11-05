---
name: git-worktree-cleanup
description: Close out git worktrees and branches. `mine` (default) commits this session's worktree, merges it locally into the default branch and removes the worktree and branch. `all` deletes every worktree and local branch already merged into the default branch. Pull requests only when the user asks. Use only when the user asks to clean up or close worktrees or branches; do not use to commit changes alone (use git-status-cleanup).
---

# Git worktree cleanup

Works on local branches and linked worktrees of the current repository. One argument picks the scope.

## Scope

| Argument | Does | Does not |
|---|---|---|
| `mine` (default) | closes this session's worktree: commit → check → merge into the default branch → remove worktree and branch | touch any other worktree or branch |
| `all` | deletes every local branch already merged into the default branch, and the clean worktrees on them | commit, merge or open pull requests |

If the session is not running in a linked worktree, `mine` has nothing to close: say so and stop.

## Rules (both scopes)

- Never delete the default branch. Never use `--force`, `reset`, `clean` or `stash`. If git refuses something, leave it and report the refusal.
- Run `git fetch --prune origin` first when an `origin` exists.
- A worktree is clean when `git -C <path> status --porcelain` prints nothing.
- Removing a worktree deletes its ignored files (`.env`, `node_modules`). Check `git -C <path> status --ignored --short` before removing, and say in the report when it had any.
- Harness runs (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`, at `<repo>/<name>/`) store the path of the checkout they launched from in a `repo` file, and `finish` runs git there. Before removing a detached worktree, search those `repo` files for its path; if one names it, leave it and report which run.

## `mine`

1. Commit the worktree with `git-status-cleanup mine` (`all` if the user says so). Nothing else may be uncommitted afterwards that is the session's.
2. Run the repository's own check, as its instructions name it. If it fails or none is named, stop: leave everything and report why.
3. Merge into the default branch from its checkout with `git -C <default-checkout> merge`, `--ff-only` when possible. Changes in the default checkout that do not overlap the merge are fine: git carries them along, so do not stop for them. If git refuses, or the merge conflicts, resolve the conflict yourself only when the right result is clear from both sides; otherwise abort the merge, leave the branch and ask the user.
4. Run every command with `git -C <default-checkout>` so the session never depends on the worktree it is removing. Remove the worktree (`git worktree remove`) and the branch (`git branch -d`).
5. Tell the user the worktree is gone, so the session's own directory no longer exists.

## `all`

Delete a branch without asking only when it is merged: its tip is an ancestor of the default branch (`git merge-base --is-ancestor`), deleted with `git branch -d`. Delete a worktree only when it is also clean. Everything else is reported, not deleted: a worktree with changes, or a branch with commits outside the default branch, belongs to another agent. Never delete the current branch or the worktree you stand in.

## Pull requests

Only when the user asks (`git-worktree-cleanup mine pr`). It replaces the local merge in `mine`; the rest of `mine` up to the check is the same.

- Push the branch (`git push -u origin <branch>`) and open the pull request with `gh pr create`. Without `gh`, leave the branch and report it.
- Never force-push, never push the default branch, never rewrite history.
- The worktree and branch stay until the pull request is merged. After that, `all` or `mine` finishes the cleanup.
- A branch merged by squash or rebase is not an ancestor. In `all`, treat it as merged only when `gh pr list --state merged --head <branch> --json headRefOid` returns a pull request whose `headRefOid` equals the local branch tip; then use `git branch -D` and say it was a squash merge. Without `gh` or a match, leave the branch.
- The merged pull request leaves its `origin/*` branch behind. Report it as a candidate with `git push origin --delete <branch>`, and run that only after the user confirms. A remote deletion is hard to undo and an agent or preview deployment may still use the branch; say so when you ask. Candidate: not the default branch, not `origin/HEAD`, no local branch of the same name, and merged (ancestor of `origin/<default>`, or a matching merged pull request as above).

## Report

What was merged, deleted (branch, worktree path) or opened as a pull request, what was left with the reason, and any remote candidates awaiting confirmation.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

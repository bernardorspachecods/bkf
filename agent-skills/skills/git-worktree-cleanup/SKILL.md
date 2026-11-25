---
name: git-worktree-cleanup
description: Close out git worktrees and branches. `mine` (default) commits this session's changes, lands its branch on the default branch through the merge queue (bkf merge, never a rebase), then removes the session worktree (if any) and branch and closes its task. `all` deletes every worktree and local branch already merged into the default branch. Pull requests only when the user asks. Use only when the user asks to clean up or close worktrees or branches; do not use to commit changes alone (use git-status-cleanup).
---

Apaga só o que já está no main ou o que o utilizador pediu para apagar.

- `mine` (default): commit with [git-status-cleanup](../git-status-cleanup/SKILL.md), land with [git-merge-queue](../git-merge-queue/SKILL.md), then remove this session's worktree and branch and run `bkf task close` (only after the land). On the default branch there is nothing to land. If the queue or checks refuse, stop and tell the user.
- `mine pr`: instead of the queue, `git push -u origin <branch>` and `gh pr create`; keep the worktree and branch until the PR merges.
- `all`: delete local branches merged into the default branch and clean worktrees. No commits, merges or PRs. A squash- or rebase-merged branch counts only if `gh pr list --state merged --head <branch> --json headRefOid` matches the local tip.

Report what was removed, what was left and why. Remote branch deletion only after the user confirms.

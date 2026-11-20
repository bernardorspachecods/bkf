---
name: git-worktree-cleanup
description: Close out git worktrees and branches. `mine` (default) commits this session's changes, lands its branch on the default branch through the merge queue (bkf merge, never a rebase), then removes the session worktree (if any) and branch and closes its card. `all` deletes every worktree and local branch already merged into the default branch. Pull requests only when the user asks. Use only when the user asks to clean up or close worktrees or branches; do not use to commit changes alone (use git-status-cleanup).
---

`mine` (default): this session's work only, in a linked worktree or in the main checkout. `all`: delete every local branch merged into default and clean worktrees; no commits, merges or pull requests.

- Never delete default or use `--force`, `reset`, `clean` or `stash`; on refusal, leave it and report why.
- If `origin` exists, run `git fetch --prune origin` first.
- Clean: `git -C <path> status --porcelain` prints nothing. Before removal, run `git -C <path> status --ignored --short`; report ignored `.env`/`node_modules` (removal deletes them).
- Harness runs (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`, at `<repo>/<name>/`) record the launch checkout in `repo`; `finish` runs git there. Before removing a detached worktree, search these files for its path; if found, leave it and report that run.

## `mine`

1. Commit with `git-status-cleanup mine` (`all` if the user says so); no session changes may remain uncommitted. If the session is on the default branch, stop here: there is nothing to land.
2. Land through the queue: follow the steps of [git-merge-queue](../git-merge-queue/SKILL.md) (`bkf merge enter`, `bkf merge wait`, then on its turn `git merge <default>` into the branch, the repository's named check, `bkf merge verify`, `bkf merge land`). The merge is a merge commit, never a rebase, so the branch's history is what the sessions made. If no check is named, or the queue or the checks refuse, stop, leave all, and tell the user. A session without a task card cannot join the queue: stop and say so.
3. After `bkf merge land` exits 0, remove the session's own state: in a linked worktree, leave it with `ExitWorktree` (`keep`) when the session is inside it, remove it (`git worktree remove`), then delete the branch (`git -C <default-checkout> branch -d <branch>`). In the main checkout, switch it to default (`git switch <default>`; the checkout is clean, and land does not move it), then delete the branch. If the environment denies `git -C <default-checkout>` (worktree isolation; a permission rule does not lift it), run the same commands from the default checkout without `-C`. If that is impossible too, give the user the exact commands to run with `!`; leave the branch and worktree.
4. Close the card: `bkf task close`. It deletes the card; run it only after the branch has landed.
5. Tell the user what is gone: the worktree or session directory, the branch, and the card, or only what was left and why.

## `all`

Delete without asking only branches whose tip is an ancestor of default (`git merge-base --is-ancestor`), using `git branch -d`; delete worktrees only if clean. Report dirty worktrees or branches with commits outside default (another agent's). Never delete these or the current branch/worktree. A branch merged by squash or rebase is not an ancestor of default: leave it unless you read [pull-requests.md](pull-requests.md).

## Pull requests

Only when the user asks (`mine pr`), to count squash or rebase merges in `all`, or to offer remote branch deletion: read [pull-requests.md](pull-requests.md) first. Otherwise do not open it.

Report merge/delete/PR outcomes (branch/worktree path), leftovers/reasons and remote candidates awaiting confirmation.

Metadata: [agents/openai.yaml](agents/openai.yaml)

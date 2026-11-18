---
name: git-worktree-cleanup
description: Close out git worktrees and branches. `mine` (default) commits this session's changes, merges its branch locally into the default branch and removes the session worktree (if any) and branch. `all` deletes every worktree and local branch already merged into the default branch. Pull requests only when the user asks. Use only when the user asks to clean up or close worktrees or branches; do not use to commit changes alone (use git-status-cleanup).
---

`mine` (default): this session's work only, in a linked worktree or in the main checkout. `all`: delete every local branch merged into default and clean worktrees; no commits, merges or pull requests.

- Never delete default or use `--force`, `reset`, `clean` or `stash`; on refusal, leave it and report why.
- If `origin` exists, run `git fetch --prune origin` first.
- Clean: `git -C <path> status --porcelain` prints nothing. Before removal, run `git -C <path> status --ignored --short`; report ignored `.env`/`node_modules` (removal deletes them).
- Harness runs (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`, at `<repo>/<name>/`) record the launch checkout in `repo`; `finish` runs git there. Before removing a detached worktree, search these files for its path; if found, leave it and report that run.

## `mine`

1. Commit with `git-status-cleanup mine` (`all` if the user says so); no session changes may remain uncommitted.
2. Rebase the session branch onto the local default, from inside the worktree: `git rebase <default>` (no `-C`, never `origin/<default>`). The branch is local, so rewriting it is safe; cite commit SHAs only after this step. Resolve conflicts only when both sides make the right result clear; otherwise `git rebase --abort`, leave the branch and ask the user. Then the final merge is always a fast-forward and the check below runs on exactly what will land.
3. Run the repo's named check on that result; on failure or if none is named, stop, leave all and explain. Then, if the `git-merge-queue` skill's `scripts/merge_queue.py` exists, run `python3 -I <that script> busy; echo "exit=$?"`; read the exit code: if 1, stop, leave all and tell the user to use `git-merge-queue`.
4. Land it with one command: `git -C <default-checkout> merge --ff-only <branch>`. If default moved since step 2, repeat steps 2-3 once (`--ff-only` never creates a merge commit). If the environment denies the command on the default checkout (worktree isolation), do not give the user a menu and do not work around the denial: say it in one line and give the exact commands (this merge, then `git branch -d`, then `git worktree remove`) for the user to run with `!`; leave branch and worktree.
5. After the merge, in a linked worktree remove it first (`git worktree remove`), then delete the branch (`git -C <default-checkout> branch -d`).
6. Tell the user what is gone: the worktree/session directory, or only the branch.

Main checkout: there is no worktree to remove. If the session branch is not default, the checkout must be clean after step 1; switch it to default (`git switch <default>`), merge, delete the branch, and say the checkout is now on default. If the session is already on default, stop after step 1: there is nothing to merge or delete.

## `all`

Delete without asking only branches whose tip is an ancestor of default (`git merge-base --is-ancestor`), using `git branch -d`; delete worktrees only if clean. Report dirty worktrees or branches with commits outside default (another agent's). Never delete these or the current branch/worktree. A branch merged by squash or rebase is not an ancestor of default: leave it unless you read [pull-requests.md](pull-requests.md).

## Pull requests

Only when the user asks (`mine pr`), to count squash or rebase merges in `all`, or to offer remote branch deletion: read [pull-requests.md](pull-requests.md) first. Otherwise do not open it.

Report merge/delete/PR outcomes (branch/worktree path), leftovers/reasons and remote candidates awaiting confirmation.

Metadata: [agents/openai.yaml](agents/openai.yaml)

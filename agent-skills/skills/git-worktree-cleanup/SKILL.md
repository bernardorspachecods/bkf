---
name: git-worktree-cleanup
description: Close out git worktrees and branches. `mine` (default) commits this session's worktree, merges it locally into the default branch and removes the worktree and branch. `all` deletes every worktree and local branch already merged into the default branch. Pull requests only when the user asks. Use only when the user asks to clean up or close worktrees or branches; do not use to commit changes alone (use git-status-cleanup).
---

`mine` (default): session worktree only; if not linked, report and stop. `all`: delete every local branch merged into default and clean worktrees; no commits, merges or pull requests.

- Never delete default or use `--force`, `reset`, `clean` or `stash`; on refusal, leave it and report why.
- If `origin` exists, run `git fetch --prune origin` first.
- Clean: `git -C <path> status --porcelain` prints nothing. Before removal, run `git -C <path> status --ignored --short`; report ignored `.env`/`node_modules` (removal deletes them).
- Harness runs (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`, at `<repo>/<name>/`) record the launch checkout in `repo`; `finish` runs git there. Before removing a detached worktree, search these files for its path; if found, leave it and report that run.

## `mine`

1. Commit with `git-status-cleanup mine` (`all` if the user says so); no session changes may remain uncommitted.
2. Run the repo's named check; on failure or if none is named, stop, leave all and explain.
3. From default checkout, run `git -C <default-checkout> merge` (`--ff-only` when possible). Keep non-overlapping changes there. If refused or conflicted, resolve only when both sides make the right result clear; otherwise abort, leave the branch and ask the user.
4. Run every command with `git -C <default-checkout>`; remove the worktree (`git worktree remove`) and branch (`git branch -d`).
5. Tell the user the worktree/session directory is gone.

## `all`

Delete without asking only branches whose tip is an ancestor of default (`git merge-base --is-ancestor`), using `git branch -d`; delete worktrees only if clean. Report dirty worktrees or branches with commits outside default (another agent's). Never delete these or the current branch/worktree.

## Pull requests

On request (`git-worktree-cleanup mine pr`); PR replaces local merge; other `mine` steps through check stay unchanged.

- Push with `git push -u origin <branch>` and open with `gh pr create`. Without `gh`, leave the branch and report it.
- Never force-push, push default or rewrite history. Keep worktree and branch until PR merge; then `all` or `mine` completes cleanup.
- In `all`, squash/rebase merges count only if `gh pr list --state merged --head <branch> --json headRefOid` returns a PR whose `headRefOid` equals the local tip; then use `git branch -D` and report a squash merge. Without `gh` or a match, leave it.
- A merged PR leaves `origin/*`. Report candidates for `git push origin --delete <branch>`, running only after confirmation. Warn remote deletion is hard to undo and an agent or preview deployment may use it. Candidate: merged (ancestor of `origin/<default>` or matching merged PR above), not default/`origin/HEAD`, and no same-name local branch.

Report merge/delete/PR outcomes (branch/worktree path), leftovers/reasons and remote candidates awaiting confirmation.

Metadata: [agents/openai.yaml](agents/openai.yaml)

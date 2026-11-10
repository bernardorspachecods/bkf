# Pull requests

Read this only for `mine pr`, for squash or rebase merges in `all`, or for remote branch deletion. The rules of [SKILL.md](SKILL.md) still apply.

On request (`git-worktree-cleanup mine pr`); PR replaces local merge; other `mine` steps through check stay unchanged.

- Push with `git push -u origin <branch>` and open with `gh pr create`. Without `gh`, leave the branch and report it.
- Never force-push, push default or rewrite history. Keep worktree and branch until PR merge; then `all` or `mine` completes cleanup.
- In `all`, squash/rebase merges count only if `gh pr list --state merged --head <branch> --json headRefOid` returns a PR whose `headRefOid` equals the local tip; then use `git branch -D` and report a squash merge. Without `gh` or a match, leave it.
- A merged PR leaves `origin/*`. Report candidates for `git push origin --delete <branch>`, running only after confirmation. Warn remote deletion is hard to undo and an agent or preview deployment may use it. Candidate: merged (ancestor of `origin/<default>` or matching merged PR above), not default/`origin/HEAD`, and no same-name local branch.

Report the PR (branch, URL) and the remote candidates awaiting confirmation.

---
name: git-merge-queue
description: Land this session's finished branch on the target branch through the repository's merge queue (bkf merge), which joins it, waits for the turn, merges the target into the branch, verifies and lands it. Use when the owner moves this session's card to "to be merged", when the user asks you to queue, land or merge the branch, to land a batch now while the session keeps working on the branch, or to continue after a failed merge; do not use to clean up worktrees without landing (use git-worktree-cleanup).
---

Sessions land one at a time, and you run every step yourself. Run from your worktree; `BKF_TASK` names your card. `bkf merge status` shows the queue.

1. Commit your work, then `bkf merge enter`.
2. `bkf merge wait` until your turn (exit 75: run it again).
3. `git merge <target>` into the branch: a merge commit, never a rebase. Resolve conflicts you can; otherwise go to 6.
4. Run the repository's checks. If it names none, go to 6: nothing lands untested.
5. `bkf merge verify`, then `bkf merge land`. Exit 3 means the target moved: back to 3. After a plain land, remove the worktree and branch ([git-worktree-cleanup](../git-worktree-cleanup/SKILL.md)) and run `bkf task close`.
6. To give up: `bkf merge fail --reason "<one line>"`, fix, and re-enter at 1.

To land a batch and keep working, use `bkf merge land --continue`, then `bkf merge enter` again before the next land.

If your entry leaves the queue (`wait` exit 2, or "not in the merge queue"), read the message. After a take-out by the owner or your own `bkf merge leave`, stop and do not re-enter until asked. "Already landed": clean up. Dropped by the queue: re-enter if you still want to land. Any other refusal explains itself on stderr.

Rules and exit statuses: [bkf merge](../../../bkf/tooling/commands.md#bkf-merge).

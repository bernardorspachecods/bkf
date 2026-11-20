---
name: git-merge-queue
description: Land this session's finished branch on the target branch through the repository's merge queue (bkf merge), which joins it, waits for the turn, merges the target into the branch, verifies and lands it. Use when the owner moves this session's card to "to be merged", when the user asks you to queue, land or merge the branch, or to continue after a failed merge; do not use to clean up worktrees without landing (use git-worktree-cleanup).
---

Sessions that finish in separate worktrees land one at a time. The queue gives
each session the turn when the one before it has landed or given up, so the
target you merge is the one you test. You run every step yourself: the merge,
the checks, and any conflict resolution. Nothing in the queue merges for you.

Run each command from your session's worktree. `BKF_TASK` names your card, so
the commands need no id. `bkf merge status` shows the queue and never changes it.

## Steps

1. Commit your work (`git-status-cleanup`). `bkf merge enter` joins the back of
   the queue and moves your card to "to be merged".
2. `bkf merge wait` blocks until your turn:
   - exit 0: your turn; go on.
   - exit 75: still waiting after nine minutes; run it again.
   - exit 2: your entry left the queue. The output says why. Fix what it names,
     then run `bkf merge enter` again.
3. On your turn, run `git merge <target>` into your branch. Make a merge commit:
   do not rebase, squash, reset or stash. Resolve a conflict yourself when both
   sides make the right result clear; read the plans and the diffs. When the
   result needs the other session's intent, go to step 6.
4. Run the repository's own verification on the result: its fast check and its
   full suite, as its docs name them. If the repository names none, go to step 6
   and tell the user: nothing lands untested.
5. `bkf merge verify`, then `bkf merge land`:
   - exit 0: landed. The output names the next step: remove your worktree and
     branch (`git-worktree-cleanup`), then `bkf task close`.
   - exit 3: the target moved, your branch changed since verify, or the branch
     does not contain the target. Go back to step 3, then verify again.
   - exit 4: the target's own checkout refuses (it has uncommitted changes, or
     the fast-forward failed). Tell the user; the owner cleans that checkout. Do
     not touch it. Run `bkf merge land` again when they say it is clean.
   - exit 5: not your turn; the queue no longer holds you. Go to step 1.
6. When you cannot finish: `bkf merge fail --reason "<one line>"`. The card goes
   back to working with the merge-failed mark and your reason, and the next
   session gets the turn. Fix the branch, commit, and go to step 1.
   To withdraw without a failure, run `bkf merge leave`.

Any other exit status is a refusal; its line on standard error says what to fix.

## Rules

- Run only these commands. Never edit a queue file, never move the target
  yourself, never stash, never force.
- Your turn is kept while you make `bkf merge` calls or tool calls. It is lost
  after an hour with neither, when your card or tmux window is gone, or when
  your entry sat unpolled for three minutes. Recovery writes the reason on your
  card, and the next `bkf merge wait` reports it.

Not yet run with two real sessions in one repository; the first time, use two
and check `bkf merge status` after each step.

Metadata: [agents/openai.yaml](agents/openai.yaml)

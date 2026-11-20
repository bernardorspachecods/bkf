---
name: git-merge-queue
description: Land this session's finished branch on the target branch through the repository's merge queue (bkf merge), which joins it, waits for the turn, merges the target into the branch, verifies and lands it. Use when the owner moves this session's card to "to be merged", when the user asks you to queue, land or merge the branch, to land a batch now while the session keeps working on the branch, or to continue after a failed merge; do not use to clean up worktrees without landing (use git-worktree-cleanup).
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
   - exit 2: your entry left the queue. The owner took it out, or the queue
     dropped it. Stop the merge flow: see [Take-out](#take-out).
3. On your turn, run `git merge <target>` into your branch. Make a merge commit:
   do not rebase, squash, reset or stash. Resolve a conflict yourself when both
   sides make the right result clear; read the plans and the diffs. When the
   result needs the other session's intent, go to step 6.
4. Run the repository's own verification on the result: its fast check and its
   full suite, as its docs name them. If the repository names none, go to step 6
   and tell the user: nothing lands untested.
5. `bkf merge verify`, then `bkf merge land` (or `bkf merge land --continue` for
   an [interim land](#interim-lands)):
   - exit 0, plain land: landed. The output names the next step: remove your
     worktree and branch (`git-worktree-cleanup`), then `bkf task close`.
   - exit 0, `--continue`: the batch landed and the session keeps its branch. The
     card is "working" again; see [Interim lands](#interim-lands).
   - exit 3: the target moved, your branch changed since verify, or the branch
     does not contain the target. Go back to step 3, then verify again.
   - exit 4: the target's own checkout refuses (it has uncommitted changes, or
     the fast-forward failed). Tell the user; the owner cleans that checkout. Do
     not touch it. Run `bkf merge land` again when they say it is clean.
   - exit 5 with "not your turn": run `bkf merge wait` again (step 2).
   - exit 5 with "not in the merge queue": your entry is gone. See
     [Take-out](#take-out).
6. When you cannot finish: `bkf merge fail --reason "<one line>"`. The card goes
   back to working with the merge-failed mark and your reason, and the next
   session gets the turn. Fix the branch, commit, and go to step 1: this re-entry
   is yours, because the failure is your own.
   To withdraw without a failure, run `bkf merge leave`; that counts as a
   take-out for you, so do not re-enter on your own afterwards.

Any other exit status is a refusal; its line on standard error says what to fix.

## Interim lands

Use `bkf merge land --continue` when the owner or the brief asks you to land a
batch while the session keeps working on the same branch, for example a long
job that lands in parts. It runs the same checks and the same fast-forward as a
plain land. Then:

- Each land passes the repository's checks on its own, on the result you test
  on that turn (step 4 every time), and each land needs its own `verify`.
- Between lands the branch may keep receiving commits. Before the next verify,
  merge the target again on your turn (step 3); a merge with nothing new is
  harmless. A land refused with exit 3 is the sign the target moved and was not
  merged in.
- After an interim land your card is "working". Before the next land, run
  `bkf merge enter` again, then `bkf merge wait`, then steps 3 to 5.
- The final land of the branch is the plain `bkf merge land`, without
  `--continue`. Then follow step 5's cleanup: remove the worktree and branch
  (`git-worktree-cleanup`), then `bkf task close`.

## Take-out

The owner can take your card out of "to be merged" at any time. The app then
types the owner's message into your window: "The owner took this task out of
"to be merged": stop the merge flow, do not run bkf merge land or re-enter the
queue, and go on with what you were doing or wait for instructions."

When `bkf merge wait` exits 2, or `bkf merge verify` or `bkf merge land` exits
5 with "not in the merge queue", the message says why the entry is gone. Act on
it:

- "the owner took the task out", or you ran `bkf merge leave` yourself: this is
  a take-out. Stop the merge flow, do not run `bkf merge land`, and do not run
  `bkf merge enter` on your own. Re-enter only when the owner asks again, or
  after your own `bkf merge fail` (step 6), once you have fixed the branch. Go
  on with your work, or tell the owner what you were doing and wait for
  instructions.
- "its branch already landed": there is nothing left to land. Do not enter
  again; go to step 5's cleanup.
- "the queue removed it, not the owner": recovery dropped the entry (a lost
  lease or window, an unpolled wait, a land that died). The reason is in the
  message and on your card. If you still want to land, run `bkf merge enter`
  again; it joins the back of the queue.

The re-entry before the next land of an interim land is planned, not a
take-out, so it is not covered by this rule.

## Rules

- Run only these commands. Never edit a queue file, never move the target
  yourself, never stash, never force.
- Your turn is kept while you make `bkf merge` calls or tool calls. It is lost
  after an hour with neither, when your card or tmux window is gone, or when
  your entry sat unpolled for three minutes. Recovery writes the reason on your
  card, and the next `bkf merge wait` reports it; you may re-enter: see
  [Take-out](#take-out).

Not yet run with two real sessions in one repository; the first time, use two
and check `bkf merge status` after each step.

The queue's rules and exit statuses are owned by [bkf merge](../../../bkf/tooling/commands.md#bkf-merge).

Metadata: [agents/openai.yaml](agents/openai.yaml)

# Close the batch

Read this only when the user says to close the batch, or to resume or abort an
integration. Prefer a fresh session: one that carries another branch's work is
judge in its own case.

1. `list`. Entries marked STALE are skipped; tell the user.
2. `integrate --fast-check "<cmd>" --full-check "<cmd>"` with the repo's named
   checks. It merges each entry in registration order into a temporary
   worktree, runs the fast check after each merge, then the full suite once on
   the combined result. Only then does it fast-forward `main`, move the task
   card of each merged branch to done (when exactly one card is on it and it is
   working or in review), delete the merged sessions' worktrees and branches,
   and report any it left (a worktree with uncommitted or untracked files, or
   the main checkout).
3. Act on the exit code:

| Exit | Meaning | What you do |
| --- | --- | --- |
| 0 | Merged; entries dropped for a failing fast check stay queued | Tell the user who merged and who stayed, with the check output, then finish the cleanup below |
| 2 | Conflict, or `--resume` before it was resolved | Read each side's plans and deviations from the entries' paths and the diffs. Resolve in the printed worktree and commit when both sides make the result clear. Otherwise ask the user whether you may message the session, never message it unasked: it may be cached. Then `integrate ... --resume` |
| 3 | Full suite failed on the combined result; `main` untouched | Fix what the failure shows in the printed worktree and commit, then `--resume`. Ask the user about a session only as in exit 2. `--abort` if it cannot be fixed, and tell the user |
| 4 | `main` moved while it ran; nothing overwritten | `--abort` and integrate again |

An entry whose session gave up blocks every direct merge until it is gone:
with the user's approval, `unregister --session "<name> [ref]"`. Never edit the
queue files by hand. The script does not bisect: a full-suite
failure names the batch, not one branch. The paths in an entry are the
sessions' own word: compare them with each diff when a conflict is semantic.

## Cleanup after `main` advanced

You may delete everything that belonged to the sessions you merged. The script
already removed their worktrees and branches. For what it reported as left, and
for the rest (run folders under `~/.plan-runs`, `~/.delegate-runs`,
`~/.research-runs`, `~/.council-runs` and `~/.review-runs` that record those
worktrees, for example in their `worktree` file), search for each merged
session's worktree path, delete only the runs that match, and report what you
deleted and what you left.

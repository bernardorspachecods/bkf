---
name: git-status-cleanup
description: Commit the uncommitted changes of the current worktree, either only what this session changed (default) or everything. Do not use to delete merged branches or worktrees (use git-worktree-cleanup).
---

# Git status cleanup

One commit with a concise message. `mine` (default) commits only what this session changed, staged by path or hunk; if you cannot separate your changes from someone else's in a file, ask. `all` commits every non-ignored change. Clean worktree: say so and stop. Report the message and, for `mine`, what was left behind.

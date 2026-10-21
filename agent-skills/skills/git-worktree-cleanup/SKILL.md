---
name: git-worktree-cleanup
description: Commit selected worktree changes while preserving changes outside the chosen scope.
---

# Git worktree cleanup

## Core rules

- Keep ignored files out of scope unless requested.
- Verify the worktree and report the commit message, and anything intentionally left behind.
- Create one commit for the selected scope, with a concise message that describes it. For a start-of-task snapshot without a better description, use `chore(worktree): snapshot existing changes`.
- If the worktree is clean, report that no commit was necessary.

## Choose the commit scope

### `all`

When the user says `git-worktree-cleanup all`, commit all non-ignored changes in the worktree in one commit. This includes unrelated pre-existing changes. Ignored files remain out of scope unless the user explicitly requests them.

### `only`

When the user says `git-worktree-cleanup only`, commit only changes made for the current task and preserve unrelated pre-existing work. If isolating the task changes requires more than three separate staging groups, stop and report back to the user. Count each group that must be selectively staged or excluded as one staging group.

### `pre-existing`

When the user says `git-worktree-cleanup pre-existing`, use the snapshot captured before the current work to identify and commit only the changes that were already present then. The snapshot is whatever the user or the harness recorded before the work (for example a commit or a saved `git status` and diff); if none can be found, stop and ask the user for it instead of guessing. Preserve changes made after that snapshot in the worktree and keep them out of the commit. If the snapshot contains no changes relative to its base, report that no commit was necessary.

### No mode specified

If the user says `git-worktree-cleanup` without a mode, assume `git-worktree-cleanup all`.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

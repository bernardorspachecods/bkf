# Register a finished branch

Read this when the user tells you to put your finished work in the merge queue.
Sessions may be cached and idle, so a registered session does nothing more: no
merge, no cleanup, no waiting for questions.

1. Commit with `git-status-cleanup mine`. Run the repo's fast check and its
   full suite on your branch, on top of the current `main`. If the repo names
   neither, ask the user before registering.
2. Run `register --session "<name> [ref]" --branch <branch> --plans <paths>
   --deviations <paths> --base <main SHA tested> --fast pass --full pass`.
   - `--session`: your name and ref exactly as `ListAgents` shows them.
   - `--plans` and `--deviations`: comma-separated paths only. Point to where
     the plans you ran and the deviations from them are already recorded, the
     way the run records them. Write no prose and no new document for the
     queue.
   - The command refuses unless both `--fast` and `--full` are `pass`.
3. Tell the user the entry is registered, and stop.

Do not commit to the branch afterwards: the entry goes stale and is skipped.
To change it, register again.

---
name: git-merge-queue
description: Merge the finished work of several sessions of one repository as a batch. Each session registers its branch in a shared queue, then one integrator merges the batch, tests the result and cleans up the sessions it merged. Use only when the user asks to queue a branch, close the batch or resume an integration; do not use for a single session's merge (use git-worktree-cleanup).
---

Several sessions finish in separate worktrees. Merging them one by one leaves
each one behind the `main` the previous one just changed and repeats the full
suite per session. Here they register first and one integrator merges them
together, tests the final state and cleans up.

Pick your part from what the user asked and read only that file:

- Register your finished branch in the queue: [register.md](register.md).
- Close the batch (merge the queue, test, clean up), or resume or abort an
  integration: [integrate.md](integrate.md).

A batch of one session is not a batch: the user sends that session to
`git-worktree-cleanup` instead. The user decides which, by whether another
session also has a merge pending.

The queue is shared by every worktree of the repository and never tracked by
git. [scripts/merge_queue.py](scripts/merge_queue.py) owns its format and
behavior; run it as `python3 -I <skill>/scripts/merge_queue.py <command>`, from
any worktree of the repository. Read the script only to change it; its tests
run with `python3 -I -m unittest discover -s <skill>/tests`
([tests/test_merge_queue.py](tests/test_merge_queue.py)).

Not yet run against a real batch of sessions: the first time, use two.

Metadata: [agents/openai.yaml](agents/openai.yaml)

---
bkf: document
description: "Defines every parallel group, each branch in its own worktree: the gate each branch brief declares and `bkf gate` checks, the mechanical merge, cleaning up merged branches, failed branches, and when merging may read content. Agent assignment is covered by delegate-work and workflow sequencing by coordinate-a-workflow."
tags: [delegation, planning]
---

# Run parallel work

- Run branches in parallel only when their outputs and write boundaries are independent (see delegate-work.md). Run each branch in its own worktree and git branch, never two in one checkout: only a separate diff per branch shows which branch changed which file, and the gate depends on it.
- Each branch brief declares its gate before the branch starts: the files it may change, the command that shows its output is complete, and the commands it must not run. The merging agent does not choose or add checks.
- When a branch finishes, run `bkf gate` on it with the brief's permitted files and completeness commands. The gate reads no content: every changed file must be permitted, the branch must have changed something, and every completeness command must exit 0. Each branch gets pass or fail; a branch that wrote nothing fails.
- The merge is mechanical: it merges only branches that passed, reads no branch content, and does not resolve conflicts: branches own disjoint files, so a conflict is a scope breach and goes back to the coordinator. Merge each branch as it passes; do not wait for the others.
- A branch that fails is not merged. It follows the failure rule in coordinate-a-workflow.md and merges when it later passes its gate.
- After a branch is merged, remove its worktree and git branch, but only when `git branch --merged <integration branch>` lists the branch and its worktree has no uncommitted changes. Otherwise keep it and ask the user. Never remove a branch that failed its gate. Keep the run folder as the record of the run.
- Content is read only when the plan names a stage for it. That stage is separate from the merge and has a reviewer distinct from the merging agent.
- The step after a parallel group starts only when every branch of the group has passed its gate and is merged.
- The merge lands on the plan or integration branch. Moving it onto the user's branch needs the user's approval.

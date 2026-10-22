---
name: work-with-code
description: Use when building a feature, fixing a bug, or reviewing code changes (source code and tests).
---

# Work with code

Open the files below before starting; they hold the rules for this kind of work. Always read determinism and core-code-principles; open each of the others whose description fits the task.

<!-- BKF:GENERATED-TAGGED-LIST tags: code -->
| What it is | Document |
| --- | --- |
| Sets the principles and practices for building code: test first, growing in layers, long-term decisions, dependency choices and code smells. How work is verified follows determinism, reviews follow the plan and code-review guides. | [core-code-principles.md](../../library/modules/core-code-principles.md) |
| Sets the rules for verifying work with code: let code decide what code can decide, make every check able to fail, never weaken an existing check, and report what is unverified and what ran. Covers any work with code, including work handed to other agents; how a plan or a code review runs its checks is owned by the plan and code-review guides. | [determinism.md](../../library/modules/determinism.md) |
| Guides a code review of a branch, pull request, range or working tree, for the coordinator who works with the user. Covers when to review, how to set up the target and run its gate, how the two axes and their checkers run apart, and what the user receives. | [code-review.md](../../library/workflow-types/code-review/code-review.md) |
<!-- BKF:GENERATED-TAGGED-LIST-END -->

The library is for substantial work. A small change is still verified: run its tests or checks, following the determinism principle in [determinism.md](../../library/modules/determinism.md), and apply the rules above with your own judgment. Review a small change directly; the multi-agent `code-review` workflow is reserved for large or high-stakes reviews.

When the work has several stages, several agents, or a plan, also use the `work-in-stages` skill.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

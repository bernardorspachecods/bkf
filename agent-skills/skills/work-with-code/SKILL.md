---
name: work-with-code
description: Use when building a feature, fixing a bug, or reviewing code changes (source code and tests).
---

# Work with code

Open the files below before starting; they hold the rules for this kind of work. Open each one whose description fits the task.

<!-- BKF:GENERATED-TAGGED-LIST tags: always, code -->
| What it is | Document |
| --- | --- |
| Sets rules for acting within an approved task, deciding when to ask, which rule wins when rules conflict, how to make a risky structural change, and when to keep an interface or document for compatibility. Activity-specific methods belong in other modules. | [act-within-scope.md](../../library/modules/act-within-scope.md) |
| Names common code smells introduced during implementation and the corresponding fixes. Repository-specific standards take precedence, while module design and implementation practices are covered by design-modules and build-software. | [avoid-code-smells.md](../../library/modules/avoid-code-smells.md) |
| Sets implementation practices for building features and fixing bugs, including test-first slices and dependency choices. Module interface design and boundaries are covered by design-modules. | [build-software.md](../../library/modules/build-software.md) |
| Provides vocabulary and decision rules for module depth, interface seams, dependencies, and tests across interfaces. Implementation sequencing and test-first practices are covered by build-software. | [design-modules.md](../../library/modules/design-modules.md) |
| Gives the rules for looking after a repository's documents under BKF: keep them consistent with the code and each other as part of every change, write each fact in one place, decide where information lives and how it ages, state a document's scope in its description, log only the files the map cannot list, and stop and ask the user when the organization has drifted. Covers placing, splitting, merging, and restructuring documents; does not cover writing the text itself, glossaries and decision records, or organizing a repo for the first time, which belongs to the BKF manual. | [organize-documents.md](../../library/modules/organize-documents.md) |
| Guides a code review of a branch, pull request, range or working tree, for the coordinator who works with the user. Covers when to review, how to set up the target, how the two axes and their checkers run apart, and what the user receives. | [code-review.md](../../library/workflow-types/code-review/code-review.md) |
<!-- BKF:GENERATED-TAGGED-LIST-END -->

When reviewing code changes, also open [review-work](../../library/modules/review-work.md).

The library is for substantial work. For a small change, apply the rules above with your own judgment and review it directly; the `code-review` shape is for large or high-stakes reviews.

When the work has several stages, several agents, or a plan, also use the `work-in-stages` skill.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

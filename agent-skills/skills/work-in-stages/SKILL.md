---
name: work-in-stages
description: Use when work has several stages, hands work to other agents, needs a plan or a review stage, or resumes from a plan.
---

# Work in stages

Open the files below before starting; they hold the rules for planning, delegating, and reviewing multi-step work, or for handing work to other agents. Open each one whose description fits the task.

<!-- BKF:GENERATED-TAGGED-LIST tags: always, delegation, planning, review, repo-library -->
| What it is | Document |
| --- | --- |
| Sets rules for acting within an approved task, deciding when to ask, and which rule wins when rules conflict. It governs authorization and scope; activity-specific methods belong in other modules. | [act-within-scope.md](../../library/modules/act-within-scope.md) |
| Defines how to prepare prompts and handoffs for agents, including source authority, write boundaries, and completion checks. Workflow coordination and execution are covered by coordinate-a-workflow. | [brief-another-agent.md](../../library/modules/brief-another-agent.md) |
| Defines the coordinator's duties in staged workflows, including checkpoints, output reconciliation, failed work, and delivery gates. Agent assignment and handoff rules are covered by delegate-work. | [coordinate-a-workflow.md](../../library/modules/coordinate-a-workflow.md) |
| Defines how to assign work to agents and reconcile handoffs, including independence, write boundaries, and completion reports. Workflow sequencing and user checkpoints are covered by coordinate-a-workflow. | [delegate-work.md](../../library/modules/delegate-work.md) |
| Defines how to identify, propose, write, and validate reusable procedures in a repository's repo-library, or in the general library when the rule applies to any repository, including when it comes from an external source. Day-to-day document organization is covered by organize-documents. | [grow-libraries.md](../../library/modules/grow-libraries.md) |
| Gives the rules for looking after a repository's documents under BKF: keep them consistent with the code and each other as part of every change, write each fact in one place, decide where information lives and how it ages, state a document's scope in its description, log only the files the map cannot list, and stop and ask the user when the organization has drifted. Covers placing, splitting, merging, and restructuring documents; does not cover writing the text itself, glossaries and decision records, or organizing a repo for the first time, which belongs to the BKF manual. | [organize-documents.md](../../library/modules/organize-documents.md) |
| Defines how to form and agree a durable plan, write its phases and subplan briefs, and set completion gates. Workflow execution and recovery are covered by coordinate-a-workflow and the selected workflow type. | [plan-work.md](../../library/modules/plan-work.md) |
| Defines how to assess prior work against assigned criteria and report evidence-based findings. Workflow coordination handles review returns and delivery gates. | [review-work.md](../../library/modules/review-work.md) |
| Defines every parallel group, each branch in its own worktree: the gate each branch brief declares and `bkf gate` checks, the mechanical merge, cleaning up merged branches, failed branches, and when merging may read content. Agent assignment is covered by delegate-work and workflow sequencing by coordinate-a-workflow. | [run-parallel-work.md](../../library/modules/run-parallel-work.md) |
| Defines the syntax and editing rules for `bkf-workflow` declarations, including step types, references, IDs, and sync commands. Workflow mechanics and validation rules are specified by agent-workflow-foundation. | [write-a-declaration.md](../../library/modules/write-a-declaration.md) |
| Defines a two-axis review workflow that checks a pinned change against repository standards and its originating specification, then reports each axis separately. Correcting review findings is a separate task. | [code-review.md](../../library/workflow-types/code-review.md) |
| Defines a full council workflow with five independent advisors, five peer reviewers, and a chairman for an explicitly requested question or decision. Every phase is required; ordinary advice and lightweight reviews use other methods. | [council.md](../../library/workflow-types/council.md) |
| Defines a durable planning workflow with phases, at least two subplans, configurable research, checkpoints and subplan reviews, an agreed executor, and optional Claude review. Conversation plans stay outside this workflow type. | [plan.md](../../library/workflow-types/plan.md) |
<!-- BKF:GENERATED-TAGGED-LIST-END -->

For a specific kind of work, also use its own skill (for example `work-with-code` or `do-research`).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

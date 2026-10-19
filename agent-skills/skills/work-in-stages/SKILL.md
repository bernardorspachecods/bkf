---
name: work-in-stages
description: Use when work has several stages or roles, hands work to other agents, needs a plan, a council or a code review, or resumes a stopped run.
---

# Work in stages

Open the files below before starting; they hold the rules for planning, delegating, and reviewing multi-step work, or for handing work to other agents. Open each one whose description fits the task.

<!-- BKF:GENERATED-TAGGED-LIST tags: always, delegation, planning, review, repo-library -->
| What it is | Document |
| --- | --- |
| Sets rules for acting within an approved task, deciding when to ask, and which rule wins when rules conflict. It governs authorization and scope; activity-specific methods belong in other modules. | [act-within-scope.md](../../library/modules/act-within-scope.md) |
| Defines how to prepare prompts and handoffs for agents, including source authority, write boundaries, and completion checks. Coordination across a run is covered by coordinate-a-run. | [brief-another-agent.md](../../library/modules/brief-another-agent.md) |
| Defines the coordinator's duties in a run where agents work apart and a script chains their phases: stay out of the roles, stay quiet between checkpoints, treat agent output as unverified, and treat a failure as an escalation. Each workflow's coordinator guide owns its own phases and files. | [coordinate-a-run.md](../../library/modules/coordinate-a-run.md) |
| Defines how to assign work to agents outside a run script and reconcile their handoffs, including independence, write boundaries, and completion reports. Coordination across a run is covered by coordinate-a-run. | [delegate-work.md](../../library/modules/delegate-work.md) |
| Defines how to identify, propose, write, and validate reusable procedures in a repository's repo-library, or in the general library when the rule applies to any repository, including when it comes from an external source. Day-to-day document organization is covered by organize-documents. | [grow-libraries.md](../../library/modules/grow-libraries.md) |
| Gives the rules for looking after a repository's documents under BKF: keep them consistent with the code and each other as part of every change, write each fact in one place, decide where information lives and how it ages, state a document's scope in its description, log only the files the map cannot list, and stop and ask the user when the organization has drifted. Covers placing, splitting, merging, and restructuring documents; does not cover writing the text itself, glossaries and decision records, or organizing a repo for the first time, which belongs to the BKF manual. | [organize-documents.md](../../library/modules/organize-documents.md) |
| Defines how to form and agree a plan: state the outcome, the boundaries, the work and how completion is recognized in checkable terms, and get the user's agreement before work starts. A plan run on a script follows the plan workflow guide. | [plan-work.md](../../library/modules/plan-work.md) |
| Defines how to assess prior work against assigned criteria and report evidence-based findings. Each workflow guide owns its own review roles and verdicts. | [review-work.md](../../library/modules/review-work.md) |
| Guides a code review of a branch, pull request, range or working tree, for the coordinator who works with the user. Covers when to review, how to set up the target, how the two axes and their checkers run apart, and what the user receives. | [code-review.md](../../library/workflow-types/code-review/code-review.md) |
| Guides a council on an explicitly requested question or decision, for the coordinator who works with the user. Covers when to run one, how to write the brief, how the five advisors and five reviewers run apart, how you write the chairman's report and what the user receives. | [council.md](../../library/workflow-types/council/council.md) |
| Guides planning from goal to result, for the coordinator who works with the user. Covers when to plan, how to split a goal into isolated units, what a unit brief states, how to delegate implementation and review, and what the user receives. | [plan.md](../../library/workflow-types/plan/plan.md) |
<!-- BKF:GENERATED-TAGGED-LIST-END -->

For a specific kind of work, also use its own skill (for example `work-with-code` or `do-research`).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

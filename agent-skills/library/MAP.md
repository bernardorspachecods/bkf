---
bkf_version: "0.1"
description: Owns the shared rule modules and workflow types selected by entry skills; request-matching skills and their generated lists live outside this bundle.
---

# Library Map

Use `modules/` for task rules and review guidance, and `workflow-types/` for
multi-stage processes. The tag vocabulary below explains how entry skills
select modules.

## Tag vocabulary

A tag names a situation in which an agent should open the module. Use only these
tags, two or three per file at most; the entry skills select modules by them.

| Tag | Open when |
| --- | --- |
| `always` | Any task; the rule applies whatever the work is. |
| `code` | Designing, implementing, or prototyping software. |
| `research` | Collecting evidence, concluding from it, or reading sources. |
| `planning` | Planning, running, or redoing multi-step work. |
| `review` | Assessing work against criteria. |
| `delegation` | Handing work to agents or acting as a stage agent. |
| `writing` | Writing or revising any text, prompt, or document. |
| `knowledge` | Placing documentation, or recording glossary terms and decisions. |
| `repo-library` | Spotting a repeated repository procedure and adding it to the repo library. |

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Sets rules for acting within an approved task, deciding when to ask, and which rule wins when rules conflict. It governs authorization and scope; activity-specific methods belong in other modules. | [act-within-scope.md](/modules/act-within-scope.md) |
| Names common code smells introduced during implementation and the corresponding fixes. Repository-specific standards take precedence, while module design and implementation practices are covered by design-modules and build-software. | [avoid-code-smells.md](/modules/avoid-code-smells.md) |
| Defines how to prepare prompts and handoffs for agents, including source authority, write boundaries, and completion checks. Workflow coordination and execution are covered by coordinate-a-workflow. | [brief-another-agent.md](/modules/brief-another-agent.md) |
| Sets implementation practices for building features and fixing bugs, including test-first slices and dependency choices. Module interface design and boundaries are covered by design-modules. | [build-software.md](/modules/build-software.md) |
| Defines how to assess evidence into findings, support statuses, confidence, and audited conclusions. Source collection and evidence extraction are covered by frame-and-collect-evidence. | [conclude-from-evidence.md](/modules/conclude-from-evidence.md) |
| Defines the coordinator's duties in staged workflows, including checkpoints, output reconciliation, failed work, and delivery gates. Agent assignment and handoff rules are covered by delegate-work. | [coordinate-a-workflow.md](/modules/coordinate-a-workflow.md) |
| Defines how to assign work to agents and reconcile handoffs, including independence, write boundaries, and completion reports. Workflow sequencing and user checkpoints are covered by coordinate-a-workflow. | [delegate-work.md](/modules/delegate-work.md) |
| Provides vocabulary and decision rules for module depth, interface seams, dependencies, and tests across interfaces. Implementation sequencing and test-first practices are covered by build-software. | [design-modules.md](/modules/design-modules.md) |
| Defines claim framing and source collection for research, including scope, rigor, provenance, and evidence extraction. Evidence assessment and conclusion audits are covered by conclude-from-evidence. | [frame-and-collect-evidence.md](/modules/frame-and-collect-evidence.md) |
| Defines how to identify, propose, write, and validate reusable procedures in a repository's repo-library, or in the general library when the rule applies to any repository, including when it comes from an external source. Day-to-day document organization is covered by organize-documents. | [grow-libraries.md](/modules/grow-libraries.md) |
| Gives the rules for looking after a repository's documents under BKF: keep them consistent with the code and each other as part of every change, write each fact in one place, decide where information lives and how it ages, state a document's scope in its description, log only the files the map cannot list, and stop and ask the user when the organization has drifted. Covers placing, splitting, merging, and restructuring documents; does not cover writing the text itself, glossaries and decision records, or organizing a repo for the first time, which belongs to the BKF manual. | [organize-documents.md](/modules/organize-documents.md) |
| Defines how to form and agree a durable plan, write its phases and subplan briefs, and set completion gates. Workflow execution and recovery are covered by coordinate-a-workflow and the selected workflow type. | [plan-work.md](/modules/plan-work.md) |
| Adds criteria for reading academic studies, synthesizing literature, developing research questions, and critiquing theses. It extends the general collection and evidence-assessment rules in frame-and-collect-evidence and conclude-from-evidence. | [read-academic-sources.md](/modules/read-academic-sources.md) |
| Defines the content and use of glossaries, context maps, and decision records. Document placement and restructuring are covered by organize-documents. | [record-domain-terms.md](/modules/record-domain-terms.md) |
| Defines how to assess prior work against assigned criteria and report evidence-based findings. Workflow coordination handles review returns and delivery gates. | [review-work.md](/modules/review-work.md) |
| Defines how to revise an existing document while preserving its facts, scope, authority, and operational meaning. General principles for writing actionable text are covered by writing-principles. | [revise-a-document.md](/modules/revise-a-document.md) |
| Defines every parallel group, each branch in its own worktree: the gate each branch brief declares and `bkf gate` checks, the mechanical merge, cleaning up merged branches, failed branches, and when merging may read content. Agent assignment is covered by delegate-work and workflow sequencing by coordinate-a-workflow. | [run-parallel-work.md](/modules/run-parallel-work.md) |
| Defines the syntax and editing rules for `bkf-workflow` declarations, including step types, references, IDs, and sync commands. Workflow mechanics and validation rules are specified by agent-workflow-foundation. | [write-a-declaration.md](/modules/write-a-declaration.md) |
| Defines the structure and evidence handling for synthesis reports and research answers. The evidence record and claim assessment are covered by research modules. | [write-a-report.md](/modules/write-a-report.md) |
| Sets general principles for writing actionable text, including organization, examples, uncertainty, and plain language. Revision-specific guidance is covered by revise-a-document. | [writing-principles.md](/modules/writing-principles.md) |
| Defines a two-axis review workflow that checks a pinned change against repository standards and its originating specification, then reports each axis separately. Correcting review findings is a separate task. | [code-review.md](/workflow-types/code-review.md) |
| Defines a full council workflow with five independent advisors, five peer reviewers, and a chairman for an explicitly requested question or decision. Every phase is required; ordinary advice and lightweight reviews use other methods. | [council.md](/workflow-types/council.md) |
| Defines a durable planning workflow with phases, at least two subplans, configurable research, checkpoints and subplan reviews, an agreed executor, and optional Claude review. Conversation plans stay outside this workflow type. | [plan.md](/workflow-types/plan.md) |
| Defines a throwaway prototype workflow for answering a logic or UI design question, then carrying the decision into real code or discarding it. The prototype itself is not a production deliverable. | [prototype.md](/workflow-types/prototype.md) |
| Defines a workflow for sourced research that needs comparison or an auditable evidence trail, from claim framing and collection through synthesis and audit. A narrow lookup follows the Quick path and does not use this workflow type. | [research.md](/workflow-types/research.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

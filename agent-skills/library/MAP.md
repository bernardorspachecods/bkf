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
| `always` | Any task of a skill that selects library modules; the rule applies whatever the work is. Skills that carry their own rules and link the modules they need do not select by tag. |
| `code` | Designing, implementing, or prototyping software. |
| `research` | Collecting evidence, concluding from it, or reading sources. |
| `planning` | Planning, running, or redoing multi-step work. |
| `review` | Assessing work against criteria. |
| `delegation` | Handing work to agents or acting as a stage agent. |
| `writing` | Writing or revising any text, prompt, or document. |
| `knowledge` | Placing documentation, or recording glossary terms and decisions. |
| `role-guide` | Never selected by a skill: a brief for a role in a workflow points the agent to it. |
| `repo-library` | Spotting a repeated repository procedure and adding it to the repo library. |

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Sets rules for acting within an approved task, deciding when to ask, which rule wins when rules conflict, how to make a risky structural change, and when to keep an interface or document for compatibility. Activity-specific methods belong in other modules. | [act-within-scope.md](/modules/act-within-scope.md) |
| Names common code smells introduced during implementation and the corresponding fixes. Repository-specific standards take precedence, while module design and implementation practices are covered by design-modules and build-software. | [avoid-code-smells.md](/modules/avoid-code-smells.md) |
| Defines how to prepare prompts and handoffs for agents, including source authority, write boundaries, and completion checks. Coordination across a run is covered by coordinate-a-run. | [brief-another-agent.md](/modules/brief-another-agent.md) |
| Sets implementation practices for building features and fixing bugs, including test-first slices and dependency choices. Module interface design and boundaries are covered by design-modules. | [build-software.md](/modules/build-software.md) |
| Defines the coordinator's duties in a run where agents work apart and a script chains their phases: stay out of the roles, stay quiet between checkpoints, treat agent output as unverified, and treat a failure as an escalation. Each workflow's coordinator guide owns its own phases and files. | [coordinate-a-run.md](/modules/coordinate-a-run.md) |
| Defines how to assign work to agents outside a run script and reconcile their handoffs, including independence, write boundaries, and completion reports. Coordination across a run is covered by coordinate-a-run. | [delegate-work.md](/modules/delegate-work.md) |
| Provides vocabulary and decision rules for module depth, interface seams, dependencies, and tests across interfaces. Implementation sequencing and test-first practices are covered by build-software. | [design-modules.md](/modules/design-modules.md) |
| Defines how to identify, propose, write, and validate reusable procedures in a repository's repo-library, or in the general library when the rule applies to any repository, including when it comes from an external source. Day-to-day document organization is covered by organize-documents. | [grow-libraries.md](/modules/grow-libraries.md) |
| Gives the rules for looking after a repository's documents under BKF: keep them consistent with the code and each other as part of every change, write each fact in one place, decide where information lives and how it ages, state a document's scope in its description, log only the files the map cannot list, and stop and ask the user when the organization has drifted. Covers placing, splitting, merging, and restructuring documents; does not cover writing the text itself, glossaries and decision records, or organizing a repo for the first time, which belongs to the BKF manual. | [organize-documents.md](/modules/organize-documents.md) |
| Defines how to form and agree a plan: state the outcome, the boundaries, the work and how completion is recognized in checkable terms, and get the user's agreement before work starts. A plan run on a script follows the plan workflow guide. | [plan-work.md](/modules/plan-work.md) |
| Defines the content and use of glossaries, context maps, and decision records. Document placement and restructuring are covered by organize-documents. | [record-domain-terms.md](/modules/record-domain-terms.md) |
| Defines how to assess prior work against assigned criteria and report evidence-based findings. Each workflow guide owns its own review roles and verdicts. | [review-work.md](/modules/review-work.md) |
| Defines how to revise an existing document while preserving its facts, scope, authority, and operational meaning. General principles for writing actionable text are covered by writing-principles. | [revise-a-document.md](/modules/revise-a-document.md) |
| Sets general principles for writing actionable text, including organization, examples, uncertainty, and plain language. Revision-specific guidance is covered by revise-a-document. | [writing-principles.md](/modules/writing-principles.md) |
| Owns the code review guides - the coordinator's guide and one guide per role, axis reviewer and checker - that a review brief points agents to. | [MAP.md](/workflow-types/code-review/MAP.md) |
| Owns the council guides - the coordinator's guide and one guide per role in advice, review and the completeness check - that a council brief points agents to. | [MAP.md](/workflow-types/council/MAP.md) |
| Owns the plan guides - the coordinator's guide and one guide per role in implementation, review and integration - that a plan brief points agents to. | [MAP.md](/workflow-types/plan/MAP.md) |
| Owns the sourced-research guides - the coordinator's guide and one guide per role in collection, digest and review - that a research brief points agents to. | [MAP.md](/workflow-types/research/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

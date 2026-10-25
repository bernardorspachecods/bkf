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
| `research` | Collecting evidence, concluding from it, or reading sources. |
| `planning` | Planning, running, or redoing multi-step work. |
| `review` | Assessing work against criteria. |
| `delegation` | Handing work to agents or acting as a stage agent. |
| `knowledge` | Placing documentation, or recording glossary terms and decisions. |
| `role-guide` | Never selected by a skill: a brief for a role in a workflow points the agent to it. |
| `injected` | Never selected by a skill list: skills inject the module's text with `<!-- inject: ... -->`. |

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Defines the coordinator's duties in a run where agents work apart and a script chains their phases: stay out of the roles, stay quiet between checkpoints, treat agent output as unverified, and treat a failure as an escalation. Each workflow's coordinator guide owns its own phases and files, and points here for what every run shares. | [coordinate-a-run.md](/modules/coordinate-a-run.md) |
| Sets the principles for work with code: test first, growing in layers, long-term decisions, reuse and code smells; and how it is verified: let code decide what code can decide, make every check able to fail. Covers any work with code, including work handed to other agents; the gate a script runs for a plan or a review is owned by the gate module. | [core-code-principles.md](/modules/core-code-principles.md) |
| States the contract of the gate, the commands a script runs outside any agent to decide what code can decide: how they run, what they record, and what an agent that receives the result does with it. | [gate.md](/modules/gate.md) |
| Sets how an agent settles intent with the user before work that is more than a small change, so it can then work alone: what is wanted and why, when it is done, what is out of scope and decided, when to stop and ask, and how a change of intent is recorded. Long or delegated work keeps the intent in a goal file; small work restates it in the conversation. | [intent.md](/modules/intent.md) |
| Owns the code review guides - the coordinator's guide and one guide per role, axis reviewer and checker - that a review brief points agents to. | [MAP.md](/workflow-types/code-review/MAP.md) |
| Owns the council guides - the coordinator's guide and one guide per role in advice, review and the completeness check - that a council brief points agents to. | [MAP.md](/workflow-types/council/MAP.md) |
| Owns the plan guides - the coordinator's guide and one guide per role in implementation, review and integration - that a plan brief points agents to. | [MAP.md](/workflow-types/plan/MAP.md) |
| Owns the sourced-research guides - the coordinator's guide and one guide per role in collection, digest and review - that a research brief points agents to. | [MAP.md](/workflow-types/research/MAP.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

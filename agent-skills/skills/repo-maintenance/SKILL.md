---
name: repo-maintenance
description: Use when changing or organizing a repository's documentation, including under BKF, when writing or revising a document, guide, report, prompt, handoff or instruction that another reader will act on, or when recording repeated procedures.
---

# Repo maintenance

## Writing

- Produce the least reading burden that reliably supports the reader's task. Assume ordinary task competence: supply only the local conventions, owners, workflows, exceptions, facts and prior decisions the reader lacks, and do not repeat general behavior in repository documents.
- Keep supporting content only when it adds a fact, a decision distinction or reasoning not already established. Ground precautionary guidance in a credible scenario and its consequence; guardrails added by habit are noise. Remove repeated meaning across instructions, rationale, examples and checklists, and replace a list of cases with a general rule when it keeps the distinctions the reader needs to act.
- State required behavior, constraints and completion conditions explicitly, and organize around them. Put task-defining instructions and critical constraints early, with their priority stated.
- Start with a direct instruction and give each hard rule its reason, so the reader can apply it to cases it does not mention. For decisions that vary by context, add a diagnostic question and its principle.
- Choose modal verbs by intended force: "must" for a requirement, "can" for a capability, a direct statement for an observation.
- Add an example only to clarify a hard distinction or resolve competing interpretations. A single example is copied closely, incidental details included, so label examples as illustrations of the format, not templates, or give two that visibly differ.
- In a long document (several hundred lines, or several independent areas), add a short navigation map near the start whose entries link to real headings and are phrased as reader tasks. At a link to detail that only some readers need, name the condition for following it. In skills and context files, keep instructions (what to do) separate from descriptions (what something is).

## Reporting what is known

- State current behavior, intended change and uncertainty separately, and do not turn a possibility into a fact. Separate confirmed findings from inferences and recommendations, label the evidence source of each claim, and do not present a report as direct observation. When the evidence is incomplete, say so and limit conclusions to the supported part.

## Revising an existing document

- Keep facts, commands, code, link targets, file paths, identifiers, quoted errors and product names exact. Structure, such as headings, lists, tables and navigation, may be reorganized when that serves the reader, but keep it where it carries meaning, such as a route through the documentation or the order of a procedure.
- Assess the whole target file before choosing how much to rewrite; a local correction alone does not complete that assessment.
- Compare the original and revised requirements in both directions: behavior lost and obligations newly introduced. Preserve scope, authority, conditions, exceptions, dependencies, uncertainty and completion criteria unless a change is authorized. For an edit that must leave exact content alone, also confirm that facts, links, commands, code and identifiers are unchanged.
- Walk through a representative task using only the context the reader will have. Repair gaps, and remove content that helps none of: finding the instructions, resolving conditions, producing the result, recognizing completion. Treat the walkthrough as an inspection, not evidence that another agent would succeed.
- When instructions fail, identify the cause from observed behavior before adding rules. Name the mechanism at play (a duplicated source, drift from the source, missing reader context, a buried critical instruction) and fix that, not the nearest-looking example, and check that the fix preserves other requirements.
- Treat automated checks, such as prose linters and structure auditors, as advisory: review each finding with the owner before deciding what to change. A structural validator cannot judge whether the objective or deliverable is right.

## Recording a recurring procedure

- The same procedure or rule has come up more than once in the repository, or the user says "we always do X here": [Grow the repo library](../repo-library/SKILL.md#grow-the-repo-library).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

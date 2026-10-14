---
bkf: document
description: "Defines how to revise an existing document while preserving its facts, scope, authority, and operational meaning. General principles for writing actionable text are covered by writing-principles."
tags: [writing]
---

# Revise a document

- Keep facts, commands, code, link targets, file paths, identifiers, quoted errors, and product names exact. Do not normalize technical terms in ways that change their meaning. Structure, such as headings, lists, tables, and navigation, may be reorganized or consolidated when that serves the reader, but keep it where it carries meaning, such as a route through the documentation or the order of a procedure.
- Assess the whole target file before choosing how much to rewrite; a local correction alone does not complete that assessment.
- Compare the original and revised requirements in both directions: behavior lost and obligations newly introduced. Preserve scope, authority, conditions, exceptions, dependencies, uncertainty, and completion criteria unless a change is authorized. For an edit that must leave exact content alone, also confirm that facts, links, commands, code, and identifiers are unchanged.
- Walk through a representative task using only the context the reader will have. Repair gaps, and remove content that helps none of: finding the instructions, resolving conditions, producing the result, recognizing completion. Also check what the reader can ignore. Treat the walkthrough as an inspection, not evidence that another agent would succeed.
- When instructions fail, identify the cause from observed behavior before adding rules. If uncertain, state a hypothesis and test it against an actual task; if no known rule fits, name the mechanism at play (a duplicated source, drift from the source, missing reader context, a buried critical instruction) and fix that. Fix the mechanism, not the nearest-looking example, and check that the fix preserves other requirements.
- Treat automated checks, such as prose linters and structure auditors, as advisory: they report findings and do not modify files, and each finding is reviewed with the owner before deciding what to change. A structural validator cannot judge whether the objective or deliverable is right; review that separately.

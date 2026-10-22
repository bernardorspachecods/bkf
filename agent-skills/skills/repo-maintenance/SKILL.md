---
name: repo-maintenance
description: Use when your change affects a repository's documents, when organizing or restructuring them, or when writing or revising a document that other agents will act on, mostly under BKF.
---

# Repo maintenance

## Keeping the organization

These rules apply to every change in a BKF repo, while building its organization and after. Follow them; do not restate them in the repo's documents.

- **Update the owner in the same change.** Before changing behavior, structure, or a decision, find the document that owns it through the nearest map. After the change, update that document, then look for other documents that state the same thing and replace each with a link to the owner. The change is not finished while documents contradict the code or each other. If the owner is unclear, ask the user.
- **Write each fact once.** Before writing a rule, fact, or procedure, check the map for its owner and write it only there; elsewhere, link. Repeat a fact only when missing it would be costly and easy to overlook, as a one-line version that points to the owner. Needing to edit several files for one change means a fact is written in more than one place: remove the copies, do not update them all.
- **Keep authority layers distinct.** Maps route, an owner document records the intended rules, and code, migrations, or scripts confirm current behavior. Link the layers. When sources disagree or may be stale, including when the user's description of how something works differs from the code, surface the mismatch instead of silently resolving it, unless told otherwise.
- **Separate durable context from temporary work,** and keep material distinguishable by purpose and lifecycle, such as work in progress, archived material, and consolidated knowledge.
- **Log by hand only what the map cannot list, and only where it helps.** Spreadsheets, PDFs, data, and files kept out of version control get an entry only when you and the user agree it helps someone find or understand them; do not log them all. Files the harness already routes to by their own metadata, such as skill packages, need no entry. Add a task route, as the format specification defines it, only for requests that cross areas or are ambiguous, and do not impose universal destinations or authority rules the repository has not established.
- **Keep the root files to their jobs.** Create `AGENTS.md` only for rules specific to the repository's agents, never an empty or placeholder file; it is not an index or catch-all and does not hold product vision, architecture, current state, plans, or general documentation. Link the root map near its start. A README is public-facing, not internal context; when it acts as an internal manual or router while another document owns the content, move what is needed to that owner, update the consumers, and remove the rest.
- **Treat every area as live unless its description says it is stale.** Do not infer that an area is stale from which files exist or how old they look. When one seems stale, raise it with the user; once confirmed, flag it as stale in its description.
- **Restructuring is a normal outcome, not a last resort.** Existing files, paths, links, and history are evidence to assess, not constraints to preserve. Before restructuring, inspect the relevant documents, paths, links, implementation evidence, and real consumers, and decide the target from responsibility, authority, lifecycle, and real consumers. Transfer unique information to its current owner, update consumers, and remove obsolete artifacts. Keep a legacy document, interface, or contract only while it has a current owner, a real consumer, or a current requirement; when one is intentionally changed, remove the obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- **Stop and ask when the organization has drifted.** Do not reorganize alone when a mismatch between sources cannot be settled from the authority layers, an area flagged stale is still described as current elsewhere, the map or router is stale in several places, or an area's structure no longer matches how it is used. Report what you saw. Organizing a repo again is a conversation with the user, which they start explicitly; do not start it alone.

## Writing a document

- Produce the least reading burden that reliably supports the reader's task. Assume ordinary task competence: supply only the local conventions, owners, workflows, exceptions, facts and prior decisions the reader lacks, and do not repeat general behavior in repository documents.
- Keep supporting content only when it adds a fact, a decision distinction or reasoning not already established. Ground precautionary guidance in a credible scenario and its consequence; guardrails added by habit are noise. Remove repeated meaning across instructions, rationale, examples and checklists, and replace a list of cases with a general rule when it keeps the distinctions the reader needs to act.
- State required behavior, constraints and completion conditions explicitly, and organize around them. Put task-defining instructions and critical constraints early, with their priority stated.
- Start with a direct instruction and give each hard rule its reason, so the reader can apply it to cases it does not mention. For decisions that vary by context, add a diagnostic question and its principle.
- Choose modal verbs by intended force: "must" for a requirement, "can" for a capability, a direct statement for an observation.
- Add an example only to clarify a hard distinction or resolve competing interpretations. A single example is copied closely, incidental details included, so label examples as illustrations of the format, not templates, or give two that visibly differ.
- In a long document (several hundred lines, or several independent areas), add a short navigation map near the start whose entries link to real headings and are phrased as reader tasks. At a link to detail that only some readers need, name the condition for following it. In skills and context files, keep instructions (what to do) separate from descriptions (what something is).

## Revising an existing document

- Keep facts, commands, code, link targets, file paths, identifiers, quoted errors and product names exact. Structure, such as headings, lists, tables and navigation, may be reorganized when that serves the reader, but keep it where it carries meaning, such as a route through the documentation or the order of a procedure.
- Assess the whole target file before choosing how much to rewrite; a local correction alone does not complete that assessment.
- Compare the original and revised requirements in both directions: behavior lost and obligations newly introduced. Preserve scope, authority, conditions, exceptions, dependencies, uncertainty and completion criteria unless a change is authorized. For an edit that must leave exact content alone, also confirm that facts, links, commands, code and identifiers are unchanged.
- Walk through a representative task using only the context the reader will have. Repair gaps, and remove content that helps none of: finding the instructions, resolving conditions, producing the result, recognizing completion. Treat the walkthrough as an inspection, not evidence that another agent would succeed.
- When instructions fail, identify the cause from observed behavior before adding rules. Name the mechanism at play (a duplicated source, drift from the source, missing reader context, a buried critical instruction) and fix that, not the nearest-looking example, and check that the fix preserves other requirements.
- Run `bkf validate .` after changing documents; it checks structure, not whether the content is right. Treat other automated checks, such as prose linters, as advisory: review each finding with the owner before deciding what to change.

## Recording a recurring procedure

- The same procedure or rule has come up more than once in the repository, or the user says "we always do X here": [Grow the repo library](../repo-library/SKILL.md#grow-the-repo-library).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

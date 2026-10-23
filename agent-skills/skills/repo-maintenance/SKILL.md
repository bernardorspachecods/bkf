---
name: repo-maintenance
description: Use when your change affects a repository's documents, when organizing or restructuring them, or when writing or revising a document that other agents will act on, mostly under BKF.
---

# Repo maintenance

These rules apply to every change that touches a BKF repo's documents, whatever its size. Follow them; do not restate them in the repo's documents.

## Principles

- **One owner per fact.** Before changing behavior, structure, or a decision, and before writing any rule, fact, or procedure, find the document that owns it through the nearest map and work there. Everywhere else, link to it. Needing to edit several files for one change means a fact is written in more than one place: remove the copies instead of updating them all. Repeat a fact only when missing it would be costly and easy to overlook, as one line that points to the owner.
- **Verify against the source.** Maps route, an owner document records the intended rules, and code, migrations, or scripts confirm current behavior. Judge whether a document is current by comparing it with the code, never by which files exist or how old they look. When sources disagree, including when the user's description differs from the code, surface the mismatch instead of resolving it silently.
- **Revise, do not append.** A change is not finished while documents contradict the code or each other. Read the whole document you touch and leave it reading as if written once: edit the section where the change belongs, merge what now overlaps, remove what no longer holds. Documents are not history.
- **Add only what helps the agent.** The agent has ordinary competence: supply the local conventions, owners, exceptions, facts, and decisions it lacks, and nothing else. Remove repeated meaning across instructions, rationale, examples, and checklists. A rule added by habit is noise; ground a precaution in a credible failure.
- **Documents hold what lasts.** Temporary work, such as a plan or notes on work in progress, goes where the repo keeps its plans, not in the owner documents. When the work ends, move what lasts to its owner and drop the rest.
- **Fix what is clearly wrong, ask about what is not.** Moving, merging, or removing documents is normal when your change calls for it. A legacy file, path, or interface stays only while it has a current owner, a real consumer, or a current requirement; remove obsolete paths instead of adding compatibility layers. A clear contradiction you meet outside your change is yours to correct when you have a good reason; say what you fixed. Stop and ask when sources cannot be settled from the authority layers, the map is stale in several places, or an area's structure no longer matches how it is used. Reorganizing a repo is a conversation the user starts.

## Writing for agents

- Start with a direct instruction, put critical constraints early with their priority, and give each hard rule its reason, so the agent can apply it to cases it does not mention. For decisions that vary by context, add a diagnostic question and its principle.
- Add an example only to clarify a hard distinction. One example is copied closely, incidental details included: label it an illustration, or give two that visibly differ.
- At a link to detail that only some agents need, name the condition for following it. In skills and context files, keep instructions (what to do) separate from descriptions (what something is).
- When revising, keep facts, commands, code, link targets, paths, identifiers, quoted errors, and product names exact, and compare the old and new requirements in both directions: behavior lost, obligations newly added. Then walk through a representative task using only the context the agent will have.
- When instructions fail, find the cause from observed behavior (a duplicated source, drift from the source, missing agent context, a buried constraint) and fix that, not the nearest-looking example.

## Conventions

- **Root files.** `AGENTS.md` holds only rules specific to the repository's agents; it is not an index or catch-all. Link the root map near its start. A README is public-facing, not internal context; when it acts as an internal manual or router while another document owns the content, move what is needed to that owner, update the consumers, and remove the rest.
- **Log by hand only what the map cannot list,** and only where it helps: spreadsheets, PDFs, data, and files kept out of version control, when you and the user agree it helps someone find them. Files the harness routes to by their own metadata, such as skill packages, need no entry. Add a task route only for requests that cross areas or are ambiguous; do not impose destinations or authority rules the repository has not established.
- Run `bkf validate .` after changing documents; it checks structure, not whether the content is right.
- The same procedure or rule has come up more than once in the repository, or the user says "we always do X here": [Grow the repo library](../repo-library/SKILL.md).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

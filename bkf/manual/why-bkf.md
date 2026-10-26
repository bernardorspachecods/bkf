---
bkf: document
description: "Compares BKF with three common ways to give agents repository knowledge (a single AGENTS.md, editor rule files, and skill collections): what each does well, what BKF adds, what it costs, and when not to use it. Does not explain how BKF works (what-is-bkf) or how to adopt it (build-repo-organization)."
tags: [bkf, manual]
---

# Why BKF

This compares BKF with the three alternatives most repositories start with. It describes categories, not specific products, and it is a design argument, not a measurement: no head-to-head test of agent results has been run. Where BKF's advantage is a claim and not a checked fact, the text says so.

## Which alternative fits

| You have | A simple alternative is enough when | BKF starts to pay off when |
| --- | --- | --- |
| One repo, one or two agents | One `AGENTS.md` holds all rules and stays under a screen or two | The file grows past what an agent reads in full, or its facts start contradicting the code |
| Editor rule files | Rules are short, per-tool, and rarely change | The same rule is copied across files or tools, or nobody can say which copy is current |
| A skill collection | You want generic procedures you do not have to maintain | You need repo-specific rules, or skills repeat shared guidance and each change is made many times |

## Against a single AGENTS.md

A single file is the cheapest option and the right one for a small repo. It fails in a predictable way: every new fact is appended, nothing marks which facts are current, and the agent either reads everything or misses the one rule that mattered.

BKF keeps `AGENTS.md` for rules specific to the repository's agents and moves everything else to documents with one owner each, found through generated maps. The advantage is checkable: `bkf validate` fails on structural drift, and `bkf inventory` fails when a map is stale. A single file has no such check.

## Against editor rule files

Rule files are loaded automatically and scoped to file patterns, which BKF does not do. Their weakness is that they are tied to one tool, and nothing stops the same rule living in several files with different wording.

BKF is plain Markdown with YAML frontmatter, so any agent that can read files can use it. Its rule is one owner per fact, with links elsewhere, and the validator checks the structure that makes this possible. It cannot check that a fact is true.

## Against skill collections

A collection gives you ready procedures, and BKF's skills are the same kind of thing. The difference is where shared rules live. In a plain collection, guidance common to many skills is usually copied into each, so each change is made many times. BKF writes each rule once in a module, and a skill injects the text of the modules that apply. Repo-specific rules go in the repo's own `repo-library/`, which adds to the shared modules and never restates them.

BKF also covers what a collection does not: how a repo's own documents are organized, and workflows with separate roles, independent review, and user checkpoints for work that passes between agents.

## What BKF costs

- Adoption takes effort. Organizing a repo is a conversation with the user, and the documents have to be kept up to date on every change.
- The tooling must be installed, and its checks cover structure only. A wrong fact, or a document that is missing, passes validation.
- Discipline is the real requirement. A repo that ignores the upkeep rules in the `repo-maintenance` skill ends up with the drift BKF was built to prevent, now with more files.
- BKF is young and has one maintainer's conventions built in. Expect to adapt it.

## When not to use BKF

Use a single `AGENTS.md` if the repo is small, has one author, and its rules fit on a screen. Use plain editor rules if you work in one tool and the rules are stable. Revisit when you notice the same fact written in two places or an agent acting on an outdated rule.

To learn what BKF is and how it is layered, read [what BKF is](/manual/what-is-bkf.md). To adopt it, use [the build procedure](/manual/build-repo-organization.md).

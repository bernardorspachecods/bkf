---
bkf_version: "0.2"
description: Defines the BKF document, map, and bundle format and provides tooling to generate inventories and check conformance.
---

# BKF Map

## Member inventory

<!-- BKF:GENERATED-MEMBER-INVENTORY:START -->
| What it is | Document |
| --- | --- |
| Sets the standing agent instructions for this bundle: when to record problems in feedback.md or ideas in ideas.md, and how design work is run. | [AGENTS.md](/bkf/AGENTS.md) |
| Collects evidence about problems in agent work on this bundle for later filtering with the user. It records events rather than supplying instructions. | [feedback.md](/bkf/feedback.md) |
| Defines BKF bundle membership, tracking, maps, links, reserved files, and conformance. Terms are defined in glossary.md; field requirements are in frontmatter-profiles.md. | [format-specification.md](/bkf/format/format-specification.md) |
| Defines YAML frontmatter rules, tracking, and fields for generic documents, feedback and ideas files. Bundle structure and conformance are specified by format-specification.md. | [frontmatter-profiles.md](/bkf/format/frontmatter-profiles.md) |
| Owns one definition for every BKF term; the rules that use those terms belong to their specification and profile documents. | [glossary.md](/bkf/format/glossary.md) |
| Collects ideas from the user and agents for later review as future possibilities, not instructions. | [ideas.md](/bkf/ideas.md) |
| The procedure for organizing a repository's documents under BKF for the first time, or revamping an outdated one, as a conversation with the user. Owns the build-only rules, the user's decision points and what the repository has when it is done; the upkeep rules are in the `repo-maintenance` skill and the reasons in what-is-bkf. | [build-repo-organization.md](/bkf/manual/build-repo-organization.md) |
| Explains what BKF is and why it is built this way: the problem it solves, the layers, how a task moves through them, and what keeps a repo healthy. Does not hold the rules (modules) or the build procedure (build-repo-organization). | [what-is-bkf.md](/bkf/manual/what-is-bkf.md) |
| Compares BKF with three common ways to give agents repository knowledge (a single AGENTS.md, editor rule files, and skill collections): what each does well, what BKF adds, what it costs, and when not to use it. Does not explain how BKF works (what-is-bkf) or how to adopt it (build-repo-organization). | [why-bkf.md](/bkf/manual/why-bkf.md) |
| Defines the BKF command interfaces and implements tools that generate inventories, and validate bundles. | [MAP.md](/bkf/tooling/MAP.md) |
| Describes the move to BKF format 0.2, in which every link in a nested bundle resolves from the outermost bundle root, and the steps to migrate a bundle with bkf upgrade. | [0-2.md](/bkf/updates/0-2.md) |
<!-- BKF:GENERATED-MEMBER-INVENTORY:END -->

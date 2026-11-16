---
name: research
description: Use when the user asks for sourced or verified findings, a comparison across sources, an audit of a conclusion, or literature work that needs multiple sources or an evidence trail; or a stopped research run to resume.
---

# Research

<!-- inject: ../../modules/agentic-roles.md -->
<!-- BKF:GENERATED-INJECTED -->
## Agentic roles

| Role | Exists to | Protects | Sees |
| --- | --- | --- | --- |
| Coordinator | Own the goal and the contracts: write the briefs and checks, decide within the agreed intent, close small gaps, write the report | That the user's intent survives the run | Everything |
| Author | Do the piece of work its brief names and nothing around it | Scope: other pieces rely on what it left alone | Its brief, and its earlier handoff on a retry |
| Reviewer | Stand in for the user on one question: does this work do what the brief asked | Independent judgment | The brief, the work and the check results; never the author's reasoning or handoff |
| Integrator | Only for parallel work: make the pieces fit without redoing them | The contracts between pieces | The pieces' briefs and the goal |

The coordinator may hold any other role, never authoring and reviewing the same piece. Every piece is reviewed; only the user can waive a review, and the report says so. A failed or escalated run is not a block: read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user.

A run's checkpoints are usually the start, the end and an escalation. At a checkpoint, stop until the user approves, and link the file instead of pasting it. Between checkpoints, decide within the agreed intent (`align-intent`) and continue without messaging the user: no progress updates or questions about small decisions.

Report an outcome as it is: what passed, what escalated, what was skipped.
<!-- BKF:GENERATED-INJECTED-END -->

A lookup is one fact one authoritative source can give: open it and answer with the citation, its date and its limits, and escalate to research only if the source is weak or the answer disputed. One research is one objective; split a request with several questions. A fact about the repository is not research: read the thing itself.

```
Map ─► Collection ─► Review of collection ─► Digest ─► Review of digest ─► You write ─► Review of delivery ─► User
           └ back to collection                 └ back to digest                         └ back to you
```

Each agent is pointed to its guide: [collection](roles/research-collection.md), [review of the collection](roles/research-review-collection.md), [digest](roles/research-digest.md), [review of the digest](roles/research-review-digest.md) and [review of the delivery](roles/research-review-delivery.md).

## 1. The objective

Settle it with the user as `align-intent` does, and write it to `objective.md` with what the agents filter by:

- **Use:** who reads the result and what they will do with it.
- **What is sought:** a question, not a topic, and the kind of delivery (a fact, a comparison, a map of the terrain, a recommendation).
- **Priorities:** where depth goes.
- **Mode:** broad or focused, chosen by the user.
- **Out of scope, and what counts as enough.**
- **Stakes,** when the result carries a safety, legal, financial, medical or hard-to-reverse decision: then the claims behind it need several independent authoritative sources, the delivery recommends specialist review, and thin evidence gives a bounded answer.

## 2. The map of sources

List with the user the obvious sites and niches of the subject; the user confirms that list. Write it to `sourcemap.md`, one numbered niche per line, with "Counterweight." on niches meant for evidence against the common view; the map agent adds niches marked "(agent)". Do not read pages yourself: the reading belongs to the collectors. In `collectors.txt`, give each collector its niches (`name: 1,2,5`).

## 3. What the user receives

You write the delivery from the reviewed digest, not from the raw sources:

1. **The answer,** organized by views, each finding with its source and where in it, showing what was merged or split.
2. **Weak points and the suggested next step,** including what appeared outside the focus.
3. **Not consulted:** the relevant sources that could not be opened.
4. **Annex:** what else was collected.

Your own opinion from memory enters only at the end, only if asked, and said to be so.

## Running

Before the first `start` or `resume`, read [run-commands.md](../../modules/run-commands.md). Then `research-run.sh start [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>` ([research-run.sh](scripts/research-run.sh)). When it prints `READY`, the digest is `<run>/03-digest/digest.md`; write the delivery and run `research-run.sh deliver [-m model] [-e effort] <name> <delivery.md>` to review it (exit 0 `pass`, 1 `back`, 2 `escalate`), correcting and rerunning `deliver` until it passes. When the digest review escalated and the user judges the digest good enough, `research-run.sh accept-digest <name> --why <text>` closes it by hand. `finish --delivery-only <name>` keeps only `delivery.md`; `finish --keep-attempts <name>` also keeps failed or redone attempts.

Collectors and the map agent need web access: on Claude the harness grants it to them alone; on Codex they use its built-in web tool (search and open), which is on by default.

Maintainers: [the package's files](files.md).

---
bkf: document
description: Defines a workflow for sourced research that needs comparison or an auditable evidence trail, from claim framing and collection through synthesis and audit. A narrow lookup follows the Quick path and does not use this workflow type.
tags: [research]
---

# Research

**Use when** the user asks for sourced or verified findings that need multiple
sources, comparison, or an auditable evidence trail, or a plan assigns a
research unit. There are no fixed levels. A narrow lookup is **Quick**: the
orchestrator does it alone, with no stages and no audit record (see "Match
rigor to stakes" in frame-and-collect-evidence.md), and this workflow type does
not apply. Anything else runs the stages below, with a session table that says
who does each stage (see [Session table](#session-table), and its
[default table](#default-table)). When unsure whether a request is a
narrow lookup, run the workflow.

## Declaration

The evaluation and audit stages are not known up front: the
coordinator adds one evaluation stage per source group after discovery, and
one audit stage per claim after the claim matrix exists. The evidence check is
one stage. The groups below show the workflow type.

```bkf-workflow
steps:
  - work_unit:
      title: "Question framing"
      steps:
        - stage:
            key: claims
            title: "Question framing — define the question and the claim matrix"
            file: research-record

  - work_unit:
      title: "Source discovery"
      steps:
        - stage: {title: "Collect sources for all material claims", file: research-record}

  - work_unit:
      title: "Source evaluation"
      steps:
        - parallel:
            - stage: {title: "Evaluate source group 1 and extract evidence"}
            - stage: {title: "Evaluate source group 2 and extract evidence"}

  - work_unit:
      title: "Evidence check"
      steps:
        - stage: {title: "Check the evidence entries against the stored sources"}

  - work_unit:
      title: "Synthesis"
      steps:
        - stage:
            key: draft
            title: "Write findings, support status, and the draft answer"
            file: research-record

  - work_unit:
      title: "Audit"
      steps:
        - parallel:
            - stage: {title: "Audit claim 1", reviews: [draft]}
            - stage: {title: "Audit claim 2", reviews: [draft]}
```

Every `parallel` group in this workflow type follows run-parallel-work.md: each branch brief declares its gate, and a branch is checked with `bkf gate` before the next step uses it.

## Session table

The stages are fixed. Who does them is chosen per session. Before spending
anything, the coordinator proposes a table with one row per stage and the user
approves it. Each row gives the agent grouping, the capability tier, and a
justification. A row that departs from the reference below needs a stronger
justification that names the risk taken or the cost saved. The table is the
only record of these choices, departures included.

The table lives in the body of the workflow's parent file, which the
coordinator reads and writes, under a heading naming the research unit (a plan
with several research units has one table per unit). The coordinator adds the
evaluation and audit rows once those stages exist. It gives each stage agent
only that agent's row in its brief; stage agents do not open the parent file
and do not copy the table into their own files.

| Stage | Reference grouping | Reference tier |
| --- | --- | --- |
| Question framing | One agent | Highest. It fixes what is claimed and sought, so an error contaminates every later stage. |
| Discovery | One agent, apart from framing | Middle. The work is high-volume and mostly mechanical. |
| Evaluation | One agent per source group, apart from discovery | Middle. It may not search for new evidence. |
| Evidence check | One agent, apart from evaluation | Middle. It reads the stored sources in context and does not search. Independence from the evaluator matters more than capability. |
| Synthesis | One agent, apart from evaluation | High. It must keep the claims coherent. |
| Audit | One agent per high-importance claim; medium and low claims share one agent | High, and a different model family from synthesis where available. Independence matters more than capability. |

Tiers are capability levels, not model names, so this document does not age
with model releases. The tiers are a judgment from each stage's function, not
a measurement; the justification column is where a case contradicts them.

### Default table

The user's default, which the coordinator proposes unless the user names
another. It is the one place this document names models, so it changes when the
user's models change, and the user still approves the table per session. It
keeps the reference grouping and fits a limited Codex budget: Claude holds the
two judgment stages, and every Codex stage uses `gpt-6-luna` except the audit.

| Stage | Agent | Why |
| --- | --- | --- |
| Question framing | Claude Sonnet 5.5, `medium` | An error here contaminates every later stage. |
| Discovery | Codex `gpt-6-luna`, `high` | High-volume, mostly mechanical; the sentinel catches a weak collection. |
| Evaluation | Codex `gpt-6-luna`, `xhigh` | Judging sources takes more reasoning than collecting them. |
| Evidence check | Codex `gpt-6-luna`, `xhigh`, an agent apart from the evaluator | Independence from the evaluator is the hard rule below. |
| Synthesis | Claude Sonnet 5.5, `medium` | Keeps the claims coherent. |
| Audit | Codex `gpt-6.1-sol`, `medium`, one agent per high-importance claim | The last check and part of the required core; a different family from the synthesis. The only `gpt-6.1-sol` use. |

Departures from the reference, for the justification the table needs: `luna` is
described by Codex as a model for easier tasks, so the evidence check's
`fail-context` and `fail-omission` verdicts are the weakest control, backed
only by the discovery sentinel and the audit; and framing and synthesis use
`medium` effort to save budget. If a session shows either is too weak, raise
the effort of that stage and lower another before dropping a stage.

- **Hard rule:** the audit is by an agent other than the synthesizer. If none is
  available, say so (see "Going back and limits" for reopen and caps). The
  coordinator does not accept a table that breaks this.
- **Hard rule:** the evidence check is by an agent other than the evaluator
  whose entries it checks. The coordinator does not accept a table that breaks
  this.
- **Warned and justified in the table:** one agent doing both discovery and
  evaluation, which anchors evaluation on discovery's notes. Discovery that only registers
  user-supplied sources is a legitimate case.
- **Merging stages** to save cost is allowed when justified. A short claim
  matrix of one or two rows, or evaluation as one stage for few sources or one
  claim, are ordinary cases.
- **Grouping audit claims:** the session may give claims that share sources one
  auditor, and the grouping is justified in the table. If most claims in the matrix are high
  importance, framing did not prioritize: the coordinator returns it to framing
  before hiring auditors, and logs why.
- **Source requirements follow the claim, not the session.** The rules in
  "Match rigor to stakes" in frame-and-collect-evidence.md (independent primary
  or authoritative sources, specialist or human review for high-consequence
  claims) apply by what the claim is. The table cannot lower them.
- **Required core:** the independent audit, and the evidence record (claim
  matrix, source assessments with their limits, evidence entries, conflict log).

## Stage notes

| Stage | Receives | Does not receive | Output |
| --- | --- | --- | --- |
| Question framing | The request or assignment brief, the approved session table, constraints | | The bounded question and the claim matrix. |
| Discovery | The claim matrix, the approved session table, a search ceiling per claim, any user-supplied sources | | A source map, collected sources saved as files in the workflow folder with access mode, search records written to the search log (see below), and a coverage summary with the stop rationale. With user-supplied sources it still runs in a registration-only role: it records them and skips the searches, noting that in the coverage summary. A known relevant document is used as a sentinel to check that collection finds it. |
| Evaluation (one per source group) | The claim matrix and the source list, each source's collected-for claims as a lead only; its own block of evidence IDs | Discovery's relevance notes, search records, any preliminary answer | The source assessments and evidence entries linked to claims, or a gap record for a claim with none. It may search about a source but not for new evidence on a claim. It writes no support status. |
| Evidence check | The claim matrix, the evidence entries, the stored sources, the approved session table | The evaluator's reasoning, discovery's relevance notes and search records | A verdict per entry and per claim (see "Evidence check verdicts"). It rewrites no entry and adds no evidence. |
| Synthesis (one agent, for coherence) | The claim matrix, the evidence entries that passed the check and the gap records, the source assessments, the coverage summary | The working record, discovery notes | Findings per claim with support status and confidence, a conflict log, and the draft answer. |
| Audit (per the session table) | The claim matrix with status and confidence, the draft, the evidence entries, the ledger, the coverage summary, the conflict log | The synthesizer's reasoning notes, the working record | An audit report with a verdict per claim (pass, weaken, remove, reopen) and any counter-evidence it found. Its own searches do not count against discovery's ceilings. |

### Evidence check verdicts

Every fail quotes the source text that justifies it.

- Per entry: `pass`; `fail-quote` (the quote is absent from the cited source or
  not verbatim); `fail-claim` (the entry belongs to another claim);
  `fail-context` (read in context, the quote does not support the entry, or its
  limits are incomplete); `fail-omission` (text in the same source contradicts
  or weakens the entry and the entry ignores it).
- Per claim: `covered`, or `fail-coverage` with the source text that answers
  the claim and no entry cites.

The records (claim matrix, source ledger, evidence entries, evidence check
report, coverage summary, conflict log, reopen log, audit report) form the
audit record, kept apart from the search log. The search log is a separate document that the discovery
stage's body names. Only discovery writes it, and no other stage opens it,
except discovery again when a reopen sends work back to it. It has no
lifecycle of its own: it stays with the workflow folder and goes when the
workflow does. Each field has one stage that writes it: framing
writes the claim rows, evaluation the evidence links and source assessment,
the evidence check the entry and coverage verdicts, synthesis the status and
confidence, audit the claim verdict.

## Going back and limits

- Any stage can send a reopen request through the coordinator: audit may reach
  synthesis, evaluation, or discovery; synthesis may reach evaluation,
  discovery, or framing; the evidence check may reach evaluation; evaluation
  may reach discovery or framing; discovery may reach framing. A request names the claims affected, the stage it targets,
  what is missing or wrong, and the evidence for that. The coordinator accepts,
  merges, or declines each with a reason and logs it. The coordinator returns the work to the earlier stage, and every later stage runs again. Rework only the parts that
  the claim-to-evidence links show as affected, then re-audit them with a
  regression check.
- A claim changes only through framing, and append-only: new claims are added,
  replaced ones are marked superseded or split with a reason, and no ID is
  deleted or reused.
- A source found by audit goes to discovery, then evaluation; it is not added
  to the evidence by the auditor. A source already in the ledger goes straight
  to evaluation.
- A fail verdict from the evidence check goes to evaluation as a reopen
  request. The coordinator accepts, merges, or declines it like any other, and
  declines one it judges a false positive. Evaluation reworks only the named
  entries and claims, and the check rechecks them. An entry that fails the
  recheck is discarded and replaced by a gap record on its claim, and a
  coverage gap that remains goes in the coverage summary. The work goes on, and
  audit, which receives both, may reopen from them.
- A weaken or remove verdict sends the claims to synthesis, which revises, then
  audit rechecks. A reopen verdict goes to the stage that owns the missing
  work, then every downstream stage runs again in order.
- Limits (starting values, which the assignment may override):
  - Search ceiling per claim, counted per query or citation lead followed,
    by importance: high 20, medium 10, low 5. The session table may raise or
    lower them, and discovery's stop rationale is still recorded. At the ceiling discovery stops that claim and may request an
    extension; a declined request leaves the claim reported as
    budget-constrained, not covered.
  - One evaluation rework per source group after the evidence check. It counts
    against neither cap below, because it comes before the first audit.
  - At most 2 accepted reopen cycles per claim and 3 rework rounds overall
    after the first audit; an accepted extension counts as one. At a cap, apply
    any required audit correction and deliver a bounded conclusion that states
    what was tried and what remains.
- Before delivery the coordinator checks that blocking items are resolved or
  disclosed, that audit verdicts were applied, and that the answer states why
  collection stopped.

## Academic extension

For papers, literature reviews, thesis planning, or research-question design,
the same workflow type holds and two stages gain extra work: evaluation also
writes an orientation map and finding summaries, and synthesis also writes a thematic
synthesis, research questions, or a thesis critique, as the task needs.

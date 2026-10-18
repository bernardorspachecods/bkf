---
bkf: document
description: Defines a full council workflow with five independent advisors, five peer reviewers, and a chairman for an explicitly requested question or decision. Every phase is required; ordinary advice and lightweight reviews use other methods.
tags: [planning]
---

# LLM Council

**Use when** the user explicitly invokes a council on a question or decision.
Do not use it for ordinary questions or decisions without an explicit request.
Every session runs the full workflow; no phase is skipped.

## Declaration

```bkf-workflow
steps:
  - work_unit:
      title: "Advisor round"
      work_unit_file: true
      steps:
        - stage:
            title: "Council brief preparation"
            human_checkpoint: true
        - parallel:
            - stage: {title: "Contrarian advisor — write independent advice"}
            - stage: {title: "First principles advisor — write independent advice"}
            - stage: {title: "Expansionist advisor — write independent advice"}
            - stage: {title: "Outsider advisor — write independent advice"}
            - stage: {title: "Executor advisor — write independent advice"}
        - stage:
            key: packet
            title: "Anonymized response packet preparation"

  - work_unit:
      title: "Peer review"
      steps:
        - parallel:
            - stage: {title: "Reviewer 1 — review the anonymized responses", reviews: [packet]}
            - stage: {title: "Reviewer 2 — review the anonymized responses", reviews: [packet]}
            - stage: {title: "Reviewer 3 — review the anonymized responses", reviews: [packet]}
            - stage: {title: "Reviewer 4 — review the anonymized responses", reviews: [packet]}
            - stage: {title: "Reviewer 5 — review the anonymized responses", reviews: [packet]}

  - work_unit:
      title: "Report and delivery check"
      steps:
        - stage:
            key: report
            title: "Chairman report preparation"
        - stage:
            title: "Completeness check"
            reviews: [report]
```

Every `parallel` group in this workflow type follows run-parallel-work.md: each branch brief declares its gate, and a branch is checked with `bkf gate` before the next step uses it.

## Required core and optional stages

Every stage is required: the council is run only when the user explicitly asks, and "Use when" already says every session runs the full workflow.
There are no optional stages and no light run; a smaller question is not a council.

## What each stage receives

| Stage | Receives | Does not receive |
| --- | --- | --- |
| Brief | The user's question and context | Any advisor perspective |
| Advisors (contrarian, first principles, expansionist, outsider, executor) | Its perspective and the same brief as the others | Other advisors' work |
| Packet | The five advisor responses, without perspective text | |
| Reviewers | The anonymized packet | Other reviewers' work, the key, any persona |
| Chairman | The brief, the identified responses, the five reviews, and the key | |
| Completeness check | The report and its sources | |

The coordinator prepares the packet: it strips identity and perspective text from the five responses, assigns randomized labels, and keeps the key from the reviewers. Anonymization is imperfect, since distinctive arguments can still reveal an author.

Each advisor writes its response in its own file: position and confidence, analysis of alternatives and tradeoffs, the strongest counterargument, the key risk or opportunity, and evidence and assumptions. It may research only material factual gaps and cites what it uses. It does not name its own role.

Brief approval is a checkpoint and is not recorded in the workflow files.

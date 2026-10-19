---
bkf: document
tags: [research, planning]
description: Plans the research on web application foundations - its objective, the areas with what each covers, the rules the objectives follow, and the state of each run.
---

# Web foundations research plan

## Objective

Research the foundations of building web apps, one area at a time, so Bernardo
can later improve `desmor-hub` and steer planning agents before an app's
structure is fixed. The research is general and does not read `desmor-hub`.

## Areas

Each area is one research run with its own objective, confirmed by Bernardo
before the run starts, following [research](/agent-skills/library/workflow-types/research/research.md).
The runs start in parallel.

| # | Area | Covers |
| --- | --- | --- |
| 1 | Architecture | How the app is divided and how its parts communicate. |
| 2 | Data | How information is modeled and stored. |
| 3 | Identity and access | Authentication, sessions, authorization, roles. |
| 4 | Security and privacy | Personal data, file uploads, secrets, threats. Legal impact: the objective states the stakes and the guide needs specialist review. |
| 5 | Frontend structure | Components, state, forms, data fetching, boards and charts. |
| 6 | Frontend experience | Performance, accessibility, responsive layout, languages. |
| 7 | Testing | Strategy, levels, test data. |
| 8 | Delivery | CI/CD, environments, running migrations in a release, hosting cost. |
| 9 | Observability and operations | Logs, technical metrics, alerts, backups and restore tests, maintenance. |
| 10 | Background work | Queues, scheduled tasks, retries, idempotency. |
| 11 | Email and messaging | Receiving and sending, templates, reminders, languages, attachments. |
| 12 | Business logic | Pricing and rules, states and flows, approvals, audit trail, versions. |
| 13 | Applied AI | AI reading and filling records, limits, personal data sent to providers. |
| 14 | Metrics and reporting | Business indicators, filters, scheduled reports, export. |

## Rules for the objectives

- Each objective follows section 1 of the research guide: use, question,
  priorities, mode, out of scope, what counts as enough.
- The commercial proposal `Proposta_Comercial_DESMOR.pdf` is input for the
  priorities of each objective, never for which areas exist or as a
  requirement. Its price, schedule, methodology and sales text are not used.
- Architecture and Data each point to the other in one sentence; other
  overlaps get one owner and a pointer in the others.
- No run reads `desmor-hub` or is conditioned by a baseline of it.

## Open

- The final checklist of the earlier plan: whether it stays and in what form.
- Models and settings per role.

## State

| Area | State |
| --- | --- |
| All 14 | Objective not yet written |

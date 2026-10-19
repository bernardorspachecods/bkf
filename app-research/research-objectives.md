---
bkf: document
description: Holds the proposed objective of each of the 14 research areas in the web foundations plan, each stating use, question, priorities, mode, out of scope and what counts as enough. Proposals only until Bernardo confirms each one; the areas themselves live in research-plan.md.
tags: [research, planning, objectives]
---

# Research objectives

Every objective below is a **proposal**. Bernardo confirms each one after
reading it, and no run starts before its objective is confirmed. The areas,
their coverage and the rules these objectives follow belong to the
[research plan](/app-research/research-plan.md); this file does not change them.

## Contents

- [Ground rules for all fourteen](#ground-rules-for-all-fourteen), with the owner of each shared topic.
- Objectives: [1 Architecture](#1-architecture), [2 Data](#2-data),
  [3 Identity and access](#3-identity-and-access),
  [4 Security and privacy](#4-security-and-privacy),
  [5 Frontend structure](#5-frontend-structure),
  [6 Frontend experience](#6-frontend-experience), [7 Testing](#7-testing),
  [8 Delivery](#8-delivery),
  [9 Observability and operations](#9-observability-and-operations),
  [10 Background work](#10-background-work),
  [11 Email and messaging](#11-email-and-messaging),
  [12 Business logic](#12-business-logic), [13 Applied AI](#13-applied-ai),
  [14 Metrics and reporting](#14-metrics-and-reporting).
- [Points for Bernardo](#points-for-bernardo)

## Ground rules for all fourteen

- **Use.** Each result is a guide that supports the decisions of Bernardo and
  of the agents building the app, as they build it. Bernardo can also use it
  later to improve `desmor-hub`. No run reads `desmor-hub` or depends on a
  baseline of it.
- **Priorities come from a commercial proposal, not from it as a requirement.**
  The proposal describes a business that receives group-stay requests through
  several channels and answers them with quotes. It only decides where depth
  goes inside an area. It never decides which areas exist. Its example values
  are fictitious, and its price, schedule, methodology and sales text are not
  used.
- **Priorities are written as general capabilities**, so the research answers
  how such apps are built, not how one product was sold.
- **Overlaps have one owner.** Each shared topic is researched by its owner and
  only pointed at in the others.

| Shared topic | Owner | Pointed at from |
| --- | --- | --- |
| Audit trail and record versions | 12 Business logic | 2, 4 |
| Approvals (the rule and its flow) | 12 Business logic | 3 |
| Who may approve, role checks | 3 Identity and access | 12 |
| Access without an account (links in emails) | 3 Identity and access | 4 |
| Personal data, retention, uploads, secrets, abuse of public forms | 4 Security and privacy | 2, 11, 13 |
| Personal data sent to AI providers | 13 Applied AI | 4 |
| Scheduled sends and reminders, how they run once and on time | 10 Background work | 11, 14 |
| Messages and templates | 11 Email and messaging | 10 |
| Application languages, formatting and translation method | 6 Frontend experience | 11 |
| Boards and charts as interface | 5 Frontend structure | 12, 14 |
| State rules and what a change triggers | 12 Business logic | 5 |
| Which indicators exist and how they are defined | 14 Metrics and reporting | 5 |
| Backups and restores | 9 Observability and operations | 2 |
| Running migrations in a release | 8 Delivery | 2 |
| Judging the quality of AI output | 13 Applied AI | 7 |
| Test data | 7 Testing | 2, 13 |
| Importing a legacy spreadsheet | 2 Data | 8 |

## 1. Architecture

- **Use.** The guide supports Bernardo and the agents building the app when they decide how it is divided into parts and how those parts communicate, now and when the structure has to change.
- **Question.** How are web apps of this kind divided into parts, how do those
  parts talk to each other, and what does each division make easy or hard
  later? Delivery: a map of the main options with the conditions under which
  each fits.
- **Priorities.** An app that takes requests in from outside (email, a public
  form, pasted text), runs slow or scheduled work, and sends messages out. How
  a small team can keep such an app understandable. When a single deployable
  unit stops being enough. Where the line sits between the app and the
  external systems it hands work to without direct integration.
- **Mode.** Broad.
- **Out of scope.** Choosing a framework or vendor for this product, how data
  is modeled (Data, which points back here in a sentence, as this area points to
  it), and the internals of each other area.
- **Enough.** The main structural options are laid out, each with where it fits and where it breaks, sourced, and the guide lets Bernardo and a building agent tell which structural decisions to settle first.

## 2. Data

- **Use.** The guide supports Bernardo and the agents building the app when they decide how information is modeled and stored, and when they judge a change to the model.
- **Question.** How is information modeled and stored when records have
  history, relate to each other and get merged? Delivery: a comparison of
  modeling approaches and what each costs later. It names its structural limits
  in one sentence each and points to Architecture, which points back here.
- **Priorities.** One customer holding several requests, and duplicates found
  and merged afterwards. Records that gain versions without losing the old
  ones. Fields that start empty or wrong and are completed later. Questions
  that cut across many records (counts, sums, by period, channel or group).
  Importing a legacy spreadsheet into a clean model. Test data and retention
  are pointed at, not researched here.
- **Mode.** Focused on the priorities.
- **Out of scope.** The audit trail and version rules (Business logic), backups
  and restores (Observability and operations), running migrations in a release
  (Delivery), what personal data may be kept and for how long (Security and
  privacy), and choosing a database product.
- **Enough.** For each priority, the usual modeling approaches are described with their trade-offs and a source, and the guide lets them choose an approach and justify it.

## 3. Identity and access

- **Use.** The guide supports Bernardo and the agents building the app when they decide how people sign in, what each role may do, and how outsiders reach the app.
- **Question.** How do web apps establish who a person is, keep them signed in,
  and decide what they may do? Delivery: a comparison of approaches with the
  situations that favour each.
- **Priorities.** A small internal team with different roles and permissions.
  Actions that need a second, higher role to approve. People outside the team
  acting without an account, for example accepting something from a link in an
  email. Sessions on shared or office devices. Adding and removing users
  without breaking the history of what they did.
- **Mode.** Focused on the priorities.
- **Out of scope.** Threats and hardening in general (Security and privacy,
  which receives a pointer on account-free access), the approval flow itself
  (Business logic), and picking a vendor for this product.
- **Enough.** For each priority the main approaches are described with their failure modes, sourced, and the guide lets them choose an access model and justify it.

## 4. Security and privacy

- **Use.** The guide supports Bernardo and the agents building the app when they decide how personal data, files, secrets and threats are handled. It is a guide to decide with, not legal advice.
- **What is at stake.** The app holds personal data of customers and of the
  people they bring, possibly including minors and data that can reveal health,
  such as dietary needs. Those people can live in several countries, which
  brings several data protection regimes. The app receives files, sends data to
  external providers, and holds credentials for mailboxes. Mistakes here carry
  legal and financial consequences and some cannot be undone. The claims that
  carry these decisions need several independent primary or authoritative
  sources. The delivery gives a bounded answer where evidence is inadequate.
  **The guide that results needs review by a specialist before anyone acts on
  it.** The run does not give legal advice.
- **Question.** Which privacy obligations and security threats apply to an app
  that handles this data, and which practices address them? Delivery: a map of
  obligations and threats, with practices ranked by consequence.
- **Priorities.** Personal data of people who are not users of the app, and what
  lawful handling asks for (purpose, retention, deletion, access requests).
  Possible special-category and minors' data. Files and pasted images arriving
  from outside. Secrets, including mailbox and sending-domain credentials.
  Abuse of a public form. Access without an account is pointed at.
- **Mode.** Focused on the priorities, at the highest depth the sources allow.
- **Out of scope.** The authentication mechanics (Identity and access), data
  sent to AI providers (Applied AI owns that flow and points here for the
  rules), record audit trail (Business logic), and a legal opinion.
- **Enough.** Each obligation and threat in the priorities is covered by
  several independent authoritative sources, with unresolved points listed as
  such, and Bernardo has a list of what the specialist must check.

## 5. Frontend structure

- **Use.** The guide supports Bernardo and the agents building the app when they decide how screens, state, forms, data fetching, boards and charts are structured.
- **Question.** How are the interfaces of data-heavy business apps structured:
  components, state, forms, data fetching, boards and charts? Delivery: a map of
  the common structures with when each fits.
- **Priorities.** Long forms where some values are filled by a machine and a
  person confirms them. A board whose cards change state by dragging and where a
  change has consequences. Dashboards with filters. Lists with many records. How
  the interface stays consistent with a server that changes data on its own.
- **Mode.** Broad.
- **Out of scope.** What a state change triggers (Business logic), which
  indicators exist (Metrics and reporting), performance and accessibility
  (Frontend experience), and choosing a UI library for this product.
- **Enough.** The common structures for each element are described with trade-offs and sources, and the guide shows which choices are reversible and which are not.

## 6. Frontend experience

- **Use.** The guide supports Bernardo and the agents building the app when they decide how fast, accessible, responsive and multilingual the interface must be, and how to get there.
- **Question.** What does a good experience require in performance,
  accessibility, responsive layout and languages, and how is it achieved?
  Delivery: a map of requirements and techniques.
- **Priorities.** An interface offered in several languages, with dates,
  numbers and currency formatted per locale and the translation method owned
  here. Fast entry of a record while someone is on the phone. Use on a phone
  and a desktop by the same person. Accessibility for staff working all day in
  the tool.
- **Mode.** Broad.
- **Out of scope.** The language of outgoing messages and templates (Email and
  messaging, which points here), the structure of components and state
  (Frontend structure), and visual brand design.
- **Enough.** Each requirement is described with its common techniques and limits, sourced, and the guide lets them set the experience criteria the app must meet.

## 7. Testing

- **Use.** The guide supports Bernardo and the agents building the app when they decide what to test, at which level, and with what data.
- **Question.** Which testing strategies and levels suit apps of this kind and
  how is test data handled? Delivery: a comparison of strategies with when each
  pays off.
- **Priorities.** Rules whose wrong output is costly (prices, discounts,
  validity dates). Flows that run across time (reminders, expiries). Messages
  sent to real people, tested without sending. Output of a machine that can vary
  from run to run. Realistic, safe test data.
- **Mode.** Broad.
- **Out of scope.** Evaluating the quality of AI output (Applied AI, which
  points to this area for test data), CI pipelines (Delivery), and the choice of
  a test tool for this product.
- **Enough.** The levels and strategies are described with the risks each covers and a source, and the guide states what to test at each level for the priorities above.

## 8. Delivery

- **Use.** The guide supports Bernardo and the agents building the app when they decide how changes are built, released and hosted, and what that costs.
- **Question.** How are web apps built, released and hosted: CI/CD,
  environments, running migrations during a release, and hosting cost?
  Delivery: a map of options with their effects on risk and cost.
- **Priorities.** A small team releasing often. Changes to the data structure
  that ship with the code. Preview and test environments that must not touch
  real customers or send real messages. What hosting a small, always-on app with
  background work and file storage tends to cost, and what makes cost grow.
- **Mode.** Broad.
- **Out of scope.** Schema design (Data, which points here for migrations in a
  release), monitoring and backups (Observability and operations), test levels
  (Testing).
- **Enough.** The release and environment options are laid out with their
  failure modes, and cost drivers are named with sourced ranges where sources
  exist, flagged as ranges, not quotes.

## 9. Observability and operations

- **Use.** The guide supports Bernardo and the agents building the app when they decide what to log, measure, alert on, back up and maintain.
- **Question.** What must a small production app log, measure, alert on, back
  up and maintain, and how is recovery proven? Delivery: a map of practices
  ordered by consequence.
- **Priorities.** Failures of work that runs unattended (a message not sent, a
  reminder missed) noticed before a customer notices. Backups that are restored
  in a test, not only taken. Keeping personal data out of logs. Updates and
  maintenance by a very small team.
- **Mode.** Broad.
- **Out of scope.** Business indicators (Metrics and reporting), how background
  jobs retry (Background work), and choosing a monitoring product.
- **Enough.** Each practice is described with what it protects against and a source, and the guide gives the minimum the app must include.

## 10. Background work

- **Use.** The guide supports Bernardo and the agents building the app when they decide how queued and scheduled work is run, retried and kept from repeating its effect.
- **Question.** How do web apps run queued and scheduled work with retries and
  idempotency? Delivery: a comparison of approaches with when each is enough.
- **Priorities.** Messages that must go out once, at the right time, after an
  event or after days without one (reminders, expiry warnings). A scheduled
  monthly job that builds and sends a report. Work that fails halfway and is
  retried without duplicating its effect. Cancelling pending work when the
  situation changes, for example when a customer answers.
- **Mode.** Focused on the priorities.
- **Out of scope.** What the messages say (Email and messaging), the metrics in
  the report (Metrics and reporting), and choosing a queue product.
- **Enough.** For each priority the main approaches and their failure modes are described, sourced, and the guide states the guarantees to design for.

## 11. Email and messaging

- **Use.** The guide supports Bernardo and the agents building the app when they decide how email and messages are received, sent, templated and approved.
- **Question.** How do web apps receive and send email and related messages,
  with templates, languages and attachments? Delivery: a map of approaches with
  their limits.
- **Priorities.** Reading a shared mailbox and turning incoming messages and
  attachments into records. A customer's reply landing back on the right record.
  Sending from the organization's own address and keeping messages out of spam.
  Editable templates filled from a record, in several languages. Messages that
  need human approval before sending. Receiving by pasted text or screenshots is
  pointed at, since that is Applied AI.
- **Mode.** Focused on the priorities.
- **Out of scope.** When scheduled messages run (Background work), the
  application's language method (Frontend experience), storing credentials
  (Security and privacy), consent rules for marketing messages beyond a pointer
  to Security and privacy, and direct connections to chat networks.
- **Enough.** Each priority has its main approaches with their limits and a source, and the guide names the choices that depend on the mailbox provider.

## 12. Business logic

- **Use.** The guide supports Bernardo and the agents building the app when they decide how rules, states, approvals, versions and the audit trail are represented so they can change without rewriting the app.
- **What is at stake.** Rules that set prices and discounts produce documents
  customers accept, which carries financial and contractual consequences. Claims
  about the effect of electronic acceptance or record keeping need several
  independent authoritative sources, and Bernardo is told where a specialist
  must decide.
- **Question.** How do apps represent pricing and rules, states and flows,
  approvals, audit trail and versions? Delivery: a comparison of approaches with
  what each makes easy or hard to change.
- **Priorities.** A price table with rules by season, group size, length of
  stay and discounts, editable by the business. A quote that is calculated,
  reviewed when it falls outside the rules, versioned on every change, valid
  until a date, and accepted by the customer. Statuses and what moves between
  them. Recording who changed what and when. Generating a document from a record
  and keeping the version that was sent. Handing the accepted record to
  systems that are outside the app.
- **Mode.** Focused on the priorities.
- **Out of scope.** Who is allowed to approve (Identity and access), the board as
  interface (Frontend structure), when reminders run (Background work), and
  billing and invoicing.
- **Enough.** Each priority has its main modeling approaches with sources, and the guide says which rules must live as data and which as code.

## 13. Applied AI

- **Use.** The guide supports Bernardo and the agents building the app when they decide where AI is used, what it must never decide, and how its output and data flows are controlled.
- **Question.** How is AI used to read inputs and fill records, what are its
  reliable limits, and what happens to the personal data sent to providers?
  Delivery: a map of uses, limits and safeguards.
- **Priorities.** Turning pasted conversations and screenshots, in several
  languages, into a pre-filled record that a person confirms. Detecting missing
  data and duplicates. Drafting replies for a person to approve. Keeping figures
  that matter (prices) out of the model's reach. What providers do with the
  data sent and how to reduce what is sent. Judging output quality and cost per
  use.
- **Mode.** Focused on the priorities.
- **Out of scope.** General data protection obligations (Security and privacy,
  which owns the rules and receives a pointer from here), tests of
  non-AI code (Testing, which owns test data), and choosing a model or vendor
  for this product.
- **Enough.** Each use has its demonstrated limits and safeguards with sources, the provider data terms are read at their origin, and the guide states what the AI may and may not do in the app.

## 14. Metrics and reporting

- **Use.** The guide supports Bernardo and the agents building the app when they decide which indicators exist, how they are computed, filtered, scheduled and exported.
- **Question.** How do apps define, compute, filter, schedule and export
  business indicators? Delivery: a map of approaches with when each fits.
- **Priorities.** Indicators on volume, source, conversion and value over
  time, compared with a previous period. Filters by period, source, market and
  owner. Time-to-response and lateness measured from recorded events. Indicators
  that stay correct when records are corrected or versioned. A report sent on a
  schedule and exportable to a spreadsheet.
- **Mode.** Focused on the priorities.
- **Out of scope.** How charts are drawn (Frontend structure), how the schedule
  runs (Background work), what is recorded and how it is versioned (Business
  logic), and choosing a BI product.
- **Enough.** Each priority has its main approaches, with what each costs in freshness, correctness and effort, sourced, and the guide states which indicators need event data captured from day one.
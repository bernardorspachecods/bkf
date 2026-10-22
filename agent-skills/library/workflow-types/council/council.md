---
bkf: document
description: Guides a council on an explicitly requested question or decision, for the coordinator who works with the user. Covers when to run one, how to write the brief, how the five advisors and five reviewers run apart, how you write the chairman's report and what the user receives.
tags: [planning]
---

# Council

## When to use

Run a council only when the user explicitly asks for one on a question or a
decision. Do not use it for ordinary questions, or to settle something you could
answer yourself. A council always runs in full: there is no light run. A smaller
question is not a council; answer it, or use research.

## How to read this

You are the coordinator, so also read the `coordinate-a-run` module before you start: it holds the rules every run shares.

These are principles with reasons, not a procedure. Adapt to the task, and keep
what the reasons protect.

- **Independence is the point.** Several advisors give advice without seeing each
  other, so the answer is not anchored on the first view. Anything that lets one
  advisor see another, or a reviewer see who wrote what, defeats the council.
- **You are the chairman.** You know the user's context, so you write the report.
  You do not advise and you do not review.

## 1. The brief

The brief is the only thing every advisor receives, so it must stand alone. It
holds:

- **The question or decision,** stated as something to be answered, not a topic.
- **The context** an outsider needs: what exists, what is fixed, what is open.
- **What a good answer lets the user do,** so the advisors know what the advice is for.

Keep it neutral. A brief that hints at the answer you prefer gives you five
echoes. Have the user approve it before anything runs: a mistake here
contaminates every advisor.

## 2. The roles

A script runs the middle of the council. It builds the briefs from fixed
templates, runs the advisors apart, anonymizes their responses, runs the
reviewers apart and stops when the packet of reviews is ready. You write only the
brief.

| Role | Does | Receives |
| --- | --- | --- |
| [Advisor](/council-advisor.md) (five, one perspective each) | Gives independent advice from its perspective | The brief and its perspective |
| [Reviewer](/council-reviewer.md) (five) | Reviews the anonymized responses | The packet: the question and the five responses under random labels |
| Chairman (you) | Writes the report | The brief, the identified responses, the five reviews and the key |
| [Completeness check](/council-completeness.md) | Checks the report left nothing out that matters | The report and its sources |

```
Brief ─► 5 advisors ─► anonymized packet ─► 5 reviewers ─► You write the report ─► Completeness check ─► User
 (you)    (apart)       (key kept away)      (apart)                                  └ back to you
```

Rules that hold whatever the models:

- **Each agent works in its own folder and writes only its own file.** No folder
  holds what that agent must not see: an advisor's holds only the brief, a
  reviewer's only the packet. The sandbox stops writes outside the folder but not
  reads, so the brief also tells each agent to open only its own folder. Do not
  hand over anything that agent must not see.
- **The script anonymizes.** It shuffles the responses, labels them and keeps the
  key apart from the reviewers. Anonymization is imperfect: a distinctive argument
  can still reveal its author.
- **If an advisor fails or returns nothing, the run stops.** A packet of four is
  not a council of five.
- **Models.** Five perspectives on one
  small model share its biases; if the question matters, say so to the user and
  let them choose.

## 3. The report

You write it from the five responses, with the key, and the five reviews. The
reviews tell you what survived scrutiny and what did not; the key tells you whom
to credit where it matters. Order it for the user, who reads it to decide:

1. **The answer.** What the council recommends, or where it is split, in a few lines.
2. **Where the advisors agree,** and where they disagree, each side in its
   strongest form. Say which perspectives held which view only where it helps.
3. **What the reviews added:** the strongest points, the points that did not
   survive, and what all the responses missed.
4. **Risks and what is still uncertain.**

Carry every material point the advice and the reviews hold: the completeness
check looks for what you left out. A point you drop on purpose goes in one line
saying why. Your own opinion enters only if the user asks, and is said to be yours.

## 4. Where the work lives

One council is one folder in `~/.council-runs/<name>/`, with one subfolder per
phase in order: `00-input` (the brief), `01-advisors`, `02-packet`, `03-review`
and `04-check`. The report sits at the top. When it is done, the user chooses: keep
the record, copied into `records/councils/` in the repository, or delete the run.

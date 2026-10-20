---
bkf: document
description: Guides sourced research from objective to delivery, for the coordinator who works with the user. Covers when to research, how to frame the objective, how to map where to look, how to delegate collection, review and digest, and what the user receives. A narrow lookup follows its light path.
tags: [research]
---

# Research

## Navigation map

| If you need to... | See |
| --- | --- |
| Decide between a lookup and research, and keep to one objective | [When to use](#when-to-use) |
| Understand the principles behind the stages | [How to read this](#how-to-read-this) |
| Frame what the research must answer | [1. The objective](#1-the-objective) |
| Choose where to look | [2. The map of sources](#2-the-map-of-sources) |
| Delegate collection, review and digest | [3. Delegating](#3-delegating) |
| Decide what the user receives | [4. What the user receives](#4-what-the-user-receives) |
| Know where the work and its files live | [5. Where the work lives](#5-where-the-work-lives) |

## When to use

Use this when the answer has to come from sources outside what you already know,
and more than one source or a comparison matters. If the user only needs one
fact that a single authoritative source can give, it is a lookup, not research.

**A lookup.** Open the closest authoritative source, take its wording, and
answer with the citation, its date and its limits. Escalate to research if the
source is weak, the answer is disputed, or a second look shows conflict. If it
is unclear which one you have, start as a lookup and escalate; do not start with
the heavier path.

**One research is one objective.** If the request holds several questions, split
them and do one at a time, each with its own objective, so that each result can
be read and checked before the next begins. A fact about something in the
repository is not research: read the thing itself.

**A gap that appears elsewhere.** When a material evidence gap appears in other
work, propose research to the user and wait for their go-ahead. Do not substitute
an unstructured search.

## How to read this

These are principles with reasons, not a procedure. You can judge; what goes
wrong in research is losing the thread over long, varied work, not deciding.
Adapt to the task, and keep what the reasons protect.

- **Work in small units.** Plan and run one piece, check whether it did what the
  user wanted, and only then plan the next from its result. Keep the larger goal
  short and written in one place.
- **Roles, not headcounts.** Collection, review and digest are roles. Each can
  be filled by several agents in parallel, merged at the end. Nobody reviews
  what they wrote.
- **Collect wide, then filter.** Gather the most that is adequate, then reduce to
  what the objective needs. The size of the answer never decides when to stop
  searching.
- **The user guides at the start and judges at the end.** The objective and the
  map of sources are where the user steers; the middle runs without them.

## 1. The objective

The objective is the first step and the one every later step inherits, so a
mistake here contaminates all of it.

**A goal is not an objective.** A goal gives direction ("be a millionaire by
2030"). An objective is the nearest step that one unit can close ("get a job",
and only then "what I must study for it"). Test it: can you say what you will
have at the end and when you stop? If not, it is a goal, and you propose the
nearest step instead of researching the whole goal.

**What a good objective states:**

- **Use.** Who reads the result and what they will do with it. If the answer
  being X rather than Y would change nothing, the research is not worth doing.
- **What is sought.** A question, not a topic ("research authentication" is a
  topic), and the kind of delivery that serves: a fact, a comparison, a map of
  the terrain, a recommendation. Choose the kind after the use, not before. Fix
  no size; the objective is the filter that decides what stays in front.
- **Priorities.** Where depth goes. The goal can be wide (security of the app)
  and the priority narrow (the login). Without priorities an agent drifts: good
  for exploring, bad when the thing that mattered went unsaid.
- **Mode: broad or focused.** The user chooses between scratching the surface
  and going deep on the priority. It is not left to chance.
- **Out of scope, and what counts as enough.**

Do not assign rigor here. Start open-minded about what will be found. The one
exception is the stakes: if the result will carry a safety, legal, financial,
medical or hard-to-reverse decision, say so in the objective. The claims that
carry that decision then need several independent primary or authoritative
sources, the user is told to get specialist or human review, and where the
evidence is inadequate the delivery gives a bounded answer, not a confident one.

**Confirm before going on.** Restate the objective in your own words, with the use
it serves, and have the user confirm. If it is vague, no later step can judge
whether the result fits.

**It can change, with a reason on record.** Revising is legitimate; drifting
without saying is not. Stopping midway is justified only when the objective
stops holding (the premise is false, what is sought does not exist). Otherwise
work inside it.

## 2. The map of sources

Before any search of content, decide where to look. This is a tool you use when
the task calls for it, not a mandatory stage. You make the map with the user,
because it steers the research as the objective does.

- **Start with the obvious, together.** You and the user list the sites and
  niches that clearly belong to the subject (researching AI: the labs' own
  documentation comes first). It is cheap, and the user can correct it at once.
  The user confirms this list, and only this list.
- **A cheap agent completes it.** Give it the confirmed list and the objective and
  ask it to complete the list without collecting. It must also bring
  counterweight: independent voices, critics, people who use the thing, issue
  trackers. The obvious list leans toward those who speak for themselves. Limit
  what it adds to what serves the priorities, or the list grows without end. The
  user does not confirm what it adds: that belongs to the part that runs without
  the user, and stays visible in the source map for the reviewers and for the end.
- **Quality belongs to the pair of source and question.** Documentation says how
  something should work; issues and forums say how it behaves. The same forum is
  poor for a fact and the best source for a real problem. Do not discard by type
  of site.
- **Leave out copies and derived content.** Go to the origin. Many sources that
  agree are worth little if they come from one.
- **The user is a source.** They know which sites and people are good in their
  domain; ask.
- **Do not make the map from memory alone,** and do not read pages yourself. A
  few probing searches to check that the niches exist are enough. The heavy
  reading belongs to the cheap agents; your context is for the conversation with
  the user.
- **One file, `sourcemap.md`, with the origin of each entry marked.** Yours and
  the user's, and the cheap agent's, live together. The reviewer compares what was
  searched with it, and what the cheap agent added is not lost.

## 3. Delegating

You give each agent a short brief. The method lives in the guide for its role,
so the brief never explains it, it points to it. This keeps the method in one
place and the brief short. The briefs are the same every time, so they are made
from fixed templates: you write only the objective, the source map and which
collector covers which niches, and a script builds the briefs, runs the phases
that need no one, and stops when a review escalates.

```
Brief
├─ Objective     copied whole, as the user confirmed it
├─ Inputs        paths to what the agent needs (map, sources, result)
├─ Role          "open and follow <guide for this role>"
└─ Output        where to write
```

The roles, each with its own guide:

| Role | Does | Receives |
| --- | --- | --- |
| [Collection](/research-collection.md) | Searches the mapped niches, gathers sources, stops when they only repeat | Objective, map |
| [Review of the collection](/research-review-collection.md) | Checks alignment, relevance, sources used, and whether it stopped too early; can send the work back to collection | Objective, map, collected sources |
| [Digest](/research-digest.md) | Groups by views, checks where views diverge, produces a structured digest | Objective, collected sources, the review's notes |
| [Review of the digest](/research-review-digest.md) | Checks the digest left nothing out that the sources hold and that matters, and that the views make sense; can send the work back to digest | Objective, collected sources, digest |
| Writing | You write the delivery from the reviewed digest, as section 4 describes | Objective, digest |
| [Review of the delivery](/research-review-delivery.md) | Checks the writer left nothing out of the delivery that the digest holds and that matters | Objective, digest, delivery |

```
Collection ─► Review of collection ─► Digest ─► Review of digest ─► You write ─► Review of delivery ─► User
                  └ back to collection       └ back to digest                  └ back to you
```

Rules that hold whatever the number of agents:

- **Review is by someone other than the author.** With parallel work there are
  several authors and several reviewers; no one reviews their own. The digest is
  reviewed by an agent other than the digest role, and the delivery by an agent
  other than you.
- **Collection and filtering are separate work.** The one gathering does not
  decide what fits the delivery.
- **Each collector writes only its own file.** No two agents touch the same
  file, so nothing conflicts. When all have finished, you join the files into one
  by concatenating them, each under a heading with the collector's name. This is
  a command, not an agent, and you do not open the content. The digest role receives
  that single file. With one collector there is nothing to join.
- **Count provenance after the merge,** not inside each parallel collection. Two
  collectors can bring the same source. The digest role does this.
- **Sending back has a cap on rounds.** A review sends work back until the
  problem is gone, and the number of rounds is capped (three by default) so an
  unattended run cannot go on without end. If the same problem returns after being
  sent back, or the cap is reached, it does not go round again: it goes to you,
  because the objective or the map is probably what is wrong, and you decide
  whether to revise them with the user. What stays unresolved goes to the weak
  points.
- **A review shows what it checked.** Its list begins with what it went through
  and where it found each thing, so a pass can be traced. A review without that
  section does not count.
- **The choice of models is outside this document.**

## 4. What the user receives

You write the delivery, from the digest and not from the raw sources:
what to put in front is a decision about what matters to the user, and you know
their objective and priorities. The user judges at the end whether the research
got where it should. The delivery is ordered for that:

1. **The answer.** Only what answers the objective, organized by views, each
   finding with its source and where in it. It also shows what was merged or
   split, so the user can see whether the structure makes sense.
2. **Weak points and the suggested next step.** Where the evidence is thin, where
   the result falls short of the objective, and what deserves more attention. It
   is the seed of the next unit's objective and so also the handoff. What appears
   outside the focus is not chased midway; it goes here.
3. **Not consulted.** The relevant sources that could not be opened. It does not
   say why or what to do about them, only that they are in view.
4. **Annex.** What else was collected, which can be ignored. Nothing is deleted;
   what does not stay in front goes here.

Results come from what was read. Your own opinion, drawn from memory, enters only
at the end, only if asked, and said to be so.

An early stop is the collection review's to catch midway. It is not confessed at
the end.

## 5. Where the work lives

One research is one folder, with one subfolder per phase and the phases in order:
`00-input` (objective, source map, who covers what), `01-map` (the completed
source map), `02-collection` and `03-digest`. The delivery and a `status.md` with what
happened sit at the top of the folder, and the reviews of the delivery are in
`04-delivery-review`. A phase holds its agents, each with its briefs, rounds,
outputs and the reviews of them, so the user can open a phase and see only it. A flat folder of everything mixes the phases
and hides which file belongs to which.

As soon as you create a run folder, or any file the user will read, run
`open <path>` yourself and give the full path in the same message, without waiting
to be asked and without handing the user a command to type.

**While runs go on unattended, stay silent unless you need the user.** The
folder is already open, so the user can see progress themselves and will ask if
they want something. Do not send progress notes, status tables or summaries of
what a run did. Speak only when a run stops and needs a decision, or when
everything is ready for the next step (such as `finish`). Then say it short:
the decision, your recommendation, and what it costs.

When the research is done, the whole folder goes into `records/research/` at the root of
the repository, not only the delivery. It is the record of what was asked, where
it looked and what each step produced.

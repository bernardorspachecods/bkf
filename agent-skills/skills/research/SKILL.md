---
name: research
description: Use when the user asks for sourced or verified findings, a comparison across sources, an audit of a conclusion, or literature work that needs multiple sources or an evidence trail; or a stopped research run to resume.
---

# Research

<!-- inject: ../../modules/coordinate-a-run.md -->
<!-- BKF:GENERATED-INJECTED -->
## Coordinate a run

The skills of the plan, code review, council and research workflows include this module. Their coordinator guides own the phases, files and roles; this module holds what every run shares.

- Stay out of the roles. The coordinator keeps the conversation with the user and prepares the briefs and inputs; it does not act as researcher, implementer, advisor or reviewer, even for a small run. A gap in an agent's work goes back to a fresh agent through the script, not to the coordinator to fill.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start and judges at the end; between checkpoints do not message them: no progress updates, status summaries or questions about small decisions. Decide those within the intent agreed with the user (`align-intent`) and continue, and stop and ask only as that intent says. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked.
- An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- If the same problem returns after being sent back, or the script's cap on rounds is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.
<!-- BKF:GENERATED-INJECTED-END -->

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
- **Collect wide, then filter.** Gather the most that is adequate, then reduce to
  what the objective needs. The size of the answer never decides when to stop
  searching.
- **The objective and the map of sources are where the user steers.**

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
collector covers which niches, and the engine builds the briefs, runs the phases
that need no coordinator, and stops when a review escalates.

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
| [Collection](roles/research-collection.md) | Searches the mapped niches, gathers sources, stops when they only repeat | Objective, map |
| [Review of the collection](roles/research-review-collection.md) | Checks alignment, relevance, sources used, and whether it stopped too early; can send the work back to collection | Objective, map, collected sources |
| [Digest](roles/research-digest.md) | Groups by views, checks where views diverge, produces a structured digest | Objective, collected sources, the review's notes |
| [Review of the digest](roles/research-review-digest.md) | Checks the digest left nothing out that the sources hold and that matters, and that the views make sense; can send the work back to digest | Objective, collected sources, digest |
| Writing | You write the delivery from the reviewed digest, as section 4 describes | Objective, digest |
| [Review of the delivery](roles/research-review-delivery.md) | Checks the writer left nothing out of the delivery that the digest holds and that matters | Objective, digest, delivery |

```
Collection ─► Review of collection ─► Digest ─► Review of digest ─► You write ─► Review of delivery ─► User
                  └ back to collection       └ back to digest                  └ back to you
```

Rules that hold whatever the number of agents:

- **Collection and filtering are separate work.** The one gathering does not
  decide what fits the delivery.
- **Each collector writes only its own file.** No two agents touch the same
  file, so nothing conflicts. When all have finished, the engine joins the files
  into one by concatenating them, each under a heading with the collector's name.
  This deterministic step does not open the content. The digest role receives that
  single file. With one collector there is nothing to join.
- **Count provenance after the merge,** not inside each parallel collection. Two
  collectors can bring the same source. The digest role does this.

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

When the research is done, the whole folder goes into `records/research/` at the root of
the repository, not only the delivery. It is the record of what was asked, where
it looked and what each step produced.

For the written answer, also use `repo-maintenance`.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

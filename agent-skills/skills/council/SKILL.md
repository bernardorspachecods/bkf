---
name: council
description: Use only when the user explicitly asks for a council on a question or decision, or a stopped council run to resume.
---

# Council

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

## When to use

Run a council only when the user explicitly asks for one on a question or a
decision. Do not use it for ordinary questions, or to settle something you could
answer yourself. A council always runs in full: there is no light run. A smaller
question is not a council; answer it, or use research.

## How to read this

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
| [Advisor](roles/council-advisor.md) (five, one perspective each) | Gives independent advice from its perspective | The brief and its perspective |
| [Reviewer](roles/council-reviewer.md) (five) | Reviews the anonymized responses | The packet: the question and the five responses under random labels |
| Chairman (you) | Writes the report | The brief, the identified responses, the five reviews and the key |
| [Completeness check](roles/council-completeness.md) | Checks the report left nothing out that matters | The report and its sources |

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

## Run commands

<!-- inject: ../../modules/run-commands.md -->
<!-- BKF:GENERATED-INJECTED -->
## Run commands

The scripts of the plan, research, council and code-review skills run on one engine, `agent-skills/harness`. Each takes the same commands: `<script> start ...`, `resume`, `status <name>`, `board <name>` and `finish <name>`. Start each `start` and `resume` with Bash `run_in_background: true` and stay quiet until it ends; the `guard` hook of `bkf hooks` refuses a launch in the foreground or one backgrounded by hand, including from an agent inside a run.

- **Backend.** Agents are Codex by default. `HARNESS_BACKEND=claude` runs a whole run on `claude -p`: give `-m` a Claude model such as `sonnet` and `-e` an effort from `low` to `max`. Write access is then confined to the agent's working directory, a reviewer can only read, and the quota signal is Claude's `rate_limit_event`. Set the variable on every `resume` too, or the run goes back to Codex. A run refuses to start when the backend's command is not installed.
- **State** is in `~/.<workflow>-runs/<name>/` (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`); `<WORKFLOW>_RUNS_DIR` or `HARNESS_RUNS_DIR` sets another root, and `<WORKFLOW>_GUIDES` replaces the folder of role guides (by default the `roles/` folder of the skill). `start` creates the folder and fails if it exists: do not create it by hand. It is never under `/tmp`, which the sandbox leaves writable.
- **Progress.** `status.log` is the event history; `status` prints it and `board` prints a board of the steps and their agents, which is also saved as `board.txt`. Progress lines go to stderr.
- **A run that stops** (an agent failed, a review escalated, the account ran out of quota) writes `STOPPED` in `status.log` with the reason. Read the rounds in the run folder, fix the cause (usually the brief or the inputs, under `00-input/`), then `resume <name>`: finished steps stay done and the unfinished one runs again. A run that was killed is detected on `resume` and continues the same way.
- **Usage limit.** The run stops with the reason `usage limit reached` and `status.log` gets `QUOTA: <the text after "try again at">`, as the agent wrote it, not parsed. `resume` after that time.
- **Lock.** A live script holds `<run>/.lock`; a second `resume`, a `finish` or a recovery command refuses while it does. A lock whose process is gone is replaced.
- **When it prints `READY`** the result is in the run folder. `finish <name>` copies the record to `records/<plans|reviews|councils|research>/<name>/` in the repository, checks the copy and removes the run folder; `finish --discard <name>` deletes the run.
- **Limits** (environment variables): a review is capped at `<WORKFLOW>_MAX_ROUNDS` rounds (default 3), and must give at least `<WORKFLOW>_MIN_CHECKED` lines (default 3) under `## What I checked`, or it is repeated and then fails. Counts start again at every `resume`.
- **Sandbox.** Runs use the `workspace-write` sandbox. It confines writes to the agent's folder, but an agent can still read files outside the checkout, such as the login sessions of CLI tools in the home folder, and reach HTTPS, so it can use any session left open. The repository's own rules say what to keep logged out.
<!-- BKF:GENERATED-INJECTED-END -->

The script is [council-run.sh](scripts/council-run.sh). `council-run.sh start [-m model] [-e effort] <name> <brief.md>` runs five advisors independently, anonymizes their responses into a packet (the key is in `02-packet/key.md`), runs five independent reviewers and prints `READY`. When you have written the report, `council-run.sh check [-m model] [-e effort] <name> <report.md>` runs a completeness check (exit 0 `pass`, 1 `back`, 2 `escalate`). Its workflow definition is [council.py](scripts/council.py); the briefs it sends are templates, edit them without touching the code: [advisor](briefs/advisor.md), [reviewer](briefs/reviewer.md) and, for the completeness check, [the brief](briefs/completeness.md) with its [previous-round note](briefs/completeness-previous.md), [instructions](briefs/completeness-instructions.md) and [retry note](briefs/completeness-retry.md); its tests are [test_council.py](tests/test_council.py) and [test-council-run-board.sh](tests/test-council-run-board.sh).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

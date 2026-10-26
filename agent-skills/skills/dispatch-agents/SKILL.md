---
name: dispatch-agents
description: Run multi-phase workflows (plan, research, council, code review) as scripts that chain Codex or Claude agents, review them and record the run. Use when a workflow guide sends you to its script; for a single short task, use delegate-work.
---

## Use

- Briefs are written and handoffs checked by the rules of the `delegate-work` skill.
- Each workflow has a skill (`plan`, `research`, `council`, `code-review`) that says when and how to use it; this skill says how its script behaves.
- Agents are Codex by default. `HARNESS_BACKEND=claude` runs a whole run on `claude -p`: give `-m` a Claude model such as `sonnet` and `-e` an effort from `low` to `max`. Write access is then confined to the agent's working directory, a reviewer can only read, and the quota signal is Claude's `rate_limit_event`. Set the variable on every `resume` too, or the run goes back to Codex.
- The code is a Python engine and the four workflows are definitions on it; [harness/README.md](harness/README.md) lists its files and commands.

## Every run

The four scripts take the same commands: `<script> start ...`, `resume`, `status <name>`, `board <name>` and `finish <name>`. Start each `start` and `resume` with Bash `run_in_background: true` and stay quiet until it ends.

- **State** is in `~/.<workflow>-runs/<name>/` (`~/.plan-runs`, `~/.research-runs`, `~/.council-runs`, `~/.review-runs`); `<WORKFLOW>_RUNS_DIR` or `HARNESS_RUNS_DIR` sets another root, and `<WORKFLOW>_GUIDES` the folder of role guides. `start` creates the folder and fails if it exists: do not create it by hand. It is never under `/tmp`, which the sandbox leaves writable.
- **Progress.** `status.log` is the event history; `status` prints it and `board` prints a board of the steps and their agents, which is also saved as `board.txt`. Progress lines go to stderr.
- **A run that stops** (an agent failed, a review escalated, the account ran out of quota) writes `STOPPED` in `status.log` with the reason. Read the rounds in the run folder, fix the cause (usually the brief or the inputs, under `00-input/`), then `resume <name>`: finished steps stay done and the unfinished one runs again. A run that was killed is detected on `resume` and continues the same way.
- **Usage limit.** The run stops with the reason `usage limit reached` and `status.log` gets `QUOTA: <the text after "try again at">`, as the agent wrote it, not parsed. `resume` after that time.
- **Lock.** A live script holds `<run>/.lock`; a second `resume`, a `finish` or a recovery command refuses while it does. A lock whose process is gone is replaced.
- **When it prints `READY`** the result is in the run folder (`report.md` for plan and review, the advice, key and reviews for a council, the digest for research). `finish <name>` copies the record to `records/<plans|reviews|councils|research>/<name>/` in the repository, checks the copy and removes the run folder; `finish --discard <name>` deletes the run.
- **Limits** (environment variables): a review is capped at `<WORKFLOW>_MAX_ROUNDS` rounds (default 3), and must give at least `<WORKFLOW>_MIN_CHECKED` lines (default 3) under `## What I checked`, or it is repeated and then fails. Counts start again at every `resume`.
- Runs use the `workspace-write` sandbox. It confines writes to the agent's folder, but an agent can still read files outside the checkout, such as the login sessions of CLI tools in the home folder, and reach HTTPS, so it can use any session left open. The repository's own rules say what to keep logged out.

## Plan runs

For a whole [plan](../plan/SKILL.md), use [scripts/plan-run.sh](scripts/plan-run.sh), inside the repository the plan changes. `plan-run.sh start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>`: `-e` sets the implementers' reasoning effort and `-r` the reviewers' (and the final review's); without `-r` both use `-e`. `resume` takes the same options and keeps what the run already stored.

- You write `goal.md`, one brief per unit, and `plan.txt`: one step per line, holding the unit briefs' paths (relative to `plan.txt`). A line with one brief runs a unit in the checkout; several briefs on a line run as a parallel group in separate worktrees, followed by integration and review of the combined result. Before creating a group the runner checks the disk and refuses the step if the worktrees will not fit (the first worktree is measured and the others projected from it with a quarter of margin; the estimate does not cover what units create while they run).
- Keep a plan that is ready but not to be launched yet as `goal.md`, `plan.txt` and the briefs in a folder outside `~/.plan-runs` (for example `~/.plan-runs-pending/<name>/`) and run `start` from it. The script prefixes each unit name with its step number, so name the brief files without one.
- Step numbers are the lines of `plan.txt`; the markers `.done-S<n>` and `.paused-S<n>` use them. A unit may be added in `00-input/order` and `00-input/units/` only after every step already finished or in progress, so that no marker changes meaning.
- **Diff base.** A unit's diff is taken against the checkout as the previous step left it (`state-after-S<n>` in the run folder): a snapshot of the working files, untracked ones included and ignored ones left out. A commit, a dependency install or another unit's changes made while a unit is stopped never land in its diff. A group's units are made in worktrees from the checkout as it was when the group started, and `resume` does not recreate them, so a change to a shared file reaches a unit still to run only if it was in the checkout before the group started; otherwise put it in that unit's brief. The integration takes its base when it starts and keeps it. Do not edit the checkout during a step; `rebase-integration` is the emergency exit.
- **Gate.** A unit brief may hold a fenced block tagged `gate`, one command per line. After each implementation round the script runs the commands itself, in the checkout and outside any agent, and calls the reviewer only when all pass. A failing command sends the work back to the implementer with its output tail and no review, so a reviewer can never pass a red gate. `PLAN_GATE_TIMEOUT` (default 900 seconds) limits each command (a timeout stops its process group, exit code 124); `PLAN_MAX_GATE_ROUNDS` (default 5) stops a unit whose gate keeps failing. `start` notes the units with no gate, and `plan-run.sh gates <plan.txt|name>` prints the commands of every unit (exit 1 if one has none): read them before `start` and whenever a unit changes.
- **Repeated failures.** A failed gate command gets one immediate repeat; if it passes then, the round is treated as flaky. The run stops early when the same gate fails the same way in consecutive rounds or the reviewer sends the unit back twice for the same files.
- **Brief problems.** An implementer may end with `BLOCKED: ...` when the brief prevents progress, and a reviewer may return `VERDICT: brief` when the brief is contradictory or impossible; either stops the unit and signals the coordinator that the brief may be wrong.
- **Brief lint.** `plan-run.sh gates <plan.txt|name>` prints brief lint after the gate commands: errors make the command exit 1, while warnings do not.
- **Rehearsal.** `plan-run.sh rehearse <plan.txt>` runs the plan's gate commands informationally before `start`; failures are reported but do not fail the rehearsal.
- **The bridge.** While an implementer works, `.plan-porteiro/ponte <command...>` lets it request an allowed command outside the Codex sandbox and returns the output and exit code. The committed `.plan-run.json` at the unit's base lists allowed `pnpm` script-name patterns under `bridge.pnpmScripts` (for example `{ "bridge": { "pnpmScripts": ["^db:test(:[a-z0-9-]+)*$"] } }`; the script definition must match the base version); the bridge also accepts the unit's gate commands exactly as written. Requests run without a shell, so pass arguments rather than shell syntax. Requests and refusals are logged in `<run>/porteiro.log`; `PLAN_PORTEIRO_TIMEOUT` (default 900 seconds) limits each. Reviewers are read-only and do not use it.
- Each unit is implemented, then reviewed by another agent (verdict `pass`, `back` or `escalate`, capped at `PLAN_MAX_ROUNDS` reviews). A brief can be corrected in `00-input/units/` before `resume`: a unit copies its brief when it starts and a passed unit does not start again, so the correction reaches the units still to run and always the integration of a group and the final review, which read the current briefs; the copy in `<unit>/brief.md` stays as what the implementer received. Where the two differ, the integration and the final review show both and judge against the current one, and the integration notes in `status.log` that a unit passed against another gate.
- `-p each` or `-p 2,4` pauses after those steps (exit 3, `PAUSED` in `status.log`) for the user to read or to merge outside work; some environments show exit 3 as a failure, but it is a pause. `resume -p none` clears it.
- `plan-run.sh` runs Codex in the `fast` service tier. `PLAN_CODEX_TIER=` (empty) keeps the account default; `PLAN_CODEX_TIER=<tier>` picks another.
- The run records for each implementation round the minutes, the agent's steps, the files in the diff and the input tokens (`<run>/metrics.tsv`, and a table in `status.md` after `finish`), to calibrate how big a unit should be. First measurement (17 units of one plan, one repository, one model, 2026-10-20, so a starting point and not a law): rounds of 14 to 60 agent steps took 1 to 5 minutes and rounds of 100 or more steps took 12 to 16 minutes; the slowest carried about 156 thousand input tokens per step against 30 to 60 thousand usual; a unit that repeated a known pattern across nine files took 32 steps. Correct these numbers after a plan.

**Who reads what.**

| Agent | Brief | `goal.md` |
|---|---|---|
| Implementer and reviewer of a unit | the unit's own copy, made when the unit starts | no |
| Integrator and reviewer of a group's integration | the current brief in `00-input/units/` of every unit | yes, read from `00-input/goal.md` when the integration starts; a `gate` block in it is not run |
| Final review | the current briefs | yes |

A rule the unit reviewers must apply goes in the briefs of the units still to run: `goal.md` never reaches them. `goal.md` serves the integration and the final review to judge how the units fit and what is out of scope; it adds no criteria. It may also note how the run was carried out, for example "the owner committed in the checkout during step 2: ignore those files".

**Reading and changing a stopped run.**

- `plan-run.sh rebase-integration <name> <step> [--paths <path>...]` moves the base of a group's integration when the checkout was edited after the integration started and those edits sit in its diff. Without `--paths` the base becomes the checkout minus the diffs of the units already applied; it refuses once the integrator ran (its own edits would become base and hide from the reviewer) and when the checkout changed a file of a unit's diff. With `--paths`, the base stays and the given files or folders (relative to the repository) take the checkout's current version as their base; it refuses paths that hold a file of a unit's diff, and paths where nothing differs, prints the files that leave the diff and writes the list to `status.log`. Name only what the owner touched: an edit of the integrator in those paths would hide from the reviewer too. Both keep the old base as `.base.before-rebase-<time>` in the integration folder. Then `resume`.
- `plan-run.sh accept-integration <name> <step> --why <text>` closes a group's integration by hand, when the owner judged the combined result. It applies and reviews nothing: it needs every unit of the step `passed` with its diff applied, marks the integration done, removes the worktrees and writes in `status.log` who closed it, at which `HEAD`, and why. Then `resume`.

## Research runs

For a whole [research](../research/SKILL.md), use [scripts/research-run.sh](scripts/research-run.sh). Write `objective.md`, `sourcemap.md` (one numbered niche per line) and `collectors.txt` (`name: 1,2,5` per line, the niches each collector covers), then `research-run.sh start [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>`. A cheap agent completes the source map, one agent per collector collects, the collections are joined and digested, and the collection and the digest are reviewed. When it prints `READY`, write the delivery and run `research-run.sh deliver [-m model] [-e effort] <name> <delivery.md>` to review it (exit 0 `pass`, 1 `back`, 2 `escalate`); correct a returned delivery and run `deliver` again. `finish --delivery-only <name>` keeps only `delivery.md`; `finish --keep-attempts <name>` also keeps failed or redone attempts. Collectors and the map agent need web access: on Claude the harness gives them `WebFetch` and `WebSearch` (no other agent gets them).

## Council runs

For a [council](../council/SKILL.md), use [scripts/council-run.sh](scripts/council-run.sh). `council-run.sh start [-m model] [-e effort] <name> <brief.md>` runs five advisors independently, anonymizes their responses into a packet (the key is in `02-packet/key.md`), runs five independent reviewers and prints `READY`. When you have written the report, `council-run.sh check [-m model] [-e effort] <name> <report.md>` runs a completeness check (exit 0 `pass`, 1 `back`, 2 `escalate`).

## Review runs

For a [code review](../code-review/SKILL.md), use [scripts/review-run.sh](scripts/review-run.sh). `review-run.sh start [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... [-g command]... <name> <target>`, where the target is `working-tree` or a revision range such as `main...feature`. Each `-g` command runs in the repository before the reviewers start, with its command, output and exit code saved in `00-input/gate.md` and shown in the report; a red check stays visible and no checks is reported as a gap. `REVIEW_GATE_TIMEOUT` (default 900 seconds) limits each. `-2` adds a second reviewer per axis.

## Runtime metadata

## Shared code

The new convergence files are [the convergence heuristics](harness/harness/engine/converge.py) and [their tests](harness/tests/test_engine_converge.py). The plan brief lint files are [the lint module](workflows/plan_lint.py) and [its tests](harness/tests/test_workflow_plan_lint.py). The plan rehearsal files are [the rehearsal module](workflows/plan_rehearse.py) and [its tests](harness/tests/test_workflow_plan_rehearse.py).

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

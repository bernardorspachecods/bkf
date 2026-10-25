---
name: dispatch-codex
description: Run multi-phase workflows (plan, research, council, code review) as Codex CLI scripts that chain agents, review them and record the run. Use when a workflow guide sends you to its script; for a single short task, use delegate-work.
---

## Use

- Briefs are written and handoffs checked by the rules of the `delegate-work` skill.
- For a whole plan, use [Plan runs](#plan-runs).

## Gate harness

The stdlib gate runner lives in [harness](harness/pyproject.toml):
[package](harness/harness/__init__.py), [module entry point](harness/harness/__main__.py),
[CLI](harness/harness/cli.py), [gate runner](harness/harness/gate.py),
[agent runner](harness/harness/agent.py), [rule injection](harness/harness/inject.py),
[verdict handling](harness/harness/verdict.py), and the [tests](harness/tests/test_gate.py),
[agent tests](harness/tests/test_agent.py), [injection tests](harness/tests/test_inject.py),
and [verdict tests](harness/tests/test_verdict.py).

## Research runs

For a whole [research](../../library/workflow-types/research/research.md), use [scripts/research-run.sh](scripts/research-run.sh), which runs the research workflow on the engine.

- Write `objective.md`, `sourcemap.md` (one numbered niche per line) and `collectors.txt` (`name: 1,2,5` per line, the niches each collector covers), then run `research-run.sh start [-m model] [-e effort] <name> <objective.md> <sourcemap.md> <collectors.txt>` with `run_in_background: true`. The engine completes the source map with a cheap agent, collects with one agent per collector, joins the collections, digests them and reviews the collection and digest. State defaults to `~/.research-runs/<name>/`; `RESEARCH_RUNS_DIR` or `HARNESS_RUNS_DIR` can set another root.
- The engine records progress in `status.log` and shows a step board. `research-run.sh status <name>` prints the log, and `research-run.sh board <name>` prints the board. If a step fails or is escalated, fix the cause and run `research-run.sh resume <name>`; completed steps stay done and the unfinished step runs again. If a run is killed, resume detects the interrupted attempt and continues from the unfinished step.
- [test-research-run-board.sh](scripts/test-research-run-board.sh) checks the board output with a fake `codex`.
- A review is capped at `RESEARCH_MAX_ROUNDS` rounds (default 3) and must give at least `RESEARCH_MIN_CHECKED` lines (default 3) under `## What I checked`, or it is repeated and then fails. `RESEARCH_GUIDES` names the folder with the role guides.
- When the engine prints `READY`, write the delivery, then run `research-run.sh deliver [-m model] [-e effort] <name> <delivery.md>` to review it (exit 0 `pass`, 1 `back`, 2 `escalate`). Correct a returned delivery and run `deliver` again for the next round.
- `research-run.sh finish <name>` writes a run summary, copies the record into `records/research/<name>/`, verifies the copy and removes the run folder. `finish --delivery-only <name>` keeps only `delivery.md`; `finish --keep-attempts <name>` also keeps failed or redone attempts.

## Plan runs

For a whole [plan](../../library/workflow-types/plan/plan.md), use [scripts/plan-run.sh](scripts/plan-run.sh). Run it inside the repository the plan changes.

- You write `goal.md`, one brief per unit, and `plan.txt`: one step per line, holding the unit briefs' paths (relative to `plan.txt`). A line with one brief runs a unit in the checkout; several briefs on a line run as a parallel group in separate worktrees, followed by integration and review of the combined result. Before creating a parallel group, the runner checks available disk space; if the projected worktrees will not fit, it refuses the step. Run `plan-run.sh start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>` with `run_in_background: true`. `-e` sets the implementers' reasoning effort and `-r` the reviewers' (and the final review's); without `-r` both use `-e`. `resume` takes the same options and keeps what the run already stored.
- `start` creates `~/.plan-runs/<name>/` and begins the run at once; it fails if that folder exists. Do not create the folder by hand. Keep a plan that is ready but not to be launched yet as `goal.md`, `plan.txt` and the briefs in a folder outside `~/.plan-runs` (for example `~/.plan-runs-pending/<name>/`), and run `start` from it. The script prefixes each unit name with its step number, so name the brief files without one.
- Step numbers are the lines of `plan.txt`, and the finished and paused markers (`.done-S<n>`, `.paused-S<n>`) use them. A unit may be added in `00-input/order` and `00-input/units/` only after every step already finished or in progress, so that no marker changes meaning.
- A unit's diff is taken against the checkout as the previous step left it (`state-after-S<n>` in the run folder), as a snapshot of the working files, untracked ones included and ignored ones left out. So a commit, a dependency install or another unit's changes made while a unit is stopped never land in its diff, and edits to files git did not track yet are visible to the reviewer. A parallel group's units are made in worktrees from the checkout as it was when the group started, and the group's integration takes its base when it starts and keeps it, so a commit or edit made in the checkout after that shows up in the integration's diff, and its reviewer may call those files out of scope. Do not edit the checkout during a step; [`rebase-integration`](#reading-and-changing-a-stopped-run) is the emergency exit.
- A unit brief may hold a **gate**: a fenced block tagged `gate`, one command per line. After each implementation round the script runs these commands itself, in the checkout and outside any agent, and calls the reviewer only when all pass. A failing command sends the work back to the implementer with its output tail and no review, so a reviewer can never pass a red gate; a unit passes when the gate is green and the reviewer passes. `PLAN_GATE_TIMEOUT` (default 900 seconds) limits each command; a timeout stops its process group and records exit code 124. `PLAN_MAX_GATE_ROUNDS` (default 5) stops a unit whose gate keeps failing. A brief with no gate is reviewed as before, and `start` notes which units have none. `plan-run.sh gates <plan.txt|name>` prints the commands of every unit (exit 1 if one has none), so the coordinator reads what code will run before `start` and whenever a unit changes.
- **The bridge.** While an implementer works, `.plan-porteiro/ponte <command...>` lets it request an allowed command outside the Codex sandbox and returns the output and exit code. The committed `.plan-run.json` at the unit's base lists allowed `pnpm` script-name patterns under `bridge.pnpmScripts`; the bridge also accepts the unit's gate commands exactly as written. For example: `{ "bridge": { "pnpmScripts": ["^db:test(:[a-z0-9-]+)*$"] } }`. The script definition must match the base version. Requests run without a shell, so pass arguments rather than shell syntax. Refused and accepted requests are logged in `<run>/porteiro.log`. Reviewers are read-only and receive gate results; they do not use the bridge. `PLAN_PORTEIRO_TIMEOUT` (default 900 seconds) limits each request.
- `plan-run.sh` runs Codex in the `fast` service tier (quicker output, more plan quota per token). `PLAN_CODEX_TIER=` (empty) keeps the account default; `PLAN_CODEX_TIER=<tier>` picks another.
- The run also records, for each implementation round, the minutes, the agent's steps, the files in the diff and the input tokens (`<run>/metrics.tsv`, and a table in `status.md` after `finish`), to calibrate how big a unit should be. First measurement (17 units of one plan, one repository, one model, 2026-10-20, so a starting point and not a law): rounds of 14 to 60 agent steps took 1 to 5 minutes and rounds of 100 or more steps took 12 to 16 minutes; the slowest carried about 156 thousand input tokens per step against 30 to 60 thousand usual; a unit that repeated a known pattern across nine files took 32 steps. Correct these numbers after a plan.
- The complete board is saved in `<run>/board.txt`. Progress lines are followed by the compact board; `plan-run.sh board <name>` prints that compact view on demand. It folds completed early steps into a summary and keeps active steps, their units, group integration and the final review visible.
- [scripts/test-plan-run-gate.sh](scripts/test-plan-run-gate.sh) tests the gate, the bridge, the metrics, the briefs of the integration and the final review, the run lock, `rebase-integration`, `accept-integration`, the usage-limit notice and the disk check with a fake `codex`, including that breaking each guard makes a test fail. Every `plan-run.sh` call in it has a time limit (`PLAN_TEST_LIMIT`, default 120 seconds), so a broken guard fails a test instead of hanging the suite.
- Each unit is implemented, then reviewed by another agent (verdict `pass`, `back` or `escalate`, capped at `PLAN_MAX_ROUNDS` reviews, default 3; that count, and `PLAN_MAX_GATE_ROUNDS`'s, start again at every `resume`). The run stops at an escalation or a failure and writes `status.log`; after you fix the cause, `resume <name>` continues, and a brief can be corrected in `00-input/units/` first. A unit copies its brief when it starts and a passed unit does not start again, so the correction reaches the units still to run, and always the integration of a group and the final review, which read the current briefs; the copy in `<unit>/brief.md` stays as what the implementer received. Where the two differ, the integration brief and the final review show both and tell the reviewer to judge against the current one and to say when a unit met the copy but not the current brief; the integration also writes a note in `status.log`, a stronger one when the gate differs, because that unit passed against another gate and the integration runs the current one. State is in `~/.plan-runs/<name>/`.
- `-p each` or `-p 2,4` pauses after those steps (exit 3, `PAUSED` in `status.log`) for the user to read or to merge outside work before the next step; some environments show exit 3 as a failure, but it is a pause. `resume -p none` clears it.
- When it prints `READY`, the final review is in `report.md`. Progress lines go to stderr, for example `[plan] S1 unidade 01-unit · ronda 1 · implementação`. `finish <name>` copies the record to `records/plans/<name>/` in the repository; `finish --discard <name>` deletes the run.

### Who reads what

| Agent | Brief | `goal.md` |
|---|---|---|
| Implementer and reviewer of a unit | the unit's own copy, made when the unit starts | no |
| Integrator and reviewer of a group's integration | the current brief in `00-input/units/` of every unit | yes, read from `00-input/goal.md` when the integration starts; a `gate` block in it is not run |
| Final review | the current briefs | yes |

- A rule the unit reviewers must apply goes in the briefs of the units still to run: `goal.md` never reaches them.
- `goal.md` serves the integration and the final review to judge how the units fit and what is out of scope; it adds no criteria to the briefs. It may also hold a note on how the run was carried out, for example "the owner committed in the checkout during step 2: ignore those files".
- `resume` does not recreate worktrees. A group's worktrees are made once, from the checkout as it was when the group started, so a change to a shared file reaches a unit still to run only if it was in the checkout before the group started; otherwise put it in that unit's brief.

### Reading and changing a stopped run

- **Lock.** While a `plan-run.sh` works on a run it holds `<run>/.lock` (its pid). A second `resume`, a `finish`, `rebase-integration` and `accept-integration` refuse while a live `plan-run.sh` holds it; a lock whose pid is gone, or now belongs to another program, is stale and is replaced.
- **`plan-run.sh rebase-integration <name> <step> [--paths <path>...]`** moves the base of a group's integration when the checkout was edited after the integration started and those edits sit in its diff. It is an emergency exit: the rule is not to edit the checkout during a step.
  - Without `--paths`, the base becomes the checkout minus the diffs of the units already applied. It refuses once the integrator ran, in this attempt or an earlier one, because the integrator's own edits would then become base and hide from the reviewer; it also refuses, naming the git error, when the checkout changed a file of a unit's diff.
  - With `--paths`, the base stays and the given files or folders (relative to the repository) take the checkout's current version as their base. It refuses paths that hold a file of a unit's diff, and paths where nothing differs. It prints the files that leave the diff and writes the same list to `status.log`. If one of them is an edit of the integrator, the reviewer will not see it either, so name only what the owner touched.
  - Both keep the old base as `.base.before-rebase-<time>` in the integration folder. Then `resume`.
- **`plan-run.sh accept-integration <name> <step> --why <text>`** closes a group's integration by hand, when the owner judged the combined result. It applies and reviews nothing: it needs every unit of the step `passed` with its diff applied, marks the integration done, removes the worktrees and writes in `status.log` who closed it, at which `HEAD`, and why. Then `resume`.
- **Usage limit.** When Codex reports that the account is out of quota, the run stops with the reason `usage limit reached` and `status.log` gets `QUOTA: <the text after "try again at">`, kept as Codex wrote it and not parsed. `resume` after that time.
- **Disk.** Before a parallel group starts, the first worktree measures what one takes (`df` before and after); the others are projected from it with a margin of a quarter, and the step is refused, with the worktrees removed, if they will not fit. `status.log` records the measure. The estimate covers worktrees only, not what the units create while they run (temporary database clusters, build output), and `df` is not exact.

## Council runs

For a [council](../../library/workflow-types/council/council.md), use [scripts/council-run.sh](scripts/council-run.sh), which runs the council workflow on the engine. `council-run.sh start [-m model] [-e effort] <name> <brief.md>` runs five advisors independently, anonymizes their responses into a packet with the key in `02-packet/key.md`, then runs five independent reviewers and prints `READY`. State defaults to `~/.council-runs/<name>/`; `COUNCIL_RUNS_DIR` or `HARNESS_RUNS_DIR` can set another root. `COUNCIL_GUIDES` sets the folder containing role guides.

The engine records progress in `status.log` and shows a step board. `council-run.sh status <name>` prints the log, and `council-run.sh board <name>` prints the board. If a step fails, fix the cause and run `council-run.sh resume <name>`; completed steps stay done and the unfinished step runs again. If a run is killed, resume detects the interrupted attempt and continues from the unfinished step.

[test-council-run-board.sh](scripts/test-council-run-board.sh) checks the board output with a fake `codex`.

When the engine prints `READY`, write the report and run `council-run.sh check [-m model] [-e effort] <name> <report.md>` (exit 0 `pass`, 1 `back`, 2 `escalate`) for a completeness check. `council-run.sh finish <name>` keeps the record in `records/councils/<name>/` and removes the run folder.

## Review runs

For a [code review](../../library/workflow-types/code-review/code-review.md), use [scripts/review-run.sh](scripts/review-run.sh), which runs the review workflow on the engine. Start with `review-run.sh start [-m model] [-e effort] [-2] [-s spec.md] [-d standards.md]... [-g command]... <name> <target>`, where the target is `working-tree` or a revision range such as `main...feature`. Each `-g` command runs in the repository before the reviewers start; its command, output and exit code are saved in `00-input/gate.md` and shown in the report. Red checks remain visible in the report, and no checks are reported as a gap. `REVIEW_GATE_TIMEOUT` (default 900 seconds) limits each check. `-2` adds a second reviewer per axis. State defaults to `~/.review-runs/<name>/`; `REVIEW_RUNS_DIR` or `HARNESS_RUNS_DIR` can set another root, and `REVIEW_GUIDES` sets the role guides folder.

The engine records progress in `status.log` and shows a step board. `review-run.sh status <name>` prints the log, and `review-run.sh board <name>` prints the board. If a step fails, fix the cause and run `review-run.sh resume <name>`; completed steps stay done and the unfinished step runs again. If a run is killed, resume detects the interrupted attempt and continues from the unfinished step. When it prints `READY`, read `report.md`; `review-run.sh finish <name>` keeps the record in `records/reviews/<name>/` and removes the run folder.

[test-review-run-gate.sh](scripts/test-review-run-gate.sh) checks the gate behavior, and [test-review-run-board.sh](scripts/test-review-run-board.sh) checks the board output, both with a fake `codex`.

## Shared code

The `harness/` project is a standard-library Python CLI called by the scripts through the `harness` function in [`scripts/lib-codex.sh`](scripts/lib-codex.sh). Its files are [the project metadata](harness/pyproject.toml), [package initializer](harness/harness/__init__.py), [module entry point](harness/harness/__main__.py), [CLI](harness/harness/cli.py), [gate module](harness/harness/gate.py), [agent module](harness/harness/agent.py), [injection module](harness/harness/inject.py), [verdict module](harness/harness/verdict.py), [engine package initializer](harness/harness/engine/__init__.py), [run state module](harness/harness/engine/run.py), [run lock module](harness/harness/engine/lock.py), [workflow contract module](harness/harness/engine/workflow.py), [workflow pipeline module](harness/harness/engine/pipeline.py), [plan input workflow module](workflows/plan_inputs.py), [plan integration recovery module](workflows/plan_integration.py), [review workflow module](workflows/review.py), [council workflow module](workflows/council.py), [diff base module](harness/harness/engine/diffbase.py), [round metrics module](harness/harness/engine/metrics.py), [agent step module](harness/harness/engine/agentstep.py), [review module](harness/harness/engine/review.py), [phase module](harness/harness/engine/phase.py), [stepboard module](harness/harness/engine/stepboard.py), [record module](harness/harness/engine/record.py), [unit loop module](harness/harness/engine/loop.py), [integration loop module](harness/harness/engine/integration.py), [bridge module](harness/harness/engine/bridge.py), [group worktree module](harness/harness/engine/group.py), [plan workflow module](workflows/plan.py), [plan board and record module](workflows/plan_board.py), [plan runner](scripts/plan-run.sh), and the [gate tests](harness/tests/test_gate.py), [agent tests](harness/tests/test_agent.py), [injection tests](harness/tests/test_inject.py), [verdict tests](harness/tests/test_verdict.py), [run state tests](harness/tests/test_engine_run.py), [run lock tests](harness/tests/test_engine_lock.py), [workflow pipeline tests](harness/tests/test_engine_pipeline.py), [plan input tests](harness/tests/test_workflow_plan_inputs.py), [plan workflow tests](harness/tests/test_workflow_plan.py), [plan board and record tests](harness/tests/test_workflow_plan_board.py), [plan test support](harness/tests/plan_test_support.py), [review workflow tests](harness/tests/test_workflow_review.py), [council workflow tests](harness/tests/test_workflow_council.py), [engine robustness tests](harness/tests/test_engine_robustness.py), [diff base tests](harness/tests/test_engine_diffbase.py), [round metrics tests](harness/tests/test_engine_metrics.py), [agent step tests](harness/tests/test_engine_agentstep.py), [review tests](harness/tests/test_engine_review.py), [phase tests](harness/tests/test_engine_phase.py), [stepboard tests](harness/tests/test_engine_stepboard.py), [record tests](harness/tests/test_engine_record.py), [unit loop tests](harness/tests/test_engine_loop.py), [integration loop tests](harness/tests/test_engine_integration.py), [bridge tests](harness/tests/test_engine_bridge.py), [group worktree tests](harness/tests/test_engine_group.py), [plan integration recovery tests](harness/tests/test_workflow_plan_integration.py), [research workflow module](workflows/research.py), and [research workflow tests](harness/tests/test_workflow_research.py). `bkf skills` requires links to every module and test file.

Run any command by hand with `PYTHONPATH=<repo>/agent-skills/skills/dispatch-codex/harness python3 -m harness ...`.

The shared engine and its first workflow are described in [The engine](#the-engine).

- `gate run --cwd DIR --timeout SECONDS --out DIR [--note TEXT]... -- COMMAND...` writes `gate.md`, `gate.json`, and `gate-N.log` files in `DIR`; it exits 0 when all commands pass, 1 when any fail, or 2 for invalid usage or a runner error.
- `inject PROMPT_FILE` adds requested rules to the prompt file; it exits 0 on success, 1 for an invalid injection request, or 2 for an operating-system error.
- `verdict read FILE` prints the valid verdict from the last non-empty line and exits 0, or exits 1 for a missing or invalid verdict. `verdict checked FILE --min N` exits 0 when `## What I checked` has at least `N` non-empty lines (or `N` is zero or less), otherwise 1.
- `agent run --dir DIR --prompt FILE --out-prefix PREFIX --model MODEL --effort EFFORT [--sandbox SANDBOX] [--tier TIER] [--backend BACKEND]` writes `PREFIX.events.jsonl`, `PREFIX.stderr.log`, and `PREFIX.last-message.md`; it returns the backend's exit status, 1 for an injection error, or 2 for an unsupported backend or operating-system error. Launch goes through a backend class; only `codex` exists, so `--backend claude` exits 2 with “backend not implemented”.

The `lib-codex.sh` library provides `die`, `valid_name`, `harness`, `codex_run` and `inject_rules`. A role guide requests injection with a line such as `<!-- inject: ../../modules/core-code-principles.md -->`; the script adds the rule text to the brief under a `## Rules from <name>` heading, then adds a marker so retries inject it only once. [`scripts/test-inject.sh`](scripts/test-inject.sh) checks injection and its use by `codex_run` with a fake `codex` command.

## The engine

Run plans with [`scripts/plan-run.sh`](scripts/plan-run.sh), from the repository the plan changes. Prepare `goal.md`, one brief per unit and `plan.txt` (one step per line; separate briefs on the same line with spaces for a parallel group), then start with:

```sh
scripts/plan-run.sh start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <goal.md> <plan.txt>
```

Start long-running commands in the background. `start` creates `~/.plan-runs/<name>/`; keep a prepared plan outside that directory until it is ready to run. Each unit is implemented, gated if its brief has a gate, and reviewed in rounds. A parallel group runs its units in separate worktrees, checks disk space before creating the group, then applies and reviews the combined changes through integration. After all steps, a final review writes `report.md` and the run reaches `READY`.

Use `scripts/plan-run.sh status <name>` to read `status.log`, or `scripts/plan-run.sh board <name>` to see the compact board. The board folds earlier completed steps and shows current units, group integration and final review. If a step stops or escalates, read the relevant unit or `S<n>-integration` folder, its `rounds/`, and `status.log`; correct the cause (or the brief under `00-input/units/`) and run `scripts/plan-run.sh resume <name>`. Completed steps stay done. A checkpoint selected with `-p each` or `-p 2,4` exits with status 3 after those steps; inspect the board and status, then resume. Use `resume -p none <name>` to clear checkpoints.

The bridge is available to implementers as `.plan-porteiro/ponte <command...>`. It permits gate commands and configured `pnpm` scripts listed by `.plan-run.json`; requests and results are recorded in `porteiro.log` at the run root. See [The bridge](#plan-runs) for its allowed-command rules.

For a group whose integration base no longer matches the checkout, use `scripts/plan-run.sh rebase-integration <name> <step> [--paths <path>...]`, then resume. Without `--paths`, it moves the base to the checkout minus already-applied unit diffs; it is unavailable after the integrator has run and refuses if a unit diff cannot be subtracted. With `--paths`, it keeps the old base except that the named checkout paths become base, removing those files from the integration diff; do not name files changed by group units. This is an emergency recovery for checkout edits made during a step.

Use `scripts/plan-run.sh accept-integration <name> <step> --why <text>` only when you have reviewed and accept the combined result yourself. It closes the integration without running an integrator or reviewer, and requires every group unit to have passed with its diff applied. Then resume the run.

Coordinator files: `status.log` is the event history; `00-input/goal.md`, `00-input/order` and `00-input/units/` are the saved plan inputs; each unit folder holds its status, brief copy, rounds and diff; `S<n>-integration/` holds a group's integration; `porteiro.log` records bridge requests; `report.md` is the final review. After `READY`, `scripts/plan-run.sh finish <name>` saves the record under `records/plans/<name>/` and removes the run folder. `finish --discard <name>` removes it without keeping a record.

When a run ends unexpectedly, read `status.log` and the board, fix the cause, then resume; completed steps are skipped and unfinished work continues. A usage-limit stop records `QUOTA`; resume after the stated reset time. A checkpoint is a pause, not a failed run.

## Safety and gotchas

- Runs use the `workspace-write` sandbox. It confines writes to the agent's folder, but an agent can still read files outside the checkout, such as the login sessions of CLI tools in the home folder, and reach HTTPS, so it can use any session left open. The repository's own rules say what to keep logged out.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

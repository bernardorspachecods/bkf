# Unit: the pipeline: steps, pauses, commands and the CLI

## Result

`H/engine/workflow.py`, `H/engine/pipeline.py`, a `run` command in `H/cli.py`, and tests. It ports `pipeline`, `cmd_start`, `cmd_resume`, `cmd_status`, `cmd_board`, the generic part of `cmd_finish` and the lock use of `plan-run.sh`, as an engine that knows no workflow by name.

`H/engine/workflow.py` defines the contract a workflow definition fulfils:

- `class Stop(Exception)` with `.reason`.
- `class Step` with `.number` (an int, or the string `final` for the last step), `.label` and `run(self, ctx)`, which raises `Stop` when it stops.
- `class Context` with `run` (the `RunDir`), `settings`, `repo`, `progress(text)` and `note(text)`. `progress` writes `[<workflow.name>] <text>` and a blank line to standard error, then the workflow's board (when `board` returns text), as the bash `progress` does.
- `class Workflow` (a base class; methods raise `NotImplementedError` unless a default is stated): `name`; `command` (the name the user types, used in hints, for example `plan-run.sh`); `usage_start` (the usage text after `start [options] <name>`); `repo_hint` (text for the error when not inside a git repository); `validate_start(args)` (no side effect; raises `RunError`); `start(ctx, args)` (writes the run's inputs and the start notes); `steps(ctx) -> list[Step]`; `final_step(ctx) -> Optional[Step]`; `after_step(ctx, step)` (default nothing); `board(ctx) -> str` (default empty); `fix_hint(ctx) -> str` (the text of the second `STOPPED` note, default `Read the rounds in <run>, then: <command> resume <name>`); `ready_path(ctx) -> str`; `finish(ctx)` (keeps the record; called for `finish` without `--discard`); `commands() -> dict` of extra subcommand names to callables taking the arguments after the name.

`H/engine/pipeline.py` runs it. Its entry is `main(definition_path, argv) -> int`, which loads the definition (a Python file path; add its directory to `sys.path` first; the file defines `WORKFLOW`, an instance of `Workflow`) and dispatches `start`, `resume`, `status`, `board`, `finish`, and the workflow's extra commands; any other name prints `usage: <command> start|resume|status|board|finish ...`. Behavior, ported from the bash and kept character for character in files, `status.log` notes, standard output text and exit codes:

- `start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <workflow arguments>`: validate the name and the checkpoints (messages as the bash's), call `validate_start`, find the repository (`git rev-parse --show-toplevel`, else die with `repo_hint`), refuse an existing run, create the `RunDir`, take the lock, call `start`, print the board to standard error, then the pipeline. Defaults: model `gpt-6-luna`, effort `xhigh`, review effort empty.
- `resume [options] <name>`: load, lock, apply the options (the checkpoints replace the list; `none` clears it), refuse outside the run's repository, rewrite the settings, note `resume`, run the pipeline.
- The pipeline prints `Run folder: <path>`; for each step not done: note `start step <k>: <label> (<model> <effort>)`, `progress`, the step, then `done step <k>` and a progress line `S<k> concluído`, `after_step`, and the pause check (note `PAUSED after step <k>: read <run>, then: <command> resume <name>`, progress `S<k> pausa`, standard output `PAUSED after step <k> (<label>). Read it in <run>, then: <command> resume <name>` and `See <run>/status.log`, exit 3). A step that raises `Stop` notes `STOPPED at step <k>: <reason>` and `workflow.fix_hint`, progress `S<k> parou`, prints `STOPPED at step <k> (<label>): <reason>` and `See <run>/status.log`, exit 1. After the steps, the final step (when any) with the notes `start final review (<model> <effort>)`, `done final review`, `STOPPED at the final review: <reason>`, progress `final · revisão`, `final · concluído`, `final · parou`; at the end the note `READY: report at <ready_path>` and standard output `READY: <ready_path>` and `See <run>/status.log`, exit 0. Marker files: `.done-S<k>` for steps (through `is_done`/`mark_done`) and `.done-report` for the final step. Progress text is prefixed with the step number as `S<k> ...`.
- `status <name>` prints `status.log`; `board <name>` prints the board to standard output; `finish [--discard] <name>`: refuses while a live process holds the lock (`run <name> is being worked on by pid <pid>: finish it when it stops`), `--discard` removes the folder and prints `Removed <path>`, otherwise it refuses with `there is no final review in this run: nothing to keep` when the workflow's `ready_path` file is missing and calls `workflow.finish(ctx)`.
- The lock is taken with `acquire(run_path, "harness")` of `H/engine/lock.py` and released when the command ends, whatever the exit.
- `RunError` anywhere prints `Error: <message>` to standard error and exits 1, like `die`.

`H/cli.py` gets `harness run <definition-path> <command> ...`, calling `pipeline.main` and returning its status.

Tests: `T/test_engine_pipeline.py` with a trivial workflow defined in the test (two steps and a final step: one runs an agent step with the fake `codex`, one runs a deterministic command through `harness gate`), no plan: a full run (files, notes, output, exit 0), pause with `-p each` and resume (exit 3, then 0), a step that raises `Stop` (exit 1, notes) and resume after the cause is fixed, an existing run refused, a second `resume` refused while the first holds the lock, `finish` refused while locked, `finish --discard`, the usage text, `status` and `board`, and that nothing in `H/engine/` mentions `plan`.

## Receives

From earlier units: `RunDir`, `RunError`, `valid_name`, `valid_pause` (`H/engine/run.py`); `acquire`, `is_active` (`H/engine/lock.py`); the agent step (`H/engine/agentstep.py`). Read their code. The bash to read: `pipeline`, `cmd_start`, `cmd_resume`, `cmd_status`, `cmd_board`, `cmd_finish`, `lock_run`, `progress` in `scripts/plan-run.sh`.

## Leaves ready

`Workflow`, `Step`, `Context`, `Stop` and `pipeline.main`, and `harness run <definition-path> ...`, as above. The plan's definition (later units) is a `Workflow`.

## Out of scope

Any `.sh` file, the plan's definition and prompts, the board's content, the records copy of `finish`, detecting a killed run and signal handling (the next unit), worktrees, groups.

## Rules for this unit

- Do not run git commands that change state in the repository you work in (no commit, stage, stash, reset, clean, checkout); throwaway repositories you create in temporary folders for tests are yours to use freely. Do not run `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name, except as the next rule says.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file under `agent-skills/skills/dispatch-codex/` is reachable by links from its `SKILL.md`. In its `## Shared code` section, extend the list of the harness files (the first paragraph names modules and tests as links) with a link to each new file of this unit and change nothing else in that file; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py`, `agent.py` and `cli.py`.
- The spec of every port is the bash in `agent-skills/skills/dispatch-codex/scripts/plan-run.sh` (function names are given) and its test `scripts/test-plan-run-gate.sh`. Where this brief and the bash differ, this brief wins; say so in the handoff. Files the run writes (names, formats, `status.log` lines) are kept character for character unless this brief says otherwise.
- All paths in this brief are relative to the repository root; `H` means `agent-skills/skills/dispatch-codex/harness/harness`, `T` means `agent-skills/skills/dispatch-codex/harness/tests`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
```

How these are shown to fail: Make a step that raises `Stop` still count as done (a throwaway copy) and show the test about resume after a stop fail; say in the handoff what you changed.

## Criteria

- Nothing in the engine mentions a workflow by name: names, hints and messages reach it through the `Workflow` attributes.
- Notes, output text and exit codes match the bash character for character, for the cases the tests list.


---
## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-agents/agent-skills/library/workflow-types/plan/plan-implementation.md (read-only). It says how to work inside the brief, what to verify and what the handoff holds.

## Rules
- The current directory is the repository: do the work here.
- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).
- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.
- You cannot reach the database from here (the database host does not resolve). To run something that needs it, ask the runner: `.plan-porteiro/ponte <command> [args...]`. It runs the command outside your sandbox and prints the output and the exit code. Only the `pnpm` scripts the repository allows for the bridge (see `.plan-run.json`) and the commands of the brief's gate, exactly as written, are accepted; anything else is refused, and every request is logged. Use it to read the data you need and to run the checks against the database.
- The brief has a `gate`. After you finish, the script runs those commands itself and sends the work back, without a review, if any fails. Run them yourself first when you can.

The script's gate or a reviewer sent your work back. The work from the earlier round is in the checkout. Fix the problems below and only those, keeping what was fine, and verify again.

Problems from the gate or the review:

## What I checked

- **Result:** Compared the new workflow contract and pipeline in `harness/engine/workflow.py` and `pipeline.py` with the required steps, pauses, notes, output, and exit codes.
- **Scope:** Compared the supplied diff with the named deliverables; it adds the two engine modules and pipeline tests, updates the CLI, and makes the requested link-only change to `SKILL.md`.
- **Criteria:** Read `test_engine_pipeline.py` and the corresponding Bash functions in `scripts/plan-run.sh`; the supplied gate result is binding and I did not rerun it.
- **Leaves ready:** Checked CLI dispatch in `harness/cli.py` and the `Workflow`, `Step`, `Context`, `Stop`, and `pipeline.main` interfaces.
- **Failure demonstration:** Not checked; the brief says it is in the handoff, which was excluded from this review.

## Problems

- **Criteria:** The requirement that nothing in `H/engine/` mention `plan` is not met. A read-only search found references in existing `loop.py`, `diffbase.py`, `agentstep.py`, `run.py`, and `metrics.py`. These files are outside this diff, but the stated criterion covers the whole engine.

VERDICT: back

Your handoff from the previous round, for you to resume from:

## Verification

- `python3 -m unittest discover -s tests` — **passed**, 105 tests.
- `bkf skills` — **passed**.
- `git diff --check` — **passed**.
- Failure demonstration: in a throwaway copy, I marked a step done when it raised `Stop`. `test_pause_resume_and_stopped_resume` failed because resuming skipped the step after its cause was fixed.

## Leaves ready

Added the workflow contract and pipeline in [workflow.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/workflow.py) and [pipeline.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/pipeline.py), wired `harness run` in [cli.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/cli.py), added pipeline tests, and linked the new files in the skill catalog.

## Differences and gaps

The new workflow modules contain no workflow-specific names. The broader “nothing in `H/engine/` mentions plan” criterion remains unmet: existing `loop.py`, `diffbase.py`, `agentstep.py`, `run.py`, and `metrics.py` contain plan-specific references. I left those files untouched because the brief excludes them.

The run root uses `HARNESS_RUNS_DIR`, then the workflow-derived `<NAME>_RUNS_DIR`, then `~/.<workflow>-runs`. For a workflow named `plan`, the default remains `~/.plan-runs`.

## Outside focus

I left other working-tree changes untouched.


---
## Rules from core-code-principles
The script added this text from ../../modules/core-code-principles.md, as the role guide asked.

# Core principles for code

## Building

- Work test first, in small slices, when the behavior is clear enough to specify (a feature or a bug fix). Write one focused test for one behavior and confirm it fails for the expected reason; make the smallest change that passes; refactor while green; then take the next behavior. For a bug, start with a regression test that reproduces it, and if it does not fail as expected, investigate before changing production code.
- Grow in layers and decide for the long term. Start from the smallest version that works end to end and extend it one verified step at a time; the scope of a step is small, but not the quality of its decisions. Do not accept a stopgap that only works for now and is meant to be replaced later.
- Reuse before building. Prefer an established pattern, a well-maintained library or an existing dependency to a new abstraction or a reimplementation. Check the repository and its dependencies before assuming a capability is missing; if a new shape is necessary, keep it local and explain why.
- Avoid these smells, with their fixes. A documented repository standard overrides them.
  - Duplicated logic in the change: extract it into one function.
  - Speculative generality, meaning abstraction, parameters or hooks nobody asked for: delete them and add them back when a real need shows.
  - Middle man, a function or class that only passes the call on: call the real target.
  - Shotgun surgery, one change forcing scattered edits: gather what changes together into one module.

## Verifying

- Let code decide what code can decide. Cover every required behavior with a test, type check or script whose result decides. A reading of the code is not evidence of what a run can show: an LLM reading LLM-written code is a probabilistic system checking another.
- A check must be able to fail. Show it failing once, against a wrong input or a throwaway copy of the code with the defect put back, before you rely on it.
- Never weaken an existing test or check to make work pass.
- What code cannot decide (visual quality, opinion, whether the spec is right) stays with a person and is reported as unverified, not as passed. No check for a changed behavior is a gap, not a pass.
- Report what ran and what came out, failures included. Work is done when the requested behavior is covered and the relevant tests and the nearest affected gate pass; work that is not verified is not done.
- The person or the approved plan decides what the tests specify. Prototypes, exploration, documentation, visual experiments and trivial configuration are exempt.

---
## Rules from gate
The script added this text from ../../modules/gate.md, as the role guide asked.

# The gate

- Code runs each command outside any agent, in its own process group.
- A time limit stops the whole process group and records exit code 124.
- The result contains the command, exit code and output tail in `gate.md`, a `gate.json`, and one log per command.
- Every command runs, even after one fails.
- A red result stands; no agent overrides it.
- No commands is a gap, not a pass.
- An agent that receives the gate takes it as given and does not run it again.

<!-- rules injected by the script -->

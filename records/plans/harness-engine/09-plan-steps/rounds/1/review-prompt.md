# Review

## The brief

# Unit: the plan as a workflow: start, units, final report

## Result

`agent-skills/skills/dispatch-codex/workflows/plan.py` defining `WORKFLOW`, a `Workflow` (`H/engine/workflow.py`) for the sequential plan, with tests `T/test_workflow_plan.py`. It ports `cmd_start`'s non-validation part, `run_step` (the single-unit branch), `run_report`, the step bookkeeping of `pipeline`, and `cmd_gates` wiring.

- `name = "plan"`, `command = "plan-run.sh"` (the name users type; the hints keep it), `usage_start = "<goal.md> <plan.txt>"` with the messages of the bash.
- `validate_start(args)`: two arguments; goal and plan non-empty (`missing or empty goal: <path>`, `missing or empty plan: <path>`); the plan parsed with `plan_inputs.parse_plan`; `codex` found on `PATH` (`codex not found`); the role guides folder exists (`no role guides at <path> (set PLAN_GUIDES)`).
- `start(ctx, args)`: `write_inputs`; the base of the whole plan (`<run>/plan-base`, with `snapshot_base`); the notes `start <name> (<model> <effort>, review <review effort or effort>, max <max rounds> rounds, <k> step(s), <i> unit(s), repo <repo>)` and `unit <u> has no gate: only a reviewer checks it`. The `.plan-run.json` notes are not written (no bridge).
- `steps(ctx)`: one `Step` per line of `00-input/order`, labelled with the unit name; running it calls `run_unit_loop` with hooks built on `plan_inputs` (prompts, `gate_commands`, `progress`), `step=<k>`, `base_from` = `state-after-S<k-1>` or, for the first step, `plan-base/base` (a step without such a file takes a fresh snapshot, as the bash), the effort of reviewers from the settings, the limits from `PLAN_MAX_ROUNDS` (3), `PLAN_MAX_GATE_ROUNDS` (5), `PLAN_GATE_TIMEOUT` (900), `PLAN_MIN_CHECKED` (3); the tier from `tier_from_environment`. A unit whose `.done-<unit>` marker exists is not run again; it writes the marker when it passes. `after_step` writes `state-after-S<k>` (`snapshot_tree`, removing the file when the snapshot fails). Progress lines `S<k> início · unidade <unit>` before a step.
- `final_step(ctx)`: the final report: the current briefs are checked (`check_briefs` of the bash, with its reason), `cumulative.patch` is made against `plan-base`, `report-prompt.md` written with `plan_inputs.report_prompt`, a read-only agent run with the review effort, quota-aware failure reason `final review exit=<code> (see <run>/report.stderr.log)`, `final review wrote no report`, and `report.md` copied from `report.last-message.md`. `ready_path` is `<run>/report.md`; `fix_hint` is the bash's second `STOPPED` text (`Read the rounds in <run> ... the briefs in <run>/00-input/units/, or the checkout ... then: plan-run.sh resume <name>`). `commands()` returns `{"gates": plan_inputs.gates_command}`.
- `board` and `finish` are not part of this unit: return an empty board and have `finish` raise `NotImplementedError` with a message naming the next unit.

Tests: `T/test_workflow_plan.py`, running `pipeline.main` on this definition in throwaway repositories with the fake `codex` of `scripts/test-plan-run-gate.sh` (reuse its logic, written in Python in a shared helper under `T/`): a one-unit plan to the end (the files `00-input`, `<unit>/`, `report.md`, `state-after-S1`, `cumulative.patch`, `status.log` lines, output, exit 0); two units where the second starts from the state the first left; a unit with a failing gate; a pause and resume; a current brief that disappears before the final review; the several-briefs refusal; the messages of `validate_start`.

## Receives

From earlier units: the engine (`H/engine/*`: `Workflow`, `Step`, `Context`, `Stop`, `pipeline.main`, `run_unit_loop`, `run_review`, `run_agent_step`, `tier_from_environment`, `snapshot_base`, `snapshot_tree`, `make_patch`) and `workflows/plan_inputs.py`; read their code. The bash to read: `cmd_start`, `run_step`, `run_report`, `pipeline`, `run_unit` (for the hooks) in `scripts/plan-run.sh`.

## Leaves ready

`WORKFLOW` in `workflows/plan.py`, runnable with `python3 -m harness run workflows/plan.py <command> ...` (the board and `finish` come next).

## Out of scope

Any `.sh` file, the board, `finish` and the records copy, groups, the bridge, changes to the engine (when the engine is wrong, fix it minimally and say so in the handoff).

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

How these are shown to fail: Make the first step take its base from a fresh snapshot instead of `plan-base` (a throwaway copy) and show the test that checks the diff of step 2 fail; say in the handoff what you changed.

## Criteria

- Every file the run writes and every `status.log` line matches the bash's for the cases the tests cover, apart from the bridge notes.
- Nothing plan-specific was added to `H/`.


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/09-plan-steps/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-engine/09-plan-steps/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-agents/agent-skills/library/workflow-types/plan/plan-review.md (read-only). You are not the author of the work.

---
Your final message is the review, and nothing else. Begin it with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:
VERDICT: pass
VERDICT: back
VERDICT: escalate


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

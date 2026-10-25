# Review

## The brief

# Unit: the plan's inputs: plan.txt, briefs, gate commands and prompts

## Result

`agent-skills/skills/dispatch-codex/workflows/plan_inputs.py` (a plain module; the engine will put its folder on `sys.path`) with tests `T/test_workflow_plan_inputs.py` (add the folder to the test's path). It ports, from `plan-run.sh`, what the plan does with its inputs, without any run or agent:

- `parse_plan(plan_path)`: reads `plan.txt` as `cmd_start` does (comments after `#`, blank lines, paths relative to the file's folder, each brief non-empty, unit name valid from the file name) and returns the steps. This engine runs one unit per step: a line with several briefs raises `RunError("step <n> has several briefs; this engine runs one unit per step")`. An empty plan raises `RunError("plan.txt has no step")`; the other messages are the bash's (`missing or empty unit brief: <w>`, `bad unit name (from the file name): <w>`).
- `write_inputs(run_path, goal_path, steps)`: copies the goal to `00-input/goal.md` and each brief to `00-input/units/<NN>-<name>.md` (`NN` from 01, two digits), and writes `00-input/order` (one unit name per line).
- `gate_commands(brief_paths) -> list[str]`: the commands of every fenced block tagged `gate`, one per line, blank lines and `#` lines ignored, trimmed, without duplicates, in order (the awk of the bash; a fence without the tag is ignored; two blocks are both read).
- `gates_command(args)`: the `gates` subcommand (`cmd_gates`): from a `plan.txt` path or a run name, prints each unit's name and its commands as `  $ <command>`, or `  NO GATE: only a reviewer checks this unit`, a blank line after each, and returns 1 when a unit has no gate.
- The brief helpers `brief_current`, `brief_differs`, `gate_differs`, `print_unit_brief` (exact text of the bash, including the "Brief received by the implementer" section).
- The three prompts as functions returning text: `implement_prompt(guides, brief, round_number, resumed, previous_problems, previous_handoff)`, `review_prompt(guides, brief, patch, previous_problems, attempt, gate_file)` and `report_prompt(run_path, guides)` (the text `run_report` writes into `report-prompt.md`, without groups or integrations). `implement_prompt` is the bash's **without the bridge bullet** (the one about `.plan-porteiro/ponte`); everything else is character for character.
- `guides_path(environ, here)`: `PLAN_GUIDES` when set, else `<git top-level of here>/agent-skills/library/workflow-types/plan`.

Tests: `T/test_workflow_plan_inputs.py`: each parse case and message; the order file and unit names; the gate parser on a brief with two blocks, a fence without the tag, comments, blank lines and duplicates; the `gates` output and its exit status for a plan and for a run; the brief helpers with a current brief that differs from the received one; the three prompts compared with expected text (write the expected text from reading the bash; for `implement_prompt` also assert the bridge bullet is absent) for a first round, a resumed first round, and a round with previous problems and handoff.

## Receives

`RunError` (`H/engine/run.py`). The bash to read: `cmd_start` (its validation and copying), `gate_commands`, `cmd_gates`, `brief_current`, `check_briefs`, `brief_differs`, `gate_differs`, `print_unit_brief`, `implement_prompt`, `review_prompt`, `run_report` (the prompt only) in `scripts/plan-run.sh`.

## Leaves ready

The functions above, in `workflows/plan_inputs.py`. The next unit (the plan's definition) imports them.

## Out of scope

Any `.sh` file, `H/` (the engine), the board, the report's execution, `finish`, groups and the bridge.

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

How these are shown to fail: Drop the dedupe in `gate_commands` (a throwaway copy) and show the matching test fail; say in the handoff what you changed.

## Criteria

- Prompts and printed text are character for character the bash's, apart from the removed bridge bullet and the new several-briefs message.
- The module imports nothing from the engine except `RunError`.


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/08-plan-inputs/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-engine/08-plan-inputs/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

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

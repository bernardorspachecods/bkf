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

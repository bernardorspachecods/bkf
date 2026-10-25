# Unit: one review of a round: attempts, form and verdict

## Result

`H/engine/review.py` with tests. It ports `do_review` of `plan-run.sh`.

`run_review(run, label, directory, round_dir, build_prompt, model, effort, tier, min_checked, previous_problems=None) -> ReviewResult` with `ReviewResult.verdict` (`pass`, `back` or `escalate`, or `None` on failure) and `.reason`:

- Up to 3 attempts. Each: delete `<round_dir>/review.last-message.md`; call `build_prompt(attempt)` (a callable supplied by the workflow that returns the prompt text) and write it to `<round_dir>/review-prompt.md`; run the agent with `run_agent_step`, sandbox `read-only`, output prefix `<round_dir>/review`, working directory `directory`. A failing agent stops the review with the quota-aware reason (`<label>: review exit=<code> (see <round_dir>/review.stderr.log)` when it is not quota).
- A review is usable when `review.last-message.md` is non-empty, `checked_ok(path, min_checked)` and `read_verdict(path)` both succeed (from `H/verdict.py`). An unusable one writes the note `<label>: review attempt <n> was not usable` and the next attempt starts.
- After 3 unusable attempts the result has no verdict and the reason `<label>: the reviewer left no usable review after <n> attempts (see <round_dir>/review.last-message.md)`.
- On success: copy `review.last-message.md` to `<round_dir>/problems.md`, write the verdict word to `<round_dir>/verdict` (with a newline) and write the note `<label>: round <basename of round_dir>: verdict <verdict>`.

Tests: `T/test_engine_review.py` with a fake `codex`: a usable review for each verdict; an unusable first attempt (no verdict line) then a usable one, and the note; three unusable attempts and the reason; a section `## What I checked` with too few lines counting as unusable; an agent failure (quota and not); that the files and notes are exactly as listed; that the prompt builder receives the attempt number.

## Receives

`run_agent_step` and `StepResult` from `H/engine/agentstep.py`, `RunDir` from `H/engine/run.py`, `read_verdict` and `checked_ok` from `H/verdict.py` (read the code). The bash to read: `do_review` and `review_run` in `scripts/plan-run.sh`.

## Leaves ready

`run_review` and `ReviewResult` as above.

## Out of scope

Any `.sh` file, the contents of the review prompt (the workflow builds it), the unit loop.

One change outside `review.py` is in scope: the exit status of a failing agent is only known after it runs, so `run_agent_step` in `H/engine/agentstep.py` must let `reason_when_not_quota` hold the placeholder `<exit>`, which it replaces with the exit status (it is how `review exit=<code>` gets its code), and must drop trailing newline characters from the quota text before it goes into the note and the reason. Make these two edits in `agentstep.py` and cover each with a test in `T/test_engine_agentstep.py`; they are fixes to the previous unit that this unit's review exposed. The reviewer does not count them as outside scope.


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

How these are shown to fail: Count the attempts wrongly (allow a fourth) in a throwaway copy and show the matching test fail; say in the handoff what you changed.

## Criteria

- Files, notes and reasons are character for character those of the bash.
- The module knows nothing about plans, units or gates.

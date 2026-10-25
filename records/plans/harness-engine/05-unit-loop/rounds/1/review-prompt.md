# Review

## The brief

# Unit: the unit loop: implement, gate, review, back

## Result

`H/engine/loop.py` with tests. It ports the round loop of `run_unit` of `plan-run.sh`, without the bridge (`porteiro_*`), and `write_gate_problems`.

`run_unit_loop(run, unit, checkout, *, source_brief, hooks, settings, tier, limits, step=None, base_from=None) -> LoopResult` with `LoopResult.ok` and `.reason`:

- `hooks` is an object the workflow supplies, with these methods (a base class `UnitHooks` in `loop.py` documents them and raises `NotImplementedError`): `implement_prompt(brief, round_number, resumed, previous_problems, previous_handoff) -> str`; `review_prompt(brief, patch, previous_problems, attempt, gate_file) -> str` (the last two as in the bash: `previous_problems` empty or a path, `gate_file` empty or the path of the round's `gate.md`); `gate_commands(brief) -> list[str]`; `progress(text)`; and `around_implement(checkout, unit, base, brief)`, a context manager entered around the implementer's run, which does nothing by default (the future place of the bridge).
- `limits` holds `max_rounds`, `max_gate_rounds`, `gate_timeout`, `min_checked`. `step` is the step number used in progress text (`S<step>`); `base_from` is the path of a file holding a tree id to use as the unit's base (or `None`).
- Every behavior of the bash round loop is kept, with these files and texts character for character: `<run>/<unit>/` with `base`, `base-format`, `brief.md` (a copy of `source_brief`), `status` (`implementing round N`, `gate round N`, `reviewing round N`, `passed`, `escalated`), `handoff.md`, `final.patch`, and `rounds/N/` with `implement-prompt.md`, `implement.*`, `handoff.md`, `diff.patch`, `gate.md`, `gate.json`, `gate-<n>.log`, `problems.md`, `verdict`, `review*`; the resume handling (`rounds` moved to `rounds.attempt-<epoch>` when the unit already has a `base`, `resumed` passed to the implement prompt, the base taken again from `base_from` when given and kept otherwise); the gate through `H/gate.py` (`run_gate`, timeout from `limits`, out dir the round); `write_gate_problems` (the exact text of the bash, `VERDICT: back` last, and the verdict file `back`); counting gate failures against `max_gate_rounds` and reviewer `back`s against `max_rounds` apart; the empty-diff stop; the implementer failing (quota-aware, through `run_agent_step`, reason `<unit>: implementer exit=<exit> (see <rd>/implement.stderr.log)`, where `<exit>` is the placeholder `run_agent_step` replaces with the exit status), leaving no handoff (`<unit>: implementer left no handoff`); the reasons for each escalation; `record_metrics` after each implementation round.
- Notes (`run.note`) and progress texts are exactly the bash's, for example `S1 unidade 01-unit · ronda 2 · gate FAIL` (progress) and `01-unit round 2: gate` (note); the progress text is built from `step`. The review of each round goes through `run_review` (`H/engine/review.py`) with `hooks.review_prompt` as the prompt builder.

Tests: `T/test_engine_loop.py`, with a fake `codex` that dispatches on the prompt (an implementation changes a file, a review answers the verdict the test sets) in a throwaway git repository and a stub `UnitHooks`: pass on the first round; gate red then green; gate always red up to the cap; reviewer back then pass; reviewer back up to the cap; reviewer escalate; empty diff; implementer failing, with quota and without; no handoff; unusable reviews; resume after a stop (the `rounds.attempt-*` folder, `resumed` true in the prompt); the files, statuses, notes and progress texts of a green round and a red-then-green round compared with expected text; `around_implement` entered and left around the implementer.

## Receives

From earlier units: `RunDir`, `RunError` (`H/engine/run.py`); `snapshot_tree`, `snapshot_base`, `make_patch` (`H/engine/diffbase.py`); `record_metrics` (`H/engine/metrics.py`); `run_agent_step`, `StepResult`, `tier_from_environment` (`H/engine/agentstep.py`); `run_review` (`H/engine/review.py`); `run_gate` (`H/gate.py`). Read their code for the exact signatures; where this brief's names differ, the code wins. The bash to read: `run_unit`, `write_gate_problems`, `codex_failed`, `do_review` in `scripts/plan-run.sh`.

## Leaves ready

`run_unit_loop`, `LoopResult`, `UnitHooks` as above.

## Out of scope

Any `.sh` file, the bridge, worktrees, parallel groups, the contents of prompts (hooks supply them), the pipeline.

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

How these are shown to fail: Count a gate failure as a reviewer round (a throwaway copy) and show the test about the two caps fail; say in the handoff what you changed.

## Criteria

- The loop knows nothing about plans, briefs' format, prompts' wording or the bridge: everything of that kind comes through `hooks`.
- Files, statuses, notes, reasons and progress texts match the bash character for character.


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/05-unit-loop/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-engine/05-unit-loop/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

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

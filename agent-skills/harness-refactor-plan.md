---
bkf: document
description: "Plan to move the harness engine out of the dispatch-agents skill and give each workflow skill its own scripts, definition and tests; the engine stays generic. Written and executed on 2026-10-26 and 2026-10-27."
tags: [harness, plan]
---

# Harness refactor plan

## Intent

The harness keeps the technical part no skill should duplicate. Each skill owns what is unique to it: its roles, its scripts, its workflow definition and its tests. The engine still knows no workflow by name: it loads a definition file it is given (`harness run <definition>`, which already adds the definition's folder to `sys.path`). `workflows/` and the `dispatch-agents` skill belong to the old model and go away.

Decisions taken in conversation, 2026-10-26: the harness code leaves `skills/`; `delegate-work` launches through the harness and owns its own wrapper; each workflow skill owns its definition.

## Target layout

```
agent-skills/
  harness/                       engine, generic (a BKF bundle: MAP.md, README.md)
    harness/  tests/  pyproject.toml  scripts/lib.sh
  modules/run-commands.md        what the four run scripts share, injected
  skills/
    plan/      roles/ scripts/{plan-run.sh, plan*.py} tests/
    research/  roles/ scripts/{research-run.sh, research.py} tests/
    council/   roles/ scripts/{council-run.sh, council.py} tests/
    code-review/ roles/ scripts/{review-run.sh, review.py} tests/
    delegate-work/ scripts/delegate-run.sh   (was run-codex.sh)
    dispatch-agents/             removed
```

## Baseline (before any step)

- Harness: `cd agent-skills/skills/dispatch-agents/harness && PYTHONPATH=. python3 -m unittest discover -s tests` is 280 tests OK; the six `scripts/test-*.sh` exit 0.
- BKF tooling: `"$(uv tool dir)/bkf-tooling/bin/python3" -m unittest discover -s bkf/tooling/tests` is 266 tests OK (the system `python3` lacks `ruamel` and fails 113).

## Status

Steps 1 to 9 are done and verified (see the checks below); nothing is committed. Counts after the refactor: engine tests 188 plus `test-inject.sh` (23 checks), plan 70, council 7, code review 10, research 10, backend check 5 (included in the 188), the delegate wrapper test 17 checks, BKF tooling 266.

## Steps

Each step ends green on the checks of its line, and nothing is committed until the owner says so.

| # | Step | Check that decides |
| --- | --- | --- |
| 1 | `git mv` `dispatch-agents/harness` to `agent-skills/harness`; `lib-codex.sh` becomes `harness/scripts/lib.sh`; scripts and README point to the new paths. Workflows and run scripts stay where they are. | Harness tests and the six shell tests, with the new paths |
| 2 | Add `harness.backend.require()`: one check that the chosen backend's CLI exists. Replace the four `shutil.which("codex")` checks. Fixes council (and the others) refusing to start on Claude. | New unit tests for the check, plus the existing workflow tests |
| 3 | Council: move `council.py`, `council-run.sh` and its tests into `skills/council/`. Replace the `parents[4]` guide lookup by the definition's own folder. | Council tests and `test-council-run-board.sh` from the new place |
| 4 | Code review: same for `review.py` and `review-run.sh` | Review tests and the two review shell tests |
| 5 | Research: same for `research.py` and `research-run.sh` | Research tests and its shell test |
| 6 | Plan: same for the six `plan*.py`, `plan-run.sh`, `plan_test_support.py` and the plan tests | Plan tests and `test-plan-run-gate.sh` |
| 7 | `delegate-work`: `run-codex.sh` becomes `delegate-run.sh`, backend-neutral (default model per backend, `HARNESS_BACKEND`), keeping its snapshot and worktree modes; update `bkf/tooling/launch_guard.py` and its tests for the new name | Guard tests; a fake-agent test of the wrapper in place and in worktree |
| 8 | Text: add the module `run-commands` (state, status, board, resume, finish, quota, lock, limits); remove the `dispatch-agents` skill; each workflow skill gets its own run commands and options from the old section (this is B1, C1 to C4 of `skills-audit.md`); shrink `delegate-work` | `bkf skills --write`, `bkf inventory --write .`, `bkf validate .` |
| 9 | Update `harness-goal.md` (where the harness lives, the new ownership rule), `skills-audit.md` (drop what is settled), the README of the harness and the `MAP.md` files | Validators, and a search finds no `dispatch-agents` outside `records/` |

## Not part of this plan

- Splitting the plan workflow's six modules or shortening `council.py`'s inline briefs into templates. Both are worth doing after the move, so the move stays mechanical and the tests prove it.
- Live model calls. The owner runs those; the checks above use the fake agents of the existing tests.
- Commits and merges.

## Risks

- Tests find the scripts through relative paths (`Path(__file__).parents[2]`); each moved test needs its paths rewritten, and a path that points at nothing could skip a test instead of failing it. After each step the test count must equal the baseline count for what moved.
- `records/` mentions old paths. It is history and stays as it is.
- The Claude backend was never run end to end for plan, council or review. Step 2 removes the start-up refusal; a real run stays unverified until the owner runs it.

## Handoff

The engine wrapper is ready at [plan-run-engine.sh](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/scripts/plan-run-engine.sh). The test script selects it with `PLAN_RUN_UNDER_TEST` and limits engine runs to sequential cases with `PLAN_RUN_SCOPE=sequential`. `plan-run.sh` was not changed.

### Verification

- Engine sequential mode: **49 passed, 0 failed, 10 skipped**.
- Default mode: **144 passed, 0 failed, 0 skipped**.
- Harness tests: **139 passed**. `bkf skills`, `test-inject.sh`, `test-review-run-gate.sh`, shell syntax checks, and `git diff --check` passed.
- Throwaway failure demonstration: changed a temporary copy so `finish` skipped the records copy. The engine-mode check `metrics: finish writes the table into status.md` failed as expected (exit 1). This demonstration is handoff-only and is not visible in the diff.

### Skips

Category skips were bridge (cases 9–10), bridge config (13–19), integration briefs (20–23), rebase and accept integration (26–30), integration quota, disk (32), parallel progress (36), and parallel board (42). These cover the requested bridge, integration, disk, and parallel cases.

The two `ENGINE GAP` skips are:

- `progress stdout`: Bash preserves `root//name` when `PLAN_RUNS_DIR` ends in `/`; the engine prints normalized `ctx.run.path`.
- `board stdout`: same path-format difference.

The engine’s `_display_run_path` was removed, as specified. Plain sequential current and received briefs passed; integration brief cases were skipped as integration cases.

### Left ready

The updated `test-plan-run-gate.sh` retains the existing assertions and emits greppable `ENGINE GAP` skip lines. The harness file links pass `bkf skills`. No other gaps are known.
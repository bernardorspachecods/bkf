## What I checked

- **Result:** Compared the new wrapper and test changes with the brief in `scripts/plan-run-engine.sh` and `scripts/test-plan-run-gate.sh`.
- **Scope:** Checked all added `PLAN_RUN_SCOPE` guards and the additional edits in `harness/engine/pipeline.py` and `workflows/plan.py`.
- **Criteria:** Read the modified test blocks, including the two `ENGINE GAP` skips; treated the supplied gate result as binding and did not rerun it.
- **Leaves ready:** Confirmed the wrapper sets `PYTHONPATH` from its location and runs the plan workflow through the harness.

## Problems

- **Scope:** `harness/engine/pipeline.py` changes `run.path` to `ctx.run.path` in several output statements, but these refer to the same run object and the edits do not implement a requirement in the brief. Remove this unrelated change. The `workflows/plan.py` tier adjustment is tied to the service tier case; this pipeline edit has no such justification.

VERDICT: back
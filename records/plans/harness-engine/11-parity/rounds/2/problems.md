## What I checked

- **Result:** The wrapper runs `workflows/plan.py` through the harness and passes arguments and exit status through; `plan-run.sh` is untouched (`scripts/plan-run-engine.sh:4–9`).
- **Scope:** The patch no longer changes `harness/engine/pipeline.py`; the earlier scope issue is gone. `workflows/plan.py` changes the plan’s tier selection (`workflows/plan.py:41, 137`).
- **Criteria:** The new skips cover bridge, integration, rebase/accept, disk, and parallel cases; the two path-format skips say `ENGINE GAP` (`scripts/test-plan-run-gate.sh:169–675`). The supplied gate result is binding and was not rerun. The throwaway failure demonstration is not in the diff; per the brief, I leave it unchecked without treating that as a problem.
- **Leaves ready:** The wrapper is linked in the `SKILL.md` Shared code list (`SKILL.md:95`). The test runner defaults to `plan-run.sh`, supports the two requested variables, and adjusts fake `ps` output for engine mode (`test-plan-run-gate.sh:70, 80`).

Problems: None.

VERDICT: pass
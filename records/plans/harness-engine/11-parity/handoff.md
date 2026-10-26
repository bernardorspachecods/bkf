## Handoff

Restored the five output references in `pipeline.py` from `ctx.run.path` to `run.path`, removing the unrelated change identified by the reviewer.

### Verification

- Harness tests: **139 passed**.
- `bkf skills`, default plan gate, engine sequential plan gate, `test-inject.sh`, and `test-review-run-gate.sh`: all passed.
- Default plan gate: **144 passed, 0 failed**.
- Engine sequential mode: **49 passed, 0 failed, 10 skipped**. The two `ENGINE GAP` skips are `progress stdout` and `board stdout`, both for the `root//name` path difference. Other skips cover bridge, integration, disk, and parallel cases.
- The earlier throwaway failure demonstration is recorded in the previous handoff: making `finish` skip the records copy caused the engine metrics assertion to fail. I did not repeat it for this return.

No other reported problems remain.
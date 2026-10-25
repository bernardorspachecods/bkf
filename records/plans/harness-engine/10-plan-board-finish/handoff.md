## Handoff

`Plan.finish` now refuses to keep a run when `report.md` is missing or empty, using the shell’s error message. The run remains in place and no record destination is created. Added regression coverage in [test_workflow_plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_workflow_plan_board.py).

- **Failure check:** Before the fix, the new test failed because `finish` did not raise and kept the run. It now checks both a missing report and an empty report.
- **Verification:** `python3 -m unittest discover -s tests -p test_workflow_plan_board.py` passed: 8 tests.
- **Gate:** I did not rerun the supplied gate, per its instruction to accept the returned gate result.
- **Scope:** No other issues pursued.
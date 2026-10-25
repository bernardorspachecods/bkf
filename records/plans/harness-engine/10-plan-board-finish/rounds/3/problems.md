## What I checked

- **Result:** `Plan.finish` now checks that `report.md` exists and is nonempty before creating the record destination ([plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan_board.py:249)); the record and summary logic is present.
- **Scope:** The diff changes only `plan.py`, `plan_board.py`, the board tests, and the required `SKILL.md` link ([SKILL.md](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/SKILL.md:95)).
- **Criteria:** The new test covers both a missing and empty report, and checks that finish refuses without creating the destination ([test_workflow_plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_workflow_plan_board.py:210)). The supplied gate is binding; I did not rerun it. The failure demonstration is not checked, as instructed.
- **Leaves ready:** The sequential workflow delegates `board` and `finish` to the helper ([plan.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan.py:197)); the helper includes the board, summary, and filtered record copy.

## Problems

None.

VERDICT: pass
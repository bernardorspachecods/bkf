## What I checked

- **Result:** Compared `Plan.board` and `Plan.finish` in [plan.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan.py:197) and the board, summary, and copy logic in [plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan_board.py:100) with the brief and shell functions.
- **Scope:** Checked the supplied diff. It stays within the named Python files, tests, and the required `SKILL.md` link update.
- **Criteria:** The hand-built board cases now compare complete expected text for the listed states in [test_workflow_plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/dispatch-codex/harness/tests/test_workflow_plan_board.py:48). I accept the supplied gate as binding and did not rerun it; the failure demonstration is not checked, as instructed.
- **Leaves ready:** Checked the sequential board, summary, filtered record copy, and record assertions in [plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/dispatch-codex/workflows/plan_board.py:249) and [test_workflow_plan_board.py](/Users/bernardopacheco/bkf-engine/agent-skills/dispatch-codex/harness/tests/test_workflow_plan_board.py:162).

## Problems

- **Result:** `finish` does not refuse to keep a run without a final review. The shell `cmd_finish` checks that `report.md` is nonempty before recording the run ([plan-run.sh](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/scripts/plan-run.sh:1139)); `plan_board.finish` proceeds directly to creating the destination and writing the summary. Add the matching guard and a test for it.

VERDICT: back
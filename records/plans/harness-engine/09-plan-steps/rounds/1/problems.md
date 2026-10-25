## What I checked

- Result — compared `WORKFLOW` and its methods in [plan.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan.py:64) with the brief and the corresponding `plan-run.sh` functions.
- Scope — the diff changes only the requested workflow, tests, support helper, and `SKILL.md` link list.
- Criteria — reviewed the new scenarios in [test_workflow_plan.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_workflow_plan.py:24) and compared reviewer invocation with the engine and bash. The reported gate is binding and was not rerun. The throwaway failure demonstration is not checked, as the brief directs.
- Leaves ready — `WORKFLOW`, `commands()`, `ready_path()`, and the stated `NotImplementedError` for `finish` are present in `plan.py`.

## Problems

- **Reviewer effort differs from the bash behavior.** The workflow’s `_review_effort()` falls back to the implementation effort, but `steps()` passes raw `settings.review_effort` into `run_unit_loop` (`plan.py:129`). The engine forwards that value unchanged to unit reviews (`loop.py:184–186`). With the default empty review setting, unit reviewers receive an empty effort; `plan-run.sh` explicitly falls back to the implementation effort. The fake Codex tests do not check the effort passed to unit reviews.
- **The tests don’t verify the complete `status.log` event sequence.** The one-unit test checks a few lines with substring assertions (`test_workflow_plan.py:44–46`), so it would still pass if other required lines were missing, reordered, or added.

VERDICT: back
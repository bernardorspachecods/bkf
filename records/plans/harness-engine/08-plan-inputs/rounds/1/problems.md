## What I checked

- **Result:** `parse_plan`, `write_inputs`, `gate_commands`, `gates_command`, the brief helpers, prompts, and `guides_path` are present in [plan_inputs.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan_inputs.py:31).
- **Scope:** The diff adds only the requested workflow module and test, plus links to both in the `## Shared code` list of [SKILL.md](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/SKILL.md:93).
- **Criteria:** Compared the implementations and prompt text with the specified functions in `scripts/plan-run.sh`. The module imports only `RunError` from the engine. The recorded gate result is binding and was not rerun. The failure demonstration is **not checked**; the brief says it is in the handoff, which is unavailable to this review.
- **Leaves ready:** [test_workflow_plan_inputs.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_workflow_plan_inputs.py:33) adds coverage for plan parsing, input copying, gate parsing and output, brief helpers, prompts, and guide paths. No problem found in the diff.

VERDICT: pass
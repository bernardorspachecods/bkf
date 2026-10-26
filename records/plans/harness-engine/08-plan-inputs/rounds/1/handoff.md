## Verification

- `python3 -m unittest discover -s tests`: 124 tests passed.
- `bkf skills`: valid, 0 issues.
- In a throwaway copy, I removed gate deduplication; the focused test failed because `alpha` appeared twice.

## Handoff

Implemented the plan input helpers in [plan_inputs.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/workflows/plan_inputs.py), added [tests](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_workflow_plan_inputs.py), and linked both from the dispatch-codex skill.

The brief intentionally differs from the bash by rejecting multiple briefs on one plan line; this engine runs one unit per step. The implement prompt also omits the bridge bullet as requested. No other known gaps. Unrelated worktree changes were left untouched.
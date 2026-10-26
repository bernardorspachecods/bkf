## What I checked

- Compared the requested scope with the diff for `agent-skills/skills/dispatch-codex/SKILL.md`; changes are in `## Shared code` and the new `## The engine` section.
- Checked the engine command, workflow contract, run state, signals, lock, and unit loop in `harness/harness/engine/` and `harness/harness/cli.py`.
- Checked the plan workflow, runner, board, and extra command in `workflows/plan.py`, `workflows/plan_inputs.py`, `workflows/plan_board.py`, and `scripts/plan-run-engine.sh`.
- Checked that the Shared code list links the engine and workflow files, and inspected the parity test’s `ENGINE GAP` branches in `scripts/test-plan-run-gate.sh`.
- The parity test command was not executed: the read-only review guide prohibits writing temporary folders. Its source shows the two `ENGINE GAP` notices under the requested environment.

No problems found in the documentation. The provided gate result is accepted as binding.

VERDICT: pass
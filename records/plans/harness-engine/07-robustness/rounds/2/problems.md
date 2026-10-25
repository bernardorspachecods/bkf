## What I checked

- **Result:** Signal cleanup blocks handled signals across spawn and process registration in [agent.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/agent.py:139); the run handler records interruption, terminates children and returns the signal exit code in [pipeline.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/pipeline.py:26). Crash logging and resume detection are also in `pipeline.py`.
- **Scope:** The patch changes the requested pipeline and agent modules, tests, and the `## Shared code` list in `SKILL.md`.
- **Criteria:** Read the signal, SIGKILL/resume, crash, and clean-stop tests in [test_engine_robustness.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_engine_robustness.py:72). The specified gate is binding and was not rerun. The throwaway-copy failure demonstration is assigned to the handoff and was not checked here, as instructed.
- **Leaves ready:** Interrupted or killed steps lack their done marker and can run again on resume; detection is written before the `resume` note in `pipeline.py`. The lock context releases the lock when the run exits.

No problems found. The previous spawn-to-registration race is addressed by blocking signals until the spawned process is registered, and the added race test exercises that window.

VERDICT: pass
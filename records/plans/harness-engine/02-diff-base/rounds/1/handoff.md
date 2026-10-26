## Handoff

**Verification:** `python3 -m unittest discover -s tests` passed (70 tests); `bkf skills` passed. The tests ran on Python 3.15; Python 3.9 was not available to check directly.

**Failure demonstration:** In a throwaway copy, I changed `snapshot_tree` to use the real index. The index-preservation test then failed at its `git diff --cached` assertion.

**Left ready:** `snapshot_tree`, `snapshot_base`, and `make_patch` in [diffbase.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/diffbase.py); `record_metrics` in [metrics.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/metrics.py); tests in [test_engine_diffbase.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_engine_diffbase.py) and [test_engine_metrics.py](/Users/bernardopacheco/bkf-engine/agent-skills/dispatch-codex/harness/tests/test_engine_metrics.py). The required harness links are in [SKILL.md](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/SKILL.md).

**Difference from bash:** As the brief specifies, the legacy base format is unsupported; only tree snapshots are handled.

**Outside focus:** `agent-skills/skills/code-work/SKILL.md` and the existing run/lock engine files and tests appeared modified or untracked. I left them untouched.
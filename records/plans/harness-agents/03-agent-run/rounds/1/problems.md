## What I checked

- **Result:** Compared the CLI and runner in [agent.py](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/agent.py:50) and [cli.py](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/cli.py:31) with the brief; they provide `harness agent run` and `run_agent(...)`.
- **Scope:** The diff changes only `agent.py`, `cli.py`, `test_agent.py`, and the existing “Gate harness” paragraph in `SKILL.md`, as allowed.
- **Criteria:** Compared Codex arguments with `codex_run` in `scripts/lib-codex.sh` and reviewed the fake-agent tests in [test_agent.py](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/tests/test_agent.py:102). The provided gate result says both commands passed; I accepted it as binding and did not rerun them. A read-only invocation with a missing prompt returned exit 2.
- **Leaves ready:** The backend registry, foreground process execution, output paths, and signal-to-status mapping are present in `agent.py`; the CLI exposes the specified flags. The throwaway argument-swap failure demonstration is not checked, as the brief directs.

## Problems

- **Injection failure status:** The brief requires any `inject_rules` failure to print its message and exit 1. `run_agent` maps `InjectionError` to 1 but maps `OSError` to 2 ([agent.py](/Users/bernardopacheco/bkf-agents/agent-skills/dispatch-codex/harness/harness/agent.py:66)). Reproduction: invoking the CLI with a nonexistent `--prompt` returns 2. The tests cover a missing directive, but not an injection filesystem error.

VERDICT: back
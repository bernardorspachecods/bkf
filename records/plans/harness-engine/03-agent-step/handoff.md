## Verification

- `python3 -m unittest discover -s tests` — passed, 78 tests.
- `bkf skills` — passed; no issues.
- `git diff --check` — passed.
- In a throwaway copy, I changed the retry-time branch to keep the full sentence. The quota extraction test failed with the expected mismatch.

## Left ready

`Backend.quota_text`, `get_backend`, `tier_from_environment`, `run_agent_step`, and threaded `run_agents` are implemented. Tests cover quota extraction, notes and failure reasons, tier values, overlapping agents, skipped outputs, and failed-agent reporting.

## Difference and outside focus

No difference from the brief; no `.sh` files changed. I left unrelated pre-existing worktree changes untouched, including `agent-skills/skills/code-work/SKILL.md` and the other untracked engine test files.
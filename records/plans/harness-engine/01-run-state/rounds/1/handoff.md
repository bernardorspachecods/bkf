## Handoff

- `python3 -m unittest discover -s tests` passed: 58 tests. `bkf skills` passed with no issues.
- In a throwaway copy, I changed `is_active` so any live PID counted as active. `test_live_process_without_marker_is_stale` failed as expected.
- The run and lock modules, their tests, and the `Shared code` links are present and match the brief. No fixes were needed.
- The brief sets the lock marker default to `harness`; the shell uses `plan-run.sh`. The brief takes precedence.
- This sandbox blocks direct `ps` execution. The lock tests use mocked `ps` output while checking live child processes, so direct behavior against the system `ps` command remains unverified.
- Outside the focus: the pre-existing `agent-skills/skills/code-work/SKILL.md` change remains untouched.
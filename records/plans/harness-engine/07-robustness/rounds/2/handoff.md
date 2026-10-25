## Verification

- Added a regression test that sends SIGTERM after the agent starts but before it is registered. It failed before the fix because the agent process remained alive.
- `python3 -m unittest discover -s tests` — **112 tests passed**.
- `bkf skills` — **valid; 0 issues**.
- The earlier handoff records the SIGKILL detection failure demonstration in a throwaway copy.

## Result left ready

`run_agent` blocks the handled signals until the spawned process is registered, then restores the parent’s signal mask. The child restores its prior mask before exec, so it still responds to signals normally.

## Outside the focus

Pre-existing backend changes in `agent.py` and other pre-existing edits were left untouched. The fix relies on POSIX signal masks, consistent with the specified signal handling.
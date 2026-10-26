## Verification

- `python3 -m unittest discover -s tests` — **111 tests passed**.
- `bkf skills` — **valid; 0 issues**.
- In a throwaway copy, I removed `_resume_detection`; the SIGKILL test failed because the required detection note was missing.

## Result left ready

SIGTERM, SIGINT, and SIGHUP write an interruption note, terminate and reap live agent processes, release the lock, and return the signal exit code. Step exceptions write `crash.log`, record the crash, and return 1. Resume detects an attempt that ended without a terminal status line; interrupted or killed steps remain eligible to run again.

The referenced Bash runner has no equivalent signal, crash, or kill-detection handling; this implementation follows the brief for those behaviors.

## Outside focus

Pre-existing edits and untracked harness files were left untouched. The `agent.py` file also contains existing backend changes outside this unit.
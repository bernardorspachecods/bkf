## Verification

- Regression test for a missing prompt failed before the fix: expected exit 1, got 2.
- `python3 -m unittest discover -s tests` — **passed**, 46 tests.
- `bkf skills` — **passed**, 15 packages valid, 0 issues.
- The throwaway argument-swap demonstration remains **not checked**, as directed.

## Result left ready

Injection filesystem errors now print their message to standard error and return 1. The regression test confirms a missing prompt does not start the fake agent.

## Outside the focus

None.
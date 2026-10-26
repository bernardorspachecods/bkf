**Verification**

- The new absolute-directive regression test failed before the fix because Python injected the existing absolute file.
- `python3 -m unittest discover -s tests` — passed, 25 tests.
- `bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh` — passed.
- `bkf skills` — passed; 0 issues.

**Left ready**

- `inject_rules` now builds directive paths the same way as Bash, including when a directive starts with `/`.
- The regression test confirms Python and Bash both fail and leave the prompt unchanged in that case.

**Differences from the brief:** none. **Outside the focus:** none.
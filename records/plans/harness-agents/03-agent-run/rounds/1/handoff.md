## Verification

- `python3 -m unittest discover -s tests` — **passed**, 45 tests.
- `bkf skills` — **passed**, 15 packages valid, 0 issues.
- The new tests first failed against the pre-change CLI: `agent` was an invalid command.
- The throwaway-copy argument-swap demonstration is **not checked**, as directed in the unit note.

## Result left ready

- `harness agent run` and `harness.agent.run_agent(...)` invoke Codex in the foreground, inject prompt rules, capture all three output files, and propagate exit status or signal death.
- Tests cover argument order and quoting, tier and sandbox options, injection, output files, exit statuses, unsupported backends, and parity with `codex_run`.
- New harness files are linked from the existing Gate harness paragraph in [SKILL.md](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/SKILL.md).

## Outside the focus

None.
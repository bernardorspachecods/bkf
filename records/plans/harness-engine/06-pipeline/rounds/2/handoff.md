## Verification

- `python3 -m unittest discover -s tests` — **passed**, 105 tests.
- `bkf skills` from the repository root — **passed**. From the harness directory it failed because BKF treated that directory as the repository root; rerunning from the root passed.
- `git diff --check` — **passed**.
- Search of `H/engine/` for `plan` — **no matches**. The prior review’s search showed the criterion failing before these changes.
- No new failure demonstration was run for this correction. The previous round’s Stop/resume failure demonstration remains as reported in its handoff.

## Leaves ready

The engine-wide `plan` references are removed. I generalized the module descriptions, changed the temporary index prefix, and renamed the tier environment variable to `HARNESS_CODEX_TIER`, updating its focused test.

## Differences and gaps

Callers that set `PLAN_CODEX_TIER` must use `HARNESS_CODEX_TIER` now. That change removes the last workflow-specific reference from `H/engine/`.

## Outside the focus

I left other working-tree changes untouched.
# Unit: the shell functions call the harness CLI

## Result

`agent-skills/skills/dispatch-codex/scripts/lib-codex.sh` keeps the functions the scripts call, with the same names, arguments and behavior, but as thin wrappers over the CLI of the previous units:

- `codex_run <dir> <prompt-file> <out-prefix> [sandbox]` calls `harness agent run --dir ... --prompt ... --out-prefix ... --model "$model" --effort "$effort" --sandbox "${4:-workspace-write}"`, adding `--tier "$PLAN_CODEX_TIER"` only when that variable is set and non-empty, and returns its exit status.
- `inject_rules <prompt-file>` calls `harness inject`. It stays because `scripts/test-inject.sh` and the maintainers use it by name.
- `read_verdict <file>` calls `harness verdict read`; `checked_ok <file>` calls `harness verdict checked --min "$min_checked"`. Their output and exit statuses are those of the bash versions they replace.
- `run_agents` is unchanged (parallel launching stays in bash and calls `codex_run`).
- `lib-codex.sh` no longer sources `lib-inject.sh`, and `lib-inject.sh` is deleted. Update the header comment of `lib-codex.sh` to say what the file now is.
- Delete the parity tests added by the earlier units in `harness/tests/` (they compare the Python code with the bash functions that no longer exist; each carries a comment saying so). Every other test stays.

The scripts (`plan-run.sh`, `review-run.sh`, `council-run.sh`, `research-run.sh`, `phase-codex.sh`) and their tests are not edited, except that a test may change only where it names `lib-inject.sh` (a comment or a path). A test that fails for another reason means the wrappers differ from the old behavior: fix the wrapper.

## Receives

`harness inject`, `harness verdict read|checked`, `harness agent run` from the earlier units, with the flags and exit statuses in their briefs (read `harness/harness/cli.py` and the modules for the facts).

## Leaves ready

The scripts run through the harness for agent launch, injection and verdict reading, with no behavior change. The next unit documents it.

## Out of scope

Any script other than `lib-codex.sh` and the deletion of `lib-inject.sh`; the Python modules except to fix a defect you can show with a failing test (say so in the handoff); documents.

## Rules for this unit

- Do not run git commands that change state, `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file is reachable by links from `agent-skills/skills/dispatch-codex/SKILL.md`. Where a unit adds files under `harness/`, extend the existing "Gate harness" paragraph of that file with links to them and nothing else; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py` and `cli.py`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh
bash agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh
bash agent-skills/skills/dispatch-codex/scripts/test-review-run-gate.sh
bash agent-skills/skills/dispatch-codex/scripts/test-council-run-board.sh
bash agent-skills/skills/dispatch-codex/scripts/test-research-run-board.sh
bash agent-skills/skills/dispatch-codex/scripts/test-review-run-board.sh
test ! -e agent-skills/skills/dispatch-codex/scripts/lib-inject.sh
! grep -rn "lib-inject" agent-skills/skills/dispatch-codex/scripts
bkf skills
```

How these are shown to fail: in a throwaway copy make `codex_run` drop the `--tier` flag and show a test of the scripts fail (the existing tests record the Codex configuration); say in the handoff what you changed. If no existing test fails, add one that does.

## Criteria

- Each wrapper is a few lines and holds no logic that the CLI also holds.
- The old behavior is kept: variables read (`model`, `effort`, `min_checked`, `PLAN_CODEX_TIER`), messages on standard error, exit statuses.

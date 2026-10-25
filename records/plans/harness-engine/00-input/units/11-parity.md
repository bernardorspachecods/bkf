# Unit: the sequential plan runs through the engine, and the old tests prove it

## Result

Two changes: a wrapper `agent-skills/skills/dispatch-codex/scripts/plan-run-engine.sh` and an edit of `agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh`. `plan-run.sh` itself is not touched.

- The wrapper runs `python3 -m harness run <repo>/agent-skills/skills/dispatch-codex/workflows/plan.py "$@"` with `PYTHONPATH` set to the harness project, found from the wrapper's own location (like the `harness` function of `lib-codex.sh`), and passes the exit status through.
- `test-plan-run-gate.sh` learns two environment variables: `PLAN_RUN_UNDER_TEST` (the script to run; default `plan-run.sh`, so the default run is exactly what it is today) and `PLAN_RUN_SCOPE=sequential`, under which every case that needs a parallel group, the bridge, the disk check, an integration, `rebase-integration`, `accept-integration` or the old base format is skipped by a guard around its block. No assertion of an existing case may be edited, loosened or removed: the only edits are the guards, the use of the two variables, and the fake `ps` (in engine mode it must print a command containing `harness` for the registered pids, as the real `ps` does for the engine). A skipped case prints `SKIP <name>`, which does not count as a failure.
- Every sequential case (start, gate, rounds and their caps, escalation, pause, resume, finish, lock, quota, progress lines, board, metrics, the service tier, the final review, current and received briefs) must pass against the engine. When one cannot, do not change the case: report it as a difference in the handoff with the failing assertion, and stop that case with a `SKIP` that names the difference and says `ENGINE GAP`, so the list of gaps is greppable. A gap that comes from a bug in the engine or the definition is fixed there (minimally, and said in the handoff); a gap that comes from a behavior of the bash that looks wrong is a gap, not a fix. One such case is settled: when the runs root ends with a slash, the bash prints the run folder with a doubled slash (`root//name`), because it joins the root and the name as text. The engine does not copy that: `pipeline.py` prints `ctx.run.path`, and `_display_run_path` is removed. The two sequential assertions that expect the doubled slash (`progress stdout` and `board stdout`) become `SKIP ... ENGINE GAP` that names this difference, with the other gaps in the handoff.

The result to report in the handoff: the count of cases passing in engine mode, the list of `ENGINE GAP` skips with their reasons, and the count passing in the default mode (which must equal today's 144).

## Receives

The engine, the plan definition with its board and `finish`, from earlier units. Read `scripts/test-plan-run-gate.sh` in full before editing it.

## Leaves ready

A wrapper that runs the plan on the engine, and a test script that can run the sequential cases against it, with the list of gaps.

## Out of scope

Any change to `plan-run.sh`, to what the existing assertions check, or to the groups, bridge, disk and integration cases (they keep running against `plan-run.sh` by default).

## Rules for this unit

- Do not run git commands that change state in the repository you work in (no commit, stage, stash, reset, clean, checkout); throwaway repositories you create in temporary folders for tests are yours to use freely. Do not run `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name, except as the next rule says.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file under `agent-skills/skills/dispatch-codex/` is reachable by links from its `SKILL.md`. In its `## Shared code` section, extend the list of the harness files (the first paragraph names modules and tests as links) with a link to each new file of this unit and change nothing else in that file; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py`, `agent.py` and `cli.py`.
- The spec of every port is the bash in `agent-skills/skills/dispatch-codex/scripts/plan-run.sh` (function names are given) and its test `scripts/test-plan-run-gate.sh`. Where this brief and the bash differ, this brief wins; say so in the handoff. Files the run writes (names, formats, `status.log` lines) are kept character for character unless this brief says otherwise.
- All paths in this brief are relative to the repository root; `H` means `agent-skills/skills/dispatch-codex/harness/harness`, `T` means `agent-skills/skills/dispatch-codex/harness/tests`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
bash agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh
PLAN_RUN_UNDER_TEST=plan-run-engine.sh PLAN_RUN_SCOPE=sequential bash agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh
bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh
bash agent-skills/skills/dispatch-codex/scripts/test-review-run-gate.sh
```

How these are shown to fail: In a throwaway copy of the engine make `finish` skip the records copy and show the engine-mode case that checks the record fail (it is a sequential case); say in the handoff what you changed. Also show that a guard did not hide a failure: list the `SKIP` lines and confirm each belongs to the groups, bridge, disk or integration cases or is an `ENGINE GAP`.

## Criteria

- The default mode of `test-plan-run-gate.sh` still passes 144 cases and the diff of the file shows only guards, the two variables and the fake `ps`.
- No case was skipped to hide a failure unless it is labelled `ENGINE GAP` in the output and the handoff.

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


---
## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-agents/agent-skills/library/workflow-types/plan/plan-implementation.md (read-only). It says how to work inside the brief, what to verify and what the handoff holds.

## Rules
- The current directory is the repository: do the work here.
- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).
- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.
- You cannot reach the database from here (the database host does not resolve). To run something that needs it, ask the runner: `.plan-porteiro/ponte <command> [args...]`. It runs the command outside your sandbox and prints the output and the exit code. Only the `pnpm` scripts the repository allows for the bridge (see `.plan-run.json`) and the commands of the brief's gate, exactly as written, are accepted; anything else is refused, and every request is logged. Use it to read the data you need and to run the checks against the database.
- The brief has a `gate`. After you finish, the script runs those commands itself and sends the work back, without a review, if any fails. Run them yourself first when you can.

An earlier attempt at this unit was stopped. The checkout may already hold its work. Judge it against the brief, keep what is right and fix the rest.


---
## Rules from core-code-principles
The script added this text from ../../modules/core-code-principles.md, as the role guide asked.

# Core principles for code

## Building

- Work test first, in small slices, when the behavior is clear enough to specify (a feature or a bug fix). Write one focused test for one behavior and confirm it fails for the expected reason; make the smallest change that passes; refactor while green; then take the next behavior. For a bug, start with a regression test that reproduces it, and if it does not fail as expected, investigate before changing production code.
- Grow in layers and decide for the long term. Start from the smallest version that works end to end and extend it one verified step at a time; the scope of a step is small, but not the quality of its decisions. Do not accept a stopgap that only works for now and is meant to be replaced later.
- Reuse before building. Prefer an established pattern, a well-maintained library or an existing dependency to a new abstraction or a reimplementation. Check the repository and its dependencies before assuming a capability is missing; if a new shape is necessary, keep it local and explain why.
- Avoid these smells, with their fixes. A documented repository standard overrides them.
  - Duplicated logic in the change: extract it into one function.
  - Speculative generality, meaning abstraction, parameters or hooks nobody asked for: delete them and add them back when a real need shows.
  - Middle man, a function or class that only passes the call on: call the real target.
  - Shotgun surgery, one change forcing scattered edits: gather what changes together into one module.

## Verifying

- Let code decide what code can decide. Cover every required behavior with a test, type check or script whose result decides. A reading of the code is not evidence of what a run can show: an LLM reading LLM-written code is a probabilistic system checking another.
- A check must be able to fail. Show it failing once, against a wrong input or a throwaway copy of the code with the defect put back, before you rely on it.
- Never weaken an existing test or check to make work pass.
- What code cannot decide (visual quality, opinion, whether the spec is right) stays with a person and is reported as unverified, not as passed. No check for a changed behavior is a gap, not a pass.
- Report what ran and what came out, failures included. Work is done when the requested behavior is covered and the relevant tests and the nearest affected gate pass; work that is not verified is not done.
- The person or the approved plan decides what the tests specify. Prototypes, exploration, documentation, visual experiments and trivial configuration are exempt.

---
## Rules from gate
The script added this text from ../../modules/gate.md, as the role guide asked.

# The gate

- Code runs each command outside any agent, in its own process group.
- A time limit stops the whole process group and records exit code 124.
- The result contains the command, exit code and output tail in `gate.md`, a `gate.json`, and one log per command.
- Every command runs, even after one fails.
- A red result stands; no agent overrides it.
- No commands is a gap, not a pass.
- An agent that receives the gate takes it as given and does not run it again.

<!-- rules injected by the script -->

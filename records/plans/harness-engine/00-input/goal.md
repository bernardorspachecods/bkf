# Goal: the harness engine, with the sequential plan as its first workflow

## Intent (what and why)

The harness is the common code for agentic engineering: launching agents, checking them, keeping a run's state and
resuming it. Each workflow (plan, review, research, council) should define only what is its own: its steps, its briefs
and role guides, and a few functions. Today every `*-run.sh` repeats the same loop in bash, and the loop is where runs
break: the run that escalated three times on a contradictory brief, the run that died without a trace, the stop that
nobody was told about. Passing the loop to one tested engine is what lets the user brief a run once and leave it.

This plan builds the engine and proves it on the part of `plan-run.sh` that has no worktrees, bridge or integration.
`plan-run.sh` stays as it is until the engine reaches parity; the engine does not replace it in this plan.

## What exists at the end

- `harness run <path-to-definition> ...` runs a workflow written in Python. The engine knows no workflow by name:
  it is given the path of a definition file, and the definition of a workflow lives with that workflow's own files,
  not in the harness. A definition lists steps of four kinds
  (agents run in parallel; a review with verdict pass/back/escalate; a deterministic command; a coordinator pause)
  and the rules between them. No new language: a definition is Python data and functions.
- The engine owns, once: the run folder and `status.log`, which steps are done, rounds and their caps, the lock,
  pause and resume (`-p`, exit 3), the usage-limit stop, the board, and `finish`.
- The sequential plan (one unit per step, with its gate and its review loop, the final report, metrics) is a
  workflow definition (kept with the plan's own files, outside the harness package) run by the engine, with the same files, `status.log` lines, exit codes and board as `plan-run.sh`
  produces for the same input. Parallel groups, worktrees, the bridge, the disk check and the integration are not in it. What a sequential unit needs
  stays in: the base of each step and its diff (`snapshot_tree`, `make_patch`), metrics, and the final report.
- A second, trivial workflow definition (two steps, one with an agent, one with a command) in the engine's tests,
  to show the engine holds nothing that belongs to the plan.

## Done when

- The cases of `scripts/test-plan-run-gate.sh` that concern sequential plans (start, gate, rounds, escalation, pause,
  resume, finish, lock, quota, board, metrics) pass against the engine, unchanged in what they check; the cases about
  groups, bridge, disk and integration still pass against `plan-run.sh`, which is not touched.
- Every check shows it can fail, as the core principles require.
- A run killed in the middle leaves a state that `resume` completes, and the engine says so in `status.log`. (The run
  that died silently on this machine is the case: nothing in the old script records that a process was killed.)

## Out of scope

Worktrees, integration of parallel diffs and the base of a group's integration, the bridge, the disk check, the Claude backend, the other
workflows (review, research, council), renaming `dispatch-codex`, `run-codex.sh`, and any change to what a unit's
brief or a role guide says.

## Decisions already taken

- The base of a step and its diff are in scope (a sequential unit cannot be reviewed without them); the earlier draft of
  this goal listed "diff base" as out of scope by mistake. The older base format (a commit plus a list of untracked
  files) is not supported by the engine, which only starts new runs.
- The engine's package is `harness/harness/engine/`; the plan's definition and its helper modules live in
  `agent-skills/skills/dispatch-codex/workflows/`. A wrapper script `scripts/plan-run-engine.sh` runs the engine on the
  plan; `plan-run.sh` is not changed.
- The harness is Python, standard library only, a package inside `dispatch-codex`; existing tests are the spec.
- Four step kinds. Workflows are Python, not a configuration language.
- The old script and the engine coexist until parity; the user decides when the old one goes.
- Anything two workflows need goes to the harness, including capabilities only the plan uses today (as optional
  features, in later plans).

## Stop and ask the user when

A behavior of `plan-run.sh` that a test pins turns out to be wrong or contradictory (decide whether the engine keeps
it); a sequential case needs something from the group or bridge code; or the engine's shape would force a change to
the four step kinds.

## Settled with the user

- The entry point is `harness run <path-to-definition>`; the harness never names a workflow. A workflow's own command
  (`plan-run`, later) becomes a one-line wrapper that passes its definition's path. When parity is reached, whether the
  old script's name moves to the wrapper is the user's call, not this plan's.
- Detecting a run killed in the middle is part of this plan.

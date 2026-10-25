# Review

## The brief

# Unit: a run that is killed, crashes or is interrupted says so

## Result

Changes to `H/engine/pipeline.py` and `H/agent.py`, and tests. They answer a real failure: a run once died with exit code 144 in the middle of a gate, left no lock and no line in `status.log`, and nobody was told.

- **Signals.** While a run command works, SIGTERM, SIGINT and SIGHUP are handled: write the note `INTERRUPTED by signal <name> during step <k>` (or `during the final review`), stop the agent that is running (`H/agent.py` keeps a registry of the live agent processes; add `terminate_children(grace=2.0)`: SIGTERM, then SIGKILL after the grace period, then wait), release the lock, and exit with `128 + <signal number>`. The agent stays in the engine's process group, as `H/agent.py` documents.
- **Crashes.** An unexpected exception in a step writes the note `CRASHED: <exception type>: <message>` with the traceback in `<run>/crash.log`, releases the lock and exits 1 with `CRASHED at step <k>: <message>` and `See <run>/status.log` on standard output.
- **Killed without a trace.** SIGKILL cannot be caught, so `resume` detects it: when the last line of `status.log` that is not `resume` or a `resume:` note is not one that ends an attempt (starts with `STOPPED`, `PAUSED`, `READY`, `INTERRUPTED` or `CRASHED`, or is the header or the `start <name>` line of a run never started), `resume` writes, before the `resume` note, `resume: the previous attempt ended without a STOPPED, PAUSED, READY, INTERRUPTED or CRASHED line: it was killed or crashed. Steps not marked done run again.` The lock is already handled by the stale-lock rule.
- Resuming completes the work: a step interrupted or killed in the middle has no `.done-<k>` marker and runs again from its own resume rules.

Tests: `T/test_engine_robustness.py`, using the trivial workflow of `T/test_engine_pipeline.py` (reuse its helpers; move shared ones to a helper module under `T/` if needed) with a fake `codex` that sleeps: SIGTERM during a step (the note, exit 143, the lock gone, the fake agent process gone), SIGINT, SIGKILL then `resume` (the detection note, the lock replaced, the run finishing), a crash raised by a workflow step (the note, `crash.log`, exit 1), and a clean stop followed by `resume` writing no detection note.

## Receives

`pipeline.main`, the `Workflow` contract, the lock and the agent module from earlier units; read their code.

## Leaves ready

Signal handling, crash reporting and kill detection as above, for any workflow.

## Out of scope

Any `.sh` file, the plan's definition, changing what a clean run writes.

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
```

How these are shown to fail: Remove the detection (a throwaway copy) and show the SIGKILL test fail; say in the handoff what you changed.

## Criteria

- After any way a run command can end, `status.log` has a line that says how, or the next `resume` writes one.
- No stale agent process is left behind by a signal.


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/07-robustness/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-engine/07-robustness/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-agents/agent-skills/library/workflow-types/plan/plan-review.md (read-only). You are not the author of the work.

---
Your final message is the review, and nothing else. Begin it with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:
VERDICT: pass
VERDICT: back
VERDICT: escalate


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

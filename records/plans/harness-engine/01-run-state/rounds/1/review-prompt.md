# Review

## The brief

# Unit: the state of a run and its lock

## Result

The new package `H/engine/` (with `__init__.py`, a one-line docstring) holds two modules and their tests. They port, to Python, what `plan-run.sh` keeps in the run folder: `valid_name` (lib-codex.sh), `valid_pause`, `load_run`, `note`, `pause_here`, and the lock (`run_active`, `lock_run`, `unlock_run`).

`H/engine/run.py`:

- `class RunError(Exception)`: a message for the user; the CLI will print it and exit 1.
- `valid_name(name) -> bool` and `valid_pause(text) -> bool` (`none`, `each`, or step numbers like `2,4`), exactly the bash patterns.
- `class Settings` (a namedtuple: `model`, `effort`, `review_effort`), stored in the file `settings` as one line `"<model> <effort> <review_effort>\n"` (the third field may be empty, which leaves a trailing space, as `printf '%s %s %s\n'` does).
- `class RunDir`, built on a run folder `<root>/<name>`:
  - `RunDir.create(root, name, repo, settings, pause)`: refuses a bad name (`bad run name: NAME`) and an existing folder (`run already exists: PATH (finish it, or resume it)`); creates the folder (with parents) and writes `repo` (the path and a newline), `pause` (the text and a newline), `settings`, and `status.log` holding the header line `time\tevent`.
  - `RunDir.load(root, name)`: `bad run name: NAME`, `no such run: PATH`; reads `repo`, `settings` (when the file exists) and `pause`.
  - Attributes `path`, `name`, `repo`, `settings`, `pause`; methods `save_settings(settings)` and `set_pause(text)` (write the files).
  - `note(text)`: appends `<local time as %Y-%m-%dT%H:%M:%S>\t<text>\n` to `status.log`.
  - `is_done(marker)`, `mark_done(marker)`: the file `.done-<marker>`.
  - `pause_here(step: int) -> bool`: the bash semantics: false when `.paused-S<step>` exists; true for pause `each` or when the step is in the list; false for empty or `none`. `mark_paused(step)` writes `.paused-S<step>`.

`H/engine/lock.py`: `acquire(run_path, marker="harness") -> Lock` and `is_active(run_path, marker) -> bool`.

- The lock is the file `<run>/.lock` holding the pid, created exclusively. A lock is live when the pid is a number, the process exists, and `ps -p <pid> -o command=` prints a line containing `marker`; otherwise it is stale and `acquire` replaces it (two attempts, as the bash does). A live lock raises `RunError("run <name> is already being worked on by pid <pid>")`; failing twice raises `RunError("cannot lock <path>")`.
- `Lock.release()` removes the file only when it holds this process's pid. `Lock` is also a context manager.

Tests: `T/test_engine_run.py`, `T/test_engine_lock.py`: every message above, the exact `status.log` header and note format (the timestamp matched by a pattern), the settings line with an empty review effort, `pause_here` for `each`, a list, `none`, empty and an already-paused step, a lock held by a live process whose command contains the marker (a child `sleep` started with an argument containing it), a live process without it (stale), a dead pid (stale), exclusive creation, and release leaving another pid's lock alone.

## Receives

Nothing from other units. The bash to read: `valid_name` in `scripts/lib-codex.sh`; `note`, `load_run`, `pause_here`, `run_active`, `unlock_run`, `lock_run` and the `.paused`/`.done` markers in `scripts/plan-run.sh`.

## Leaves ready

The two modules as above. Every later unit of the engine imports them.

## Out of scope

One exception, already present in the checkout and not to be reverted: `agent-skills/skills/code-work/SKILL.md` shows a one-line change, quotes added around its `description`. A tool of the repository normalizes it that way; it is valid and unrelated to this unit. The implementer does not touch it and the reviewer does not count it as a change outside scope.

Any `.sh` file, the engine's other modules, the CLI, the pipeline.

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

How these are shown to fail: Break the stale-lock rule once in a throwaway copy (let a live pid without the marker count as active) and show the matching test fail; say in the handoff what you broke.

## Criteria

- Every message and file format above is character for character.
- The tests prove the marker check, not only the pid check: a live process that is not ours does not hold the run.


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/01-run-state/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-engine/01-run-state/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

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

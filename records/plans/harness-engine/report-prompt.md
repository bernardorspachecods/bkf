# Final review of the plan

## The goal

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


## The unit briefs, in order

### 01-run-state

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


### 02-diff-base

# Unit: the base of a step, its diff, and the metrics of a round

## Result

Two modules in `H/engine/`, with tests. They port `snapshot_tree`, `snapshot_base`, `make_patch` (tree format only) and `record_metrics` of `plan-run.sh`.

`H/engine/diffbase.py`:

- `snapshot_tree(checkout) -> str`: the id of a git tree holding the checkout as it is now, tracked and untracked files alike (ignored ones left out), built in a throwaway index file outside the repository (`GIT_INDEX_FILE`: `read-tree HEAD`, `add -A`, `write-tree`), so the real index and the working files are untouched and a commit made meanwhile changes nothing. On failure raise `RunError` from `H/engine/run.py`; remove the throwaway index in every case.
- `snapshot_base(directory, checkout)`: writes `<directory>/base` (the tree id and a newline) and `<directory>/base-format` (`tree` and a newline). On failure `RunError("cannot snapshot the checkout <path>")`.
- `make_patch(base_dir, out_file, checkout)`: snapshots the checkout now and writes `git diff --no-ext-diff <base> <now>` to `out_file`; the file is written even when empty. Only the tree format exists; the older base format of the bash is not supported.

`H/engine/metrics.py`: `record_metrics(run_path, unit, round_number, round_dir, start_epoch)` appends one line to `<run>/metrics.tsv`: `unit<TAB>round<TAB>minutes<TAB>steps<TAB>files<TAB>input_tokens`, where minutes is `(now - start_epoch) // 60`, steps counts lines of `<round_dir>/implement.events.jsonl` containing `"type":"item.completed"`, files counts lines of `<round_dir>/diff.patch` starting with `diff --git`, and tokens is the number after the last `"input_tokens":` in the events file; each is 0 when the file or the match is missing.

Tests: `T/test_engine_diffbase.py`, `T/test_engine_metrics.py`, in throwaway git repositories: a modified tracked file, a new untracked file and a deleted file appear in the diff; an ignored file does not; a commit made between the snapshot and the diff changes nothing in what the diff shows; `git status --porcelain` and `git diff --cached` are the same before and after a snapshot; an empty diff gives an empty file; the throwaway index is gone afterwards; the metrics line for a fixture with known counts, and for missing files.

## Receives

`RunError` from `H/engine/run.py` (unit 01 of this plan; read the code). The bash to read: `snapshot_tree`, `snapshot_base`, `make_patch`, `record_metrics` in `scripts/plan-run.sh`.

## Leaves ready

`snapshot_tree`, `snapshot_base`, `make_patch` and `record_metrics` as above.

## Out of scope

Any `.sh` file, the old base format, the commit-shaped snapshot (`snapshot_commit`) that parallel groups use, worktrees.

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

How these are shown to fail: Make `snapshot_tree` use the real index (a throwaway copy of the module) and show the test that checks `git diff --cached` fail; say in the handoff what you changed.

## Criteria

- The tree built is identical to the one the bash builds for the same checkout (a test compares the two on a fixture by running both).
- No test depends on the machine's global git configuration.


### 03-agent-step

# Unit: running agents as steps: quota, failures, parallel agents

## Result

Changes to `H/agent.py` and a new `H/engine/agentstep.py`, with tests. They port `quota_text`, `codex_failed`, the `PLAN_CODEX_TIER` default of `plan-run.sh`, and `run_agents` of `scripts/lib-codex.sh`.

- In `H/agent.py` the `Backend` base class gets `quota_text(self, events_path) -> Optional[str]` (default `None`); `CodexBackend` implements it as `quota_text` of the bash: the first line of the events file containing `hit your usage limit`; when it contains `try again at `, the text after that up to (and not including) the last `"` of the line; otherwise the text after `"message":"` up to the last `"`; `None` when no line matches. Add a module function `get_backend(name)` returning the class or `None` (use it in `run_agent` instead of reading the registry directly).
- `H/engine/agentstep.py`:
  - `tier_from_environment(environ=None)`: `PLAN_CODEX_TIER` unset gives `"fast"`, set but empty gives `None`, any other value gives that value.
  - `class StepResult` with `ok: bool`, `reason: str`, `quota: Optional[str]`.
  - `run_agent_step(run, label, directory, prompt_file, out_prefix, model, effort, sandbox, tier, reason_when_not_quota, backend="codex") -> StepResult`: calls `agent.run_agent`; status 0 gives ok; otherwise, when the backend finds a quota text in `<out_prefix>.events.jsonl`, the reason is `<label>: usage limit reached. QUOTA: <text> (see <events file>)` and `run.note("QUOTA: <text>")` is written; any other failure uses `reason_when_not_quota`.
  - `run_agents(phase_dir, output_file, folders, model, effort, tier, backend="codex") -> StepResult`: runs, in parallel, the agents among `folders` whose `<phase_dir>/<folder>/<output_file>` is missing or empty (each reads `brief.md` in its folder, writes `run.*` files there, sandbox `workspace-write`); waits for all; a folder that failed leaves a `failed` file `exit=<code> (see <folder>/run.stderr.log)`; afterwards, for every folder still without output, the reason collects `<folder>: <failed text, or "wrote no <output_file>">; ` and the `failed` files are removed, as `run_agents` of the bash does. Use threads or processes; the agents must overlap in time.

Tests: `T/test_engine_agentstep.py`, extending `T/test_agent.py` for the backend method, with a fake `codex` on `PATH` as in `T/test_agent.py`: each quota message form (with and without `try again at`, the typographic apostrophe of the real message), no match, the reason and the `QUOTA:` note, a failure that is not quota keeping the given reason, the tier values, two agents that overlap in time, an agent skipped because its output exists, a failed agent's reason text.

## Receives

`RunDir.note` from `H/engine/run.py` and `run_agent` from `H/agent.py` (read the code). The bash to read: `quota_text`, `codex_failed` and the tier line in `scripts/plan-run.sh`; `run_agents` in `scripts/lib-codex.sh`.

## Leaves ready

`Backend.quota_text`, `get_backend`, `tier_from_environment`, `run_agent_step`, `run_agents` as above.

## Out of scope

Any `.sh` file (`lib-codex.sh` keeps its own `run_agents`), the review loop, the unit loop.

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

How these are shown to fail: Return the wrong text from the `try again at` branch (keep the whole sentence) in a throwaway copy and show the matching test fail; say in the handoff what you changed.

## Criteria

- The quota text is character for character what the bash extracts, on the same fixtures.
- `run_agents` really overlaps: a test with two fake agents that each wait for the other's marker file fails when they run one after the other.


### 04-review

# Unit: one review of a round: attempts, form and verdict

## Result

`H/engine/review.py` with tests. It ports `do_review` of `plan-run.sh`.

`run_review(run, label, directory, round_dir, build_prompt, model, effort, tier, min_checked, previous_problems=None) -> ReviewResult` with `ReviewResult.verdict` (`pass`, `back` or `escalate`, or `None` on failure) and `.reason`:

- Up to 3 attempts. Each: delete `<round_dir>/review.last-message.md`; call `build_prompt(attempt)` (a callable supplied by the workflow that returns the prompt text) and write it to `<round_dir>/review-prompt.md`; run the agent with `run_agent_step`, sandbox `read-only`, output prefix `<round_dir>/review`, working directory `directory`. A failing agent stops the review with the quota-aware reason (`<label>: review exit=<code> (see <round_dir>/review.stderr.log)` when it is not quota).
- A review is usable when `review.last-message.md` is non-empty, `checked_ok(path, min_checked)` and `read_verdict(path)` both succeed (from `H/verdict.py`). An unusable one writes the note `<label>: review attempt <n> was not usable` and the next attempt starts.
- After 3 unusable attempts the result has no verdict and the reason `<label>: the reviewer left no usable review after <n> attempts (see <round_dir>/review.last-message.md)`.
- On success: copy `review.last-message.md` to `<round_dir>/problems.md`, write the verdict word to `<round_dir>/verdict` (with a newline) and write the note `<label>: round <basename of round_dir>: verdict <verdict>`.

Tests: `T/test_engine_review.py` with a fake `codex`: a usable review for each verdict; an unusable first attempt (no verdict line) then a usable one, and the note; three unusable attempts and the reason; a section `## What I checked` with too few lines counting as unusable; an agent failure (quota and not); that the files and notes are exactly as listed; that the prompt builder receives the attempt number.

## Receives

`run_agent_step` and `StepResult` from `H/engine/agentstep.py`, `RunDir` from `H/engine/run.py`, `read_verdict` and `checked_ok` from `H/verdict.py` (read the code). The bash to read: `do_review` and `review_run` in `scripts/plan-run.sh`.

## Leaves ready

`run_review` and `ReviewResult` as above.

## Out of scope

Any `.sh` file, the contents of the review prompt (the workflow builds it), the unit loop.

One change outside `review.py` is in scope: the exit status of a failing agent is only known after it runs, so `run_agent_step` in `H/engine/agentstep.py` must let `reason_when_not_quota` hold the placeholder `<exit>`, which it replaces with the exit status (it is how `review exit=<code>` gets its code), and must drop trailing newline characters from the quota text before it goes into the note and the reason. Make these two edits in `agentstep.py` and cover each with a test in `T/test_engine_agentstep.py`; they are fixes to the previous unit that this unit's review exposed. The reviewer does not count them as outside scope.


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

How these are shown to fail: Count the attempts wrongly (allow a fourth) in a throwaway copy and show the matching test fail; say in the handoff what you changed.

## Criteria

- Files, notes and reasons are character for character those of the bash.
- The module knows nothing about plans, units or gates.


### 05-unit-loop

# Unit: the unit loop: implement, gate, review, back

## Result

`H/engine/loop.py` with tests. It ports the round loop of `run_unit` of `plan-run.sh`, without the bridge (`porteiro_*`), and `write_gate_problems`.

`run_unit_loop(run, unit, checkout, *, source_brief, hooks, settings, tier, limits, step=None, base_from=None) -> LoopResult` with `LoopResult.ok` and `.reason`:

- `hooks` is an object the workflow supplies, with these methods (a base class `UnitHooks` in `loop.py` documents them and raises `NotImplementedError`): `implement_prompt(brief, round_number, resumed, previous_problems, previous_handoff) -> str`; `review_prompt(brief, patch, previous_problems, attempt, gate_file) -> str` (the last two as in the bash: `previous_problems` empty or a path, `gate_file` empty or the path of the round's `gate.md`); `gate_commands(brief) -> list[str]`; `progress(text)`; and `around_implement(checkout, unit, base, brief)`, a context manager entered around the implementer's run, which does nothing by default (the future place of the bridge).
- `limits` holds `max_rounds`, `max_gate_rounds`, `gate_timeout`, `min_checked`. `step` is the step number used in progress text (`S<step>`); `base_from` is the path of a file holding a tree id to use as the unit's base (or `None`).
- Every behavior of the bash round loop is kept, with these files and texts character for character: `<run>/<unit>/` with `base`, `base-format`, `brief.md` (a copy of `source_brief`), `status` (`implementing round N`, `gate round N`, `reviewing round N`, `passed`, `escalated`), `handoff.md`, `final.patch`, and `rounds/N/` with `implement-prompt.md`, `implement.*`, `handoff.md`, `diff.patch`, `gate.md`, `gate.json`, `gate-<n>.log`, `problems.md`, `verdict`, `review*`; the resume handling (`rounds` moved to `rounds.attempt-<epoch>` when the unit already has a `base`, `resumed` passed to the implement prompt, the base taken again from `base_from` when given and kept otherwise); the gate through `H/gate.py` (`run_gate`, timeout from `limits`, out dir the round); `write_gate_problems` (the exact text of the bash, `VERDICT: back` last, and the verdict file `back`); counting gate failures against `max_gate_rounds` and reviewer `back`s against `max_rounds` apart; the empty-diff stop; the implementer failing (quota-aware, through `run_agent_step`, reason `<unit>: implementer exit=<exit> (see <rd>/implement.stderr.log)`, where `<exit>` is the placeholder `run_agent_step` replaces with the exit status), leaving no handoff (`<unit>: implementer left no handoff`); the reasons for each escalation; `record_metrics` after each implementation round.
- Notes (`run.note`) and progress texts are exactly the bash's, for example `S1 unidade 01-unit · ronda 2 · gate FAIL` (progress) and `01-unit round 2: gate` (note); the progress text is built from `step`. The review of each round goes through `run_review` (`H/engine/review.py`) with `hooks.review_prompt` as the prompt builder.

Tests: `T/test_engine_loop.py`, with a fake `codex` that dispatches on the prompt (an implementation changes a file, a review answers the verdict the test sets) in a throwaway git repository and a stub `UnitHooks`: pass on the first round; gate red then green; gate always red up to the cap; reviewer back then pass; reviewer back up to the cap; reviewer escalate; empty diff; implementer failing, with quota and without; no handoff; unusable reviews; resume after a stop (the `rounds.attempt-*` folder, `resumed` true in the prompt); the files, statuses, notes and progress texts of a green round and a red-then-green round compared with expected text; `around_implement` entered and left around the implementer.

## Receives

From earlier units: `RunDir`, `RunError` (`H/engine/run.py`); `snapshot_tree`, `snapshot_base`, `make_patch` (`H/engine/diffbase.py`); `record_metrics` (`H/engine/metrics.py`); `run_agent_step`, `StepResult`, `tier_from_environment` (`H/engine/agentstep.py`); `run_review` (`H/engine/review.py`); `run_gate` (`H/gate.py`). Read their code for the exact signatures; where this brief's names differ, the code wins. The bash to read: `run_unit`, `write_gate_problems`, `codex_failed`, `do_review` in `scripts/plan-run.sh`.

## Leaves ready

`run_unit_loop`, `LoopResult`, `UnitHooks` as above.

## Out of scope

Any `.sh` file, the bridge, worktrees, parallel groups, the contents of prompts (hooks supply them), the pipeline.

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

How these are shown to fail: Count a gate failure as a reviewer round (a throwaway copy) and show the test about the two caps fail; say in the handoff what you changed.

## Criteria

- The loop knows nothing about plans, briefs' format, prompts' wording or the bridge: everything of that kind comes through `hooks`.
- Files, statuses, notes, reasons and progress texts match the bash character for character.


### 06-pipeline

# Unit: the pipeline: steps, pauses, commands and the CLI

## Result

`H/engine/workflow.py`, `H/engine/pipeline.py`, a `run` command in `H/cli.py`, and tests. It ports `pipeline`, `cmd_start`, `cmd_resume`, `cmd_status`, `cmd_board`, the generic part of `cmd_finish` and the lock use of `plan-run.sh`, as an engine that knows no workflow by name.

`H/engine/workflow.py` defines the contract a workflow definition fulfils:

- `class Stop(Exception)` with `.reason`.
- `class Step` with `.number` (an int, or the string `final` for the last step), `.label` and `run(self, ctx)`, which raises `Stop` when it stops.
- `class Context` with `run` (the `RunDir`), `settings`, `repo`, `progress(text)` and `note(text)`. `progress` writes `[<workflow.name>] <text>` and a blank line to standard error, then the workflow's board (when `board` returns text), as the bash `progress` does.
- `class Workflow` (a base class; methods raise `NotImplementedError` unless a default is stated): `name`; `command` (the name the user types, used in hints, for example `plan-run.sh`); `usage_start` (the usage text after `start [options] <name>`); `repo_hint` (text for the error when not inside a git repository); `validate_start(args)` (no side effect; raises `RunError`); `start(ctx, args)` (writes the run's inputs and the start notes); `steps(ctx) -> list[Step]`; `final_step(ctx) -> Optional[Step]`; `after_step(ctx, step)` (default nothing); `board(ctx) -> str` (default empty); `fix_hint(ctx) -> str` (the text of the second `STOPPED` note, default `Read the rounds in <run>, then: <command> resume <name>`); `ready_path(ctx) -> str`; `finish(ctx)` (keeps the record; called for `finish` without `--discard`); `commands() -> dict` of extra subcommand names to callables taking the arguments after the name.

`H/engine/pipeline.py` runs it. Its entry is `main(definition_path, argv) -> int`, which loads the definition (a Python file path; add its directory to `sys.path` first; the file defines `WORKFLOW`, an instance of `Workflow`) and dispatches `start`, `resume`, `status`, `board`, `finish`, and the workflow's extra commands; any other name prints `usage: <command> start|resume|status|board|finish ...`. Behavior, ported from the bash and kept character for character in files, `status.log` notes, standard output text and exit codes:

- `start [-m model] [-e effort] [-r review-effort] [-p checkpoints] <name> <workflow arguments>`: validate the name and the checkpoints (messages as the bash's), call `validate_start`, find the repository (`git rev-parse --show-toplevel`, else die with `repo_hint`), refuse an existing run, create the `RunDir`, take the lock, call `start`, print the board to standard error, then the pipeline. Defaults: model `gpt-6-luna`, effort `xhigh`, review effort empty.
- `resume [options] <name>`: load, lock, apply the options (the checkpoints replace the list; `none` clears it), refuse outside the run's repository, rewrite the settings, note `resume`, run the pipeline.
- The pipeline prints `Run folder: <path>`; for each step not done: note `start step <k>: <label> (<model> <effort>)`, `progress`, the step, then `done step <k>` and a progress line `S<k> concluído`, `after_step`, and the pause check (note `PAUSED after step <k>: read <run>, then: <command> resume <name>`, progress `S<k> pausa`, standard output `PAUSED after step <k> (<label>). Read it in <run>, then: <command> resume <name>` and `See <run>/status.log`, exit 3). A step that raises `Stop` notes `STOPPED at step <k>: <reason>` and `workflow.fix_hint`, progress `S<k> parou`, prints `STOPPED at step <k> (<label>): <reason>` and `See <run>/status.log`, exit 1. After the steps, the final step (when any) with the notes `start final review (<model> <effort>)`, `done final review`, `STOPPED at the final review: <reason>`, progress `final · revisão`, `final · concluído`, `final · parou`; at the end the note `READY: report at <ready_path>` and standard output `READY: <ready_path>` and `See <run>/status.log`, exit 0. Marker files: `.done-S<k>` for steps (through `is_done`/`mark_done`) and `.done-report` for the final step. Progress text is prefixed with the step number as `S<k> ...`.
- `status <name>` prints `status.log`; `board <name>` prints the board to standard output; `finish [--discard] <name>`: refuses while a live process holds the lock (`run <name> is being worked on by pid <pid>: finish it when it stops`), `--discard` removes the folder and prints `Removed <path>`, otherwise it refuses with `there is no final review in this run: nothing to keep` when the workflow's `ready_path` file is missing and calls `workflow.finish(ctx)`.
- The lock is taken with `acquire(run_path, "harness")` of `H/engine/lock.py` and released when the command ends, whatever the exit.
- `RunError` anywhere prints `Error: <message>` to standard error and exits 1, like `die`.

`H/cli.py` gets `harness run <definition-path> <command> ...`, calling `pipeline.main` and returning its status.

Tests: `T/test_engine_pipeline.py` with a trivial workflow defined in the test (two steps and a final step: one runs an agent step with the fake `codex`, one runs a deterministic command through `harness gate`), no plan: a full run (files, notes, output, exit 0), pause with `-p each` and resume (exit 3, then 0), a step that raises `Stop` (exit 1, notes) and resume after the cause is fixed, an existing run refused, a second `resume` refused while the first holds the lock, `finish` refused while locked, `finish --discard`, the usage text, `status` and `board`, and that nothing in `H/engine/` mentions `plan`.

## Receives

From earlier units: `RunDir`, `RunError`, `valid_name`, `valid_pause` (`H/engine/run.py`); `acquire`, `is_active` (`H/engine/lock.py`); the agent step (`H/engine/agentstep.py`). Read their code. The bash to read: `pipeline`, `cmd_start`, `cmd_resume`, `cmd_status`, `cmd_board`, `cmd_finish`, `lock_run`, `progress` in `scripts/plan-run.sh`.

## Leaves ready

`Workflow`, `Step`, `Context`, `Stop` and `pipeline.main`, and `harness run <definition-path> ...`, as above. The plan's definition (later units) is a `Workflow`.

## Out of scope

Any `.sh` file, the plan's definition and prompts, the board's content, the records copy of `finish`, detecting a killed run and signal handling (the next unit), worktrees, groups.

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

How these are shown to fail: Make a step that raises `Stop` still count as done (a throwaway copy) and show the test about resume after a stop fail; say in the handoff what you changed.

## Criteria

- Nothing in the engine mentions a workflow by name: names, hints and messages reach it through the `Workflow` attributes.
- Notes, output text and exit codes match the bash character for character, for the cases the tests list.


### 07-robustness

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


### 08-plan-inputs

# Unit: the plan's inputs: plan.txt, briefs, gate commands and prompts

## Result

`agent-skills/skills/dispatch-codex/workflows/plan_inputs.py` (a plain module; the engine will put its folder on `sys.path`) with tests `T/test_workflow_plan_inputs.py` (add the folder to the test's path). It ports, from `plan-run.sh`, what the plan does with its inputs, without any run or agent:

- `parse_plan(plan_path)`: reads `plan.txt` as `cmd_start` does (comments after `#`, blank lines, paths relative to the file's folder, each brief non-empty, unit name valid from the file name) and returns the steps. This engine runs one unit per step: a line with several briefs raises `RunError("step <n> has several briefs; this engine runs one unit per step")`. An empty plan raises `RunError("plan.txt has no step")`; the other messages are the bash's (`missing or empty unit brief: <w>`, `bad unit name (from the file name): <w>`).
- `write_inputs(run_path, goal_path, steps)`: copies the goal to `00-input/goal.md` and each brief to `00-input/units/<NN>-<name>.md` (`NN` from 01, two digits), and writes `00-input/order` (one unit name per line).
- `gate_commands(brief_paths) -> list[str]`: the commands of every fenced block tagged `gate`, one per line, blank lines and `#` lines ignored, trimmed, without duplicates, in order (the awk of the bash; a fence without the tag is ignored; two blocks are both read).
- `gates_command(args)`: the `gates` subcommand (`cmd_gates`): from a `plan.txt` path or a run name, prints each unit's name and its commands as `  $ <command>`, or `  NO GATE: only a reviewer checks this unit`, a blank line after each, and returns 1 when a unit has no gate.
- The brief helpers `brief_current`, `brief_differs`, `gate_differs`, `print_unit_brief` (exact text of the bash, including the "Brief received by the implementer" section).
- The three prompts as functions returning text: `implement_prompt(guides, brief, round_number, resumed, previous_problems, previous_handoff)`, `review_prompt(guides, brief, patch, previous_problems, attempt, gate_file)` and `report_prompt(run_path, guides)` (the text `run_report` writes into `report-prompt.md`, without groups or integrations). `implement_prompt` is the bash's **without the bridge bullet** (the one about `.plan-porteiro/ponte`); everything else is character for character.
- `guides_path(environ, here)`: `PLAN_GUIDES` when set, else `<git top-level of here>/agent-skills/library/workflow-types/plan`.

Tests: `T/test_workflow_plan_inputs.py`: each parse case and message; the order file and unit names; the gate parser on a brief with two blocks, a fence without the tag, comments, blank lines and duplicates; the `gates` output and its exit status for a plan and for a run; the brief helpers with a current brief that differs from the received one; the three prompts compared with expected text (write the expected text from reading the bash; for `implement_prompt` also assert the bridge bullet is absent) for a first round, a resumed first round, and a round with previous problems and handoff.

## Receives

`RunError` (`H/engine/run.py`). The bash to read: `cmd_start` (its validation and copying), `gate_commands`, `cmd_gates`, `brief_current`, `check_briefs`, `brief_differs`, `gate_differs`, `print_unit_brief`, `implement_prompt`, `review_prompt`, `run_report` (the prompt only) in `scripts/plan-run.sh`.

## Leaves ready

The functions above, in `workflows/plan_inputs.py`. The next unit (the plan's definition) imports them.

## Out of scope

Any `.sh` file, `H/` (the engine), the board, the report's execution, `finish`, groups and the bridge.

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

How these are shown to fail: Drop the dedupe in `gate_commands` (a throwaway copy) and show the matching test fail; say in the handoff what you changed.

## Criteria

- Prompts and printed text are character for character the bash's, apart from the removed bridge bullet and the new several-briefs message.
- The module imports nothing from the engine except `RunError`.


### 09-plan-steps

# Unit: the plan as a workflow: start, units, final report

## Result

`agent-skills/skills/dispatch-codex/workflows/plan.py` defining `WORKFLOW`, a `Workflow` (`H/engine/workflow.py`) for the sequential plan, with tests `T/test_workflow_plan.py`. It ports `cmd_start`'s non-validation part, `run_step` (the single-unit branch), `run_report`, the step bookkeeping of `pipeline`, and `cmd_gates` wiring.

- `name = "plan"`, `command = "plan-run.sh"` (the name users type; the hints keep it), `usage_start = "<goal.md> <plan.txt>"` with the messages of the bash.
- `validate_start(args)`: two arguments; goal and plan non-empty (`missing or empty goal: <path>`, `missing or empty plan: <path>`); the plan parsed with `plan_inputs.parse_plan`; `codex` found on `PATH` (`codex not found`); the role guides folder exists (`no role guides at <path> (set PLAN_GUIDES)`).
- `start(ctx, args)`: `write_inputs`; the base of the whole plan (`<run>/plan-base`, with `snapshot_base`); the notes `start <name> (<model> <effort>, review <review effort or effort>, max <max rounds> rounds, <k> step(s), <i> unit(s), repo <repo>)` and `unit <u> has no gate: only a reviewer checks it`. The `.plan-run.json` notes are not written (no bridge).
- `steps(ctx)`: one `Step` per line of `00-input/order`, labelled with the unit name; running it calls `run_unit_loop` with hooks built on `plan_inputs` (prompts, `gate_commands`, `progress`), `step=<k>`, `base_from` = `state-after-S<k-1>` or, for the first step, `plan-base/base` (a step without such a file takes a fresh snapshot, as the bash), the effort of reviewers from the settings, the limits from `PLAN_MAX_ROUNDS` (3), `PLAN_MAX_GATE_ROUNDS` (5), `PLAN_GATE_TIMEOUT` (900), `PLAN_MIN_CHECKED` (3); the tier from `tier_from_environment`. A unit whose `.done-<unit>` marker exists is not run again; it writes the marker when it passes. `after_step` writes `state-after-S<k>` (`snapshot_tree`, removing the file when the snapshot fails). Progress lines `S<k> início · unidade <unit>` before a step.
- `final_step(ctx)`: the final report: the current briefs are checked (`check_briefs` of the bash, with its reason), `cumulative.patch` is made against `plan-base`, `report-prompt.md` written with `plan_inputs.report_prompt`, a read-only agent run with the review effort, quota-aware failure reason `final review exit=<code> (see <run>/report.stderr.log)`, `final review wrote no report`, and `report.md` copied from `report.last-message.md`. `ready_path` is `<run>/report.md`; `fix_hint` is the bash's second `STOPPED` text (`Read the rounds in <run> ... the briefs in <run>/00-input/units/, or the checkout ... then: plan-run.sh resume <name>`). `commands()` returns `{"gates": plan_inputs.gates_command}`.
- `board` and `finish` are not part of this unit: return an empty board and have `finish` raise `NotImplementedError` with a message naming the next unit.

Tests: `T/test_workflow_plan.py`, running `pipeline.main` on this definition in throwaway repositories with the fake `codex` of `scripts/test-plan-run-gate.sh` (reuse its logic, written in Python in a shared helper under `T/`): a one-unit plan to the end (the files `00-input`, `<unit>/`, `report.md`, `state-after-S1`, `cumulative.patch`, `status.log` lines, output, exit 0); two units where the second starts from the state the first left; a unit with a failing gate; a pause and resume; a current brief that disappears before the final review; the several-briefs refusal; the messages of `validate_start`.

## Receives

From earlier units: the engine (`H/engine/*`: `Workflow`, `Step`, `Context`, `Stop`, `pipeline.main`, `run_unit_loop`, `run_review`, `run_agent_step`, `tier_from_environment`, `snapshot_base`, `snapshot_tree`, `make_patch`) and `workflows/plan_inputs.py`; read their code. The bash to read: `cmd_start`, `run_step`, `run_report`, `pipeline`, `run_unit` (for the hooks) in `scripts/plan-run.sh`.

## Leaves ready

`WORKFLOW` in `workflows/plan.py`, runnable with `python3 -m harness run workflows/plan.py <command> ...` (the board and `finish` come next).

## Out of scope

Any `.sh` file, the board, `finish` and the records copy, groups, the bridge, changes to the engine (when the engine is wrong, fix it minimally and say so in the handoff).

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

How these are shown to fail: Make the first step take its base from a fresh snapshot instead of `plan-base` (a throwaway copy) and show the test that checks the diff of step 2 fail; say in the handoff what you changed.

## Criteria

- Every file the run writes and every `status.log` line matches the bash's for the cases the tests cover, apart from the bridge notes.
- Nothing plan-specific was added to `H/`.


### 10-plan-board-finish

# Unit: the plan's board, its summary and its record

## Result

Changes to `agent-skills/skills/dispatch-codex/workflows/plan.py` (and a helper `plan_board.py` next to it), with tests `T/test_workflow_plan_board.py`. They port `board` (with `board_emit`, `board_rounds`, `board_state_row`), `write_summary` and the record copy of `cmd_finish`, for the sequential plan (no parallel headings, no integration rows).

- `Plan.board(ctx)` returns exactly the text the bash `board` prints for a sequential run: the header `Plano <name> · <n> unidades · início HH:MM → agora HH:MM`, a blank line, `Passo <k>`, one row per unit with its icon (`✓`, `◐`, `○`, `✗`, `↩`) and state text (`pendente`, `implementação · ronda N`, `gate falhou · ronda N a implementar`, `devolvida · ronda N a implementar`, `passou · N ronda(s)`, `escalada`, the review and gate states and every other state of `board_state_row` that applies to a single unit), blank line after each step, then the row `Revisão final` with `passou`, `parou`, `revisão` or `pendente`. Labels are padded as the bash does. It reads only files under the run folder. Progress (`Context.progress`) shows this board on standard error; `board <name>` prints it on standard output.
- `Plan.finish(ctx)`: writes `status.md` (the summary of `write_summary`: the table of steps, units, rounds and last verdict, the metrics table when `metrics.tsv` exists, and the closing line), then keeps the record exactly as `cmd_finish` does: copy the run into `<repo>/records/plans/<name>` excluding the same names (`*.events.jsonl`, `*.stderr.log`, `*.last-message.md`, files starting with `.`, `*.attempt-*`, `untracked-*.txt`, `base`, `plan-base`, `*.worktree.log`, `repo`, `pause`, `settings`, `status`, `status.log`), verify the copy against the source with the same exclusions, remove the run, print `Kept in <dest>; removed <run>`, refuse with `already exists: <dest>` and `run finish inside the plan's repository: <repo>` where the bash does, and print the `records_note` text when the repository's `AGENTS.md` does not mention `records/`. Do it in Python (no `rsync`).

Tests: `T/test_workflow_plan_board.py`: the board of a run at each stage (not started, a unit implementing, in gate, in review, back to implement after a red gate, back after a review, passed, escalated, final review running, stopped, done) compared with expected text (each case builds the run files by hand and by a real run with the fake `codex`); `finish` keeping the record (the excluded names are absent, the others present, the run folder gone, the message), refusing when the destination exists, and the note about `AGENTS.md`; the `status.md` text for a two-unit run with metrics.

## Receives

The sequential plan workflow (`workflows/plan.py`, `workflows/plan_inputs.py`) and the engine from earlier units; read their code. The bash to read: `board`, `board_emit`, `board_rounds`, `board_state_row`, `write_summary`, `cmd_finish`, and `records_note` in `scripts/lib-codex.sh`.

## Leaves ready

A plan definition with its board, summary and record, complete for the sequential plan.

## Out of scope

Any `.sh` file, the group and integration rows, the bridge, changes to the engine other than a minimal fix reported in the handoff.

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

How these are shown to fail: Drop `gate falhou` (show `devolvida` for a red gate, a throwaway copy) and show the matching board test fail; say in the handoff what you changed.

## Criteria

- The board text is character for character the bash's for sequential runs, for every state the tests list.
- `finish` keeps the same files the bash keeps.


### 11-parity

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


### 12-docs

# Unit: document the engine

## Result

Documentation only, in `agent-skills/skills/dispatch-codex/SKILL.md`: extend the `## Shared code` section (and, if that is the better place, add a section `## The engine`) so it says, for a reader who has never seen it:

- what the engine is (the common loop for workflows: run folder and `status.log`, rounds and caps, lock, pause and resume, usage-limit stop, kill detection, board, finish) and what a workflow contributes (a `Workflow` definition: steps, briefs and role guides, small functions); that the harness knows no workflow by name;
- the commands: `harness run <definition-path> start|resume|status|board|finish ...` and a workflow's extra commands, with the options and the exit statuses (0, 1, 3, 128+signal);
- the `Workflow` contract in a short table (the methods, what each is for), the four step kinds as the engine implements them and where the unit loop fits;
- the sequential plan as the first workflow, `scripts/plan-run-engine.sh`, that `plan-run.sh` still exists and is the one that supports groups, worktrees and the bridge, and what is not in the engine yet (point to the `ENGINE GAP` list printed by the parity test run, do not copy it);
- how it behaves when a run is killed: what is written, what `resume` says, what the user does.

Keep every other part of the file as it is. Every path, flag, exit status and message in the new text must exist in the code. Link every new file of the engine and the workflows (`bkf skills` fails if one is unlinked).

## Receives

The engine and the plan workflow from all earlier units; read their code and `scripts/plan-run-engine.sh`, and run `PLAN_RUN_UNDER_TEST=plan-run-engine.sh PLAN_RUN_SCOPE=sequential bash agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh | grep 'SKIP'` yourself to see the gaps.

## Leaves ready

A `dispatch-codex/SKILL.md` that matches the code.

## Out of scope

Any code or test; other documents.

## Rules for this unit

- Do not run git commands that change state in the repository you work in (no commit, stage, stash, reset, clean, checkout); throwaway repositories you create in temporary folders for tests are yours to use freely. Do not run `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name, except as the next rule says.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file under `agent-skills/skills/dispatch-codex/` is reachable by links from its `SKILL.md`. In its `## Shared code` section, extend the list of the harness files (the first paragraph names modules and tests as links) with a link to each new file of this unit. This unit is the last one, so the "change nothing else in that file" restriction of the earlier units does not apply: the engine documentation this unit's Result asks for goes in `SKILL.md`.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py`, `agent.py` and `cli.py`.
- The spec of every port is the bash in `agent-skills/skills/dispatch-codex/scripts/plan-run.sh` (function names are given) and its test `scripts/test-plan-run-gate.sh`. Where this brief and the bash differ, this brief wins; say so in the handoff. Files the run writes (names, formats, `status.log` lines) are kept character for character unless this brief says otherwise.
- All paths in this brief are relative to the repository root; `H` means `agent-skills/skills/dispatch-codex/harness/harness`, `T` means `agent-skills/skills/dispatch-codex/harness/tests`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
bkf validate .
```

How these are shown to fail: Before editing, run `grep -c "harness run" agent-skills/skills/dispatch-codex/SKILL.md` and note the number; after, it must be higher; report both in the handoff.

## Criteria

- Every flag, file name, message and exit status in the new text exists in the code.
- Nothing outside the sections named above differs from before the edit.


## Inputs (read-only)
- The diff of the whole plan, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/cumulative.patch
- The reviews of each unit and of each parallel group: /Users/bernardopacheco/.plan-runs/harness-engine/01-run-state/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/02-diff-base/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/03-agent-step/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/04-review/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/05-unit-loop/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/06-pipeline/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/07-robustness/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/08-plan-inputs/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/09-plan-steps/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/10-plan-board-finish/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/11-parity/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/12-docs/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-engine/S*-integration/rounds/*/problems.md
- The repository is your current directory. Open it read-only. Do not change anything. Do not open the handoffs.

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-agents/agent-skills/library/workflow-types/plan/plan-review.md (read-only), section "The final review". You are not the author of the work.

---
Your final message is the report, and nothing else.


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

# Review

## The brief

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


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-engine/02-diff-base/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-engine/02-diff-base/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

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

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


---
## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-harness/agent-skills/library/workflow-types/plan/plan-implementation.md (read-only). It says how to work inside the brief, what to verify and what the handoff holds.

## Rules
- The current directory is the repository: do the work here.
- Do not run git commands that change state (no commit, stage, stash, reset, clean, checkout).
- Do not write the handoff to a file. Your final message is the handoff, in the form the guide gives, and nothing else.
- You cannot reach the database from here (the database host does not resolve). To run something that needs it, ask the runner: `.plan-porteiro/ponte <command> [args...]`. It runs the command outside your sandbox and prints the output and the exit code. Only the `pnpm` scripts the repository allows for the bridge (see `.plan-run.json`) and the commands of the brief's gate, exactly as written, are accepted; anything else is refused, and every request is logged. Use it to read the data you need and to run the checks against the database.
- The brief has a `gate`. After you finish, the script runs those commands itself and sends the work back, without a review, if any fails. Run them yourself first when you can.

The script's gate or a reviewer sent your work back. The work from the earlier round is in the checkout. Fix the problems below and only those, keeping what was fine, and verify again.

Problems from the gate or the review:

## What I checked

- **Result:** Compared the wrappers and deleted `lib-inject.sh` in [lib-codex.sh](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/scripts/lib-codex.sh:15) with the brief. `codex_run` injects through the agent CLI, which calls injection before launch in [agent.py](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/agent.py:60).
- **Scope:** Compared changed files in the supplied diff with the brief’s scope limits. The diff also edits [SKILL.md](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/SKILL.md:99) and a test comment in [test_inject.py](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/tests/test_inject.py:97).
- **Criteria:** Checked argument forwarding, tier handling, verdict wrappers, and unchanged `run_agents` in `lib-codex.sh`; accepted the supplied green gate without rerunning it. The throwaway failure demonstration is not checked, as directed.
- **Leaves ready:** Confirmed the CLI wrappers and deletion are present in the diff; the harness agent and verdict commands are implemented in `harness/`.

## Problems

- **Scope:** The brief puts documents out of scope, but the diff updates the documentation in `SKILL.md`. No harness files were added that would require the specified link update.
- **Scope:** The brief allows test edits only to references naming `lib-inject.sh` (or deletion of the specified parity tests). The retained test comment at `test_inject.py:97` was rewritten even though it did not name `lib-inject.sh`.

VERDICT: back

Your handoff from the previous round, for you to resume from:

## Verification

All gate commands passed: 43 harness tests, the injection test, the plan and review gate tests, all three board tests, the deletion and grep checks, and `bkf skills`.

## Left ready

`lib-codex.sh` now wraps `harness agent run`, `harness inject`, and the verdict commands; `run_agents` is unchanged. `lib-inject.sh` is deleted. The dangling skill reference was corrected so `bkf skills` passes.

No harness tests matched the brief’s description of parity tests, so I kept the Python module tests.

## Not checked

I did not run the requested throwaway-copy failure demonstration. The brief says to report it as unchecked.

## Outside focus

The existing harness Python changes and new module tests were already in the checkout; I left them unchanged.


---
## Rules from determinism
The script added this text from ../../modules/determinism.md, as the role guide asked.

# Determinism

- Let code decide what code can decide. Cover every required behavior with a test, type check or script whose result decides. A reading of the code is not evidence of what a run can show: an LLM reading LLM-written code is a probabilistic system checking another.
- A check must be able to fail. Show it failing once, against a wrong input or a throwaway copy of the code with the defect put back, before you rely on it.
- Never weaken an existing test or check to make work pass.
- What code cannot decide (visual quality, opinion, whether the spec is right) stays with a person and is reported as unverified, not as passed. No check for a changed behavior is a gap, not a pass.
- Report what ran and what came out, failures included. Work that is not verified is not done.
- The person or the approved plan decides what the tests specify. Prototypes, exploration, documentation, visual experiments and trivial configuration are exempt.

## The gate

- Code runs each command outside any agent, in its own process group.
- A time limit stops the whole process group and records exit code 124.
- The result contains the command, exit code and output tail in `gate.md`, a `gate.json`, and one log per command.
- Every command runs, even after one fails.
- A red result stands; no agent overrides it.
- No commands is a gap, not a pass.
- An agent that receives the gate takes it as given and does not run it again.

<!-- rules injected by the script -->

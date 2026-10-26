# Final review of the plan

## The goal

# Goal: launching an agent and reading its verdict, in Python, shared by the run scripts

Second piece of the harness (the first was the gate). Today `lib-codex.sh` launches Codex (`codex_run`), reads the
verdict of a review (`read_verdict`) and checks the "What I checked" section (`checked_ok`), and `lib-inject.sh` adds
the text a role guide asks for to a brief (`inject_rules`). All four run scripts and `phase-codex.sh` depend on them.
They move into the `harness` Python project, with the agent launch behind a backend interface so a second backend
(Claude headless) can be added later without touching the scripts.

At the end:

- `agent-skills/skills/dispatch-codex/harness/` has three new modules with tests and a CLI each:
  `python3 -m harness inject PROMPT`, `python3 -m harness verdict read|checked FILE`, and
  `python3 -m harness agent run ...`.
- `agent run` builds the Codex command through a backend class; `--backend codex` is the default and the only one
  implemented. Its result (files, argv, exit code) is the same as `codex_run`'s was.
- `lib-codex.sh` keeps the functions the scripts call (`codex_run`, `inject_rules`, `read_verdict`, `checked_ok`,
  `run_agents`) but they are thin wrappers over the CLI. `lib-inject.sh` is gone. No script changes.
- `dispatch-codex/SKILL.md` documents the harness CLI.
- Every existing test of the scripts still passes without being weakened.

Out of scope: the Claude backend, state/resume/quota/lock, worktrees, the bridge, the board, parallel launching
(`run_agents` stays in bash and calls `codex_run`), renaming `dispatch-codex`, and `run-codex.sh`.


## The unit briefs, in order

### 01-inject

# Unit: injecting role-guide text into a brief, in Python

## Result

`agent-skills/skills/dispatch-codex/harness/harness/inject.py` ports `inject_rules` of `agent-skills/skills/dispatch-codex/scripts/lib-inject.sh`, with the same behavior and the same bytes added, and a CLI entry:

```
PYTHONPATH=<harness project dir> python3 -m harness inject PROMPT_FILE
```

- Exit 0 when the prompt was changed or needed no change; exit 1 with the message on standard error, leaving the prompt untouched, when a guide asks for a file that is not Markdown or does not exist; exit 2 on a usage error or an unreadable prompt.
- A function `inject_rules(prompt_path)` in `inject.py` does the work (raising an exception the CLI turns into exit 1), because the next unit calls it as a library.
- Read `lib-inject.sh` and `scripts/test-inject.sh`: they are the specification. The text added must be byte-identical to what the bash version adds for the same inputs, including blank lines, the heading, the "The script added this text from..." line, the end marker, frontmatter removal and once-only injection.
- Tests: `harness/tests/test_inject.py` (unittest), covering at least each case of `test-inject.sh` (no guide, no directive, one directive, run twice, two directives in order, missing file, non-Markdown file, a duplicated directive added once) plus a guide named twice in one brief.

## Receives

Nothing from other units.

## Leaves ready

`harness inject PROMPT_FILE` and `harness.inject.inject_rules(path)`, as above. The next units call them.

## Out of scope

Any `.sh` file (including `lib-inject.sh`, which stays until a later unit), the role guides, the modules.

## Rules for this unit

- Do not run git commands that change state, `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file is reachable by links from `agent-skills/skills/dispatch-codex/SKILL.md`. Where a unit adds files under `harness/`, extend the existing "Gate harness" paragraph of that file with links to them and nothing else; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py` and `cli.py`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh
bkf skills
```

The parity with the bash version is part of the tests, not of the gate: a test builds the briefs for the three real guides `plan/plan-implementation.md`, `plan/plan-review.md` and `code-review/code-review-axis.md` (under `agent-skills/library/workflow-types/`, found relative to the test file), runs `bash -c '. lib-inject.sh; inject_rules FILE'` on one copy and the Python function on another, and asserts the files are byte-identical. Mark these tests with a comment saying a later unit deletes them together with `lib-inject.sh`.

How these are shown to fail: change the end marker once in a throwaway copy, show the parity test fail, and say in the handoff what you changed.

## Criteria

- No behavior beyond the bash version (no new directive syntax, no config).
- The CLI never leaves a half-written prompt: on exit 1 the file is byte-identical to before.


### 02-verdict

# Unit: reading a verdict and checking "What I checked", in Python

## Result

`agent-skills/skills/dispatch-codex/harness/harness/verdict.py` ports `read_verdict` and `checked_ok` of `agent-skills/skills/dispatch-codex/scripts/lib-codex.sh`, with a CLI:

```
PYTHONPATH=<harness project dir> python3 -m harness verdict read FILE
PYTHONPATH=<harness project dir> python3 -m harness verdict checked FILE --min N
```

- `read`: prints `pass`, `back` or `escalate` and exits 0 when the last non-empty line of FILE, with all whitespace removed, is exactly `VERDICT:pass`, `VERDICT:back` or `VERDICT:escalate`. Otherwise prints nothing and exits 1 (a missing or empty file included).
- `checked`: exits 0 when N is 0 or less, or when FILE has a line starting with `## What I checked` followed by at least N non-empty lines (a line with a non-whitespace character) before the next line that starts with one or more `#` and a space; otherwise exits 1 (a missing file included). Exit 2 on a usage error.
- Library functions `read_verdict(path)` (returns the word or `None`) and `checked_ok(path, minimum)` (bool) in `verdict.py`; the CLI calls them.
- The bash functions are the specification; the awk in them defines the edge cases (Windows line endings are not special-cased there: do not add handling). One deliberate difference: for a missing or unreadable FILE, `checked` exits 1 (bash's awk exits 2); the callers only test for zero, so parity tests compare success against failure for that case, not the exact non-zero number. The exit statuses written in this brief win over bash's wherever they differ.
- Tests: `harness/tests/test_verdict.py` (unittest) with a parity test that runs the bash functions of `lib-codex.sh` (`bash -c '. lib-codex.sh; min_checked=N; checked_ok FILE'` and `read_verdict FILE`) and the Python ones on the same files and compares exit statuses and output (a comment marks it for deletion by a later unit), and with a case for each verdict, the verdict not on the last line, trailing blank lines, whitespace inside the verdict line, a wrong word, a missing file, the section at the start, in the middle and at the end of the file, a count one short of the minimum and exactly at it, a nested `### ` heading inside the section (it ends the section, as the awk does), and N = 0.

## Receives

Nothing from other units.

## Leaves ready

`harness verdict read|checked` and the two library functions, as above.

## Out of scope

Any `.sh` file, the review guides, any other module.

## Rules for this unit

- Do not run git commands that change state, `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file is reachable by links from `agent-skills/skills/dispatch-codex/SKILL.md`. Where a unit adds files under `harness/`, extend the existing "Gate harness" paragraph of that file with links to them and nothing else; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py` and `cli.py`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
```

How these are shown to fail: break the nested-heading rule (let a `###` line not end the section) once in a throwaway copy and show the matching test fail; say in the handoff what you broke.

## Criteria

- The behavior matches the bash functions on every case the tests list; where this brief states an exit status or output, the brief wins.


### 03-agent-run

# Unit: launching an agent, behind a backend interface

## Result

`agent-skills/skills/dispatch-codex/harness/harness/agent.py` and the CLI

```
PYTHONPATH=<harness project dir> python3 -m harness agent run --dir DIR --prompt FILE --out-prefix PREFIX --model M --effort E [--sandbox S] [--tier T] [--backend codex]
```

which does what `codex_run` in `scripts/lib-codex.sh` does today (read it; it is the specification):

1. Calls `harness.inject.inject_rules` on the prompt file. If that fails, prints the message on standard error, starts no agent and exits 1.
2. Runs the backend's command in the foreground, with the prompt file as standard input, standard output to `PREFIX.events.jsonl`, standard error to `PREFIX.stderr.log`. For `codex` the argument list is, in this order: `exec`, then `-c service_tier="T"` only when `--tier` is given and non-empty, then `--skip-git-repo-check`, `-C DIR`, `-m M`, `-c model_reasoning_effort="E"`, `-s S` (default `workspace-write`), `--json`, `-o PREFIX.last-message.md`, and `-`.
3. Exits with the agent's exit status; an agent killed by signal N gives 128+N.

Design:

- A small `Backend` base class with one method that returns the argument list for a spec (dir, model, effort, sandbox, tier, last-message path); `CodexBackend` implements it; a registry maps the name to the class. An unknown name, or `--backend claude`, exits 2 with "backend not implemented: NAME" and starts nothing. Do not write any Claude code.
- Do not start a new session or process group for the agent: the run scripts stop agents by signalling their process group, and the agent must stay in it.
- The agent is found on `PATH` as `codex`.
- Tests: `harness/tests/test_agent.py` (unittest) with a fake `codex` script on `PATH` that records its argument list and standard input: the exact argument list with and without tier and with a non-default sandbox; the prompt arrives on standard input after injection (use a guide with a directive, as `scripts/test-inject.sh` does); the three output files land where named; the exit status is propagated; death by signal gives 128+N; a failed injection starts no agent (the fake never ran) and exits 1; an unknown backend exits 2.

## Receives

`harness.inject.inject_rules` from the first unit (raises on a bad directive; read its code).

## Leaves ready

`harness agent run` and `harness.agent.run_agent(...)`, as above. The next unit makes `codex_run` call the CLI.

## Out of scope

Any `.sh` file, retrying, quota detection, parallel launching, anything for Claude.

## Rules for this unit

- Do not run git commands that change state, `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file is reachable by links from `agent-skills/skills/dispatch-codex/SKILL.md`. Where a unit adds files under `harness/`, extend the existing "Gate harness" paragraph of that file with links to them and nothing else; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py` and `cli.py`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
```

The parity of the argument list with `codex_run` is part of the tests: have a test source `lib-codex.sh`, run `codex_run` against the fake `codex` for a tier and a no-tier case, and compare the recorded argument list with the one `harness agent run` records (this test is removed by the next unit, which replaces `codex_run`; say so in a comment in the test).

How these are shown to fail: swap two arguments in the Python command once in a throwaway copy and show the parity test fail; say in the handoff what you changed.

## Criteria

- The argument list is character for character that of `codex_run`, including the quoting of the two `-c` values.
- `Backend` is the only place that knows about `codex`; `run_agent` knows files, injection and exit status.


### 04-scripts-use-cli

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


### 05-docs

# Unit: document the harness commands

## Result

One document changes: `agent-skills/skills/dispatch-codex/SKILL.md`. Documentation only; no code.

- Replace the "Gate harness" paragraph (added by the earlier units to keep `bkf skills` green) and the paragraphs of `## Shared code` that describe `lib-codex.sh` and `lib-inject.sh` with an accurate `## Shared code` section covering:
  - the `harness/` project: stdlib Python, called by the scripts through the `harness` function of `lib-codex.sh`, with links to every module and test file (`bkf skills` fails if one is unlinked);
  - the commands with their flags, output files and exit statuses, each in one or two lines: `gate run` (already documented), `inject`, `verdict read|checked`, `agent run`; and how to run them by hand with `PYTHONPATH=<repo>/agent-skills/skills/dispatch-codex/harness python3 -m harness ...`;
  - that agent launch goes through a backend class, that only `codex` exists, and that `--backend claude` exits 2 as not implemented;
  - what `lib-codex.sh` is now (wrappers with the old names, plus `run_agents`), that `lib-inject.sh` no longer exists, how a role guide asks for injection (keep the sentence about `<!-- inject: ... -->`, the heading in the brief and the once-only rule), and `scripts/test-inject.sh`.
- Keep every other part of the file exactly as it is.

## Receives

The CLI and modules from the earlier units; read `harness/harness/cli.py` and the modules for the exact flags and statuses. Do not describe anything the code does not do.

## Leaves ready

A `dispatch-codex/SKILL.md` that matches the code.

## Out of scope

Any code or test, other documents.

## Rules for this unit

- Do not run git commands that change state, `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file is reachable by links from `agent-skills/skills/dispatch-codex/SKILL.md`. Where a unit adds files under `harness/`, extend the existing "Gate harness" paragraph of that file with links to them and nothing else; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py` and `cli.py`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
bkf validate .
```

How these are shown to fail: before editing, run `grep -n "lib-inject" agent-skills/skills/dispatch-codex/SKILL.md` and note it matches; after, it must not. Report both results in the handoff.

## Criteria

- Every flag, file name and exit status in the new text exists in the code.
- Nothing outside the `## Shared code` section differs from before the edit.


## Inputs (read-only)
- The diff of the whole plan, new files included: /Users/bernardopacheco/.plan-runs/harness-agents/cumulative.patch
- The reviews of each unit and of each parallel group: /Users/bernardopacheco/.plan-runs/harness-agents/01-inject/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-agents/02-verdict/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-agents/03-agent-run/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-agents/04-scripts-use-cli/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-agents/05-docs/rounds/*/problems.md /Users/bernardopacheco/.plan-runs/harness-agents/S*-integration/rounds/*/problems.md
- The repository is your current directory. Open it read-only. Do not change anything. Do not open the handoffs.

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-harness/agent-skills/library/workflow-types/plan/plan-review.md (read-only), section "The final review". You are not the author of the work.

---
Your final message is the report, and nothing else.


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

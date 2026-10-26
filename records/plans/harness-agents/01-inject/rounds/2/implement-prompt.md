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

- Result and ready contract: the new module, CLI route, and tests in `diff.patch`; compared injection behavior with `lib-inject.sh` and `test-inject.sh`.
- Scope: all files in `diff.patch`; changes are limited to the harness and the required `SKILL.md` links.
- Criteria: `inject.py` and `test_inject.py` against the brief; the supplied gate is accepted as passed and was not rerun.
- Leaves ready: `inject_rules(prompt_path)` and `harness inject PROMPT_FILE` are present in the diff. The throwaway-copy failure demonstration is not checked, as the brief directs.
- Review guidance: `plan-review.md`; root and area maps: `MAP.md` and `agent-skills/MAP.md`.

## Problems

1. **Criteria — shell parity differs for an absolute directive path.** In `inject.py`, `_requested_files` joins the guide directory and directive with `os.path.join(directory, relative)`. If `relative` begins with `/`, Python discards `directory` and may read that absolute file. The shell implementation uses `$dir/$rel`, which keeps the guide directory prefix and will fail if that nested path is missing. For example, with an existing `/tmp/rule.md` and a guide containing `<!-- inject: /tmp/rule.md -->`, Python may inject it while Bash looks under the guide directory. Add a parity test for this input and match the shell behavior.

VERDICT: back

Your handoff from the previous round, for you to resume from:

**Verification**

- `python3 -m unittest discover -s tests` — passed, 24 tests.
- `bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh` — passed.
- `bkf skills` — passed; status valid, 0 issues.
- The throwaway parity check failed as intended after I changed the Bash end marker to `<!-- intentionally wrong marker -->`. That change was temporary and is not in the diff; it is not reviewer-visible there.

**Left ready**

- [`inject.py`](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/inject.py) provides `inject_rules(prompt_path)` and preserves the Bash output bytes.
- [`cli.py`](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/cli.py) supports `python3 -m harness inject PROMPT_FILE` with the requested exit codes.
- [`test_inject.py`](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/tests/test_inject.py) covers the specified cases and parity with the three real guides.
- The Gate harness paragraph in the skill links to the new module and tests.

No differences from the brief; nothing outside the focus. Python syntax is kept to 3.9-compatible features; the checks ran under Python 3.15.


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

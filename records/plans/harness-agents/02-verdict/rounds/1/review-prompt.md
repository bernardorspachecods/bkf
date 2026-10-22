# Review

## The brief

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


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-agents/02-verdict/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-agents/02-verdict/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf-harness/agent-skills/library/workflow-types/plan/plan-review.md (read-only). You are not the author of the work.

---
Your final message is the review, and nothing else. Begin it with a section headed "## What I checked": one line per thing you went through and where you found it. Then list the problems. Its last line must be exactly one of:
VERDICT: pass
VERDICT: back
VERDICT: escalate


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

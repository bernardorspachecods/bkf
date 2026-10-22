# Review

## The brief

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


---
## Inputs (read-only)
- The diff, new files included: /Users/bernardopacheco/.plan-runs/harness-agents/05-docs/rounds/1/diff.patch
- The repository is your current directory. Open it read-only to check the criteria. Do not change anything.
- Do not open anything else under the run folder, in particular no handoff: you judge the brief against the diff.
- The gate: the script ran the brief's `gate` commands itself, outside your sandbox, and every one passed: /Users/bernardopacheco/.plan-runs/harness-agents/05-docs/rounds/1/gate.md. They are binding and not open to your verdict. Do not run them again and do not report them as unchecked. You judge what code did not check.

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

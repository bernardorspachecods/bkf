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

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

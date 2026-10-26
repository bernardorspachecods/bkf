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

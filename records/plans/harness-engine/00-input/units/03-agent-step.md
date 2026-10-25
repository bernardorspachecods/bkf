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

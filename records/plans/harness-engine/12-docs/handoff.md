### Verification

- `python3 -m unittest discover -s tests` — 139 tests passed.
- `bkf skills` and `bkf validate .` — passed.
- Ran the requested parity command. It reported skips for bridge, integration, disk and parallel progress/board cases, plus the `ENGINE GAP` for trailing-slash path normalization.
- `grep -c "harness run"`: **2 before, 3 after**.
- `git diff --check` — passed.

### Left ready

Updated only `Shared code` and added `The engine` in [SKILL.md](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/SKILL.md). The engine and workflow files are linked; `bkf skills` found no unlinked files.

### Limits and handoff notes

The requested failure demonstration in a throwaway copy was **not checked**, as the brief directs. The engine’s generated pause/stop hints use `plan-run.sh resume`; the documentation gives the engine’s generic `harness run ... resume` form. I left code outside this unit unchanged.
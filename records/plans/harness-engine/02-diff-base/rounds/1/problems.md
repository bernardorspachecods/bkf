## What I checked

- **Result:** `diffbase.py` implements tree snapshots, base files and tree diffs; `metrics.py` appends the specified TSV fields. Compared with the Bash functions in `scripts/plan-run.sh`.
- **Scope:** The patch adds the two modules and their tests, and updates only the `Shared code` links in `SKILL.md`, as requested.
- **Criteria:** `test_engine_diffbase.py` checks Bash tree parity, index and status preservation, ignored files, commit independence, empty output and index cleanup. `test_engine_metrics.py` checks known counts, missing matches and append behavior. Their cases are at the corresponding test files; I accepted the supplied gate as binding.
- **Leaves ready:** The requested functions are present in the named engine modules and raise or use `RunError` from `run.py`.

Problems: None.

VERDICT: pass
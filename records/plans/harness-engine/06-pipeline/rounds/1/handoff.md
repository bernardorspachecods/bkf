## Verification

- `python3 -m unittest discover -s tests` — **passed**, 105 tests.
- `bkf skills` — **passed**.
- `git diff --check` — **passed**.
- Failure demonstration: in a throwaway copy, I marked a step done when it raised `Stop`. `test_pause_resume_and_stopped_resume` failed because resuming skipped the step after its cause was fixed.

## Leaves ready

Added the workflow contract and pipeline in [workflow.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/workflow.py) and [pipeline.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/pipeline.py), wired `harness run` in [cli.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/cli.py), added pipeline tests, and linked the new files in the skill catalog.

## Differences and gaps

The new workflow modules contain no workflow-specific names. The broader “nothing in `H/engine/` mentions plan” criterion remains unmet: existing `loop.py`, `diffbase.py`, `agentstep.py`, `run.py`, and `metrics.py` contain plan-specific references. I left those files untouched because the brief excludes them.

The run root uses `HARNESS_RUNS_DIR`, then the workflow-derived `<NAME>_RUNS_DIR`, then `~/.<workflow>-runs`. For a workflow named `plan`, the default remains `~/.plan-runs`.

## Outside focus

I left other working-tree changes untouched.
# Harness files

The standard-library Python CLI that the scripts of [dispatch-agents](../SKILL.md) call through the `harness` function in [lib-codex.sh](../scripts/lib-codex.sh). Run any command by hand with `PYTHONPATH=<repo>/agent-skills/skills/dispatch-agents/harness python3 -m harness ...`.

## Commands

- `gate run --cwd DIR --timeout SECONDS --out DIR [--note TEXT]... -- COMMAND...` writes `gate.md`, `gate.json` and `gate-N.log` in `DIR`; exit 0 when all commands pass, 1 when any fails, 2 for invalid usage or a runner error.
- `inject PROMPT_FILE` adds the rules a prompt asks for; exit 0, 1 for an invalid request, 2 for an operating-system error. A role guide or brief asks with a line such as `<!-- inject: ../../../modules/core-code-principles.md -->`; the text is added under a `## Rules from <name>` heading with a marker so a retry injects it once. [test-inject.sh](../scripts/test-inject.sh) checks it.
- `verdict read FILE` prints the verdict from the last non-empty line (exit 0) or exits 1; `verdict checked FILE --min N` exits 0 when `## What I checked` has at least `N` non-empty lines.
- `agent run --dir DIR --prompt FILE --out-prefix PREFIX --model MODEL --effort EFFORT [--sandbox SANDBOX] [--tier TIER] [--backend BACKEND]` writes `PREFIX.events.jsonl`, `PREFIX.stderr.log` and `PREFIX.last-message.md`; it returns the backend's exit status, 1 for an injection error, 2 for an unknown backend or an operating-system error. The backend is `codex` or `claude`; without `--backend`, `HARNESS_BACKEND` picks it, else `codex`.
- `run DEFINITION ...` runs a workflow definition under `workflows/` on the engine.

## Files

- [`scripts/lib-codex.sh`](../scripts/lib-codex.sh)
- [the project metadata](pyproject.toml)
- [package initializer](harness/__init__.py)
- [module entry point](harness/__main__.py)
- [CLI](harness/cli.py)
- [gate module](harness/gate.py)
- [agent module](harness/agent.py)
- [injection module](harness/inject.py)
- [verdict module](harness/verdict.py)
- [engine package initializer](harness/engine/__init__.py)
- [run state module](harness/engine/run.py)
- [run lock module](harness/engine/lock.py)
- [workflow contract module](harness/engine/workflow.py)
- [workflow pipeline module](harness/engine/pipeline.py)
- [plan input workflow module](../workflows/plan_inputs.py)
- [plan integration recovery module](../workflows/plan_integration.py)
- [review workflow module](../workflows/review.py)
- [council workflow module](../workflows/council.py)
- [diff base module](harness/engine/diffbase.py)
- [round metrics module](harness/engine/metrics.py)
- [agent step module](harness/engine/agentstep.py)
- [review module](harness/engine/review.py)
- [phase module](harness/engine/phase.py)
- [stepboard module](harness/engine/stepboard.py)
- [record module](harness/engine/record.py)
- [unit loop module](harness/engine/loop.py)
- [integration loop module](harness/engine/integration.py)
- [bridge module](harness/engine/bridge.py)
- [group worktree module](harness/engine/group.py)
- [plan workflow module](../workflows/plan.py)
- [plan board and record module](../workflows/plan_board.py)
- [plan runner](../scripts/plan-run.sh)
- [gate tests](tests/test_gate.py)
- [agent tests](tests/test_agent.py)
- [injection tests](tests/test_inject.py)
- [verdict tests](tests/test_verdict.py)
- [run state tests](tests/test_engine_run.py)
- [run lock tests](tests/test_engine_lock.py)
- [workflow pipeline tests](tests/test_engine_pipeline.py)
- [plan input tests](tests/test_workflow_plan_inputs.py)
- [plan workflow tests](tests/test_workflow_plan.py)
- [plan board and record tests](tests/test_workflow_plan_board.py)
- [plan test support](tests/plan_test_support.py)
- [review workflow tests](tests/test_workflow_review.py)
- [council workflow tests](tests/test_workflow_council.py)
- [engine robustness tests](tests/test_engine_robustness.py)
- [diff base tests](tests/test_engine_diffbase.py)
- [round metrics tests](tests/test_engine_metrics.py)
- [agent step tests](tests/test_engine_agentstep.py)
- [review tests](tests/test_engine_review.py)
- [phase tests](tests/test_engine_phase.py)
- [stepboard tests](tests/test_engine_stepboard.py)
- [record tests](tests/test_engine_record.py)
- [unit loop tests](tests/test_engine_loop.py)
- [integration loop tests](tests/test_engine_integration.py)
- [bridge tests](tests/test_engine_bridge.py)
- [group worktree tests](tests/test_engine_group.py)
- [plan integration recovery tests](tests/test_workflow_plan_integration.py)
- [research workflow module](../workflows/research.py)
- [research workflow tests](tests/test_workflow_research.py)
- [`scripts/test-inject.sh`](../scripts/test-inject.sh)
- [Claude backend tests](tests/test_agent_claude.py)

## Shell tests

The scripts under [scripts](../scripts/test-plan-run-gate.sh) test the plan runner (gate, bridge, metrics, integration briefs, final review, the run lock, `rebase-integration`, `accept-integration`, the usage-limit notice, the disk check), the board of each workflow and the review gate, all with a fake `codex`: [plan](../scripts/test-plan-run-gate.sh), [review gate](../scripts/test-review-run-gate.sh), [review board](../scripts/test-review-run-board.sh), [research board](../scripts/test-research-run-board.sh) and [council board](../scripts/test-council-run-board.sh). Every `plan-run.sh` call in the plan test has a time limit (`PLAN_TEST_LIMIT`, default 120 seconds).

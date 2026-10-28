# Harness files

The standard-library Python engine that the run scripts of the `plan`, `research`, `council` and `code-review` skills call through the `harness` function in [lib.sh](scripts/lib.sh), and that `delegate-work` uses to launch one agent. The engine knows no workflow by name: `run DEFINITION` loads a definition file that a skill owns (`skills/<name>/scripts/<name>.py`) and runs it. Run any command by hand with `PYTHONPATH=<repo>/agent-skills/harness python3 -m harness ...`.

## Commands

- `gate run --cwd DIR --timeout SECONDS --out DIR [--note TEXT]... -- COMMAND...` writes `gate.md`, `gate.json` and `gate-N.log` in `DIR`; exit 0 when all commands pass, 1 when any fails, 2 for invalid usage or a runner error.
- `verdict read FILE` prints the verdict from the last non-empty line (exit 0) or exits 1; `verdict checked FILE --min N` exits 0 when `## What I checked` has at least `N` non-empty lines.
- `agent run --dir DIR --prompt FILE --out-prefix PREFIX --model MODEL --effort EFFORT [--sandbox SANDBOX] [--tier TIER] [--backend BACKEND] [--web]` writes `PREFIX.events.jsonl`, `PREFIX.stderr.log` and `PREFIX.last-message.md`; it returns the backend's exit status, 1 for an injection error, 2 for an unknown backend or an operating-system error. The backend is `codex` or `claude`; without `--backend`, `HARNESS_BACKEND` picks it, else `codex`. `--web` adds `WebFetch` and `WebSearch` to a Claude agent's tools; Codex ignores it. The research workflow sets it for its map agent and collectors only. An agent whose events and stderr files stay the same size for `HARNESS_AGENT_STALL_TIMEOUT` seconds (default 1200, 0 turns it off) is ended and `agent run` returns 124, so a hung agent stops the run with a `STALLED` reason instead of leaving it waiting.
- `run DEFINITION ...` runs a workflow definition under `workflows/` on the engine.
- [`scripts/launch-session.sh`](scripts/launch-session.sh) `[--name N] [--model M] [--effort E] [--permission-mode P] [--window W] <claude|codex> <working-dir> <prompt-file>` opens an interactive session in a new tab beside the caller, with the prompt file as its first message: a tmux window right after the caller's when `$TMUX` is set (with iTerm2 attached, shown as a tab of the caller's iTerm2 window), a new Terminal.app window otherwise. The `handoff` and `crew` skills launch their sessions through it; it is shell, not part of the Python engine.

## Files

- [`scripts/lib.sh`](scripts/lib.sh)
- [session launcher](scripts/launch-session.sh)
- [the project metadata](pyproject.toml)
- [package initializer](harness/__init__.py)
- [module entry point](harness/__main__.py)
- [CLI](harness/cli.py)
- [gate module](harness/gate.py)
- [agent module](harness/agent.py)
- [injection module](harness/inject.py)
- [brief template module](harness/template.py)
- [verdict module](harness/verdict.py)
- [engine package initializer](harness/engine/__init__.py)
- [run state module](harness/engine/run.py)
- [run lock module](harness/engine/lock.py)
- [workflow contract module](harness/engine/workflow.py)
- [workflow pipeline module](harness/engine/pipeline.py)
- [backend check module](harness/engine/backend.py)
- [run layout module](harness/engine/layout.py)
- [run worktree module](harness/engine/checkout.py)
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
- [gate tests](tests/test_gate.py)
- [agent tests](tests/test_agent.py)
- [injection tests](tests/test_inject.py)
- [brief template tests](tests/test_template.py)
- [verdict tests](tests/test_verdict.py)
- [run state tests](tests/test_engine_run.py)
- [run lock tests](tests/test_engine_lock.py)
- [workflow pipeline tests](tests/test_engine_pipeline.py)
- [backend check tests](tests/test_engine_backend.py)
- [run layout tests](tests/test_engine_layout.py)
- [run worktree tests](tests/test_engine_checkout.py)
- [engine robustness tests](tests/test_engine_robustness.py)
- [diff base tests](tests/test_engine_diffbase.py)
- [round metrics tests](tests/test_engine_metrics.py)
- [agent step tests](tests/test_engine_agentstep.py)
- [review tests](tests/test_engine_review.py)
- [phase tests](tests/test_engine_phase.py)
- [stepboard tests](tests/test_engine_stepboard.py)
- [record tests](tests/test_engine_record.py)
- [unit loop tests](tests/test_engine_loop.py)
- [bridge tests](tests/test_engine_bridge.py)
- [group worktree tests](tests/test_engine_group.py)
- [Claude backend tests](tests/test_agent_claude.py)

## Tests

Run the Python tests with `PYTHONPATH=agent-skills/harness python3 -m unittest discover -s agent-skills/harness/tests`, and the shell tests [test-inject.sh](tests/test-inject.sh) and [test-launch-session.sh](tests/test-launch-session.sh) with `bash`; the second needs `tmux` and starts a throwaway tmux server of its own. Each workflow skill keeps its own tests in its `tests/` folder (see the skill's `SKILL.md`).

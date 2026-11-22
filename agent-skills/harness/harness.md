---
bkf: document
description: Documents the harness engine's commands, exit codes and environment variables, and how to run its tests; read it when you change how agents, gates, injection or workflow definitions run.
tags: [harness]
---

# Harness

The standard-library Python engine that the run scripts of the `agentic-work` skill calls through the `harness` function in [lib.sh](/agent-skills/harness/scripts/lib.sh), and that the agentic-work [agent launcher](/agent-skills/skills/agentic-work/conversation-run.md#launching-an-implementer) uses to launch one agent. The engine knows no workflow by name: `run DEFINITION` loads a definition file that a skill owns (`skills/<name>/scripts/<name>.py`) and runs it. Run any command by hand with `PYTHONPATH=<repo>/agent-skills/harness python3 -m harness ...`.

## Commands

- `gate run --cwd DIR --timeout SECONDS --out DIR [--note TEXT]... -- COMMAND...` writes `gate.md`, `gate.json` and `gate-N.log` in `DIR`; exit 0 when all commands pass, 1 when any fails, 2 for invalid usage or a runner error.
- `verdict read FILE` prints the verdict from the last non-empty line (exit 0) or exits 1; `verdict checked FILE --min N` exits 0 when `## What I checked` has at least `N` non-empty lines.
- `prepare --run DIR --repo DIR --tree DIR [--timeout SECONDS]` applies the repository's committed `.plan-run.json` `worktree.copy` and `worktree.prepare` setup to a new worktree; the timeout defaults to `PLAN_PREPARE_TIMEOUT` or 1800 seconds.
- `agent run --dir DIR --prompt FILE --out-prefix PREFIX --model MODEL --effort EFFORT [--sandbox SANDBOX] [--tier TIER] [--backend BACKEND] [--web] [--bridge-base-file FILE --bridge-log FILE --bridge-unit NAME [--bridge-receipt-dir DIR] [--bridge-gate-brief FILE]]` writes `PREFIX.events.jsonl`, `PREFIX.stderr.log` and `PREFIX.last-message.md`; it returns the backend's exit status, 1 for an injection error, 2 for an unknown backend or an operating-system error. The bridge flags serve `.plan-porteiro/ponte` for the agent's run, allowing only the unchanged pnpm scripts listed by `.plan-run.json` at the base and the gate commands. With `--bridge-receipt-dir` and `--bridge-gate-brief`, `ponte gate` runs the brief's whole gate outside the agent's sandbox and writes the gate receipt in that folder (see the receipt module): the proof that the gate passed on this tree, which `plan-unit.sh check` and the unit loop accept instead of running the gate again. The backend is `codex` or `claude`; without `--backend`, `HARNESS_BACKEND` picks it, else `codex`. `--web` adds `WebFetch` and `WebSearch` to a Claude agent's tools; Codex ignores it. An agent whose events and stderr files stay the same size for `HARNESS_AGENT_STALL_TIMEOUT` seconds (default 1200, 0 turns it off) is ended and `agent run` returns 124, so a hung agent stops the run with a `STALLED` reason instead of leaving it waiting. Every agent it starts gets `BKF_DELEGATED=1` in its environment, so the `rules` session-start hook leaves out the rules marked `[interactive]` (see [`bkf hooks`](/bkf/tooling/commands.md#bkf-hooks)); without it a delegated agent would load `align-intent` and wait for an answer nobody can give. The harness also removes `BKF_TASK` from that environment, so a delegated agent never takes the caller's task for its own session.
- `quota-wait [--margin SECONDS] TEXT` sleeps until the reset time that `TEXT` (the text of a `QUOTA:` line) names, plus the margin (default 120), then exits 0; it exits 2 at once, without waiting, when the text is not `H:MM AM|PM` or `YYYY-MM-DD HH:MM` with an optional `UTC`. A time without `UTC` is local; a clock time that passed less than 6 hours ago counts as reached.
- `run DEFINITION ...` runs a workflow definition under `workflows/` on the engine.
- The interactive sessions of the `handoff` skill are not run by the engine: `bkf launch` opens each one with its task card (see [`bkf launch`](/bkf/tooling/commands.md#bkf-launch)). `--delegated` there sets `BKF_DELEGATED=1` in the session, like the agents `agent run` starts; `handoff` does not use it.

## Tests

Run the Python tests with `PYTHONPATH=agent-skills/harness python3 -m unittest discover -s agent-skills/harness/tests`, and the shell test [test-inject.sh](/agent-skills/harness/tests/test-inject.sh) with `bash`. Each workflow skill keeps its own tests in its `tests/` folder (see the skill's `SKILL.md`). The end-to-end check of the agent CLI (task, launch, hooks, delegate, merge queue, plan run, the bkf suites) is [e2e-agent-cli.sh](/agent-skills/tests/e2e-agent-cli.sh), run with `bash` in a sandbox.

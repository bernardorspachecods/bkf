# Unit: launching an agent, behind a backend interface

## Result

`agent-skills/skills/dispatch-codex/harness/harness/agent.py` and the CLI

```
PYTHONPATH=<harness project dir> python3 -m harness agent run --dir DIR --prompt FILE --out-prefix PREFIX --model M --effort E [--sandbox S] [--tier T] [--backend codex]
```

which does what `codex_run` in `scripts/lib-codex.sh` does today (read it; it is the specification):

1. Calls `harness.inject.inject_rules` on the prompt file. If that fails, prints the message on standard error, starts no agent and exits 1.
2. Runs the backend's command in the foreground, with the prompt file as standard input, standard output to `PREFIX.events.jsonl`, standard error to `PREFIX.stderr.log`. For `codex` the argument list is, in this order: `exec`, then `-c service_tier="T"` only when `--tier` is given and non-empty, then `--skip-git-repo-check`, `-C DIR`, `-m M`, `-c model_reasoning_effort="E"`, `-s S` (default `workspace-write`), `--json`, `-o PREFIX.last-message.md`, and `-`.
3. Exits with the agent's exit status; an agent killed by signal N gives 128+N.

Design:

- A small `Backend` base class with one method that returns the argument list for a spec (dir, model, effort, sandbox, tier, last-message path); `CodexBackend` implements it; a registry maps the name to the class. An unknown name, or `--backend claude`, exits 2 with "backend not implemented: NAME" and starts nothing. Do not write any Claude code.
- Do not start a new session or process group for the agent: the run scripts stop agents by signalling their process group, and the agent must stay in it.
- The agent is found on `PATH` as `codex`.
- Tests: `harness/tests/test_agent.py` (unittest) with a fake `codex` script on `PATH` that records its argument list and standard input: the exact argument list with and without tier and with a non-default sandbox; the prompt arrives on standard input after injection (use a guide with a directive, as `scripts/test-inject.sh` does); the three output files land where named; the exit status is propagated; death by signal gives 128+N; a failed injection starts no agent (the fake never ran) and exits 1; an unknown backend exits 2.

## Receives

`harness.inject.inject_rules` from the first unit (raises on a bad directive; read its code).

## Leaves ready

`harness agent run` and `harness.agent.run_agent(...)`, as above. The next unit makes `codex_run` call the CLI.

## Out of scope

Any `.sh` file, retrying, quota detection, parallel launching, anything for Claude.

## Rules for this unit

- Do not run git commands that change state, `bkf skills --write` or `bkf inventory --write`. Do not edit any file the Result does not name.
- The failure demonstration asked for under Gate (a check shown failing once, in a throwaway copy) is reported in the handoff, which the reviewer does not receive: do not send the unit back or escalate because the diff does not show it; list it as not checked.
- `bkf skills` fails with `SKILL_FILE_UNLINKED` unless every new file is reachable by links from `agent-skills/skills/dispatch-codex/SKILL.md`. Where a unit adds files under `harness/`, extend the existing "Gate harness" paragraph of that file with links to them and nothing else; the real documentation is the last unit.
- Python 3.9 syntax at most, standard library only. Match the style of `harness/harness/gate.py` and `cli.py`.

## Gate

```gate
cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests
bkf skills
```

The parity of the argument list with `codex_run` is part of the tests: have a test source `lib-codex.sh`, run `codex_run` against the fake `codex` for a tier and a no-tier case, and compare the recorded argument list with the one `harness agent run` records (this test is removed by the next unit, which replaces `codex_run`; say so in a comment in the test).

How these are shown to fail: swap two arguments in the Python command once in a throwaway copy and show the parity test fail; say in the handoff what you changed.

## Criteria

- The argument list is character for character that of `codex_run`, including the quoting of the two `-c` values.
- `Backend` is the only place that knows about `codex`; `run_agent` knows files, injection and exit status.

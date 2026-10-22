# Goal: launching an agent and reading its verdict, in Python, shared by the run scripts

Second piece of the harness (the first was the gate). Today `lib-codex.sh` launches Codex (`codex_run`), reads the
verdict of a review (`read_verdict`) and checks the "What I checked" section (`checked_ok`), and `lib-inject.sh` adds
the text a role guide asks for to a brief (`inject_rules`). All four run scripts and `phase-codex.sh` depend on them.
They move into the `harness` Python project, with the agent launch behind a backend interface so a second backend
(Claude headless) can be added later without touching the scripts.

At the end:

- `agent-skills/skills/dispatch-codex/harness/` has three new modules with tests and a CLI each:
  `python3 -m harness inject PROMPT`, `python3 -m harness verdict read|checked FILE`, and
  `python3 -m harness agent run ...`.
- `agent run` builds the Codex command through a backend class; `--backend codex` is the default and the only one
  implemented. Its result (files, argv, exit code) is the same as `codex_run`'s was.
- `lib-codex.sh` keeps the functions the scripts call (`codex_run`, `inject_rules`, `read_verdict`, `checked_ok`,
  `run_agents`) but they are thin wrappers over the CLI. `lib-inject.sh` is gone. No script changes.
- `dispatch-codex/SKILL.md` documents the harness CLI.
- Every existing test of the scripts still passes without being weakened.

Out of scope: the Claude backend, state/resume/quota/lock, worktrees, the bridge, the board, parallel launching
(`run_agents` stays in bash and calls `codex_run`), renaming `dispatch-codex`, and `run-codex.sh`.

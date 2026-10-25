---
bkf: document
description: States what the agent harness is for, its layers, the decisions taken about it and what is still to build, in order. It is the working plan of the harness; the code and each skill own their own behavior.
tags: [harness, plan]
---

# Harness goal

Update this document in the same change that finishes, drops or adds a piece of the plan below.

## Intent

Agentic work should run on one common, tested harness: launching agents, checking them, keeping a run's state and resuming it. Each workflow (plan, research, council, review) defines only what is its own. The user briefs a run once, with the what and the why in enough detail that agents work on their own, and judges the result at the end; between checkpoints nobody asks small questions or sends status.

## Layers

| Layer | Holds |
| --- | --- |
| L0, harness code (Python, standard library) | Launching agents behind a backend interface, the gate, injection of text into briefs, verdict reading, state, resume, pause, lock, quota, the board, and optional capabilities. |
| L1, modules | Principles and contracts, as text that skills and briefs inject. |
| L2, workflows | The graph of steps, the briefs and role guides, and a few small functions of their own. |

Four kinds of step: agents (N in parallel), a review with a verdict (pass, back or escalate), a deterministic command, and a coordinator pause. The harness knows no workflow by name: it runs a definition it is given.

## Decisions taken

- A module is one rule set about one activity, with a consumer: shared text goes in a module, single-consumer text stays in the skill. A skill is a menu (only when it routes) or has a single objective; a skill holds only what is unique and states orders, not routing. A rule enters only when the agent would not do it by default.
- Anything two workflows need goes to the harness, including capabilities only one uses today, as optional features: worktree isolation, the base of a diff, integration of parallel diffs, the bridge (generic name), the disk check.
- The harness is Python, standard library only, a package inside `dispatch-codex`. Extraction is phased, and the existing tests are the spec. `dispatch-codex` is renamed `dispatch-agents` only when the Claude backend works.
- The Claude backend runs `claude -p` (`--bare` skips hooks). Only its flags are verified; write confinement, the quota signal and the rest of `--bare` are not.
- Long or delegated work always has a goal file the agent consults; small work is aligned in conversation, with the agent restating the intent in its own words. The same sections serve both: what and why, done when, out of scope, decisions already taken, when to stop and ask, and how a change of intent is recorded.
- Nothing from this plan goes to `main` until the user says: other plans run with the scripts installed from it.
- A skill is loaded by its description, so descriptions state the activity and, where needed, who must not load it: `code-work` and `align-intent` are for the agent working in conversation, not for an agent inside a plan, a delegated task or a review, whose brief already carries their rules. Text injected into briefs (`core-code-principles`, `gate`, `intent`) is a module with the `injected` tag.
- `repo-library` is a destination, not an entry point: nothing sends an agent there by default. Each entry must be reachable from where its activity starts (a task route in the nearest map and a link from the document that owns the activity), and `bkf validate` warns about an entry no document outside `repo-library/` links to. An `AGENTS.md` carries only repository-specific rules; it needs no pointer to `repo-library`.
- Long-running launchers (`plan-run.sh`, `review-run.sh`, `council-run.sh`, `research-run.sh`, `phase-codex.sh`, `run-codex.sh`, `codex exec`) must be started with `run_in_background: true`; the `guard` hook group of `bkf hooks` refuses a foreground launch or one backgrounded by hand.
- Workflows are to become skills; their role guides then live with their skill, and `library/` becomes `modules/` (reusable, injectable excerpts). The tag system can go once no skill selects by tag.

## State

| Piece | State |
| --- | --- |
| Gate, injection, verdict, agent launch with the Codex backend | Done. |
| The engine (run state, lock, unit loop, pipeline, kill detection) with the sequential plan as its first workflow | Done and merged. |
| Parallel groups, worktrees, group diff bases, integration and review, bridge, disk check, compact board, and ending the separate bash plan runner | Done. `scripts/plan-run.sh` runs plans through the engine. |
| `research`, `council` and `review` on the engine | Not started. |
| Claude backend | Not started. |
| `bkf validate` warning for a `repo-library` entry nobody links to | Done and merged (260 tests, +0.5 s on a large repo). |
| Docs restructure: `code-work`, `align-intent`, `repo-library` (grow only, entries reached by a link from outside), `repo-maintenance` (one skill of principles, writing rules and conventions, about 830 words), modules `core-code-principles` (absorbs `determinism`), `gate`, `intent` | Done and merged. |

## Where the work is

Everything above is merged into `integration`; the worktrees `bkf-engine`, `bkf-docs` and `bkf-codex/repo-library-reach` can be removed. Nothing is on `main` yet. Edits that had to be made in the `main` checkout, uncommitted and live because the installed `bkf` is editable from there: `bkf/tooling/default_rules.txt` (three new lines), `launch_guard.py` and its test, `hook_events.py`, `pyproject.toml` and `commands.md` for the hook, and an entry in `bkf/feedback.md`. When `integration` goes to `main`, those edits move into `integration` first and the `main` checkout is cleaned, so the merge does not collide with them.

Nothing goes to `main` while plans run on the scripts installed from it, so `integration` keeps no compatibility with the `main` scripts.

## Next, in order

1. Move `run-codex.sh` (delegate-work) onto the agent launch, which removes the last copy of the Codex command.
2. Migrate `review`, `research` and `council` onto the engine.
3. Verify the Claude backend (write confinement, the quota signal, `--bare`), implement it, then rename to `dispatch-agents`.
4. Turn the workflows into skills and rename `library/` to `modules/`; remove the tag system if nothing uses it.

## Open threads with the user

From the walk through what an agent loads in a normal session (about 1.45 thousand words always, 4 thousand for a code fix, 9 thousand to start a plan):

- Done: `repo-library` no longer loads on every task; `align-intent` and `code-work` exclude agents inside a plan, a delegated task or a review; `repo-maintenance` is one skill (about 830 words, the heaviest path went from 1,300).
- `dispatch-codex` is about 3,400 words read by every workflow, mostly command reference that the engine makes redundant: shrink it once the engine runs every workflow.
- Whether the `intent` module is also injected into the plan, research, council and code-review coordinator guides, so their goal files carry the same sections; first see whether an agent opens `align-intent` when the user starts talking about a plan.
- Check the picture with real sessions using the `retrieval-chat-audit` skill: one request of each kind, in particular adding a paragraph to an existing document (does the agent revise the section or append?) and adding a `repo-library` entry.

## Not scheduled yet

- Stopping a run ends only the agent process itself, not what it started; check whether the Codex CLI cleans up its own children.
- Failure demonstrations of the engine units are the implementers' reports in `records/plans/harness-engine`; the reviewer never saw them. Units 6, 9, 10 and 12 have none of their own.
- A compact board: finished steps fold into one line and only the active steps show in full, and the full board is also written to a file in the run folder. Today a long plan shows only its last lines in a background task. The board text is pinned by the parity tests, so change it after parity.
- The aviso of `finish` about `records/` in `AGENTS.md` can go: the maps already describe `records/`. Drop it after parity, in the shell script and in the engine.
- A gate timeout wastes two seconds because the dead shell is not reaped before the group is checked.
- The installed copy of the session rules does not carry the latest lines of the template (`default_rules.txt`: conflicts, update the documents, align intent).
- `what-is-bkf.md` still describes entry skills as thin lists of generated modules.
- `bkf validate`, `bkf skills` and `bkf inventory` do not fail when the frontmatter of a skill is not valid YAML (for example an unquoted `: ` in a description); `bkf inventory` reports up to date while skipping the documents it cannot read.
- The `guard` hook applies to Codex agents too (it is registered for both), so a Codex agent that calls `codex exec` or a run script from its shell is refused.
- In the `desmor-hub` repo: every `repo-library` entry is linked from durable documents, but the root task route "Preparar e validar uma release" leads to a protocol that links only the database module; the platform modules are reached through `docs/feedback/release.md`.

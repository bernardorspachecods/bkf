---
bkf: document
description: States what the agent harness is for, its layers, the decisions taken about it and what is still to build, in order. It is the working plan of the harness; the code and each skill own their own behavior.
tags: [harness, plan]
---

# Harness goal

Update this document in the same change that finishes, drops or adds a piece of the plan below.

## Navigation map

| What you need | Where |
| --- | --- |
| What the harness is for | [Intent](#intent) |
| The three layers and the four step kinds | [Layers](#layers) |
| What was decided and must not be reopened | [Decisions taken](#decisions-taken) |
| What is done, running and missing | [State](#state) |
| Where each branch and worktree stands | [Where the work is](#where-the-work-is) |
| The order of what remains | [Next, in order](#next-in-order) |
| Questions still open with the user | [Open threads with the user](#open-threads-with-the-user) |
| Small defects not yet scheduled | [Not scheduled yet](#not-scheduled-yet) |
| Picking the work up after a pause: limits, worktrees, the running plan, the remaining blocks, the design of workflows as skills | [How to continue](#how-to-continue-written-on-2026-10-25-for-whoever-picks-the-work-up) |

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

1. Migrate `review`, `research` and `council` onto the engine.
2. Verify the Claude backend (write confinement, the quota signal, `--bare`), implement it, then rename to `dispatch-agents`.
3. Turn the workflows into skills and rename `library/` to `modules/`; remove the tag system if nothing uses it.

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

## How to continue (written on 2026-10-25, for whoever picks the work up)

The user gave full autonomy to finish the objective: do small and medium work yourself (or with Haiku subagents for mechanical bulk edits), and give large work to Codex as a plan run, tending other work meanwhile. The user does not need to approve anything. The one hard limit: **nothing goes to `main`**, because other plans run on the scripts installed from it. Commits on `integration` and its side branches are fine; commit trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Standing rules of the session hook still apply (informal pt-PT, direct, visual aids, no flattery, do not touch what other agents changed). Nothing needs backward compatibility with the scripts on `main`.

### Worktrees and what runs now

| Worktree | Branch | State |
| --- | --- | --- |
| `bkf` | `main` | Not to be committed to. It holds uncommitted edits that are also committed on `work` (the launch guard, three session rules, the `hook_events.py` guard branch, `pyproject.toml`, `commands.md`, `feedback.md`); the installed `bkf` is editable from here, so the hook is live from these files. When `integration` goes to `main`: `git checkout -- .` and remove the two untracked files there first, then merge. If the guard files change on `work` meanwhile, copy them over (`launch_guard.py`, `tests/test_launch_guard.py`) or the live hook goes stale. |
| `bkf-agents` | `integration` | The merged base (harness gate/inject/verdict/agent, engine, docs, repo-library warning). **Its `scripts/` drive any plan run: do not edit `agent-skills/skills/dispatch-codex/scripts/` here while a run is active; work on a side branch and merge it here.** |
| `bkf-work` | `work` | Side work, from `integration`; at the moment equal to it. Merge it back into `integration` the same way as before (`git merge --no-ff work` inside `bkf-agents`). |

The run `harness-groups` (8 units, Codex) finished on 2026-10-25 and is merged into `integration`: groups, worktrees, disk check, bridge, integration and the two recovery commands run in the engine and `plan-run.sh` is the engine wrapper (144 cases PASS, 0 SKIP). Its folder `~/.plan-runs/harness-groups` and the briefs in `~/.plan-runs-pending/harness-groups/` are kept until the user chooses to keep the record or delete them. One known gap from its report: the bridge timeout handler in `engine/bridge.py` still uses the old two-second grace wait that `gate.py` no longer has.

### What remains after the run, in order

1. **Run closed.** Done (see above).
2. **`review`, `research` and `council` on the engine** (a large plan for Codex, written like `harness-groups`: goal, a plan with one brief per unit, each with a `gate` block and a failure demonstration). Read `scripts/review-run.sh`, `research-run.sh`, `council-run.sh` and `phase-codex.sh` first. Their tests are thin (board tests, and the review gate), so each unit must write its own fake-`codex` tests: they are the specification. The engine already has the parallel-agents step (`engine/agentstep.run_agents`) and the unit loop; what these workflows add is their own phases and files. At the end `lib-codex.sh` keeps only wrappers of the harness CLI, and the `*-run.sh` and `phase-codex.sh` become wrappers or go.
3. **Claude backend.** Verified so far (`claude` 2.1.310): `claude -p --output-format stream-json --verbose --no-session-persistence --model <m> --permission-mode <mode>` takes the prompt on stdin and ends with a `result` event (`subtype`, `result` text, `is_error`, `total_cost_usd`); a `rate_limit_event` carries `rate_limit_info` (`status`, `resetsAt`, `rateLimitType`), which is the quota signal; `--effort` takes low to max; `--bare` needs `ANTHROPIC_API_KEY` (it never reads the login), so it does not fit; `--safe-mode` disables hooks, CLAUDE.md and skills but was not tried; `--restricted` confines the file tools to the working directories but removes Bash. Not verified: write confinement for an implementer that needs Bash (try `--settings` with a `sandbox` section, or `--permission-mode dontAsk` with `--allowedTools`, on a throwaway directory with a Haiku model: it costs little), and what the events of a hit usage limit look like (the `rate_limit_event` with a status other than `allowed`). Then implement the backend class in `harness/harness/agent.py` (`arguments`, `quota_text`; the base class already exists), test it with a fake `claude`, and rename `dispatch-codex` to `dispatch-agents` (a mechanical rename that touches the installed skill link only on `main`, so it waits).
4. **Workflows become skills** (design below), when its turn comes in this order: done by me with Haiku subagents for the bulk renames. It stays after steps 2 and 3 because the scripts and tests of step 2 name the guide paths.
5. **Shrink `dispatch-codex/SKILL.md`** (about 3,400 words, mostly command reference the engine makes redundant) once every workflow runs on the engine.
6. **Brief failures in plans.** Handle `/Users/bernardopacheco/falhas-de-briefs-em-planos.md` (6 of 29 units in two real plans stopped or lost rounds because of the brief, not the code). Last piece of work, after the engine is complete, because the code items land in the engine and not in the bash. In the document's order: R4 (scope by exclusion, plus the clause that tests and documents broken by the change are the unit's to adapt) in the `plan` guide; R1 (the run stops when the same gate command fails on the same tests in two rounds, or a review sends back for the same file or sentence) and one automatic repeat of a failing gate before it counts; R2 (`blocked.md` from the implementer, `VERDICT: brief` from the reviewer); R3 and R5 (brief lint and ratchet numbers inside `gates`); R6 (rehearsal at the starting state); one combined round cap of 4; R7, R8 (a Haiku reads the brief for contradictions), R9. It happened in this very run: unit 2 of `harness-groups` lost four rounds to a brief that forbade editing the test its own required behavior broke (the document's F5); briefs 3 to 8 now carry a stop-asking, adapt-the-expectation rule as a stopgap.
7. **Tests with real sessions**, by the user at the end: one request of each kind with `retrieval-chat-audit`, and a small real plan.
8. **Main.** Ask the user. Before any merge into `main`, read the first row of the worktree table above.

### Workflows become skills: the design

Today: `agent-skills/library/workflow-types/<plan|code-review|council|research>/` holds a coordinator guide (`plan.md`, ...) and role guides (`plan-implementation.md`, ...), each a tracked BKF document with `tags`; `agent-skills/library/modules/` holds four modules, all tagged `injected`; the skills `work-in-stages` (a menu of plan, code review and council, built with a generated tagged list) and `do-research` (research) list the coordinator guides by tag and inject `coordinate-a-run`.

Target: one skill per workflow, whose `SKILL.md` is the coordinator guide, with its role guides next to it.

```
agent-skills/
  modules/                     (was library/modules: coordinate-a-run, core-code-principles, gate, intent)
  skills/
    plan/          SKILL.md  (was plan.md; injects coordinate-a-run)   roles/plan-implementation.md, plan-review.md, plan-integration.md
    code-review/   SKILL.md  roles/code-review-axis.md, code-review-check.md
    council/       SKILL.md  roles/council-advisor.md, council-reviewer.md, council-completeness.md
    research/      SKILL.md  (replaces do-research)   roles/research-collection.md, research-digest.md, research-review-*.md
    dispatch-codex/  (scripts, harness, workflows definitions; later dispatch-agents)
```

Decisions: keep the role guide file names (the scripts and prompts name them); `work-in-stages` goes, because each workflow skill's description already routes (a menu that only repeats descriptions routes nothing), and its "resume a stopped run" line moves into the workflow skills; the tag system goes (no skill selects by tag once the workflow skills link their roles directly): drop `tags` from the module frontmatter, the tagged-list feature of `bkf inventory --skills` and its tests, the tag vocabulary of the library map, and the words "entry skills" in the tooling and docs; the role guides lose their BKF `tags`/frontmatter requirements as they leave the tracked bundle (a skill package is routed by its own metadata, not by a map), but keep a short description line in the guide itself if the scripts read it (check first). The script defaults for the guides folders (`PLAN_GUIDES`, `REVIEW_GUIDES`, `COUNCIL_GUIDES`, `RESEARCH_GUIDES`, in `plan_inputs.guides_path` and the `*-run.sh`) and the injection lines inside the guides (relative paths to `modules/`) change with the move. Files naming the old paths (found with `grep -rln "workflow-types\|library/modules\|agent-skills/library"`): `INSTALL.md`, `README.md`, `agent-skills/MAP.md`, `library/MAP.md`, the skills `align-intent`, `code-work`, `delegate-work`, `dispatch-codex`, `do-research`, `repo-library`, `skill-authoring`, `work-in-stages`, `scripts/*-run.sh`, `scripts/test-inject.sh`, `workflows/plan_inputs.py` and its test, `bkf/format/glossary.md`, `bkf/manual/what-is-bkf.md`, `bkf/tooling/commands.md`, `generate_inventory.py` and the tests `test_skill_inventory.py` and `test_repo_library_links.py`. `records/` is history: leave it. Check at every step with `bkf skills`, `bkf validate .` and the tooling and harness tests.

### Things that are the user's, or settled

- `~/.agent-hooks/rules.md` is the user's file; the three new session rules were appended on 2026-10-25 (backup `rules.md.bak-20261025`).
- The `guard` hook also applies to Codex agents; that is intended (an agent inside a run should not launch runs).
- The `desmor-hub` task route "Preparar e validar uma release" is that repo's to fix.
- The user wants, at the end, to test the whole flow with real sessions; until then no live test.


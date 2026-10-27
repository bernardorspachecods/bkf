---
bkf: document
description: States what the agent harness is for, its layers, the decisions taken about it and what is still to verify or build. The code and each skill own their own behavior.
tags: [harness, plan]
---

# Harness goal

Update this document in the same change that settles, drops or adds an item of the lists below.

## Navigation map

| What you need | Where |
| --- | --- |
| What the harness is for | [Intent](#intent) |
| The three layers and the four step kinds | [Layers](#layers) |
| What was decided and must not be reopened | [Decisions taken](#decisions-taken) |
| What was never seen working | [Not yet seen working](#not-yet-seen-working) |
| Questions still open with the user | [Open threads with the user](#open-threads-with-the-user) |
| Small defects not yet scheduled | [Not scheduled yet](#not-scheduled-yet) |

## Intent

Agentic work should run on one common, tested harness: launching agents, checking them, keeping a run's state and resuming it. Each workflow (plan, research, council, review) defines only what is its own. The user briefs a run once, with the what and the why in enough detail that agents work on their own, and judges the result at the end; between checkpoints nobody asks small questions or sends status.

## Layers

| Layer | Holds |
| --- | --- |
| L0, harness code (Python, standard library) | Launching agents behind a backend interface (Codex or Claude), the gate, injection of text into briefs, verdict reading, state, resume, pause, lock, quota, the board, and optional capabilities. |
| L1, modules | Principles and contracts, as text that skills and briefs inject (`agent-skills/modules/`). |
| L2, workflows | The graph of steps, the briefs and role guides, and a few small functions of their own. Each workflow is a skill (`plan`, `code-review`, `council`, `research`) whose `roles/` holds its role guides and whose `scripts/` holds its run script and definition. |

Four kinds of step: agents (N in parallel), a review with a verdict (pass, back or escalate), a deterministic command, and a coordinator pause. The harness knows no workflow by name: it runs a definition it is given. The harness engine lives in `agent-skills/harness`, with its own README. Each workflow skill owns what is unique to it: its role guides in `roles/`, its run script and workflow definition in `scripts/`, and its tests in `tests/`. The engine loads a definition file it is given; it never imports a workflow.

## Decisions taken

- A module is one rule set about one activity, with a consumer: shared text goes in a module, single-consumer text stays in the skill. A skill is a menu (only when it routes) or has a single objective; a skill holds only what is unique and states orders, not routing. A rule enters only when the agent would not do it by default.
- Anything two workflows need goes to the harness, including capabilities only one uses today, as optional features: worktree isolation, the base of a diff, integration of parallel diffs, the bridge, the disk check.
- The harness is Python, standard library only. The engine is `agent-skills/harness`; the text every run script shares is the module `run-commands`; each workflow skill owns its script, definition and tests; `delegate-work` launches one agent through the same engine with a wrapper of its own.
- The Claude backend runs `claude -p` with `--permission-mode dontAsk`. Write access is confined to the working directory (path-scoped `Write` and `Edit`, plus Claude's sandbox for Bash); a reviewer can only read. Web tools (`WebFetch`, `WebSearch`) go only to research's map agent and collectors, through `agent run --web`, never to a reviewer or an implementer.
- Long or delegated work always has a goal file the agent consults; small work is aligned in conversation, with the agent restating the intent in its own words. The same sections serve both: what and why, done when, out of scope, decisions already taken, when to stop and ask, and how a change of intent is recorded.
- A skill is loaded by its description, so descriptions state the activity and, where needed, who must not load it: `code-work` and `align-intent` are for the agent working in conversation, not for an agent inside a plan, a delegated task or a review, whose brief already carries their rules. Text injected into briefs (`core-code-principles`, `gate`, `intent`) is a module with the `injected` tag.
- `repo-library` is a destination, not an entry point: nothing sends an agent there by default. Each entry must be reachable from where its activity starts (a task route in the nearest map and a link from the document that owns the activity), and `bkf validate` warns about an entry no document outside `repo-library/` links to. An `AGENTS.md` carries only repository-specific rules; it needs no pointer to `repo-library`.
- Long-running launchers (`plan-run.sh`, `review-run.sh`, `council-run.sh`, `research-run.sh`, `codex exec`) must be started with `run_in_background: true`; the `guard` hook group of `bkf hooks` refuses a foreground launch or one backgrounded by hand. It applies to Codex agents too, so an agent inside a run cannot launch runs.
- The briefs a script sends to agents are templates owned by the skill (`briefs/`, with `{{name}}` placeholders filled by `harness.template`, which fails on a placeholder without a value or a value without a placeholder); a part that depends on a condition is a fragment file. The plan's prompts stay in code for now (see `skills-audit.md`).
- The engine keeps the capabilities only the plan workflow uses today (bridge, worktree groups, integration, diff base, unit loop, metrics): they are optional features, not plan code. `agent-skills/harness` is not a BKF bundle; its README is linked from the map of `agent-skills`.
- Agents that read or write the repository work in a git worktree of the run, never in the owner's checkout: a plan on the branch `plan/<name>` (one commit per unit; the owner or the coordinator merges it), a code review at the revision under review. What a worktree lacks (dependencies, untracked configuration) is declared in the repository's committed `.plan-run.json` (`worktree.copy`, `worktree.prepare`) and set up by the script, not left to the coordinator. `--in-place` keeps the old behavior. Research and council agents never touch the repository, and `delegate-work` keeps working in place by default because its tasks are small.
- Runs live in `~/.<workflow>-runs/<repo>/<run>` and pending plans in `~/.plan-runs-pending/<repo>/<plan>`; `start <name>` starts a pending plan and consumes it. Runs of the old flat layout are still found.
- A plan run stops early when the same gate failure repeats in two rounds, and an agent can end with `BLOCKED:` or a reviewer with `VERDICT: brief`; `gates` lints the briefs and `rehearse` runs the gate lines before `start`.

## Not yet seen working

- A plan run in a worktree on a real repository with its dependencies (`desmor-hub`): the unit tests use fake agents and a repository without dependencies. How long `worktree.prepare` takes there is not known.
- The quota signal for a hit usage limit on the Claude backend. It reads `rate_limit_info.status` and `resetsAt` of the `rate_limit_event`, whose real shape was confirmed with an `allowed` event; a limit itself was never reached, so the `rejected` shape is assumed.
- A whole research run on Claude. The map agent and a collector were confirmed to open a web page with `--web`; the full workflow was not run.
- A run of plan, council, review or research on the Claude backend. `require_backend` replaced the hard-coded check for `codex`, and unit tests cover it with fake commands; no real run started on Claude for these four.
- `delegate-run.sh` on the Claude backend with a real model: its test uses a fake `claude`.

## Open threads with the user

- Whether the `intent` module is also injected into the plan, research, council and code-review coordinator guides, so their goal files carry the same sections; first see whether an agent opens `align-intent` when the user starts talking about a plan.
- Check what an agent loads in a normal session with the `retrieval-chat-audit` skill: one request of each kind, in particular adding a paragraph to an existing document (does the agent revise the section or append?) and adding a `repo-library` entry.

## Not scheduled yet

- Stopping a run ends only the agent process itself, not what it started; check whether the Codex CLI cleans up its own children.
- The bridge timeout handler in `engine/bridge.py` still waits a fixed two seconds (`_TERM_GRACE_SECONDS`) after a timeout.
- `bkf validate` and `bkf inventory` do not fail when the frontmatter of a skill is not valid YAML (for example an unquoted `: ` in a description); `bkf inventory` reports up to date while skipping the documents it cannot read. `bkf skills` reports `FRONTMATTER_INVALID`.
- In the `desmor-hub` repo: the root task route "Preparar e validar uma release" leads to a protocol that links only the database module; the platform modules are reached through `docs/feedback/release.md`. That repo owns the fix.

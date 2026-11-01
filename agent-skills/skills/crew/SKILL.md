---
name: crew
description: Open and run a crew for large work split into sub-plans, with this chat as the orchestrator. It writes a brief for each sub-plan, opens one Claude coordinator session per brief in a tmux window beside this chat, and keeps the orchestrator, the coordinators and the user in contact. Use only when the user asks for a crew or for coordinators on several sub-plans; do not use for the work itself (plan, research, council, code-review, delegate-work) or to continue one task in a new chat (handoff).
---

# Crew

A crew carries work too large for one chat. This chat is the orchestrator: it writes the briefs and opens the coordinators, and it keeps everyone in contact. Each coordinator is a full Claude session that runs its sub-plan through the existing workflows. The crew adds the management between sessions and does none of the work itself.

<!-- inject: ../../modules/coordinate-a-run.md -->
<!-- BKF:GENERATED-INJECTED -->
## Coordinate a run

The skills of the plan, code review, council and research workflows include this module, and so does the crew skill. Their guides own the phases, files and roles; this module holds what every run shares. In a workflow a script chains the phases; in a crew no script runs: the orchestrator is the coordinator, its coordinator sessions are the agents, and it chains their phases itself.

- Stay out of the roles. The coordinator keeps the conversation with the user and prepares the briefs and inputs; it does not act as researcher, implementer, advisor or reviewer, even for a small run. A gap in an agent's work goes back to an agent, through the script or in a crew through a brief, not to the coordinator to fill.
- A run has its checkpoints, usually the start, the end and an escalation. The user steers at the start and judges at the end; between checkpoints do not message them: no progress updates, status summaries or questions about small decisions. Decide those within the intent agreed with the user (`align-intent`) and continue, and stop and ask only as that intent says. The user asks for status when they want it.
- At a checkpoint the user has asked for, stop once the step's output is complete and start nothing until they approve. Give a link to the file, not its text pasted into chat. After requested changes, link the revision and wait for approval of that version.
- As soon as you create a run folder, or any file the user will read, run `open <path>` yourself and give the full path in the same message, without waiting to be asked.
- An agent's output is unverified until a reviewer who did not write it has passed it. A file existing, a handoff saying the work is done, or a provisional result unlocks nothing. The coordinator checks each return against the brief, but that check is not a formal review.
- If the same problem returns after being sent back, or a script's cap on rounds is reached, it does not go round again: it goes to the coordinator, because the brief, the objective or the inputs are probably what is wrong, and the coordinator decides whether to revise them with the user. What stays unresolved is reported plainly as weak points.
- A failed or escalated run is not a block. Read the rounds, fix the cause (usually the brief or the inputs), and resume. If an agent cannot proceed without missing guidance or a major assumption, ask the user. If no replacement agent is available, report the work as incomplete and say so.
- Report an outcome as it is: what passed, what escalated, what was skipped. Do not imply a step was done that was not.
<!-- BKF:GENERATED-INJECTED-END -->

## Settle the crew

Settle the intent with the user first (`align-intent`), for the crew as a whole:

- the sub-plans, which phase each belongs to, and what each needs from an earlier phase;
- which files, folders and schemas each coordinator owns, so no two edit the same thing;
- the workflow each coordinator is expected to use, and its model and effort if the user wants other than their defaults;
- the checkpoints: at least the end of each phase, where you stop and the user decides whether the next phase opens.

A coordinator is for work that needs coordination: several sub-plans, or one sub-plan complex enough to need its own workflows. A simple, localized fix is not: do it yourself in this chat, following `code-work`, and open no coordinator for it.

Run it inside tmux (`$TMUX` is set): coordinators open as tmux windows. In Terminal.app they open as separate windows, and in any other terminal the launcher refuses.

## Brief

Write one brief per coordinator in the scratchpad, `crew-<crew>/<name>.md`, by the rules of [handoff](../handoff/SKILL.md) for sources, access and pasted material. Give:

- the objective and when the sub-plan is done;
- what it owns and what it must not touch;
- what it receives from earlier phases, with paths or branches;
- the workflow to use;
- the roster: each coordinator open so far, with its session name and sub-plan;
- the intent: the objective, what is out of scope and the decisions already taken. The coordinator decides by it what the brief does not spell out, and logs each decision in `crew-<crew>/decisions.md`, so write it with the care that this authority needs;
- the exact command to resume the work, with its environment variables, and the decisions already taken that are not to be reopened: a coordinator loses its thread when its context is compacted, and the brief is what it rereads.

The launcher appends the crew's rules for the coordinator: when to message the orchestrator, when to message another coordinator, and when to talk to the user. Do not repeat them in the brief. Read [scripts/coordinator-rules.md](scripts/coordinator-rules.md) only to change them.

## Launch

1. Run `ListAgents`. Its first line is your own session name, which the coordinators message. Check that no live session already has the name `crew-<name>`.
2. Run [scripts/launch-coordinator.sh](scripts/launch-coordinator.sh) `<name> <your-session-name> <working-dir> <absolute-brief-path> [model] [effort]`. The model (`opus`, `sonnet`, `haiku` or a full id) and the effort (`low` to `max`) are those of the coordinator session; give them only when the user chose them while settling the crew, otherwise the session takes the user's defaults. It opens session `crew-<name>` in a window of the same name right after this one, and in this chat's iTerm2 window, without keeping focus. The session's first message is the brief followed by the rules; the full message is written next to the brief as `<name>.prompt.md`. It prints the session name.
3. Open only the coordinators of the current phase. When one joins a crew that already has others, send the new roster to each of them.
4. Write the review handoff and start the waiter, as the next section says. Then stop: do not wait on the coordinators in this chat.

The launcher starts every coordinator in auto mode. Messages between sessions are delivered only when both are in the same permission class: auto, acceptEdits and dontAsk count as prompting, bypass as the other. From an orchestrator that bypasses permissions, your messages to the coordinators are held for the user's approval, so run the crew from a session in auto mode.

A coordinator whose action is denied, or waits on the user's approval, tells you in one line what the user must approve in its window. Pass that on to the user; never do the action for it.

## End of a phase

This chat does not stay awake for the phase: every wake reloads its whole context, and a long phase outlasts the cache. The coordinators write a done file instead of a message, and a script opens a fresh orchestrator on the results.

1. Write `crew-<crew>/review-handoff.md` by the rules of [handoff](../handoff/SKILL.md). It is the first message of the orchestrator who reviews the phase, and it carries: the intent agreed with the user; the decisions taken that are not to be reopened; the roster, with each brief and its done file `crew-<crew>/done/<name>.md`; `crew-<crew>/decisions.md`, to read for what the coordinators decided; what to check in each sub-plan against its brief; and the rules of this skill that apply to it (this section, "While it runs" and the end-of-phase stop). Say that, once the user approves, it opens the next phase the same way, with its own review handoff and waiter.
2. Start the waiter in a window of its own, so that it outlives this chat (`<session>` is this chat's tmux session):

   ```
   tmux new-window -d -n crew-await '<skill>/scripts/await-crew.sh <crew-dir> <session>:crew-<name>... -- <handoff>/scripts/launch-claude.sh <working-dir> <crew-dir>/review-handoff.md [model] [effort]'
   ```

   [scripts/await-crew.sh](scripts/await-crew.sh) uses no tokens. It watches the coordinators that are not done, with [watch-coordinators.sh](scripts/watch-coordinators.sh), and sends the user a system notification on every alert (permission prompt, stalled, gone, overdue); the user answers in the coordinator's window. When every `done/<name>.md` exists and is not empty, it runs the command, which opens the new orchestrator. It never opens one for a phase where a coordinator is not done: if one fails for good, the user opens the review by hand with the same command.
3. This chat stays open and is the only one an escalation wakes: a coordinator writes to it only when blocked by something the objective does not settle, or when a decision touches a third sub-plan. Handle it as before; nothing else reaches this chat.

The orchestrator that the script opens reviews the whole phase: it reads the done files and the decisions log, checks each return against its brief and looks at the result, as "While it runs" says, and gives the user the outcome of each sub-plan.

## While it runs

- Escalations from coordinators arrive on their own. Do not poll them and do not send status requests.
- When the user changes direction on a sub-plan that is already running, a new coordinator with a new brief usually costs less than redirecting the old one, which carries the old style and a large cached context. Make sure the old one is closed before the new one acts on the same run.
- A run that stops on the agent's quota stays stopped until someone notices: with no watcher, nobody does. When the watcher is off, ask the user to say when the quota is back, or look at the run's `status.log` when they return.
- A coordinator's "done" unlocks nothing until its workflow's review has passed. Check the return against the brief and look at the result yourself. At the end of a phase, stop and give the user the outcome of each sub-plan, then open the next phase only when they approve. This is the work of the orchestrator that the waiter opens.
- When a coordinator has gone quiet longer than its work explains, look at its window before messaging: `tmux capture-pane -p -t crew-<name>` shows its screen, including a permission prompt it may be waiting on. When you wait on one result, `SendMessage` with `notify_when_idle` and no message brings one notice when it next goes idle. It also goes idle while it talks with the user, so idle does not mean done.
- A coordinator stuck on an approval prompt cannot message you. The waiter above already watches for it. Without a waiter, for a phase that runs long without the user, run [scripts/watch-coordinators.sh](scripts/watch-coordinators.sh) `<state-dir> <session>:crew-<name>...` with `run_in_background`, one target per coordinator in the roster, and `<state-dir>` a folder next to the briefs. It uses no tokens while nothing happens and exits on every alert, which wakes you. It prints one line per alert and sends the user a system notification itself. Do not replace it with a cron: each check would reload this whole chat.
  - `PROMPT <target>`: the pane shows a permission prompt. It is the user's: notify them (`PushNotification`) with the coordinator and what it asks (`tmux capture-pane -p -t <target>`), and never approve it.
  - `STILL <target>`: the pane has not changed for 10 minutes and nothing runs in the background (its status bar shows no `· N shell`), so nothing will wake the coordinator. A pane with a background shell, such as a quota wait or a workflow run, never raises it. Look at it: a prompt in other words is the user's, as above; a stalled coordinator gets one line saying why; a coordinator that waits on you needs nothing.
  - `OVERDUE <target>`: a quota wait announced a wake-up time that passed 5 minutes ago and the pane has not changed: the wait hung or the coordinator did not resume. Open the pane; if the quota is back, message the coordinator to resume.
  - `GONE <target>`: the window cannot be captured. Tell the user.
  - `WATCHER-EXIT`: the watcher stopped without an alert and nothing is watched. Find out why before relaunching.
  After handling the alerts, launch it again with the same state folder: an alert already delivered is not repeated, and an unchanged pane reminds you once an hour. Remove a coordinator from the targets when its window closes on purpose, and stop the watcher (`TaskStop`) when the phase ends.
- To change a brief, edit its file and message the coordinator that it changed; its rules name the file, so it rereads it there.
- You speak for the user to the coordinators: a decision you send or write into a brief carries the user's authority, and the coordinator acts on it without asking the user. Use that only within the intent agreed with the user; a decision outside it goes to the user first.
- A coordinator missing from `ListAgents` is not a coordinator that is gone. A session registers in `~/.claude/sessions/<pid>.json`, and `ListAgents` skips a file it cannot parse (a full disk can leave one with stray text after the JSON). Look before you conclude: `tmux list-windows` and `tmux capture-pane -p -t <window>` show whether the window lives, and a socket in `/tmp/cc-socks/<pid>.sock` means the session listens. Then, in this order:
  1. `SendMessage` to the socket address, `uds:/tmp/cc-socks/<pid>.sock`, in place of the name.
  2. Only if that fails, type into the window with `tmux send-keys -t <window> -l "[orquestrador] <message>"` and then `Enter`, after `capture-pane` shows an empty `❯` prompt and no permission prompt. Typed text arrives as if the user wrote it, so it must start with `[orquestrador]`, and it never carries a request to approve a prompt or change settings. Check the pane afterwards that it was received.
  Tell the user which registry file is unreadable; repairing it is theirs, because it is Claude Code's own state.
- A blocked coordinator gets a revised brief or a decision from you or the user, not your work in its place.
- Closing a coordinator's window is the user's call.

Tests of the launcher are in [tests/test-launch-coordinator.sh](tests/test-launch-coordinator.sh), and of the watcher in [tests/test-watch-coordinators.sh](tests/test-watch-coordinators.sh).

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

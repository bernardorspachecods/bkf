---
bkf: document
description: "Explains what BKF is and why it is built this way: the problem it solves, the layers, how a task moves through them, and what keeps a repo healthy. Does not hold the rules (library modules) or the build procedure (build-repo-organization)."
tags: [bkf, manual]
---

# What BKF is

BKF organizes a repository's knowledge and supports work with agents. It is written for agents: every document, description, map, and tag helps an agent working for the user find what it needs and act correctly. The user directs the agents and makes decisions; other human readers, such as collaborators or the public, are served where a repository has them. Read this to learn why BKF is structured as it is. An agent that knows only what the rules say applies them mechanically; an agent that knows why can explain BKF to a user and decide well in a case no rule covers.

## The problem

Left alone, an agent asked to "organize things in folders and Markdown files" produces something that works on the first day. The same fact ends up written in several files and nobody notices. Documents drift from the code. A new agent cannot tell which files are current. Rules that apply to many tasks are copied into every skill, so each skill grows and each change is made many times. Work handed from one agent to another loses what the first one knew.

BKF answers this with a few ideas applied consistently, not with a fixed set of documents.

## The ideas

- **One owner for every fact, rule, and procedure.** Everything else links to it. This makes a change cheap (one place), makes documents trustworthy (one place can be wrong, not five), and makes the documents small enough to read. The rule itself is in the library module `organize-documents`.
- **Discovery is generated, not remembered.** Each document has a description that says what it owns and where its edge is. Maps are generated from those descriptions and checked for staleness, so an agent finds a document by what it is and not by guessing a filename. A hand-written router is allowed only to add routes the map cannot express.
- **Tools do mechanical work; agents and users do judgment.** Scripts check structure, generate maps, and allocate identifiers, because an agent cannot do those reliably by hand. What belongs in a repo and what to name it are decisions between the agent and the user.
- **The user decides, the agent executes.** Organizing a repo comes from understanding what it is for and what the user needs. The agent proposes and the user decides before the agent acts. This is why the build procedure is a conversation.
- **Principles, not a fixed set of documents.** Repos differ: an app, a data project, a thesis. BKF does not prescribe which documents a repo has. The documents each one needs follow from its readers, purposes, lifecycles, and authority.
- **A rule earns its place.** A library rule is kept only if a capable agent would not follow it unprompted, it records a local preference, or it prevents a failure agents credibly show.

## The layers

| Layer | Where | What it is for | Why it exists |
| --- | --- | --- | --- |
| Format | `bkf/` | Defines a valid document, map, and bundle, and ships the tooling that checks them | Without a checkable format, structure is a convention that decays |
| Library | `agent-skills/library/` (`modules/`, `workflow-types/`) | Rule modules and workflow types for daily use, each written once | Skills repeated the same guidance; a module is written once and selected per task |
| Entry skills | `agent-skills/skills/` | Thin triggers, one per situation, each carrying a generated list of the modules that apply | The harness always loads a triggered skill's body, but a pointer to a file can be skipped, so the list sits in the skill |
| Repo library | `repo-library/` in each repo | A repo's own procedures and modules, added to the library and never restating it | A repo has local rules the library cannot know; the more specific rule wins |
| Workflows | A parent file in a bundle, shaped by `workflow-types/` | Declared stages with handoffs, independent review, user checkpoints, and going back, for complex tasks | Work that spans agents or sessions needs structure that survives a handoff; small tasks stay plain skills |

The format defines what a valid bundle is, and its tooling makes the structure checkable. The optional stop hook runs checks on changed bundles because relying on an agent to remember them in every workflow leaves gaps. The other layers guide judgment; review and the feedback file help correct the rules when something goes wrong.

## Hooks

Hooks handle behavior that must run in every session, which a skill cannot guarantee. The optional groups are: modes set talk (`t:`) or work (`w:`) mode; orient provides context at session start; check validates changed bundles when the session stops; log records ideas (`i:`) and feedback (`f:`); rules loads personal instructions. Install hooks using the repository's `INSTALL.md`. The `~/.agent-hooks/rules.md` file is personal and is not shipped with BKF. See the [hook command details](/tooling/commands.md#bkf-hooks).

## How a task moves through the layers

An entry skill matches the request. It lists the library modules that apply, and the agent reads the ones that fit. If the repo has a `repo-library/`, a line in its `AGENTS.md` sends the agent to the repo's map first, and the repo's rules add to the library's. The agent finds the documents it needs through the maps. If the task is complex, a workflow gives it stages, handoffs, and review. When it changes something, it updates the owner document in the same change.

For a complex task the coordinator picks a workflow type, the user approves the declaration, `bkf sync` scaffolds the files, and each stage agent works from an assignment and writes into its stage file. A review can send work back; a new chat resumes from the status recorded in the parent file. The steps for the coordinator are in the library module `coordinate-a-workflow`, and the file mechanics are in the [workflow foundation](/format/agent-workflow-foundation.md). Small skills such as `write-text` run anywhere in this flow.

## Keeping a BKF repo healthy

- Follow the upkeep rules in the library module `organize-documents` on every change. They are what keeps the documents current.
- Run the validator and the inventory check after changing documents. They catch structural drift. They cannot catch a wrong fact or a missing document, so judgment still reads the result.
- Record what goes wrong, a correction, an ambiguity, a failed check, in the feedback file. Review it with the user to fix the rules, not only the symptom.
- Record ideas for later in the ideas file. Review them with the user in dedicated ideas sessions.
- When the signs of drift described in `organize-documents` appear, stop and rebuild with the user using [the build procedure](/manual/build-repo-organization.md). Do not patch around them.
- When a repeated procedure appears in a repo, offer to add it to the repo library; the user approves.

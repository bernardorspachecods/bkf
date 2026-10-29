---
bkf: document
description: "The procedure for organizing a repository's documents under BKF for the first time, or revamping an outdated one, as a conversation with the user. Owns the build-only rules, the user's decision points and what the repository has when it is done; the upkeep rules are in the `repo-maintenance` skill and the reasons in what-is-bkf."
tags: [bkf, manual]
---

# Build a repo's organization

For why BKF is shaped this way, read [what BKF is](/manual/what-is-bkf.md) first.

Use this when a repo has no BKF organization, or has one that is outdated or scattered. It is a conversation with the user, not an automatic reorganizer. The user's needs decide what the repo's documents are, and the agent cannot see those needs by reading files. The BKF structure does not prescribe a fixed set of documents: repos range from apps to a thesis, so the documents each one needs come from its readers, purposes, lifecycles, and authority.

The rules that apply both while building and after are in the `repo-maintenance` skill. Follow them while building; do not restate them in the repo's documents.

## Rules for the whole procedure

- **The user decides first, the agent then executes.** While understanding the repo (step 2), take one question at a time; the target (step 3) is proposed as a whole. Write the proposal and each settled decision in a file the user can review, not only in the chat. Do not do an entire pass alone and report "repo organized". The mechanical pass in step 4 may run in one go only when everything has been settled with the user. The conversation is how you learn what the user needs, so skipping it removes the input the organization depends on.
- **Existing bundles stay separate.** A folder that is already a BKF bundle keeps its own root. The repo's root bundle lists its map and does not absorb it; see the [specification](/format/format-specification.md#33-nested-bundles).
- **Assume every area is live,** as the `repo-maintenance` skill says. In this procedure, raise an area with the user only when the repo shows it may be stale (leftovers of an earlier scheme, links to areas that no longer exist, documents that contradict the code).

## Steps

1. **Read the repo, changing nothing.** Inventory the documents, folders, maps, context files, and files the maps cannot list (spreadsheets, PDFs, data, anything kept out of version control). List files from the filesystem, not only from git, because ignored local files are invisible to a git listing and still count. Find the repo's own verification commands (documentation checks, test and lint scripts, CI) and run the cheap read-only ones for a baseline, so failures that exist before your changes are not mistaken for yours. Note the same fact stated in several places, statements that contradict each other or the code, orphaned files, and areas that look stale. Keep these findings in a working note outside the repo's documents.
2. **Understand with the user, one question at a time.** Build your understanding from the answers: choose each next question from what the last answer and the repo told you, and do not send a list. Before asking, check whether the repo, its git history, or BKF already answers it; if so, state that as an assumption in the target for the user to correct, and ask only what none of them settles. Where you would offer options, state your recommendation and what you will do unless the user objects. Ask each question as a proposal drawn from what you read in step 1 ("this folder looks like the active thesis work and that one like an abandoned first attempt; is that right?"), and ask an open question only where the repo gives you nothing to propose. The topics to cover before step 3 are what the repo is for; who else reads it besides the user and the agents working for them (collaborators, the public, a reviewer), asked only when the repo and the user's own statements leave it open; the tasks that recur; which areas exist and which look stale; what must be written down and what can be derived from the code and the documents; and which unlisted files matter enough to log. They are a checklist for you, not a script to read out.
3. **Propose the target as a whole, and get it approved by exception.** Write the target in one file, a section per area, where the user can open it. It is a working note, not a document of the repo: keep it untracked and without BKF frontmatter so no map lists it. For each area, show the documents it should have, what each owns and where its edge is (what a close neighbour owns instead), whether a task router adds anything the generated map will not, which unlisted files to log, and what to merge, move, or remove. Decide the target from responsibility, authority, lifecycle, and real consumers. The user approves the file or marks the points to change; list your assumptions in it so each can be objected to.
4. **Execute, only after step 3 is settled.** Move, merge, and remove documents by the "Fix what is clearly wrong, ask about what is not" rule in the `repo-maintenance` skill. Then add frontmatter and descriptions to every tracked document and every map, regenerate the maps with the BKF tooling, and add the repo's entry pointer in `AGENTS.md`.
5. **Verify, then ask the user to confirm.** Run the BKF validator and the inventory check, and rerun the repo's own checks from step 1 against the baseline. Read the root map as if the repo were new to you; for each row, say what the area is from the row alone. If a row does not make its area clear, its description is not done. Search every file, ignored local ones included, for the old names and paths you changed, and search for facts still written in more than one place and for stale areas that are not flagged. Trace two or three real tasks the user names to see whether an agent would find the right documents from the map. Report what was checked and what was not. Remove the working notes (findings, target) and any exported transcript from the repo unless the user asks to keep them. The repo is organized when the user says so.

## What the repo has when it is done

The target from step 3 decides the documents and areas; these are what every target ends with, or adds when its condition holds. Each row names where its rules are; do not restate them in the repo.

| In the repo | When | Rules in |
| --- | --- | --- |
| A root `MAP.md` with `bkf_version` and a generated member inventory | Always | [Specification §3.1](/format/format-specification.md#31-map-files-and-inventories) |
| A tracked root `AGENTS.md` that links the root map near its start and holds only the repo's agent rules | Always | [Specification §3](/format/format-specification.md#3-reserved-files-and-maps), the `repo-maintenance` skill |
| Frontmatter with a `description` on every tracked document | Always | [Frontmatter profiles](/format/frontmatter-profiles.md) |
| A nested `MAP.md` | A folder is a distinct navigation boundary | [Map placement guidance](/format/format-specification.md#map-placement-guidance) |
| Task routes in a map | Requests that cross areas or are ambiguous | The `repo-maintenance` skill |
| A `repo-library/` | A procedure has repeated and the user approves | The `repo-library` skill |
| `feedback.md` or `ideas.md`, with the logging rule in `AGENTS.md` | The user wants them | [Specification §3.2](/format/format-specification.md#32-feedback-file), [§3.4](/format/format-specification.md#34-ideas-file) |

The `bkf` command, the skill links and the hooks are installed on the machine, not in the repo, with this repository's `INSTALL.md`.

## For an outdated repo

Step 1 also compares what the repo says it has with what it has: stale maps, routers that point to retired areas, a legacy workspace still presented as current, and documents or maps whose descriptions no longer match their contents. Every map needs its own description. Settle with the user what becomes the owner of each fact that is stated in more than one place before moving anything. Where old and new structures must coexist for a while, flag the old one as stale in its description instead of leaving both to be inferred.

## If the user wants to skip ahead

The user may say to decide everything for them. Propose the full target in step 3 anyway and ask for approval of the whole, so the user still sees what will change. Do not start step 4 on an assumption.

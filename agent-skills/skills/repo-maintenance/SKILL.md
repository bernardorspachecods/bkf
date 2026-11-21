---
name: repo-maintenance
description: Use when your change affects a repository's documents, when organizing or restructuring them, or when writing or revising a document that other agents will act on, mostly under BKF.
---

# Repo maintenance

A BKF repository is written for agents. Each document's description says what it owns; maps are generated from the descriptions and injected at session start, so you find a document by what it owns. `bkf` and its hooks check the structure.

- **Checks before prose.** A rule that a hook or a script can check becomes that check: write or extend one before writing the rule as text, because prose can be skipped and a failing check cannot. Prose holds only what no file or check holds: context the sources do not give, and rules that need judgment.
- **One owner per fact.** Change a fact where the maps say it lives, and link to it elsewhere. Editing several files for one change means a copy exists: remove it.
- **The authority wins.** Documents record intent; the repository's sources of authority, whatever their form, settle what is true. When they disagree, or the user's account differs, say so instead of resolving it silently.
- **Revise, do not append.** Leave each document you touch reading as if written once. Keep facts, paths and identifiers exact, and check what the old text required that the new one drops.
- **Documents hold what lasts.** Work in progress lives where the repository keeps it; when it ends, move what lasts to its owner.
- **Fix what is clearly wrong, ask about what is not.** Correct a clear contradiction you meet and say so. When maps are stale in several places or an area no longer matches how it is used, stop: restructuring is a conversation the user starts.

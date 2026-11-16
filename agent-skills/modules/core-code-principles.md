---
bkf: document
description: "Sets the principles for work with code: test first, small steps with long-term decisions, reuse and code smells; and how it is verified: code decides what code can decide, every check can fail, what code cannot decide is reported as unverified. Covers any work with code, whoever does it."
tags: [injected]
---

# Core principles for code

## Building

- Test first when the behavior is clear: one failing test for one behavior (for a bug, one that reproduces it), the smallest change that passes, refactor while green.
- Small steps, long-term decisions: the smallest version that works end to end, then extend it. No stopgap meant to be replaced later.
- Reuse before building: an existing pattern, dependency or library before a new abstraction.
- Avoid these smells (a documented repository standard overrides them):
  - Duplicated logic: extract it into one function.
  - Speculative generality, abstraction or parameters nobody asked for: delete it until a real need shows.
  - Middle man, a function that only passes the call on: call the real target.
  - Shotgun surgery, one change forcing scattered edits: gather what changes together.

## Verifying

- Code decides what code can decide: every required behavior has a test, type check or script. Reading code is not evidence.
- A check must be able to fail: show it failing once before relying on it. Never weaken an existing one.
- What code cannot decide is reported as unverified, not passed. Report what ran and what came out, failures included.
- Exempt: prototypes, exploration, documentation, visual experiments, trivial config.

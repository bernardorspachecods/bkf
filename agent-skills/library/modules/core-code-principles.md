---
bkf: document
description: "Sets the principles and practices for building code: test first, growing in layers, long-term decisions, dependency choices and code smells. How work is verified follows determinism, reviews follow the plan and code-review guides."
tags: [code]
---

# Core principles for code

- Work test first, in small slices, when the behavior is clear enough to specify (a feature or a bug fix). Write one focused test for one behavior and confirm it fails for the expected reason; make the smallest change that passes; refactor while green; then take the next behavior. For a bug, start with a regression test that reproduces it, and if it does not fail as expected, investigate before changing production code. The work is done when the requested behavior is covered and the relevant tests and the nearest affected gate pass.
- Grow in layers. Start from the smallest version that works end to end and extend it one verified step at a time; the scope of a step is small, but not the quality of its decisions.
- Decide for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.
- Reuse before building. Prefer an established pattern, a well-maintained library or an existing dependency to a new abstraction or a reimplementation. Check the repository and its dependencies before assuming a capability is missing; if a new shape is necessary, keep it local and explain why.
- Avoid these smells, with their fixes. A documented repository standard overrides them.
  - Duplicated logic in the change: extract it into one function.
  - Speculative generality, meaning abstraction, parameters or hooks nobody asked for: delete them and add them back when a real need shows.
  - Middle man, a function or class that only passes the call on: call the real target.
  - Shotgun surgery, one change forcing scattered edits: gather what changes together into one module.
- How work is verified is owned by the determinism module; how a review checks code is owned by the plan and code-review guides.

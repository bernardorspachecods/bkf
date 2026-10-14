---
bkf: document
description: "Sets implementation practices for building features and fixing bugs, including test-first slices and dependency choices. Module interface design and boundaries are covered by design-modules."
tags: [code]
---

# Build software

- Grow in layers: start from the smallest version that works end to end, add each capability on top of a working product, and never trade a working product for unfinished complexity. Change one thing at a time, verify it before the next, keep intermediate states working, and do not build ahead of the next slice.
- When behavior is clear enough to specify before implementing (a feature or a bug fix, not a prototype, exploration, documentation, visual experiment, or trivial configuration), work test first in small slices: write one focused test for one concrete behavior and run it to confirm it fails for the expected reason; make the smallest change that passes; run it again and refactor while green; then take the next behavior. For a bug, start with a regression test that reproduces it, and if it does not fail as expected, investigate before changing production code. Do not write a batch of speculative tests or implementation ahead of the next slice. Finish when the requested behavior is covered, the relevant tests and the nearest affected gate pass, and no speculative behavior was added.
- Prefer an established pattern, a well-maintained library, or an existing dependency to a new abstraction or a reimplementation. Check the repository and its dependencies, and their documentation and types, before assuming a capability is missing; if a new shape is necessary, keep it local and explain why.
- Make architectural decisions for the long term; do not accept a stopgap that only works for now and is meant to be replaced later.

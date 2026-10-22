---
bkf: document
description: "Sets the principles and practices for any work with code: determinism and test-first, growing in layers, long-term decisions, dependency choices and code smells. Reviews follow the plan and code-review guides, and restructuring follows act-within-scope."
tags: [code]
---

# Core principles for code

- Let code decide what code can decide. An LLM reading LLM-written code is a probabilistic system checking a probabilistic system, so cover every behavior the task requires with a test, type check or script whose result decides, and never count a reading as evidence of what a run can show. Visual quality, opinion and whether the spec is right stay with a person and are reported as unverified, not as passed. The person or the approved plan decides what the tests specify. Prototypes, exploration, documentation, visual experiments and trivial configuration are exempt.
- Work test first, in small slices, when the behavior is clear enough to specify (a feature or a bug fix). Write one focused test for one behavior and confirm it fails for the expected reason; make the smallest change that passes; refactor while green; then take the next behavior. For a bug, start with a regression test that reproduces it, and if it does not fail as expected, investigate before changing production code. The work is done when the requested behavior is covered and the relevant tests and the nearest affected gate pass.
- Grow in layers. Start from the smallest version that works end to end and extend it one verified step at a time; the scope of a step is small, but not the quality of its decisions.
- Decide for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.
- Reuse before building. Prefer an established pattern, a well-maintained library or an existing dependency to a new abstraction or a reimplementation. Check the repository and its dependencies before assuming a capability is missing; if a new shape is necessary, keep it local and explain why.
- Avoid these smells, with their fixes. A documented repository standard overrides them.
  - Duplicated logic in the change: extract it into one function.
  - Speculative generality, meaning abstraction, parameters or hooks nobody asked for: delete them and add them back when a real need shows.
  - Middle man, a function or class that only passes the call on: call the real target.
  - Shotgun surgery, one change forcing scattered edits: gather what changes together into one module.
- How a review checks code is owned by the plan and code-review guides; changing the structure of existing code follows act-within-scope.

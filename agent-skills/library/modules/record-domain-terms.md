---
bkf: document
description: "Defines the content and use of glossaries, context maps, and decision records. Document placement and restructuring are covered by organize-documents."
tags: [writing, knowledge]
---

# Record domain terms and decisions

- Glossary: a title, a one or two sentence description of the context, and the terms, each with a one or two sentence definition of what it is, not what it does. Be opinionated: pick the best word for a concept and list the other words as terms to avoid. Group terms under subheadings when clusters emerge.
- Glossary scope: include only terms specific to this project's context, not general programming concepts however heavily the project uses them. A glossary holds no implementation details and is not a spec, a scratch pad, or a place for implementation decisions.
- Multiple contexts: a context overview lists each context, where it lives, and how the contexts relate, such as which emits what to whom and which shared types they use.
- Decision records: offer one only when the decision is hard to reverse, would surprise a future reader without context, and is the result of a real trade-off between genuine alternatives. If any of the three is missing, skip it.
- Decision records, format: follow the repository's existing location and naming convention; otherwise use `docs/adr/` with sequential numbers (`0001-slug.md`), taking the highest existing number plus one. The record is a title and one to three sentences on the context, the decision, and why; the value is that a decision was made and why, not filled-in sections.
- Decision records, optional parts, only when they add real value: a status (proposed, accepted, deprecated, or superseded by a numbered record) when decisions are revisited, considered options when the rejected alternatives are worth remembering, and consequences when downstream effects are non-obvious.

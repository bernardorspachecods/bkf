---
bkf: document
description: "Names common code smells introduced during implementation and the corresponding fixes. Repository-specific standards take precedence, while module design and implementation practices are covered by design-modules and build-software."
tags: [code]
---

# Avoid code smells

- Duplicated code: the same logic appears in more than one place in the change. Extract it into one function and call it from each place.
- Speculative generality: abstraction, parameters, or hooks added for needs nobody asked for. Delete them and add them back when a real need shows.
- Middle man: a function or class that only passes the call on. Remove it and call the real target.
- Shotgun surgery: one logical change forces scattered edits across many files. Gather what changes together into one module.
- A documented repository standard overrides these.

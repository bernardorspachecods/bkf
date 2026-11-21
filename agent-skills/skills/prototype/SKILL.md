---
name: prototype
description: Build throwaway page variants that answer what a page should look like, then carry the decision into the real code. Use when the user asks for a prototype, a demo to try, or design variants to compare; do not use for code that will ship.
---

# Prototype

A prototype exists to answer one question. Once the user has tried it and
decided, the decision goes into the real code and the prototype is discarded,
whether or not the decision is adopted.

## 1. Build

Keep it trivial to start: one command, or a file opened by double-click. Mark it clearly as a prototype.

Build several radically different variants of one page: 3 by
default, at most 5. Each differs in layout, information hierarchy or primary
affordance, not only colour; redo a variant that comes out too similar to
another with an explicit constraint.
Put them on an existing page whenever one can host them, so they meet the real
header, data and density; a new throwaway route, named so it is obviously a
prototype and following the project's routing convention, is the last resort.
For more than one variant, add a switcher: the page's data fetching stays
above it and only the rendering swaps; a fixed bottom bar shows arrows and the
variant label, updates a URL parameter, answers the arrow keys except in an
input field, and is hidden in production builds. One agent may write all the
variants.

Stop building and let the user try it. Their try-out answers the question.

## 2. Capture the decision

Rebuild the validated decision properly in the real code, following the
repository's own rules, and discard the prototype. If the user adopts nothing, only
discard the prototype.

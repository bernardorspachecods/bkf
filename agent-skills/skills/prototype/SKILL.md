---
name: prototype
description: Build throwaway code that answers a design question - does a logic or state model feel right, or what should a page look like - then carry the decision into the real code. Use when the user asks for a prototype, a demo to try, or design variants to compare; do not use for code that will ship.
---

# Prototype

A prototype exists to answer one question. Once the user has tried it and
decided, the decision goes into the real code and the prototype is discarded,
whether or not the decision is adopted.

## 1. Frame the question

Write one paragraph stating what is prototyped and the question, visibly at
the top of the prototype so it can be checked later. The question picks the
branch:

- "Does this logic or state model feel right?" - logic branch.
- "What should this look like?" - UI branch.

If the question is ambiguous and the user is not reachable, choose by the
surrounding code (a backend module is logic, a page or component is UI) and
state the assumption at the top.

## 2. Build

Keep it trivial to start: one command, or a file opened by double-click. Keep
state in memory unless persistence is the question. Skip tests, error handling
beyond what makes it run, and abstractions. Show the full relevant state after
every action or variant switch. Mark it clearly as a prototype.

**Logic branch.** One self-contained HTML file in plain HTML, CSS and JS, with
no framework or server. Put the logic in a pure module in one `<script>` (a
reducer, state machine, pure functions or a class, whichever fits) with no DOM
access, so it could later be lifted into the real code. Around it: the title
and question, the current state as labelled fields re-rendered after every
click, free-play buttons, and guided walkthroughs in tabs, each resetting to a
known state. Write labels in domain language for a non-developer.

**UI branch.** Build several radically different variants of one page: 3 by
default, at most 5. Each differs in layout, information hierarchy or primary
affordance, not only colour; redo a variant that comes out too similar to
another with an explicit constraint. Variants are read-only or point at stubs.
Put them on an existing page whenever one can host them, so they meet the real
header, data and density; a new throwaway route, named so it is obviously a
prototype and following the project's routing convention, is the last resort.
For more than one variant, add a switcher: the page's data fetching stays
above it and only the rendering swaps; a fixed bottom bar shows arrows and the
variant label, updates a URL parameter, answers the arrow keys except in an
input field, and is hidden in production builds. One agent may write all the
variants.

Stop building and let the user try it. Their try-out answers the question.

## 3. Iterate

Feedback such as "wait, that shouldn't be possible", a new action or scenario,
or "the header from B with the sidebar from C" goes back to the build step.
Stop when the question is answered.

## 4. Capture the decision

Rebuild the validated decision properly in the real code, following the
repository's own rules, and discard the prototype. Record the decision in the
repository's decision or design documents when it has a place for them, not in
the prototype and not on a kept branch. If the user adopts nothing, only
discard the prototype.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

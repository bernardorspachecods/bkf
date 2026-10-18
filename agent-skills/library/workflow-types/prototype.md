---
bkf: document
description: Defines a throwaway prototype workflow for answering a logic or UI design question, then carrying the decision into real code or discarding it. The prototype itself is not a production deliverable.
tags: [code]
---

# Prototype

**Use when** the user wants throwaway code that answers a design question:
either "does this logic or state model feel right?" or "what should this look
like?". The question decides the branch, and the two branches produce very
different artifacts. If the question is ambiguous and the user is not
reachable, choose by the surrounding code (a backend module is logic, a page or
component is UI) and state the assumption at the top of the prototype. It may be run in a reduced form; see "Required core and optional stages".

## Declaration

The same four units serve both branches; only the build differs.

Logic branch: one self-contained HTML file with free-play buttons and guided
walkthroughs, driven by a small pure module that could later be lifted into the
real code.

```bkf-workflow
steps:
  - work_unit:
      title: "Question"
      steps:
        - stage: {title: "Frame question — choose the branch and note any assumption"}

  - work_unit:
      title: "Build"
      steps:
        - stage: {title: "Build demo — write the pure logic module and the single-file demo", human_checkpoint: true}

  - work_unit:
      title: "Capture"
      steps:
        - stage: {title: "Capture decision — fold the validated decision into the real code and discard the prototype"}
```

Every `parallel` group in this workflow type follows run-parallel-work.md: each branch brief declares its gate, and a branch is checked with `bkf gate` before the next step uses it.

UI branch: several radically different variants of one page, switchable with a
URL parameter and a floating bar. The number of variants defaults to 3 and is
capped at 5.

```bkf-workflow
steps:
  - work_unit:
      title: "Question"
      steps:
        - stage: {title: "Frame question — choose the host page and set the number of variants"}

  - work_unit:
      title: "Build"
      steps:
        - parallel:
            - stage: {title: "Variant A"}
            - stage: {title: "Variant B"}
            - stage: {title: "Variant C"}
        - stage: {title: "Variant switcher — wire the variants to the switcher bar", human_checkpoint: true}

  - work_unit:
      title: "Capture"
      steps:
        - stage: {title: "Capture decision — fold the winner into the real code and discard the prototype"}
```

## Required core and optional stages

- **Required core:** a stated design question the prototype answers, written visibly at the top of the prototype (see the Question row in Stage notes), and the prototype is throwaway: it is discarded, even when its decision is adopted (see "Prototype constraints" and the Capture row).
- **Optional stages:** the Question unit may be one sentence merged into Build for an obvious question. One agent may write all the UI variants when that is cheaper, as long as they stay structurally different. The switcher is skipped for a single variant. Capture is skipped if the user adopts nothing, beyond discarding the prototype.
- The build checkpoint stays: the user trying the prototype is how the question gets answered.
- A light run: the question at the top, one small page or module, the user's try-out, then the decision built into the real code or dropped, and the prototype discarded.

## Stage notes

| Stage | Receives | Output |
| --- | --- | --- |
| Question | The user's prompt and the surrounding code | One paragraph stating what is being prototyped and the question, written visibly at the top of the prototype so it can be checked later. For UI, a one-line plan naming the host page, the variant keys, and the route. |
| Build, logic | The question | The logic in a single `<script>` as a pure module (a reducer, a state machine, pure functions, or a class, whichever fits the question) with no DOM access, and a thin page around it: title and question, the current state as labelled fields re-rendered after every click, free-play buttons, and guided walkthroughs in tabs, each resetting to a known state. Written in domain language for a non-developer, plain HTML, CSS, and JS, no framework or server. |
| Build, variants | The page's purpose and data, the project's component library | Each variant is structurally different (layout, information hierarchy, primary affordance), not only colours. Read-only or pointed at stubs. A variant that comes out too similar to another is redone with an explicit constraint. |
| Build, switcher | The variants | The existing page's data fetching stays above the switcher; only the rendering swaps. A fixed bottom bar with arrows and the variant label, updating the URL parameter and answering the arrow keys except in an input field, hidden in production builds. |
| Capture | The user's verdict | The validated decision rebuilt properly in the real code, and the prototype discarded, whether or not the decision is adopted. The decision is recorded in the repository's own decision or design documents when it has a place for such records, not in the prototype and not on a kept branch. |

For UI, a variant goes onto an existing page whenever one can host it (so it
meets the real header, data, and density). A new throwaway route, named so it
is obviously a prototype and following the project's routing convention, is the
last resort.

## Going back and limits

- Feedback such as "wait,
  that shouldn't be possible", a new action or scenario, or "the header from B
  with the sidebar from C" returns work to the build unit. Prototypes evolve.
- The prototype stops when the question is answered. Rewrite properly when folding it in.

## Prototype constraints

A prototype is clearly marked as one, and trivial to start: one command, or a
file opened by double-click. It keeps state in memory unless persistence is the
question, skips tests, error handling beyond what makes it run, and
abstractions, and shows the full relevant state after every action or variant
switch.

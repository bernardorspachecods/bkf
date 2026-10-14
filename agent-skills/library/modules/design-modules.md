---
bkf: document
description: "Provides vocabulary and decision rules for module depth, interface seams, dependencies, and tests across interfaces. Implementation sequencing and test-first practices are covered by build-software."
tags: [code]
---

# Design modules

- Aim for deep modules: a lot of behavior behind a small interface, with the seam placed where something varies and tests crossing it. A module is shallow when its interface is nearly as complex as its implementation. Depth is leverage for callers (more capability per unit of interface learned) and locality for maintainers (change, bugs, and verification concentrate in one place).
- Use these terms and avoid "unit", "component", "service", "API", and "boundary" (which clashes with bounded context) unless they name a distinct framework, deployment, or protocol concept. A module is anything with an interface and an implementation, at any scale. The interface is everything a caller must know: signature, invariants, ordering, error modes, required configuration, and performance characteristics. A seam is where a module's interface lives and behavior can change without editing in place; an adapter is a concrete thing that satisfies an interface at a seam.
- Measure depth as leverage at the interface, not as implementation lines over interface lines, which rewards padding.
- Deletion test: imagine deleting the module. If complexity vanishes, it was a pass-through; if it reappears across several callers, it earns its keep. Merge pass-throughs; do not split a module that passes the test.
- Reduce an interface by asking whether methods can be fewer, parameters simpler, and more complexity hidden inside.
- The interface is the test surface: callers and tests cross the same seam. A test that must reach past the interface, or that changes when only the implementation changes, shows the module is the wrong shape or the test is at the wrong place. Parts internal to a deep module can have private seams used by its own tests; do not expose them in the interface.
- One adapter is a hypothetical seam, two make a real one. Introduce a port only when two adapters are justified (typically production and test); otherwise it is indirection. With no tests yet, still place the seam correctly by accepting the dependency instead of constructing it, but write the in-memory or mock adapter only when a test or a second real caller needs it.
- Make code testable by accepting dependencies instead of creating them, and by returning results instead of producing side effects.
- To deepen a cluster of shallow modules, classify its dependencies, which decides how it is tested across the seam:
  - In-process (pure computation, in-memory state): merge and test through the new interface; no adapter.
  - Local-substitutable (has a local stand-in such as an in-memory database or filesystem): deepen if the stand-in exists and run it in the test suite; the seam stays internal.
  - Remote but owned (your own services across a network): define a port at the seam, with the logic in the deep module and the transport injected, an HTTP, gRPC, or queue adapter in production and an in-memory adapter in tests.
  - True external (third-party services): inject the dependency as a port and use a mock adapter in tests.
- When deepening, replace tests instead of layering: delete the old unit tests of the shallow modules once tests exist at the deepened interface, and assert observable outcomes there, not internal state.
- To design an interface twice, first show the user the problem space (constraints, dependencies and their category, a rough sketch that is not a proposal) and proceed while they read. Brief each design on separate technical facts (paths, coupling, dependency category, what sits behind the seam) and the project's own domain terms, and require each to return the interface with invariants, ordering, and error modes, a caller usage example, what the implementation hides, the adapters, and where leverage is high or thin. Suggested constraints: minimize to one to three entry points, maximize flexibility, make the common caller's case trivial, and design around ports and adapters when dependencies cross a seam.
- Present the designs one at a time, then compare them on depth, locality, and seam placement, and give one opinionated recommendation, or a hybrid, instead of a menu.

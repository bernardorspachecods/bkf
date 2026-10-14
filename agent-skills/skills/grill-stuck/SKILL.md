---
name: grill-stuck
description: Re-ground unreliable work and recover from failed approaches.
---

# Re-ground and recover unreliable work

Use this skill when the agent is stuck, repeating an approach, accumulating failures, drifting from the task, ignoring evidence or repository guidance, making unsupported claims, or adding unjustified complexity.

Pause the current task. Do not continue implementing or make new claims until the situation is re-grounded.

## Re-ground

1. Restate the original objective, the desired outcome, and the current decision or blocker.
2. Separate what is confirmed from what is inferred, assumed, unknown, or contradicted.
3. When a repository is in scope, read applicable guidance, then inspect only the relevant documentation, code, tests, errors, and recent changes.
4. Separate symptoms from the desired outcome. Review previous attempts, failures, and evidence that rules hypotheses out.
5. Identify the likely root cause, surface relevant assumptions and failure modes, compare plausible alternatives, and recommend the simplest supported direction.
6. Be honest about uncertainty. Do not repeat failed approaches, weaken tests, ignore guidance, or invent complexity. Use focused, non-destructive diagnostics when they distinguish hypotheses; do not modify the implementation.

## Clean up failed attempts

When failed attempts left changes in the repository, after diagnosing the cause and before implementing:

- inspect the current changes;
- identify the cleanup scope and revert or remove only changes attributable to the failed attempts;
- preserve unrelated or uncertain changes;
- ask before destructive actions;
- verify the baseline, then implement the approved direction.

If ownership is uncertain, leave the change untouched and report it.

Report the diagnosis, cleanup scope, recommendation, and open questions. Wait for approval before cleanup or implementation. Continue only after the user confirms the direction or the corrected understanding is sufficiently grounded for a low-risk next step.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

---
bkf: document
description: "States the contract of the gate, the commands a script runs outside any agent to decide what code can decide: how they run, what they record, and what an agent that receives the result does with it."
tags: [injected]
---

# The gate

- Code runs each command outside any agent, in its own process group.
- A time limit stops the whole process group and records exit code 124.
- The result contains the command, exit code and output tail in `gate.md`, a `gate.json`, and one log per command.
- Every command runs, even after one fails.
- A red result stands; no agent overrides it.
- No commands is a gap, not a pass.
- An agent that receives the gate takes it as given and does not run it again.

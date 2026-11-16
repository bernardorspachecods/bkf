# Agentic work implementation

You do one unit. Another agent reviews your diff against the brief and sees nothing else.

- **Stay inside the brief.** Stop where it says and leave alone what it puts out of scope. Tests and documents your change makes wrong are yours: adapt them without weakening an assertion.
- **Verify before you hand over.** Run the gate commands yourself when you can, and name any you could not. A command your sandbox blocks goes through `.plan-porteiro/ponte <command>` when the run offers it; never work around a refusal.
- **Stop when the brief no longer holds:** what you receive is false, the result cannot exist as described, or a rule forbids what the result requires. Make your last line `BLOCKED: <the sentence of the brief and what you saw>` instead of repeating the attempt.
- **If you think a returned problem is wrong,** say why.

## Handoff

Your final message: the verification you ran and its results; where the result differs from the brief, and why; what you left ready, as facts; one line for each thing you noticed outside the focus. Do not retell the diff.

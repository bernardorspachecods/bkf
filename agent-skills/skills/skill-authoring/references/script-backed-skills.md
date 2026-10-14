# Script-backed skills

Read this when authoring or reviewing a skill that bundles scripts which
generate folders, files, or text. The shared rule lives in `SKILL.md`: the
script is the source of truth, so the skill describes how to use it, not what
it contains.

## Leave out

- Full file-by-file contents or templates the script writes
- Exact text that lives in the script's templates
- Implementation details of how the script builds its output

Copies of this material drift out of sync with the script and mislead the
agent that follows the skill.

## Include

### How and when to run it

- The exact command and every argument, with a short explanation of each
- Conditions under which the script should or should not be run

### A brief map of the output

Summarize the structure the script creates, for example: "creates `project/`
with `src/`, `docs/`, and `README.md`." This should be enough for the agent to
know what to expect and to verify the run worked, without reproducing the
contents of each file.

### What the agent does afterward

This is the value the script cannot provide. Examples:

- Fill in placeholders in generated files
- Review generated configuration before presenting it to the user
- Run a validation or test step on the output

### Edge cases and gotchas

- What happens if the target folder already exists
- Required dependencies or environment setup
- Common errors and how to resolve them

### Customization points

- Generated files the user typically wants edited afterward
- Generated files the agent must not modify

## Deciding what belongs where

If the agent needs to know something to run the script correctly or to act on
its output, put it in the skill. If the agent only needs the script to do it,
leave it in the script.

## Pointing to the script

If the agent may occasionally need the script's details, for example to modify
its templates, state the script's path in the skill and say when to read it.
The agent can then inspect it on demand instead of carrying those details in
every invocation.

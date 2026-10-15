---
bkf: document
description: "Defines the syntax and editing rules for `bkf-workflow` declarations, including step types, references, IDs, and sync commands. Workflow mechanics and validation rules are specified by agent-workflow-foundation."
tags: [planning]
---

# Write a declaration

- The declaration is a `bkf-workflow` block in the parent workflow file. It is a `steps` list; each entry has exactly one key: `stage`, `work_unit`, or `parallel`. List order is execution order.
- `stage`: a `title` that begins with two words identifying the stage; they become the stage file's name. Optional: `file` (stages with the same name share one file), `human_checkpoint: true`, `key`, `after`, `reviews`.
- `work_unit`: a `title` and its own `steps`, which may nest. Add `work_unit_file: true` only when the unit needs its own file.
- Titles carry no numbering scheme of their own, such as "Phase 04" or "Subplan 04.0a": the script adds the position and the ID, so a number in the title repeats them in every file and folder name.
- `parallel`: a list of independent steps; the next step waits for all of them. `after` (sibling keys, earlier in the group) is allowed only on a step directly inside a parallel group.
- A review stage names its targets in `reviews`; a target stage or unit gets a `key` so it can be referenced. A review without `reviews` checks something outside the workflow, and its stage file names the target.
- Write no IDs; the script allocates them. Never change an existing ID.
- Run `bkf sync <parent-file>` to preview the first-time scaffold or later changes, then add `--write` to apply. Renaming while a unit is in progress needs `--confirm-in-progress`. Run `bkf validate` before delivering.

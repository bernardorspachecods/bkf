---
bkf: document
description: Defines YAML frontmatter rules, tracking, and fields for generic documents, feedback and ideas files, and workflow files. Bundle structure and conformance are specified by format-specification.md.
tags: [bkf, metadata, frontmatter]
---

# BKF Frontmatter Profiles

BKF frontmatter is YAML metadata at the beginning of a Markdown file. This file
owns all of it: the rules every profile shares, then each profile's fields and
values.

## Rules for all profiles

### YAML

Frontmatter MUST parse as YAML 1.2. Invalid YAML and duplicate keys make
frontmatter invalid. Each profile defines the fields it requires and the
types and values those fields accept.

### Preservation

When an editing operation changes a BKF document, it MUST preserve every
frontmatter field outside the operation's stated scope, including fields
the tool does not recognize. Preservation includes retaining each field's
YAML value; the tool does not need to interpret that value. A tool MAY
reformat the frontmatter as long as those values are preserved. If it
cannot preserve a field and its value, it MUST stop before writing the
document and report the limitation.

### Descriptions

For profiles and maps that define a description, write a description that
states what the file is or covers, with no "open when" or "use when" phrase.
It is the entry point an agent sees in the map, so it says what the agent needs to know before
opening the file: what the document owns and, where a close neighbour could be
confused with it, what it does not own. It is not a one-line label and not a
paragraph; specifics belong in the body. It should stand on its own in an
inventory, search result, or preview.

## Shared fields

Every profile uses this prefix, except where a profile below says otherwise:

```yaml
bkf: <profile>
```

- `bkf` names the profile. `feedback`, `ideas`, `workflow`, `workflow.work_unit`,
  `workflow.stage`, and `workflow.file` are defined in this file; every other
  document uses `document` and follows the generic rules below. BKF defines no
  other values and does not label documents by type: the description, the
  folder, and the tags say what a document is. A dot only groups profile names
  by owner; it does not imply inheritance, and each profile is a complete
  definition.
- `description` is what the map lists, so it decides tracking. A member with a
  `bkf` field and a `description` is tracked: BKF validates it and lists it in
  its map. Only the workflow internals (`workflow.work_unit`,
  `workflow.stage`, and `workflow.file`) may omit the description, and they are
  then untracked; for every other profile a missing description is a
  validation error, so a forgotten description cannot hide a file from the
  map.

A tracked member MUST NOT carry a field its profile does not define; an unknown
field is a validation error, so a misspelled or retired field cannot linger
unnoticed. The optional fields are the ones named in the workflow profiles below.

Except for structural maps, a member with no frontmatter or no `bkf` field is
untracked, and BKF ignores it. Maps have no `bkf` field and are not tracked;
their structural rules are defined by the format specification. A skill's own internal
artifacts, such as briefs, reviews, or audits, do not use the `bkf` field; the
owning skill's tooling validates them. Tracking them would flood the map.

## Generic document

`bkf: document` selects the generic rules:

| Field | Required value |
| --- | --- |
| `bkf` | The string `document`. |
| `description` | A non-empty string describing what the document is or covers. |
| `tags` | A non-empty sequence of non-empty strings. |

Every generic document MUST include all fields in this table. Empty strings,
null values, empty sequences, and other empty values are invalid. For strings,
whitespace-only content is empty. Tags are how a document is selected for a
task, so a document without them cannot be found by tag.

The generic filename rule is lowercase kebab-case. It does not apply to files
using workflow profiles, including names such as `W-01.md` and `WORK-UNIT.md`,
or to any file named `AGENTS.md`.

The description follows the [description rule](#descriptions) and supplies the
map inventory text. BKF does not define a universal document-level `title`
field. Consumers MAY use a meaningful top-level heading as a display label,
falling back to the filename stem; the bundle-root path remains the document's
identifier and navigation target.

```yaml
---
bkf: document
description: Instructions for setting up and running the build.
tags: [setup, build]
---
```

## Feedback file

`bkf: feedback` selects the profile for the optional bundle-root
`feedback.md`, where agents record what went wrong in their work. The
[format specification](/format/format-specification.md#32-feedback-file) defines
how it is used.

```yaml
---
bkf: feedback
description: Collects evidence about problems in agent work for later review with the user. It records events rather than supplying instructions.
---
```

| Field | Required value |
| --- | --- |
| `bkf` | The string `feedback`. |
| `description` | A non-empty string saying what the file holds. |

## Ideas file

`bkf: ideas` selects the profile for the optional bundle-root `ideas.md`, where
the user or agents record ideas for later. The
[format specification](/format/format-specification.md#34-ideas-file) defines
how it is used.

```yaml
---
bkf: ideas
description: Collects ideas from the user and agents for later review as future possibilities, not instructions.
---
```

| Field | Required value |
| --- | --- |
| `bkf` | The string `ideas`. |
| `description` | A non-empty string saying what the file holds. |


## Workflow document

The parent workflow is tracked in BKF. Stage files, shared stage files, and
standalone work-unit files are untracked so a large workflow does not fill the
map. Workflow tooling reads and validates these files independently of their
own tracking, for every workflow in the bundle; see
[Closing a workflow](/format/agent-workflow-foundation.md#closing-a-workflow).

### Parent workflow

```yaml
---
bkf: workflow
description: Defines the composed workflow, its declaration, and its execution order.
workflow_id: W-01
execution_status: in_progress
unit_status:
  WU-01.02: in_progress
---
```

`execution_status` records the overall workflow state and `unit_status` records
work-unit progress; it is omitted until work starts. The [workflow foundation](/format/agent-workflow-foundation.md#correction-and-resume-status)
defines their values, which entries `unit_status` keeps, and who writes them.

### Work-unit file

```yaml
---
bkf: workflow.work_unit
work_unit_id: WU-01.01
---
```

The work-unit file carries no status; progress is recorded in the parent.

### Stage file

```yaml
---
bkf: workflow.stage
stage_id: ST-01.01.03
reviews: [ST-01.01.02]
---
```

The stage order and title come from the parent workflow; the containing
folder identifies its work unit. The stage file uses the shared fields and
`stage_id`, which tooling checks against the parent declaration. `reviews`
appears only on review stages. The file also carries `human_checkpoint: true`
when the parent requires approval after that stage. The script generates these
fields; omit the optional ones when they do not apply.

A stage file may opt into tracking by adding a `description`, which the
profile allows as an optional field; the map then lists it. Tooling that edits the file preserves that field. Deliverables
that should be discoverable are normally separate ordinary documents using the
generic document profile.

### Shared stage file

Stages that name the same `file` in the declaration share one document.

```yaml
---
bkf: workflow.file
stage_ids: [ST-01.01.01, ST-01.01.02, ST-01.01.03]
---
```

It has no per-stage frontmatter, so review targets and checkpoints stay in
the declaration. Tooling does not read the body. It may opt into tracking like
a stage file.

The `workflow`, `workflow.work_unit`, `workflow.stage`, and `workflow.file`
profile values follow the `bkf` field. The
[foundation](/format/agent-workflow-foundation.md#composition-ordering-and-identity)
defines the IDs, and its [validation checks](/format/agent-workflow-foundation.md#validation)
list what tooling verifies about these files.

## Map files

`MAP.md` is a structural file and carries no `bkf` profile field. Its
`description` follows the [description rule](#descriptions). The
[format specification](/format/format-specification.md#31-map-files-and-inventories)
defines the allowed fields and other map requirements.

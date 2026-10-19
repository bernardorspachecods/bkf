---
bkf: document
description: Defines YAML frontmatter rules, tracking, and fields for generic documents, feedback and ideas files. Bundle structure and conformance are specified by format-specification.md.
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

- `bkf` names the profile. `feedback` and `ideas` are defined in this file; every
  other document uses `document` and follows the generic rules below. BKF defines no
  other values and does not label documents by type: the description, the
  folder, and the tags say what a document is. A dot only groups profile names
  by owner; it does not imply inheritance, and each profile is a complete
  definition.
- `description` is what the map lists, so it decides tracking. A member with a
  `bkf` field and a `description` is tracked: BKF validates it and lists it in
  its map. A missing description on a member with a `bkf` field is a
  validation error, so a forgotten description cannot hide a file from the
  map.

A tracked member MUST NOT carry a field its profile does not define; an unknown
field is a validation error, so a misspelled or retired field cannot linger
unnoticed.

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
task, so a document without them cannot be found by tag. A generic document
MAY also carry the optional [`ext` field](#repo-specific-fields-ext).

The generic filename rule is lowercase kebab-case. It does not apply to any
file named `AGENTS.md`.

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

### Repo-specific fields (`ext`)

A repository whose documents need fields BKF does not define keeps them in
`ext`, an optional mapping on the `document` profile. No other profile accepts
it. Repo-specific fields never sit beside the BKF fields, so a future BKF field
cannot collide with them.

```yaml
---
bkf: document
description: Explains why the pipeline uses queues instead of polling.
tags: [architecture]
ext:
  adr_number: 14
  supersedes: ADR-009
---
```

`ext` is validated against the `ext-schema.yaml` file at the bundle root. The
file is a [JSON Schema](https://json-schema.org/draft/2020-12) (draft 2020-12)
written in YAML, and BKF applies it to the object `{ext: <value>}`, so the
schema describes `ext` under `properties`. A bundle owns one schema for all its
documents; where documents have different shapes, the schema tells them apart
by a field inside `ext` with `if` and `then`.

- A document with `ext` in a bundle without `ext-schema.yaml` is invalid
  (`EXT_SCHEMA_MISSING`). A schema that is not valid JSON Schema is invalid
  (`EXT_SCHEMA_INVALID`).
- A value that does not satisfy the schema is invalid (`EXT_INVALID`); the
  message names its location, such as `ext/connections/0/relation`.
- BKF does not require the schema to be closed. A schema that omits
  `unevaluatedProperties: false` on `ext` accepts any extra field, which
  removes the protection against invented fields. Use `unevaluatedProperties`,
  not `additionalProperties`, because `additionalProperties` inside an `if` or
  `then` branch does not see the `properties` declared outside it.
- The file is not a member: BKF does not list it in the map, and it is
  referenced from the map as an artifact reference.

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


## Map files

`MAP.md` is a structural file and carries no `bkf` profile field. Its
`description` follows the [description rule](#descriptions). The
[format specification](/format/format-specification.md#31-map-files-and-inventories)
defines the allowed fields and other map requirements.

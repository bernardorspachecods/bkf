---
bkf: document
description: "Defines the shared workflow model, file generation, execution status, recovery, and validation rules for BKF workflows. Workflow types own their task-specific stages, evidence, and quality criteria."
tags: [bkf, agent-workflows, design]
---

# Agent Workflow Foundation

## Navigation map

| If you need to... | See |
| --- | --- |
| Understand the purpose and design boundaries | [Purpose and scope](#purpose-and-scope) |
| Understand work units, ordering, and parallel work | [Workflow model](#workflow-model) |
| Understand workflow files and generation | [Files and generation](#files-and-generation) |
| Understand checkpoints, correction, and resume status | [Execution and recovery](#execution-and-recovery) |
| Understand what BKF checks in a workflow | [Validation](#validation) |

## Purpose and scope

This is the common BKF foundation for agent workflows: the shared mechanics
and metadata that workflow types would otherwise each repeat. Workflow types
and tasks own task-specific instructions, criteria, evidence rules, and body
structure; BKF prescribes no workflow-document body sections and defines no
universal stage sequence. BKF validates the frontmatter and declaration rules
in this document; content, evidence, and quality checks stay with the workflow
types and tasks. Skill selection is not BKF's concern, though a workflow body may
name a user-invoked skill as a task direction.

## Workflow model

### Work units

- A workflow is composed of work units. Work units can contain nested work
  units recursively, to whatever depth is useful.
- Each work unit has a hierarchical identity and ordered steps. Artifacts
  produced by or associated with a work unit are distinct from the unit
  itself.
- A stage has no declared role. Its title and body say what it does; a stage
  that checks other work marks its targets with `reviews`.

### Composition, ordering, and identity

#### A workflow declaration is a structured block

A workflow declaration is a structured
`bkf-workflow` body block in the parent workflow file:

- The parent and each work unit have ordered `steps` lists. Each list entry
  is a single-key tagged mapping: `stage`, `work_unit`, or `parallel`.
- A `stage` value contains its `title`; each stage
  is assigned to one agent. It may also name a shared `file` (see
  [Files and generation](#files-and-generation)).
- A `work_unit` value contains its title and ordered `steps`. These steps may
  mix stages, nested work units, and parallel groups.

#### Parallel steps run independently

- A `parallel` value is a list of independent steps, such as stages or work
  units. Its steps can run concurrently, and the next step waits until every
  branch finishes. A parallel group is a control structure, not a work unit,
  and has no separate file.
- A step directly inside a parallel group may declare `after`, a list of
  sibling steps (stages or work units) that must finish before it starts. This
  expresses dependency graphs, such as one step needing only one of two
  siblings:

  ```yaml
  - parallel:
      - stage: {key: api,     title: "API implementation"}
      - stage: {key: migrate, title: "Migration writing"}
      - stage: {key: docs,    title: "API docs writing", after: [api]}
      - stage: {key: tests,   title: "Integration tests", after: [api, migrate]}
  ```

  `after` is valid only on a step directly inside a parallel group, since a
  sequence already waits for everything before it. Targets must be siblings in
  the same group and come earlier in declared order, which prevents cycles.
  A step that needs a stage inside a sibling unit either waits for that whole
  unit or the group is flattened so the steps become siblings.

#### Each entry has one tag

- Each entry has exactly one tag, making its step kind explicit and
  straightforward for the script to validate.

#### The parent workflow is the canonical source for step order

- The parent workflow is the canonical source for step order and parallel
  group membership. Folder listing order does not define execution.

#### Workflow, work-unit, and stage IDs show parentage

- A workflow uses an ID such as `W-01`, work units use nested IDs such as
  `WU-01.01` and `WU-01.01.01`, and stages use IDs such as `ST-01.01.03`
  (workflow, work unit, stage), with two digits per segment. Parentage can be
  derived from the ID, so parent relationships do not need duplicate
  frontmatter.
- The LLM writes the declaration without IDs. On first generation the script
  allocates every ID, using the shared [ID allocator](/tooling/workflow-synchronizer.md#shared-modules), and writes each
  back into each entry of the `bkf-workflow` block under an `id` key. IDs are
  never renumbered, so inserting a step does not shift existing IDs;
  declaration order, not ID order, defines execution. A stage
  directly under the parent has a two-segment ID such as `ST-01.03`; a stage in
  a work unit has three, such as `ST-01.03.01`.

#### Review stages declare the targets they check

- A review stage may declare `reviews`, a list of the stage or work-unit IDs
  it checks. A stage or work unit that is the target of `reviews` or `after`
  may carry an author-chosen `key` so the LLM can reference it before IDs
  exist; the script resolves keys to IDs. The validator checks that every target exists and comes earlier in
  declared order. Review criteria stay in the document body.

#### A review without `reviews` checks outside the workflow

- A review without `reviews` checks something outside the workflow, such as a
  diff, a file, or the workflow's own plan. The stage file names the target and
  the criteria, and the findings go to the coordinator, who decides what to
  correct. There is no declared external target.

#### The workflow defines ordering and relationships

- The workflow already defines ordering and relationships. Per-unit
  `depends_on`, `consumers`, and `starts_when` fields are unnecessary when
  that information is present in the workflow.

#### The script numbers every step in declared order

The script numbers every step in a list, whether a stage or a work unit, with
one shared two-digit sequence in declared order, so a folder listing reads in
execution order at every level. This applies equally to steps directly under
the parent. Parallel steps follow their declared order when numbered.

#### A stage file is named from its title prefix

- A stage file is named `<NN>-<title-prefix>.md`. The slug is
  the first two words of the title, lowercased, with punctuation removed and
  words joined by hyphens. Stage titles should begin with two words that
  identify the stage. A one-word title uses that word; a title with no usable
  slug falls back to `stage`; slugs are capped in length. For example,
  "Final sign-off" becomes `final-signoff`. The number keeps names unique, so
  slug collisions need no extra rule.

#### A shared file takes the first stage number

- A shared file is named `<NN>-<name>.md`, where `<name>` is the stage's
  `file` value. It takes the number of the first stage that names it. Later
  stages in the same folder that name the same file use no number of their
  own.

#### A work-unit folder is named from its unit ID

- A work-unit folder is named `<NN>-<unit-id>-<title-slug>/`, such as
  `01-WU-01.01-advisor-round/`. The ID identifies the unit; the number is only
  its position and can change when sync renumbers.

#### The workflow folder is named from its workflow ID

- The workflow folder is named `<workflow-id>-<title-slug>/`, such as
  `W-01-council/`, following the same pattern as work-unit folders.

## Files and generation

- The parent workflow has its own file, and each stage has its own file
  unless it names a shared `file`. A work unit may
  declare `work_unit_file: true` to generate its own file; omitting the field
  means no standalone work-unit file is generated. Work units remain distinct
  hierarchical entities either way, and child work units recursively own
  their ordered steps.
- BKF provides a generic script to process explicitly composed workflows and
  automate shared mechanics. The LLM composes the workflow in its parent
  file; the script allocates workflow, work-unit, and stage IDs and scaffolds the
  workflow, stage files, shared files, and any work-unit files requested on
  individual work units.
  Workflow types and tasks supply domain-specific content and should not need
  workflow-specific scripts for common mechanics. The stage and work-unit
  frontmatter profiles are defined in the
  [frontmatter profiles](/format/frontmatter-profiles.md).
- A workflow type may describe what its part of a larger piece of work needs,
  in whatever stages suit the workflow type. The coordinator adds
  those units and stages to the enclosing workflow's declaration; a workflow
  ID always means one distinct piece of work, so a workflow type's part is
  never a separate workflow. BKF defines no reusable-fragment mechanism. Stage-level
  settings, such as a research rigor level, go in the stage body.
- Titles become generated Markdown headings. BKF does not define other body
  sections; the workflow type owns the remaining document content.
- The workflow's title is the parent file's top-level heading; no title field
  exists. The script derives the workflow folder's title slug from it and
  places the parent file in that folder as `<workflow-id>.md`. The shared allocator
  assigns the workflow ID.
- A stage's response lives in its own stage file, or in the shared file it
  names. Stage files are untracked unless they add a `description` (see the
  [stage file profile](/format/frontmatter-profiles.md#stage-file)). When a stage produces a deliverable that should be
  discoverable, such as a final report, it is an ordinary BKF document at a
  path the workflow type names in the stage body, with a
  `description` and the generic document profile. It is generated into the
  map like any tracked document.
- Stages that name the same `file` share one document, so several stages can
  build on a single working file, such as a define, implement, and review
  sequence on one change record, or a research record that stages in different
  work units update. The script creates the file once, in the folder of the
  first stage in declared order that names it. Stages elsewhere use it by
  link.
- A shared file's frontmatter is defined in the
  [frontmatter profiles](/format/frontmatter-profiles.md#shared-stage-file). Review targets and
  checkpoints stay in the declaration.
- The script scaffolds a shared file's body once at creation, with a heading
  per stage that includes the stage ID, and a note under any stage with a
  human checkpoint. After creation BKF never rewrites or validates the body.
  The agent may reorganize it freely and owns adding a section when a stage
  joins. A stage may also write into shared documents that its body names;
  which fields each stage may write is the workflow type's rule.
- Revisions and criteria references such as `criteria_source` belong in
  document bodies. Review targets are the exception, because the validator
  checks them (see Metadata in `design-decisions.md`).

### Syncing after the declaration changes

When the declaration changes after files exist, an explicit sync command
brings the files back in line with it. The
[synchronizer brief](/tooling/workflow-synchronizer.md) defines what it does.

- The declaration may be extended during a run. When the number of steps
  depends on earlier results, such as one evaluation stage per source group, the
  coordinator adds the new steps to the declaration once that number is known
  and runs sync to create their files and allocate their IDs.
- Sync is explicit. It never runs automatically on a declaration change.
- Renaming a file that an agent is writing to breaks that agent, so renames
  while a work unit is `in_progress` need an explicit confirmation. The
  coordinator judges whether it is safe, for example by waiting for running
  agents to finish. Plans that only add files need none.
- References to renamed files are the agent's responsibility. Agents should
  link to workflow files with ordinary Markdown links so the references can be
  found.

### Illustrative declaration and output

This LLM Council example shows sequential stages interleaved with parallel
groups. The Advisor round requests a standalone work-unit file; the other
work units omit one. All three remain in the workflow declaration.

```bkf-workflow
steps:
  - work_unit:
      title: "Advisor round"
      work_unit_file: true
      steps:
        - stage:
            title: "Council brief preparation"
            human_checkpoint: true

        - parallel:
            - stage:
                title: "Contrarian advisor — write independent advice"
            - stage:
                title: "First principles advisor — write independent advice"
            - stage:
                title: "Expansionist advisor — write independent advice"
            - stage:
                title: "Outsider advisor — write independent advice"
            - stage:
                title: "Executor advisor — write independent advice"

        - stage:
            title: "Anonymized response packet preparation"

  - work_unit:
      title: "Peer review"
      steps:
        - parallel:
            - stage:
                title: "Reviewer 1 — review the anonymized responses"
            - stage:
                title: "Reviewer 2 — review the anonymized responses"
            - stage:
                title: "Reviewer 3 — review the anonymized responses"
            - stage:
                title: "Reviewer 4 — review the anonymized responses"
            - stage:
                title: "Reviewer 5 — review the anonymized responses"

  - work_unit:
      title: "Report and delivery check"
      steps:
        - stage:
            title: "Chairman report preparation"
        - stage:
            title: "Completeness check"
```

An illustrative hierarchical output is:

```text
W-01-council/
├── W-01.md
├── 01-WU-01.01-advisor-round/
│   ├── WORK-UNIT.md
│   ├── 01-council-brief.md
│   ├── 02-contrarian-advisor.md
│   ├── 03-first-principles.md
│   ├── 04-expansionist-advisor.md
│   ├── 05-outsider-advisor.md
│   ├── 06-executor-advisor.md
│   └── 07-anonymized-response.md
├── 02-WU-01.02-peer-review/
│   ├── 01-reviewer-1.md
│   ├── 02-reviewer-2.md
│   ├── 03-reviewer-3.md
│   ├── 04-reviewer-4.md
│   └── 05-reviewer-5.md
└── 03-WU-01.03-report-and-delivery-check/
    ├── 01-chairman-report.md
    └── 02-completeness-check.md
```

The workflow has three sibling work units for the advisor round, peer review,
and reporting. Each unit mixes sequential stages with parallel agent stages
where needed. Nested work units can appear as subfolders when useful. Each
work-unit folder contains that unit's stage files. A work unit with
`work_unit_file: true` also gets a `WORK-UNIT.md`; work units without the field
do not. Whether a unit has a file does not affect status tracking: all
execution status is recorded in the parent workflow (see
[Correction and resume status](#correction-and-resume-status)).

## Execution and recovery

What the coordinator does at a checkpoint, when a stage fails, and when a stage's inputs are restricted is in the library module `coordinate-a-workflow`. This section defines the fields and values the format records.

### Human checkpoints

A human checkpoint is a setting on a stage, not an independent work unit,
stage, or document. The parent workflow uses `human_checkpoint: true` to
require approval after a stage. The script flags it in that stage's file (the
field is in the [stage file profile](/format/frontmatter-profiles.md#stage-file)), or with a note in the
scaffold when the stage is in a shared file.

- Approval happens in the interaction with the user. The workflow files do
  not record it, and no version-bound approval fields are needed. The
  flag signals the requirement but does not enforce it; if the coordinator
  ignores a recorded approval field it would ignore the checkpoint too.
- Checkpoint frequency is fixed in the declaration. The LLM sets
  `human_checkpoint` on the stages the user wants to review, and changing the
  frequency later is a declaration edit. There is no separate per-workflow
  granularity setting.

### Correction and resume status

- A review does not need a separate `returns_to` relationship: its `reviews`
  field identifies the work whose owner receives findings for correction.
- A review may name any earlier stage or unit in `reviews`. When its findings
  show a problem upstream, the coordinator returns work to the owner of that
  stage: it re-lists the earlier unit as `in_progress` in `unit_status`, and
  every later unit counts as `not_started` again by the derivation rule. The
  declaration stays acyclic and has no loop construct; going back is a runtime
  action, not a declared loop.
- Execution status exists to let a stopped run resume at the right work unit.
  It is a resume marker, not a record of review verdicts or stage results.
  Stages store no status. Review verdicts are handled in the live
  coordination; when a review sends work back, the unit being corrected
  returns to `in_progress`.
- Status is recorded only in the parent workflow's frontmatter, and only the
  coordinator writes it. No other workflow file carries status.
- `blocked` means progress is paused waiting on a user decision; an agent
  failure is not a block. BKF does not say whether or where the reason is
  written; the agent and user decide whether to report it in the conversation,
  the parent, or a stage file.
- The parent's `execution_status` records the overall state: `not_started`,
  `in_progress`, `blocked`, or `complete`.
- The parent's `unit_status` map records work-unit progress by work-unit ID,
  using `in_progress`, `blocked`, or `complete`. It lists in-flight units and
  units completed since the last step began. A `complete` entry is dropped once
  the next step after it has started, so the map always keeps an anchor at a
  boundary between units.
- A unit not listed is `not_started` if it comes after the earliest listed
  unit in declared order, and `complete` if it comes before it. Inside a
  parallel group this rule does not apply, because branches may start out of
  declared order: a branch is `not_started` unless listed, each started
  branch is listed `in_progress`, and a finished branch stays listed as
  `complete` until the group is done and the following step begins.
- Only the leaf-most in-flight units are listed. Ancestors are derived from the
  hierarchical ID: if `WU-01.01.02` is in progress, so is `WU-01.01`.
- When the workflow finishes, the coordinator sets `execution_status:
  complete` and clears `unit_status`.
- A status update changes only `execution_status` and `unit_status`; it must
  not change the `bkf-workflow` declaration block. The validator cannot check
  this, because it has no earlier state to compare against.

### Closing a workflow

When a workflow is complete, the user deletes its folder or moves it out of the
bundle. A workflow has no closed marker: its parent always has a `description`
and is tracked, so the tooling validates and syncs every workflow in the bundle.
To redo a closed workflow, restore it from version control. Turning a
workflow's repeated procedures into repo-library entries is a separate process
that this foundation does not define; see the `grow-repo-library` module.

## Validation

The workflow validator checks every workflow in the bundle (see
[Closing a workflow](#closing-a-workflow)). It reports the checks below. All
are errors except naming drift, which is a warning because sync repairs it.
Content, evidence, and acceptance criteria stay with the workflow type. The
validator runs the same declaration-only checks as scaffold and sync, which
the tooling implements in one shared module (see the
[shared modules](/tooling/workflow-synchronizer.md#shared-modules)). This
list is the owner of what is checked.

**Declaration structure**

1. The parent contains exactly one `bkf-workflow` block, and it parses as
   YAML.
2. Every entry has exactly one tag: `stage`, `work_unit`, or `parallel`.
3. Every stage has a non-empty title.
4. Every work unit has a title and a non-empty `steps` list, and every
   `parallel` list is non-empty.
5. `human_checkpoint` and `work_unit_file` are booleans when present, and
   `file` is a lowercase hyphenated name.

**IDs and references**

6. Every ID is well formed and unique, and each stage and work unit has an
   existing parent derived from its ID prefix.
7. Every `reviews` target exists and comes earlier in declared order. Every
   `after` appears only on a step directly inside a parallel group, and its
   targets are siblings in that group that come earlier in declared order.
   Every `key` is unique.

**Files**

8. Every declared stage and work unit has a file, and every file's frontmatter
   IDs match the declaration; a shared file's `stage_ids` equal the set of
   stages that name it. Mismatches are reported, never repaired. The body is
   never checked.
9. A work-unit file's `work_unit_id` matches the ID in its folder name.
10. A stage's own file carries `human_checkpoint` exactly when the declaration
    sets it. Shared files carry none.
11. Warning: a file or folder name differs from the name the declaration
    would generate (naming drift).

**Status**

12. `execution_status` and `unit_status` values are valid, and every
    `unit_status` key is an existing work-unit ID.

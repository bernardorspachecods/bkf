---
bkf: document
description: Defines a durable planning workflow with phases, at least two subplans, configurable research and checkpoints, and review for each subplan. Conversation plans stay outside this workflow type.
tags: [planning, delegation]
---

# Plan

**Use when** the user wants an agreed objective turned into coordinated work
that must persist in the repository. A short plan kept in the conversation uses
no workflow. To explore options before agreeing an objective, use a discussion
instead. If the user says the plan or its result missed their need, revise the
declaration instead of starting over. The workflow type may be run in a reduced
form; see "Required core and optional stages".

## Declaration

The example has two phases. In the first, subplan 1 is followed by subplan 3
(which needs its output) while subplan 2 runs beside them. Each subplan is a
work unit with its own file holding its research, implementation, and review.
Research is carried only when the user enabled it; review is required for every
subplan. The checkpoint cadence here is `each_subplan`.

```bkf-workflow
steps:
  - work_unit:
      title: "Plan integrity check"
      steps:
        - stage:
            title: "Integrity check — plan logic, order, and completion conditions"
            human_checkpoint: true

  - work_unit:
      title: "Phase 1"
      steps:
        - parallel:
            - work_unit:
                title: "Subplans 1 and 3"
                steps:
                  - work_unit:
                      title: "Subplan 1"
                      work_unit_file: true
                      steps:
                        - work_unit:
                            title: "Research"
                            steps:
                              - stage: {title: "Research subplan 1"}
                        - stage: {key: sp1_impl, title: "Implement subplan 1"}
                        - stage:
                            title: "Review subplan 1"
                            reviews: [sp1_impl]
                            human_checkpoint: true
                  - work_unit:
                      title: "Subplan 3"
                      work_unit_file: true
                      steps:
                        - stage: {key: sp3_impl, title: "Implement subplan 3"}
                        - stage:
                            title: "Review subplan 3"
                            reviews: [sp3_impl]
                            human_checkpoint: true
            - work_unit:
                title: "Subplan 2"
                work_unit_file: true
                steps:
                  - stage: {key: sp2_impl, title: "Implement subplan 2"}
                  - stage:
                      title: "Review subplan 2"
                      reviews: [sp2_impl]
                      human_checkpoint: true

  - work_unit:
      title: "Phase 2"
      steps:
        - stage: {title: "..."}
```

Phase 2 is a placeholder: phases are work units in order, and each holds
subplans the same way.

## Required core and optional stages

- **Required core:** the settings in "Settings and checkpoints", agreed before
  work starts; the checkpoints the user chose, kept as agreed; and a review of
  each subplan's output. Implement stages are the work itself. A durable plan has
  at least two subplans; a single task is a conversation plan, which the workflow
  type does not cover. The plan integrity check is also core: it runs before work
  starts and after a material revision, as stated in "Going back and limits".
- **Optional stages:** subplan research is off unless the user's settings turn it on (see Stage notes). Phases may be dropped when there is one.
- A light run: one phase, two subplans, no research, a review of each subplan, the checkpoints the user chose, and the agreed settings written in the declaration.

## Stage notes

| Stage | Receives | Does not receive | Output |
| --- | --- | --- | --- |
| Plan integrity check | The root plan and subplans, and the criteria: logical coverage, ordering, dependencies, feasibility, consistent completion conditions | The coordinator's account of why the plan is sound | Findings with evidence from the plan and recommended corrections, in the stage file. It is not a review of completed output. |
| Research (per subplan, optional) | The subplan brief | | The research workflow's output, at the rigor level set in the [research workflow type](/workflow-types/research.md), passed through unchanged. Each research unit is that workflow type's units, nested in the subplan. The overall plan is researched only when the user explicitly asks. |
| Implement | The subplan brief | Other subplans' work, except declared inputs | The output, and an outcome section. |
| Review (per subplan) | The implemented output, the criteria from the brief | The implementer's account of the work | An assessment against the criteria. |

The overall objective, approach, boundaries, and completion gate live in the workflow document. Each subplan's brief lives in its work unit file.

## Settings and checkpoints

The declaration records the settings by what it contains.

| Setting | In the declaration |
| --- | --- |
| Number of subplans | The number of subplan work units |
| Subplan research, off or at a rigor level | Research stages present or absent; the level is passed to the research workflow |
| Root-level research | Off unless requested; if on, a research unit in the first work unit |
| Retaining discovery logs of the research | A property of the research workflow's records |
| Checkpoint cadence | `human_checkpoint` on: every agent stage (`each_handoff`), the last stage of each subplan (`each_subplan`), or the last stage of the plan (`plan_completion`) |

A recommended default for plans with agent assignments is `each_handoff`.

## Going back and limits

- A failed review returns work to the implementer, and later units restart.
- A revision that materially changes scope, sequence, dependencies, or
  completion conditions runs the integrity check again before work starts or
  resumes.
- A subplan starts only when it belongs to the active phase and the outputs it
  depends on are available. Later phases do not start just because their
  dependencies are met. Eligibility is derived, never stored as a status.

## Closing

When the plan is complete, the coordinator verifies outputs, dependencies,
consumers, and owned information, looks in the reconciled outputs for
procedures worth adding to the repo library, and reports them as candidates
or says none were found. Candidates follow `grow-repo-library`.
The user then chooses to delete the plan or keep it for its history; until
they choose, it stays in place, is not continued, and no replacement plan is
created. Closing deletes or untracks the parent work unit.

---
bkf: document
description: Defines a durable planning workflow with phases, at least two subplans, configurable research, checkpoints and subplan reviews, an agreed executor, and optional Claude review. Conversation plans stay outside this workflow type.
tags: [planning, delegation]
---

# Plan

**Use when** the user wants an agreed objective turned into coordinated work
that must persist in the repository. A short plan kept in the conversation uses
no workflow. To explore options before agreeing an objective, use a discussion
instead. If the user says the plan or its result missed their need, revise the
declaration instead of starting over. The workflow type may be run in a reduced
form; see "Required core and optional stages".

## Terms

- **Plan:** the workflow and its parent file.
- **Phase:** a top-level work unit that groups subplans; it has no brief or file of its own.
- **Subplan:** a work unit nested in a phase, with its own file and brief.
- **Stage:** a step of a work unit: research, implement, review, or integration. Phase-level stages, such as integration and the phase review, belong to the phase.

## Declaration

This workflow type gives no declaration to copy, because a plan's shape
follows its task. Write the declaration with
[write-a-declaration](/modules/write-a-declaration.md), composed from these
rules:

- The first work unit is the plan integrity check: one stage with
  `human_checkpoint: true`.
- Each phase is a top-level work unit, in phase order.
- Each subplan is a work unit in its phase with `work_unit_file: true`. Its
  steps are, in order: a research work unit when research is on for that
  subplan, the implement stage with a `key`, the review stage whose `reviews`
  names that key, and the Claude review when the settings select it.
  Checkpoints follow the cadence in "Settings and checkpoints".
- A subplan that needs another subplan's output comes after it. Independent
  subplans go in a `parallel` group; a branch that holds a dependent chain is a
  work unit containing those subplans in order, or uses `after`.
- A nested workflow type, such as research, brings its own units. Before
  writing them, read that workflow type and include every stage its "Required
  core" names, at the level the user chose. A single stage stands for a nested
  workflow type only when that type's required core allows it.

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
| Plan integrity check | The root plan and subplans, the workflow types the plan nests, and the criteria: logical coverage, ordering, dependencies, feasibility, consistent completion conditions, and the required core of this workflow type and of each nested one | The coordinator's account of why the plan is sound | Findings with evidence from the plan and recommended corrections, in the stage file. It is not a review of completed output. |
| Research (per subplan, optional) | The subplan brief | | The research workflow's output, with the session table set up as in the [research workflow type](/workflow-types/research.md), passed through unchanged. Each research unit is that workflow type's units, nested in the subplan. The overall plan is researched only when the user explicitly asks. |
| Implement | The subplan brief | Other subplans' work, except declared inputs | The output, and an outcome in the implement stage's own file: the verification it ran and the differences from the brief. What it did is the diff itself, so the outcome does not restate it. A stage file with only its title means there is nothing to record beyond the diff. The coordinator reads the outcome to check the handoff, the user reads it at checkpoints, and a resumed or returned run starts from it; the reviewer does not receive it. |
| Review (per subplan) | The implemented output, the criteria from the brief | The implementer's account of the work | An assessment against the criteria. |
| Claude review | The implemented output and criteria. For a phase, the output is the cumulative diff from the first run's base of that phase to the final state; the criteria are the completion conditions of its subplans plus the phase's line in the plan map. | The normal review's findings; the implementer's account | An assessment against the criteria. Findings go to the coordinator, who returns them to the Codex implementer; the coordinator does not fix them. Runs as a Claude agent distinct from the coordinator. |
| Integration (only with `real` parallelism) | The parallel branches and the verification to run | | Merged branches on the plan branch, conflicts resolved, and the named verification run after merging. Its stage file may hold only its title: the result is the git state. |

The overall objective, approach, boundaries, and completion gate live in the workflow document. Each subplan's brief lives in its work unit file.

## Execution with Codex

- With `serialized` parallelism, all stages run in the user's checkout, one at a time; branches of a `parallel` group run in declared order.
- With `real` parallelism, the plan runs in worktree mode on a plan branch (`codex/w-NN`). Parallel branches fork from it, the integration stage merges them back, and sequential stages fork from the plan branch. Use one mode per plan; never mix them.
- Name each run after its stage, using the full workflow and stage ID in lowercase hyphenated form (for example, `w-02-st-01-02-02`).
- Before launching a stage, check that its run folder does not exist. If it exists and the stage is not being deliberately relaunched, stop. See the dispatch-codex skill for launch and run-folder details.
- To resume after a session ends, read the plan's `unit_status` and open the in-flight stage's run folder. A missing folder means the stage was never launched; without an `exit` in `status`, check whether it is running or died, then relaunch; `exit=0` means it finished and awaits review.
- In the implement brief, tell Codex to write the outcome in the implement stage's file, as required by the Implement stage note.

## Settings and checkpoints

The declaration records the settings by what it contains.

| Setting | In the declaration |
| --- | --- |
| Number of subplans | The number of subplan work units |
| Subplan research, on or off | Research stages present or absent; the research workflow proposes its own session table for the user to approve |
| Root-level research | Off unless requested; if on, a research unit in the first work unit |
| Checkpoint cadence | `human_checkpoint` on: every agent stage (`each_handoff`), the last stage of each subplan (`each_subplan`), or the last stage of the plan (`plan_completion`) |
| Executor, Claude or Codex | Record the choice in the plan's settings. With Codex, Implement, Review, and Integration stages are Codex runs dispatched per the dispatch-codex skill. |
| Claude review, off, selected subplans, each phase, or plan end | Add this review after the normal review. `selected subplans` puts it in those subplans and reviews their implement stage. `each phase` puts one at the end of the phase and reviews its subplans. `plan end` puts one at the end of each phase the user marked critical; by default, that is the last phase. |
| Parallelism, `serialized` or `real` | `serialized` (default) adds no stage; `real` adds an integration stage after every `parallel` group. |

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
or says none were found. Candidates follow `grow-libraries`.
The user then chooses to delete the plan or keep it for its history; until
they choose, it stays in place, is not continued, and no replacement plan is
created. With `real` parallelism, closing includes merging the plan branch
into `main` with the user's approval. When the user chooses to delete the plan,
the coordinator lists its Codex runs, worktrees, and `codex/w-NN*` branches and
asks for confirmation before deleting them. A branch with commits not integrated
into `main` is not deleted without an explicit warning. Closing deletes or
untracks the parent work unit.

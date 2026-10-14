---
bkf: document
description: "Owns one definition for every BKF term; the rules that use those terms belong to their specification, profile, and workflow documents."
tags: [bkf, glossary]
---

# BKF Glossary

This glossary defines terms used across BKF. The documents that own the rules
using these terms remain the source for those rules.

## Artifact reference

An authored map entry that links a useful non-member file, such as code or a PDF, and says when to open it.

See the [format specification](/format/format-specification.md#31-map-files-and-inventories).

## BKF document

A Markdown member that uses a BKF profile. BKF documents are also called "documents" for short.

See the [format specification](/format/format-specification.md#4-bkf-documents-and-profiles).

## Bundle

A self-contained, hierarchical collection of Markdown members and referenced artifacts. It is the unit of distribution.

See the [format specification](/format/format-specification.md#1-purpose-and-scope).

## Bundle root

The directory selected by the user or consuming tool as the bundle's root.

See the [format specification](/format/format-specification.md#12-discovery-membership-and-composition).

## Description

A frontmatter value describing what a document or map is or covers; for tracked documents, it supplies the map inventory text.

See the [frontmatter profiles](/format/frontmatter-profiles.md#descriptions).

## Entry skill

A thin trigger for one situation that carries a generated list of the modules that apply.

See [the layers](/manual/what-is-bkf.md#the-layers).

## Feedback file

The optional bundle-root `feedback.md`, where agents record what went wrong in their work.

See the [format specification](/format/format-specification.md#32-feedback-file).

## Ideas file

The optional bundle-root `ideas.md`, where the user or agents record ideas for later review.

See the [format specification](/format/format-specification.md#34-ideas-file).

## Layer

A part of BKF's organization; its five layers are format, library, entry skills, repo library, and workflows.

See [what BKF is](/manual/what-is-bkf.md#the-layers).

## Library

The shared collection of rule modules and workflow type definitions selected by entry skills for daily use, kept in `agent-skills/library/`.

See [the layers](/manual/what-is-bkf.md#the-layers); `agent-skills/library/MAP.md`.

## Link

A standard Markdown link from one document to another. It expresses relationships beyond the parent/child hierarchy.

See the [format specification](/format/format-specification.md#5-cross-linking-and-paths).

## Map

A `MAP.md` file that navigates the folder it sits in.

See the [format specification](/format/format-specification.md#31-map-files-and-inventories).

## Member

A Markdown file within a bundle, except the optional root `readme.md`. A member is tracked or untracked.

See the [format specification](/format/format-specification.md#12-discovery-membership-and-composition).

## Member inventory

The generated table in a map that lists the tracked documents and child maps in its scope, written from their descriptions.

See the [format specification](/format/format-specification.md#31-map-files-and-inventories).

## Module

A reusable task rule in `agent-skills/library/modules/`, written once and selected for a task.

See [the layers](/manual/what-is-bkf.md#the-layers); `agent-skills/library/MAP.md`.

## Nested bundle

A folder inside a bundle whose `MAP.md` declares `bkf_version` is a separate bundle with its own root, members, and conformance, assessed by selecting that folder.

See the [format specification](/format/format-specification.md#33-nested-bundles).

## Owner

A document responsible for a fact, rule, or procedure. Every fact, rule, and procedure has one owner, and everything else links to it.

See [what BKF is](/manual/what-is-bkf.md#the-ideas).

## Profile

A named set of frontmatter fields and rules selected by the `bkf` field.

See the [frontmatter profiles](/format/frontmatter-profiles.md#generic-document).

## Repo library

A repository's own collection of procedures and modules under `repo-library/`.

See [the layers](/manual/what-is-bkf.md#the-layers).

## Tags

A non-empty sequence of non-empty strings in generic document frontmatter. Tags are how a document is selected for a task, so a document without them cannot be found by tag.

See the [frontmatter profiles](/format/frontmatter-profiles.md#generic-document).

## Task route

An authored map row that sends a task the inventory cannot route to a starting document.

See the [format specification](/format/format-specification.md#31-map-files-and-inventories).

## Tracked

A member with a `bkf` field and a `description` in its frontmatter. BKF validates it and lists it in map inventories.

See the [frontmatter profiles](/format/frontmatter-profiles.md#shared-fields).

## Untracked

A member without frontmatter or a `bkf` field, or a workflow internal that omits its optional description.

See the [frontmatter profiles](/format/frontmatter-profiles.md#shared-fields).

## Workflow

A composed piece of work whose parent file declares ordered steps. A **work unit** is a named, possibly nested part of a workflow; a **stage** is one workflow step assigned to one agent. The
[workflow foundation](/format/agent-workflow-foundation.md) defines them.

## Workflow type

A definition of a multi-stage process, kept in `agent-skills/library/workflow-types/`; a parent file in a bundle is shaped by one.

Term to avoid: "workflow shape".

See [the layers](/manual/what-is-bkf.md#the-layers); `agent-skills/library/MAP.md`.

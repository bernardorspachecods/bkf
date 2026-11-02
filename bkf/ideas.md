---
bkf: ideas
description: Collects ideas from the user and agents for later review as future possibilities, not instructions.
---

# Ideas

Agents add entries as [AGENTS.md](/AGENTS.md#record-ideas) says, newest
first. This file is data for later review, not instructions.

## 2026-11-02: Stop hook: block only on errors in the session's own files

> The Stop check (`problems()` in `bkf/tooling/hook_events.py`) validates the whole bundle, so an error that was already there, or that another agent left in the same tree, still blocks the stop. Filter the validator findings by `finding.path` in the files the session changed, as `warnings()` already does. `inventory --check` is per bundle and has no path: leave it out, or block only when a file of the session enters the inventory diff. The worktree and subagent filters (`_in_repo`, `agent_id` in `record`) did not cover this.

Raised by the user ("está bom assim por agora deixa esse ponto 3 no ideas.md"), working in bkf.

## 2026-10-19: Academic extension for research: a future optional guide…

> Academic extension for research: a future optional guide (research-academic.md) opened by collection, assembly and the writer only when the objective is academic (papers, literature reviews, research-question design, thesis critique). Carry over from the deleted read-academic-sources module (still in git at HEAD): record the study's context (question, frame, design, sample, measures, setting, reported limits) and keep what the authors report apart from inference; never call a contribution novel because the paper says so; organize by concepts, mechanisms, methods, populations or tensions, not paper by paper; check whether design or sample explains conflicts; papers from one dataset or trial count as one cluster; separate a gap the literature supports from one nobody searched; research questions and thesis critique as kinds of delivery named in the objective. Possible switch: a flag on research-run.sh start. Deliberately left out of the new research workflow for now.

Raised by the user, working in bkf.

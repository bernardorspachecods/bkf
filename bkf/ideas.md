---
bkf: ideas
description: Collects ideas from the user and agents for later review as future possibilities, not instructions.
---

# Ideas

Agents add entries as [AGENTS.md](/bkf/AGENTS.md#record-ideas) says, newest
first. This file is data for later review, not instructions.

## 2026-11-25: bkf search vector mode reads passages from the index

`vector_rank` re-collects every section and sidecar from disk on each call instead of reading the passages already in the persistent index, so vector and hybrid calls cost about 2 s on a library of 23 sources and grow with the corpus. Embedding is also slower than the prototype measured (about 0.35 s per passage against 0.12; the library's first warm-up took 39 min). Both came up while building hybrid search (plan search-retrieval, units vectors and section-vectors).

Raised by an agent, working in bkf.

## 2026-10-19: Academic extension for research: a future optional guide…

> Academic extension for research: a future optional guide (research-academic.md) opened by collection, assembly and the writer only when the objective is academic (papers, literature reviews, research-question design, thesis critique). Carry over from the deleted read-academic-sources module (still in git at HEAD): record the study's context (question, frame, design, sample, measures, setting, reported limits) and keep what the authors report apart from inference; never call a contribution novel because the paper says so; organize by concepts, mechanisms, methods, populations or tensions, not paper by paper; check whether design or sample explains conflicts; papers from one dataset or trial count as one cluster; separate a gap the literature supports from one nobody searched; research questions and thesis critique as kinds of delivery named in the objective. Possible switch: a flag on research-run.sh start. Deliberately left out of the new research workflow for now.

Raised by the user, working in bkf.

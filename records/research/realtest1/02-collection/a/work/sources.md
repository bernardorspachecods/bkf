# Source map: agent instruction length and specificity

**Scope.** Collector A’s mapped niches only: vendor guidance; academic work on many constraints/context length; independent agent benchmarks; open-model/local-agent practitioner evaluations. The question is whether research guides and briefs should stay short and principle-based or add more rules, with priority on small, cheap models doing multi-step work.

## Map of positions

| Position | Evidence in this collection | What it supports |
|---|---|---|
| Keep always-loaded guidance compact, relevant, and principle-led; make it specific enough to remove ambiguity. | Anthropic context-engineering guidance; OpenAI’s 2026 guidance for GPT-6 Astra; Google Gemini prompt-design documentation. | Avoid exhaustive edge-case lists and irrelevant material. Minimal does not mean underspecified: add concrete requirements and examples for observed failures. |
| More explicit rules can help where the task has real requirements, but instruction count and length reduce joint adherence. | AGENTIF (academic benchmark); IFScale; CELLO; context-length studies. | Longer instructions are not inherently better. Several simultaneous constraints are harder to satisfy together, especially for smaller models and in context-heavy tasks. |
| Repository-specific context can improve behavior in some settings, but generic context files do not reliably improve task success and can increase cost. | CTXbench / SWE-bench study of AGENTS.md; separate efficiency study; conflicting community reports. | Keep only requirements that add information beyond the task and existing docs; measure on representative tasks. Context length by itself is not a sufficient explanation. |
| Local-agent results are strongly affected by the harness, task design, and evaluation method. | Erfi’s Lexicanum local benchmark; r/LocalLLaMA reports; Open Agent Leaderboard; SWE-bench-Live. | Length guidance alone does not decide local multi-step performance. Evidence favors evaluating a concise baseline against targeted rules in the actual workflow, while tracking success, cost, and failure type. |

This is a position map, not a recommendation for the repo itself. The sources do not isolate “principle-based vs prescriptive” as a controlled variable across small-model multi-step agent tasks. The strongest directly relevant findings concern constraint density, context-file presence/content, and context length; these should not be conflated.

## Sources opened

### 1. Vendor docs and engineering posts on agent instructions

#### Anthropic, “Effective context engineering for AI agents”
- **Origin:** Anthropic Applied AI team, authored engineering post; primary vendor guidance.
- **Access:** Full text opened.
- **Passages:** “Finite attention budget,” performance gradient: [lines 31–40](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); prompt length and iteration: [lines 38–50](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); retrieval and progressive disclosure: [lines 55–65](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); long-horizon context: [lines 66–73](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); conclusion: [lines 98–101](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- **Establishes:** Anthropic recommends the smallest high-signal context that fully specifies expected behavior; direct and clear system prompts at an appropriate specificity; a minimal prompt as a starting point, then add instructions/examples in response to observed failures. It explicitly warns against laundry lists of edge cases, recommending canonical examples. It also says minimal need not mean short, and warns that vague guidance can fail. The post describes context as finite with diminishing returns, and says smarter models can require less prescriptive engineering.
- **Does not establish:** A controlled causal comparison of short and long repo instruction files, or model-size-specific performance measurements. Its claims are vendor practice and conceptual explanation.

#### OpenAI, “Rethinking skills and prompts for GPT-6 Astra”
- **Origin:** OpenAI developer engineering post, dated 2026-09-11; primary vendor guidance.
- **Access:** Full text opened.
- **Passages:** [lines 920–947](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) on instructions, bloated skill descriptions, progressive disclosure, elaborate itineraries, and cross-model trade-offs; [lines 948–975](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) on AGENTS.md, contextual references, and persistence.
- **Establishes:** For GPT-6 Astra, OpenAI says accumulated instructions should be revisited; long skill descriptions can be truncated, contradictory or over-broad triggers can load irrelevant material, and progressive disclosure can preserve context. It says overly specific recipes can hinder newer models and recommends docs be read when relevant to the task. It also cautions that repo guidance serves different models, so guidance useful for one may overconstrain another.
- **Does not establish:** Generalization to small, local models. The guidance is explicitly GPT-6 Astra-specific and not an experiment comparing instruction lengths.

#### Google, “Prompt design strategies” (Gemini API)
- **Origin:** Google AI for Developers documentation; primary vendor guidance.
- **Access:** Full text opened.
- **Passages:** Few-shot examples and instruction replacement: [lines 290–315](https://ai.google.dev/gemini-api/docs/prompting-strategies); risk of too many examples: [lines 348–350](https://ai.google.dev/gemini-api/docs/prompting-strategies); directness, explicit constraints, placement and structure: [lines 515–526](https://ai.google.dev/gemini-api/docs/prompting-strategies); agent behavior dimensions: [lines 635–657](https://ai.google.dev/gemini-api/docs/prompting-strategies).
- **Establishes:** Google recommends examples, noting clear examples can sometimes replace written instructions and too many examples may lead to overfitting. Its Gemini 3 guidance favors direct, concise, structured prompts and prioritizing critical instructions; it also says agentic workflows may require specific instructions to steer reasoning, execution, recovery, ambiguity handling, and output.
- **Does not establish:** Controlled performance effects for agent instruction file length or small local models. The page contains model-specific examples/templates and vendor recommendations.

#### Google Cloud, “Use system instructions”
- **Origin:** Google Cloud documentation; primary vendor documentation.
- **Access:** Full text opened.
- **Passages:** [lines 550–563](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/system-instructions?hl=en); use cases: [lines 564–574](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/system-instructions?hl=en).
- **Establishes:** Google presents system instructions as a means to set behavior, role, context, format, goals, and language across turns, while noting they guide but do not fully ensure compliance.
- **Does not establish:** Whether many detailed instructions improve performance or what length is optimal.

#### OpenAI, “Agent definitions”
- **Origin:** OpenAI API documentation; primary vendor documentation.
- **Access:** Full text opened.
- **Passages:** [`instructions` field and “Start with one focused agent,” lines 955–971](https://developers.openai.com/api/docs/guides/agents/define-agents).
- **Establishes:** Agent instructions define the job, constraints, and style; OpenAI recommends defining the smallest agent that can own a clear task.
- **Does not establish:** An effect of instruction length; this section concerns agent scope and configuration.

#### Anthropic, “Claude Code: Best practices for agentic coding”
- **Origin:** Anthropic engineering post, linked from search results.
- **Access:** Could not open. The URL redirects to `code.claude.com/docs/en/best-practices`, which the web tool returned as inaccessible.
- **Search result only (not used as evidence):** Search result description says it reports patterns used by internal and external Claude Code users. No finding is attributed here.

### 2. Academic work on many instructions and context length

#### AGENTIF, “Benchmarking Instruction Following of Large Language Models in Agentic Scenarios” (NeurIPS 2025 Datasets and Benchmarks)
- **Origin:** Independent academic benchmark paper and its benchmark site; same research origin, counted as one source.
- **Access:** Full paper and benchmark site opened. Current leaderboard page updated 2026-10-11; its 2026 evaluation setting is distinct from the paper’s original protocol.
- **Passages:** Paper’s benchmark/results: [PDF pp. 5–6, lines 389–447](https://proceedings.neurips.cc/paper_files/paper/2025/file/51bb3a8a33610a25aae074bfc51b1b1f-Paper-Datasets_and_Benchmarks_Track.pdf); length/constraint sweep: [PDF pp. 8–9, lines 562–606](https://proceedings.neurips.cc/paper_files/paper/2025/file/51bb3a8a33610a25aae074bfc51b1b1f-Paper-Datasets_and_Benchmarks_Track.pdf); live method and size grouping: [AgentIF site lines 23–40, 93–98](https://agentif.github.io/).
- **Establishes:** AGENTIF uses 707 instructions from 50 agentic applications, averaging about 1,717 tokens and 11.9 constraints (the site describes 1,723 words; paper and site appear to use different units in their summaries, so retain each stated unit). In the paper’s evaluation, model performance generally falls as instruction length and constraint count rise; at >6,000 words the all-constraints instruction success rate is near zero for all evaluated models. It identifies weak performance on conditional and tool-use constraints; examples improve performance relative to corresponding constraints without examples. Small open models are now explicitly represented on the maintained leaderboard: 1.5–4B models are locally served with vLLM and evaluated over three independent runs under vendor-recommended decoding settings. In the October 2026 table, small models show substantially lower overall individual-constraint success than stronger medium/large models, while still scoring above 50% on several models; all-constraints instruction success for displayed small models is roughly 10–27%. This offers direct model-size-aware agentic instruction adherence data.
- **Does not establish:** That brevity itself causes higher agent task completion: the length buckets also vary in task and constraint content, and AGENTIF evaluates instruction compliance in agentic scenarios rather than repository task resolution. Benchmarks’ synthetic/constructed task choices and LLM judge have limitations. The current leaderboard is maintained by the benchmark authors and may evolve; its new protocol scores should not be mixed with the paper’s original results.

#### IFScale, “How Many Instructions Can LLMs Follow at Once?”
- **Origin:** Independent research group (Distyl); arXiv preprint and authors’ released benchmark.
- **Access:** Abstract/full metadata opened; abstract only for technical details.
- **Passages:** [arXiv abstract, lines 3–5](https://arxiv.org/abs/2507.11538); benchmark site [IFScale](https://distylai.github.io/IFScale) was referenced but not separately opened.
- **Establishes:** IFScale measures 20 models from seven providers on a business-report task with up to 500 keyword-inclusion instructions. Authors report degradation as instruction density rises, only 68% accuracy for the best frontier model at maximum density, and associations between size/reasoning capability and different degradation patterns; they also report earlier-instruction bias and latency trade-offs.
- **Does not establish:** The effect of instruction prose length or rules in a persistent agent guide; its constraints are artificial keyword insertions in one output task. No specific small/local model conclusion is extracted from the abstract.

#### CELLO, “Can Large Language Models Understand Real-World Complex Instructions?” (AAAI 2024)
- **Origin:** Independent academic benchmark paper.
- **Access:** Full paper opened at the AAAI proceedings PDF.
- **Passages:** [AAAI proceedings paper](https://ojs.aaai.org/index.php/AAAI/article/download/29777/31340), including model table and evaluation discussion (AAAI-24 proceedings, pp. 18190–18193; results include task/criterion tables).
- **Establishes:** CELLO evaluates eight dimensions of complex instructions across nine tasks and four criteria, including smaller open models (7B/13B) and larger systems. It reports substantial model and task-specific differences: smaller models can perform well on some kinds of instruction, while performance varies by task/criterion and remains below GPT-4/GPT-3.5 on aggregate. This is a counterweight to a simple “larger is always better” claim and supports model-specific evaluation.
- **Does not establish:** That short principle-based instructions outperform long prescriptive instructions in agents. It combines complex task descriptions with long/noisy input and is not a multi-step tool-use benchmark.

#### “Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?” (CTXbench + SWE-bench)
- **Origin:** Independent academic study; original authors’ paper.
- **Access:** Full arXiv HTML opened.
- **Passages:** Summary and setup: [lines 3–23](https://arxiv.org/abs/2602.11988); methods: [lines 110–133](https://arxiv.org/abs/2602.11988); main effects and costs: [lines 150–176](https://arxiv.org/abs/2602.11988); length analysis: [lines 356–380](https://arxiv.org/abs/2602.11988).
- **Establishes:** Across SWE-bench and a new 138-task, 12-repository Python benchmark, LLM-generated repository context files had no statistically significant success-rate benefit on average and increased steps/cost by about 20–23%. Developer-written context files yielded a small, not statistically significant average success improvement over no file, and were better than generated files. Agents followed instructions in context files, which caused more tests, searches and reads. The study found no correlation between context-file length and success/cost in its tested range; removing existing docs changed the result, with generated files improving performance when they were the only documentation. The authors recommend human-written files contain only requirements not already in README and be evaluated before adoption.
- **Does not establish:** That short files are always better: its length analysis found no clear length relationship. It tests coding agents and repository context, not research guides or general agent briefs. Models included GPT-5.2, GPT-5.1 mini, Claude Sonnet 4.5 and Qwen3-30B coder; it does not directly test the cheapest 1–4B local models.

#### “On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents”
- **Origin:** Separate academic study, independent origin from CTXbench study.
- **Access:** Full arXiv HTML opened; abstract and setup/metadata available.
- **Passages:** [abstract and method, lines 3–5 and 28](https://arxiv.org/abs/2601.20404).
- **Establishes:** In 10 repositories and 124 pull requests, the authors report that AGENTS.md presence was associated with 28.64% lower median runtime and 16.58% fewer output tokens, with comparable task completion behavior.
- **Does not establish:** Any length or prescription effect; the abstract does not characterize instruction quality or provide model-size-specific conclusions. It is evidence that repository instructions can improve efficiency under some conditions, countering a blanket “context files are always overhead” position.

#### “Lost in the Middle: How Language Models Use Long Contexts”
- **Origin:** Independent academic paper; Liu et al., originally arXiv 2023, later TACL.
- **Access:** Full arXiv HTML opened.
- **Passages:** Summary and trade-off: [lines 4–43](https://arxiv.org/abs/2307.03172); experiment design: [lines 47–59](https://arxiv.org/abs/2307.03172); results: [lines 73–93](https://arxiv.org/abs/2307.03172).
- **Establishes:** In controlled multi-document QA and key-value retrieval, performance can fall when relevant evidence is in the middle of long contexts; more context may help by providing information but also hurt by increasing material to reason over. Extended-context variants did not necessarily use context better. Their studied models included LongChat-13B and MPT-30B-Instruct, among others.
- **Does not establish:** Persistent instruction-file length or agent task performance. It studies long input context and information position; use as related context-length evidence, not direct proof about guide length.

### 5. Independent agent benchmark builders and evaluation platforms

#### Open Agent Leaderboard (IBM Research / Hugging Face)
- **Origin:** IBM Research community article, benchmark team’s own methodology/results; paired with Exgentic framework and paper.
- **Access:** Full article opened.
- **Passages:** [lines 65–83](https://huggingface.co/blog/ibm-research/open-agent-leaderboard); benchmark set and standardized task/context/action protocol: [lines 88–99](https://huggingface.co/blog/ibm-research/open-agent-leaderboard); cost and full-agent-system results: [lines 100–120](https://huggingface.co/blog/ibm-research/open-agent-leaderboard); public artifacts: [lines 126–134](https://huggingface.co/blog/ibm-research/open-agent-leaderboard).
- **Establishes:** Agent results depend on the full system; this benchmark compares agent configurations over six different suites and reports both success and cost. In their reported leaderboard, the same model wrapped in different agents produces different success/cost outcomes. Its benchmark mix includes repository repair, research, apps, and policy-following tasks.
- **Does not establish:** Whether instruction length or prescriptiveness caused those differences; the article reports full-system comparisons, not an instruction ablation. The task suites are designed/selected by the benchmark maintainers.

#### SWE-bench-Live
- **Origin:** Microsoft-maintained benchmark, built on SWE-bench; benchmark authors’ own site and submissions.
- **Access:** Full benchmark page opened; leaderboard results failed to load in the captured page.
- **Passages:** Dataset scope and update intent: [lines 15–19](https://swe-bench-live.github.io/); task/platform changes: [lines 27–34](https://swe-bench-live.github.io/); leaderboard and archived trajectories: [lines 35–52](https://swe-bench-live.github.io/).
- **Establishes:** The benchmark is an updating multi-language/multi-OS agent task set. It archives trajectories for submitted model-agent combinations and requires trajectory submission for newer verification checks. It indicates an available source for comparing agent outcomes under repository task conditions.
- **Does not establish:** Any effect of instruction length, since no such intervention is reported. The live leaderboard data did not load in the opened page, and no quantitative result is used here.

### 7. Open-model and local-agent user evaluation communities

#### Erfi’s Lexicanum, “Benchmarking local models for agent work”
- **Origin:** Independent practitioner’s self-run local-model evaluation and harness documentation.
- **Access:** Full article opened.
- **Passages:** Suite definitions and measurements: [lines 215–219](https://erfi.dev/reference/local-model-bench/); results and limitations: [lines 233–257](https://erfi.dev/reference/local-model-bench/); practitioner’s stated generalization warning: [lines 291–305](https://erfi.dev/reference/local-model-bench/).
- **Establishes:** Provides small/local model comparisons on a local setup using a six-task agent loop and an 18-case research-agent protocol, with multiple runs and metrics including success, tool protocol validity, steps, and time. In the reported sample, Qwen3.5-4B hit 87% of research-agent cases while 9B and 12B models scored 94.4%; all models failed the same chained-tool case, and all models stalled on a write-new-tests coding task. The author emphasizes measuring against the real protocol and accounting for cost of failures as well as successes.
- **Does not establish:** An effect of instruction length; the article compares models/harness measurements, not short versus long guides. It is one practitioner’s particular hardware, task suites, and partly private harness, so absolute scores do not generalize.

#### r/LocalLLaMA, “Do you benchmark local models as agents, or only on single prompts?”
- **Origin:** Independent community discussion, self-selected commenters.
- **Access:** Full thread opened.
- **Passages:** [top-level reports and examples, lines 48–63](https://www.reddit.com/r/LocalLLaMA/comments/1tpycp8/do_you_benchmark_local_models_as_agents_or_only/); [measurement limitations and task-specific PRD comments, lines 78–110 and 180–215](https://www.reddit.com/r/LocalLLaMA/comments/1tpycp8/do_you_benchmark_local_models_as_agents_or_only/).
- **Establishes:** Practitioners report evaluating instruction execution inside agents, using their own tasks, recording latency, retries, tool-call validity, and deterministic outcomes; commenters note instability and difficulty scoring complex agent tasks.
- **Does not establish:** Generalizable comparative effects or causal evidence that one instruction style is better. Comments are anecdotal and self-selected.

#### r/LocalLLM, “I built a coding agent that gets 87% on benchmarks with a 4B parameter model, here’s how”
- **Origin:** Practitioner/developer’s self-reported system result; author’s product/benchmark claim.
- **Access:** Full Reddit post opened; linked source code not opened.
- **Passages:** [lines 22–36](https://www.reddit.com/r/LocalLLM/comments/1tged8r/i_built_a_coding_agent_that_gets_87_on_benchmarks/).
- **Establishes:** The author claims a Gemma 4 model with 4B active parameters passes 87/100 tasks in their benchmark and attributes reliability to compound tools, compile/lint feedback, decomposition, token budgeting, and code-graph retrieval.
- **Does not establish:** Whether instructions were long/short or which component caused the result. No independent reproduction was consulted; treat as a lead, not robust performance evidence.

#### r/LocalLLaMA, “Software Engineers: Do you honestly get anything useful out of LLMs?”
- **Origin:** Individual practitioner discussion; self-selected report.
- **Access:** Full Reddit thread opened.
- **Passages:** [lines 21–38](https://www.reddit.com/r/LocalLLaMA/comments/1vavh2h/software_engineers_do_you_honestly_get_anything/).
- **Establishes:** One user reports that “pages-worth” of instructions did not prevent methodology drift and instruction abandonment in long coding sessions, and describes the burden of micro-managing agents.
- **Does not establish:** A controlled comparison, model-specific generalization, or whether the failures were caused by instruction length versus model/harness/task capability.

## Not consulted

- **Google Gemini Enterprise Agent Platform, system instructions introduction** beyond the already opened `Use system instructions` page: not needed after opening the directly relevant Gemini API prompting documentation.
- **AGENTIF current run configs and source repository:** leaderboard site and paper opened, but no detailed per-model config or task records were inspected.
- **Open Agent Leaderboard evaluation paper and Exgentic repository:** the IBM Research article was opened; methodology paper/repository not opened.
- **SWE-bench-Live submission trajectories and benchmark repository:** benchmark page opened, but linked GitHub trajectory data and original repository were not inspected.
- **SmallCode repository and 100 task records:** only developer Reddit post opened.
- **Other Reddit threads and third-party explainers surfaced in search:** not opened or used as findings.

## Last sources and saturation

The last substantive sources opened were the small-model-oriented AGENTIF live table, the OpenAI GPT-6 Astra guidance, the CELLO proceedings paper, the independent CTXbench context-file study, and the local benchmark by Erfi. They added non-duplicate qualifications: (1) small models have direct measured difficulty satisfying all constraints together, although several show decent individual-constraint performance; (2) repo context can increase cost without improving average success, but contextual developer-written guidance may beat generated boilerplate; (3) some AGENTS.md research reports better efficiency with comparable completion; and (4) small/local agent success varies substantially with task and harness. The latest results continue to support concise, relevant instructions plus task-specific details/examples where failure evidence warrants them, while weakening any absolute rule that “shorter is always better.” Sources from the independent academic and practitioner origins now repeat the core finding that irrelevant length/constraint accumulation is a risk, but the direct evidence on short versus prescriptive persistent guides for small, cheap multi-step agents remains sparse. Saturation is adequate for this mapped collection: further AGENTIF examples or repetitions of generic context-window degradation are unlikely to change this map; direct ablation studies on 1–4B agents’ persistent guides would be a meaningful new result.

## Outside the focus

- The sources frequently discuss harness/tool design and task decomposition; a full survey of agent frameworks and tool architecture is outside this collection’s focus.

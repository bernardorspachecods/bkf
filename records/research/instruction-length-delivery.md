# Delivery: instruction length and agent performance

**Objective.** Decide whether the research guides and briefs in this repo should stay short and principle-based, or need more rules. What the evidence says about long, prescriptive instructions versus short, principle-based ones, in agent performance, with priority on small, cheap models running multi-step tasks. A map of the positions.

## 1. The answer, by views

Five views. Each finding carries its source and where in it. Sources that share one origin count once: the two Drew Breunig posts, the AGENTIF paper and its leaderboard, and several pages of one vendor are each one origin.

### View 1. More simultaneous constraints often lower full compliance, including for smaller models

- FollowBench adds one to five constraints and reports declining performance, including on open models such as Vicuna 7B ([arXiv 2310.20410](https://arxiv.org/abs/2310.20410), abstract and §3).
- *When Instructions Multiply* varies constraints on fixed text and code tasks, with Gemma 2 2B/9B and Llama 3.1 8B. Full compliance falls as instruction count rises; code test success stays steadier than style compliance ([paper](https://aclanthology.org/2025.findings-emnlp.896.pdf), §4).
- IFScale varies 10–500 required keywords; smaller or older models degrade earlier, and reasoning effort can improve adherence at extra latency ([arXiv 2507.11538](https://arxiv.org/html/2507.11538), setup and performance analysis).
- AGENTIF finds lower full-instruction success with longer instructions or more constraints; its leaderboard includes 1.5–4B models, for example Qwen3.5-2B at 21.64% instruction success and 55.83% constraint success ([arXiv 2505.16944](https://arxiv.org/html/2505.16944), dataset and §4.4; [leaderboard](https://agentif.github.io/), updated 2026-10-11). The length analysis is observational, and the leaderboard setting is not directly comparable with the paper's original setting.
- Counterpoint: CFBench reports a positive association between prompt length and success, with constraint count as the strongest factor; it is not a matched change in length ([arXiv 2408.01122](https://arxiv.org/abs/2408.01122), §§3, 5). ComplexBench reports difficulty with composed constraints, without testing guide length ([arXiv 2407.03978](https://arxiv.org/abs/2407.03978), abstract and benchmark description).
- Synthesis: the clearest caution for small models is that many independently checkable requirements can lower the chance that all are followed. It does not show that more words alone cause failure, or that principles are easier than specific rules.

### View 2. Direct coding-agent tests do not establish a length penalty; tested, repo-specific guidance can help in some settings

- Gloaguen et al.: no significant success gain from generated context files, a small nonsignificant gain from developer-written ones, no clear relation between file length and success or cost; generated files raised cost by 20% and 23% on the two benchmarks, and developer-written files also raised cost ([arXiv 2602.11988](https://arxiv.org/html/2602.11988), Table 2, §4.2, Appendix B). Mostly Python tasks.
- Khatri: no measurable correctness change across context strategies, 17 tasks in three Python repos; too small to detect a 10-point effect ([arXiv 2607.27250](https://arxiv.org/html/2607.27250), results and limitations).
- Lulla et al.: comparable task completion with an existing `AGENTS.md`, with 28.64% lower median runtime and 16.58% fewer output tokens in one Codex setup. A file-presence comparison, not a length comparison ([arXiv 2601.20404](https://arxiv.org/html/2601.20404), results).
- *Guardrails Beat Guidance*: no pass-rate effect across 0–50 rules in 5,000+ Opus 4.6 / Claude Code runs; a 35-task follow-up suggests negative constraints may help more than positive directives, exploratory and limited ([arXiv 2604.11088](https://arxiv.org/html/2604.11088), §§5–7).
- *Instruction Adherence in Coding Agent Configuration Files*: no detectable compliance difference across 25-, 100-, 250- and 500-line files in 1,650 sessions, mostly Sonnet 4.6; the outcome is a simple annotation rule, not task completion ([arXiv 2605.10039](https://arxiv.org/pdf/2605.10039), §§1, 3–4, 6).
- Positive counterexample: Shepard and Albrecht, iteratively refined repo guidance with Qwen3.5-35B-A3B (about 3B active parameters): 33.0% on SWE-bench Verified, against 28.3% for a static knowledge base and 25.5% with no context. The refined guidance was 63% longer, but content and length were not isolated. Static or transferred guidance reduced performance on Nemotron-3-Nano in a single-trial test ([arXiv 2606.20512](https://arxiv.org/html/2606.20512), results, transfer and limitations).
- Synthesis: repository instructions are not reliably beneficial just because they exist or are longer. Refined, repo-specific content can help, and the gain cannot be attributed to length. These tests use different models, tasks and outcomes, so they do not give a universal null for small local models or long tasks.

### View 3. Long context and multi-step execution create plausible reliability risks, but are proxies for guide design

- Retrieval: a middle-position penalty for relevant material ([*Lost in the Middle*](https://arxiv.org/abs/2307.03172)); extra retrieved material can help, saturate or reduce performance ([Databricks long-context RAG post](https://www.databricks.com/blog/long-context-rag-performance-llms), results). These concern documents, not repo rules.
- Multi-IF: an 8B Llama model's average accuracy falls from 0.688 at turn one to 0.542 at turn three ([arXiv 2410.15553](https://arxiv.org/html/2410.15553), results tables). MTAC-IFBench: strict all-constraint completion drops sharply with turn depth in coding-harness tasks, no very small model tested ([arXiv 2609.14992](https://arxiv.org/html/2609.14992), Table 2). Sinha et al.: accumulated errors and self-conditioning in synthetic long-horizon tasks, Qwen3 and Gemma3 from 4B up; transfer to real agent work is limited ([arXiv 2509.09677](https://arxiv.org/html/2509.09677), task design, results and limitations).
- Adjacent: Harness-IF finds rules opposing a model's default behavior harder to obey across multi-turn coding tasks, without varying guide size and without small models ([arXiv 2608.11727](https://arxiv.org/pdf/2608.11727), abstract and §§1–3). A Gemini 2.5 Pro report describes repetition at very long contexts, as an anecdote ([technical report](https://storage.googleapis.com/deepmind-media/gemini/gemini_v2_5_report.pdf), pp. 16–17). Breunig's two posts (["How Long Contexts Fail"](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html); ["How to Fix Your Context"](https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html)) are one practitioner's synthesis, not controlled evidence.
- Synthesis: long tasks can compound missed requirements, and irrelevant or badly placed context can impair retrieval. These findings motivate care with active context. They do not show that a short principle-based guide beats a longer prescriptive one.

### View 4. Vendor practice favors a concise, high-signal entry guide, with detail loaded when relevant

- Anthropic: a short, human-readable always-loaded `CLAUDE.md`, with sometimes-needed detail moved to on-demand skills; minimal context need not mean a short answer, and both brittle prescriptions and vague advice are cautioned against ([Claude Code best practices](https://code.claude.com/docs/en/best-practices), "Write an effective CLAUDE.md" and "Common issues"; [context-engineering post](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), "Anatomy" and "Just in time"). The [Help Center](https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts) gives a rough target of 200 lines or fewer and says to add rules when repeated errors reveal a gap.
- OpenAI: a monolithic `AGENTS.md` crowds out task context and is hard to maintain; its own practice is a short map to deeper knowledge ([Harness engineering post](https://openai.com/index/harness-engineering/), repository knowledge sections). Its [Codex documentation](https://developers.openai.com/codex/guides/agents-md) recommends concise rules and nested files.
- ["Building effective agents"](https://www.anthropic.com/engineering/building-effective-agents) (Anthropic), "When (and when not) to use agents", "Agents", summary and Appendix 2: use the simplest approach that works, test changes, document tool interfaces clearly. System-design advice, not a guide-length comparison.
- Synthesis: practice converges on a compact entry point, concrete rules and scoped detail. This supports a maintainability practice, not a measured claim that concise guides outperform longer ones.

### View 5. User reports conflict and do not identify length as the cause

- Four Claude Code issues report missed or violated rules, one about a roughly 400-line file and another with a prohibition repeated three times ([#17530](https://github.com/anthropics/claude-code/issues/17530), [#15443](https://github.com/anthropics/claude-code/issues/15443), [#34197](https://github.com/anthropics/claude-code/issues/34197), [#34774](https://github.com/anthropics/claude-code/issues/34774)). Length is unreported in most; a comment blaming context pressure is speculation.
- One local-model thread reports worse reliability as context fills; another reports benefits from detailed operating prompts ([Gemma 4 thread](https://www.reddit.com/r/LocalLLaMA/comments/1sh1bwv/gemma_4_is_terrible_with_system_prompts_and_tools/); [system-prompts thread](https://www.reddit.com/r/LocalLLM/comments/1skwxr0/system-prompts-the-missing-link-for-local-llms/)). Neither has matched conditions.

### What was merged and split

View 1 merges FollowBench, *When Instructions Multiply*, IFScale and AGENTIF as a constraint-density position, with CFBench and ComplexBench kept as a qualification of what "length" means. View 2 groups four direct null or weak results and keeps Shepard and Albrecht apart as the positive counterexample, and Lulla apart as an efficiency result. The [Arize IFScale replication](https://github.com/Arize-ai/instruction-budget/blob/main/IFSCALE_REPLICATION.md) is a separate origin; it reports very high constraint performance for frontier GPT-5.5 and excludes fast non-reasoning small models, so it is a bounded frontier-model counterpoint, not evidence about the priority class.

### Divergences kept open

1. **Constraint count lowers compliance, but file size and rule count showed no effect.** The first manipulates explicit constraints; the second manipulates repository files and measures coding success or one simple annotation. Not a direct contradiction about guide length.
2. **CFBench finds longer prompts positively associated with success; other benchmarks find the opposite.** Both are associational; explicitness, task mix and constraint type covary with length.
3. **Refined longer guidance helped one small-active-parameter model; other studies report nulls or cross-model harm.** Length was not separated from content. The evidence supports content and model fit, not a length effect.
4. **Context-fill failures and detailed-prompt benefits point opposite ways.** Both are anecdotes.

## 2. Weak points and suggested next step

- **The result does not decide the question.** No opened study compares a short principle-based guide with a longer prescriptive one on the same small, cheap model doing the same multi-step coding tasks. The collection reviewers accepted this gap; this is a map of positions, not a verdict for either style.
- "Length" means different things across the sources (words or tokens, number of constraints, lines in a file, total context, retrieved material) and cannot be combined into one length effect. Outcomes also differ (all-constraint compliance, issue resolution, tests, an annotation, runtime, tokens).
- Small-model evidence is strongest in adjacent instruction-count benchmarks and in one roughly 3B-active-parameter result. The most direct file-size study uses frontier Anthropic models and a narrow measure; the 17-task Khatri study cannot detect moderate effects.
- The Arize replication's raw outputs were not recalculated, and its lineup excludes the priority class. Lulla measures efficiency, not full correctness.
- User reports are self-selected and do not show prevalence, reproducibility or length as a cause.
- Outside the focus, not investigated: issue comments suggesting hooks or runtime enforcement; agent frameworks.

**Suggested next objective.** Because no direct comparison exists, the next unit could be a small test of our own: run the same few multi-step tasks on the cheap model with a short principle guide and with a longer prescriptive one, and compare.

## 3. Not consulted

- The OpenReview route to IFScale could not be opened, and the Pith Science IFScale review was not used. IFScale is consulted through the arXiv full text, so the failed route adds no separate evidence.
- An earlier Anthropic "Claude Code Best Practices" engineering URL returned an error and was replaced by the current official documentation. Secondary mirrors and summaries were not used where primary sources were opened.

## 4. Annex

- Google's [Gemini CLI page](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html) documents context-file discovery, concatenation and imports; it does not assess efficacy. OpenAI's AGENTS.md page documents discovery, nested guidance and a combined-size cap, which is an ingestion limit, not a performance threshold.
- *Building effective agents* also covers general agent complexity and tool-interface advice; its workflow and framework material is outside scope.
- The Gemini report anecdote, Databricks RAG tests, *Lost in the Middle* and the Breunig posts are retained as adjacent mechanisms, not direct repo-guide evidence.
- GitHub issues and Reddit threads are retained as anecdotal counterpoints.
- Collector A's first review returned the collection because "Building effective agents" was named in the map but absent from the source record; round 2 added it. Both final reviews passed.

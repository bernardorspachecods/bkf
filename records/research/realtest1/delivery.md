# Delivery: length and specificity of persistent guides and agent performance

**Objective.** Decide whether the research guides and briefs in this repo should stay short and principle-based, or need more rules. What the evidence says about long, prescriptive instructions versus short, principle-based ones, with priority on small, cheap models running multi-step tasks. A map of the positions.

## 1. The answer, by positions

The evidence separates three things that are easy to confuse: **constraint density** (how many requirements an agent must satisfy together), **context-file presence and content**, and **the file's length or prescriptiveness**. The collection has evidence about the first two. It does not compare short principle-based guides with long prescriptive ones directly, so results about more constraints or more context must not be read as results about guide length.

### Position 1. Keep always-loaded guidance selective, and specify the behavior that matters

- Anthropic's context-engineering guidance: a small, high-signal context that fully specifies expected behavior; start minimal and add requirements or examples in response to observed failures; avoid exhaustive edge-case lists; minimal does not mean vague or necessarily short (collector a, "Effective context engineering for AI agents," lines 31–50, 55–73, 98–101).
- Anthropic's support guidance: a short, signal-dense `CLAUDE.md` (commands, conventions, architecture, hard constraints, known gotchas), without what is discoverable elsewhere; add a rule after a repeated mistake. Its steering article says accumulated system instructions have diminishing returns and may be missed, especially when conflicting or in long sessions (collector b, sources 4–5, lines 65–105 and 157–167). These two are one institutional position, not two independent findings.
- Google: direct, concise, structured prompts with critical instructions first, and also specific instructions for agent execution, recovery and ambiguity; too many examples may overfit (collector a, "Prompt design strategies," lines 290–315, 348–350, 515–526, 635–657).
- OpenAI's GPT-6 Astra guidance: bloated or over-broad instructions can be truncated, load irrelevant material or overconstrain newer models; use progressive disclosure; the advice may not transfer to other model classes (collector a, lines 920–975).
- Synthesis: the sources converge on selecting for relevance and removing duplication while keeping concrete requirements tied to real failures. They give no performance threshold in words, and do not show that a principles-only file is best for small local agents.

### Position 2. Accumulating simultaneous constraints is a measurable risk, especially for weaker models

- AGENTIF: instruction following declines as instruction length and constraint count rise; above 6,000 words, all-constraints success approaches zero for the evaluated models. Conditional and tool-use constraints are weak points. The October 2026 leaderboard includes 1.5–4B open models, with all-constraints success of roughly 10–27%, though several exceed 50% on individual constraints (collector a, paper pp. 5–6 and 8–9; leaderboard lines 23–40, 93–98).
- IFScale: degradation as simultaneous instructions increase, even for strong models; the best frontier model reaches 68% at maximum density; earlier-instruction bias and latency trade-offs are also reported (collector a, abstract, lines 3–5).
- CELLO: large model- and task-specific differences; 7B/13B models do well on some instruction types but trail larger systems in aggregate (collector a, AAAI-24 proceedings, pp. 18190–18193).
- Synthesis: constraint accumulation is harder to satisfy jointly, and small models deserve particular attention. This supports caution about adding rules without a clear task need. It does not show that length alone caused AGENTIF's decline, or that trimming a repository guide improves task completion.
- Limits: AGENTIF's length buckets also differ in task and constraint content, and it is a constructed benchmark with an LLM judge; the leaderboard protocol differs from the paper's. IFScale's keyword task is not a persistent guide or an agent task. CELLO is not a tool-use benchmark.

### Position 3. Repository context can help or hurt, depending on quality, task and available documentation

- CTXbench ("Evaluating AGENTS.md"): no file, generated files and developer-written files, on SWE-bench and 138 tasks in 12 Python repositories. Generated files did not significantly improve average success and raised steps and cost by about 20–23%. Developer-written files showed a small, not statistically significant success gain over no file, and beat generated files. Agents followed the file's instructions (more tests, searches and reads). No correlation between file length and success or cost in the tested range. With other documentation removed, generated files improved performance (collector a, lines 3–23, 110–133, 150–176, 356–380; collector b, source 1, pp. 3–7).
- Codex efficiency study: on 124 small PR tasks in 10 repositories, a root `AGENTS.md` came with 28.64% lower median runtime and 16.58% fewer output tokens, with comparable task completion; correctness was checked by hand on a sample of 50 outputs (collector a, lines 3–5, 28; collector b, source 2, pp. 0–4).
- REALM ablation: no detectable correctness effect for no file, a full always-on file, or retrieval-style selective context; power-limited (15–17 tasks per agent, effects below 30 points not detectable). In one niche, a warning about slow tests reduced wall-clock time (collector b, source 3, README lines 216–236).
- Synthesis: context can change behavior and may improve efficiency; correctness effects are mixed, small or undetected. CTXbench is the only collected source that looks at file length directly, and it finds no relationship in its range. None isolates principle-based against prescriptive wording.
- Limits: CTXbench includes GPT-5.1 Mini and Qwen3-30B-Coder but not the cheapest 1–4B models; the efficiency study tests one Codex configuration and small PRs; REALM cannot establish a true null.

### Position 4. Multi-step outcomes depend on the agent and the evaluation setup, so local task testing matters

- IBM's Open Agent Leaderboard: the same model wrapped in different agents gives different success and cost. SWE-bench-Live archives trajectories for model-agent combinations but has no instruction-length intervention (collector a, lines 65–120 and 15–52).
- Erfi's local benchmark: Qwen3.5-4B scores 87% on its research-agent cases, against 94.4% for 9B and 12B models; all tested models failed a chained-tool case and stalled on a write-new-tests task. The author stresses testing against the actual protocol (collector a, lines 215–219, 233–257, 291–305).
- Community reports and an OpenAI Codex issue describe instruction drift or missed rules in long sessions; they are self-selected and uncontrolled. SmallCode's developer attributes a 4B result to tooling and feedback among other parts, without isolating instructions (collector a, community entries; collector b, source 6, issue lines 129–225, 258–335).
- Synthesis: benchmarks and local reports reinforce that outcomes depend on task and harness, not on a particular guide length. For small models, a local multi-step evaluation is a better basis for deciding whether a rule earns its context and adherence cost than an aggregate result from frontier models or another harness. This is a synthesis, not a tested prescription.

### Divergences kept open

1. **"More context is costly" versus "repository instructions improve efficiency."** CTXbench finds generated files raise steps and cost without average success gains; the Codex study finds lower runtime and output tokens with `AGENTS.md`. The agents, files, repositories and methods differ, and the Codex study tests presence, not length. Together they rule out both "always overhead" and "always beneficial".
2. **"Longer instructions hurt" versus "file length has no clear effect."** AGENTIF and IFScale report worse joint compliance as length and constraint density rise; CTXbench finds no length correlation in its range. Different interventions and outcomes: dense task instructions are not repository files whose useful content varies.
3. **"Keep guidance short" versus "specific instructions are needed."** Vendor guidance asks for concision and also for concrete requirements and examples for observed failures. Compatible if concision means removing low-value or duplicated material, not task-critical detail. The evidence does not give the balance for small local agents.
4. **Small models may be more vulnerable, but some do well on subsets.** AGENTIF's 1.5–4B models have low all-constraints rates; CELLO and Lexicanum show smaller models can do well on particular criteria or tasks. Model- and task-specific, not a size rule.

## 2. Weak points and suggested next step

- **Central gap.** No collected source randomizes small, cheap multi-step agents between short principle-based guides and longer prescriptive ones, holding content and task constant. The collection cannot settle the choice or give an optimal length.
- **Transfer.** Direct small-model evidence is strongest in AGENTIF's 1.5–4B leaderboard, which measures instruction compliance in constructed scenarios, not repository task success. The repository-file studies mostly test larger or proprietary configurations; CTXbench's Qwen3 model is 30B.
- **Causal ambiguity.** More words can mean more constraints, more examples, irrelevant context or useful detail; the studies do not consistently separate them.
- **Outcome mismatch.** Adherence, correctness, completion, runtime, tokens, tool steps and cost are not interchangeable; some correctness checks are sampled or low-powered.
- **Scope.** The findings concern agent prompts, repository files or context windows. They do not directly say what this repo's research guides and briefs should contain. Tool design and task decomposition came up often in the sources and were not investigated.
- **Saturation.** The final sources repeated the existing pattern, so the map of positions is saturated. The direct small-model comparison is not, and only that comparison would change the map.

**Suggested next objective.** A small test of our own: run the same few multi-step tasks on the cheap model with short principle-based guide variants and longer prescriptive variants, matched in content, and measure success, instruction violations, retries and steps, latency and tokens.

## 3. Not consulted

- Google Gemini Enterprise Agent Platform system-instructions introduction, beyond the Gemini API prompting page that was opened.
- AGENTIF run configurations and source repository (paper and leaderboard were consulted).
- Open Agent Leaderboard methodology paper and the Exgentic repository.
- SWE-bench-Live submission trajectories and benchmark repository.
- SmallCode repository and its 100 task records.
- Other surfaced Reddit threads and third-party explainers.
- Anthropic "Claude Code Best Practices," which could not be opened.
- Raw code, task or result files for the REALM and agenteval projects; claims here come from README and guide pages.

## 4. Annex

- Google Cloud "Use system instructions" and OpenAI "Agent definitions" describe instruction roles and configuration; they do not evaluate length or specificity.
- "Lost in the Middle" studies long-context retrieval and information position (including LongChat-13B and MPT-30B-Instruct); related context-window evidence, not a persistent-guide or agent comparison.
- Open Agent Leaderboard, SWE-bench-Live, local community discussions and the 4B system claim give evaluation context or anecdotes, no controlled guide-length result.
- The agenteval README and guide propose linting and task-based evaluation of instruction changes, with no performance result.
- Provenance: the AGENTIF paper and leaderboard count as one origin; Anthropic's pages as one position; the REALM README and project as one origin; community threads and issue comments are anecdotal. The independent empirical strands are AGENTIF, IFScale, CELLO, CTXbench, the AGENTS.md efficiency study and REALM.

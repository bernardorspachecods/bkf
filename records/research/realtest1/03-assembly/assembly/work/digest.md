# Digest: length and specificity in persistent research and agent guides

## Scope and central distinction

The evidence maps positions on whether persistent guides should remain compact and principle-led or accumulate explicit rules. The central distinction is between **constraint density** (how many requirements an agent must satisfy together), **context-file presence and content**, and **the file’s length or prescriptiveness**. The collection has evidence about the first two, but does not directly compare short principle-based guides with long prescriptive guides in small-model, multi-step tasks. Do not treat results about more constraints, more context, or context-file presence as if they measured guide length itself.

## Positions

### 1. Keep always-loaded guidance selective; specify the behavior that matters

- **Source position:** Anthropic’s context-engineering guidance recommends a small, high-signal context that fully specifies expected behavior, with enough specificity to avoid ambiguity. Start with a minimal prompt and add requirements or examples in response to observed failures; avoid exhaustive edge-case lists. It also cautions that minimal does not mean vague or necessarily short. *(Collector a, “Anthropic, Effective context engineering for AI agents,” passages at lines 31–50, 55–73, 98–101.)*
- **Source position:** Anthropic support guidance recommends a short, signal-dense `CLAUDE.md` with commands, conventions, architecture, hard constraints and known gotchas; remove information discoverable elsewhere and add a rule after a repeated mistake. Anthropic’s separate steering article says accumulated system instructions have diminishing returns and may be missed, especially when conflicting or during long sessions. These are one institutional position, not two independent empirical findings. *(Collector b, sources 4–5; “What actually belongs in it” / “How often to update it,” lines 65–105; steering article, lines 157–167.)*
- **Source position:** Google guidance favors direct, concise, structured prompts and prioritizing critical instructions, while also recommending specific instructions for agent execution, recovery and ambiguity handling. Clear examples can substitute for prose in some cases, but too many examples may overfit. *(Collector a, “Google, Prompt design strategies,” passages at lines 290–315, 348–350, 515–526, 635–657.)*
- **Source position:** OpenAI’s GPT-6 Astra engineering guidance warns that bloated or over-broad instructions can be truncated, load irrelevant material, or overconstrain newer models; it recommends progressive disclosure and notes the guidance may not transfer to other model classes. *(Collector a, “Rethinking skills and prompts for GPT-6 Astra,” lines 920–975.)*
- **Synthesis:** These vendor/practitioner sources converge on selecting for relevance and removing duplication, while retaining concrete requirements tied to real failures. They do not establish a performance threshold in words, nor demonstrate that a short principles-only file is optimal for small local agents.

### 2. Accumulating simultaneous constraints is a measurable risk, especially for weaker models

- **Source position:** AGENTIF’s paper reports declining instruction-following as instruction length and constraint count rise; at more than 6,000 words, all-constraints success approaches zero for evaluated models. Conditional and tool-use constraints are weak points, and examples improve performance against corresponding constraints without examples. The maintained October 2026 leaderboard includes 1.5–4B open models: displayed small models’ all-constraints success is roughly 10–27%, though several exceed 50% on individual-constraint success. *(Collector a, “AGENTIF,” paper pp. 5–6 and 8–9; leaderboard lines 23–40, 93–98.)*
- **Source position:** IFScale reports degradation as the number of simultaneous instructions increases, including for strong models, with only 68% accuracy for the best frontier model at maximum density. The abstract also reports earlier-instruction bias and latency trade-offs. *(Collector a, “IFScale,” abstract lines 3–5.)*
- **Source position:** CELLO finds substantial model- and task-specific differences on complex instructions; smaller 7B/13B models do well on some instruction types but trail larger systems in aggregate. *(Collector a, “CELLO,” AAAI-24 proceedings, pp. 18190–18193.)*
- **Synthesis:** Constraint accumulation appears harder to satisfy jointly than a selective set of requirements, and small models warrant particular attention because their aggregate instruction adherence is lower. This supports concern about adding rules without a clear task need; it does not show that length alone caused AGENTIF’s decline, or that trimming a repository guide improves task completion.
- **Important qualification:** AGENTIF’s length buckets also differ in task and constraint content; its constructed benchmark and LLM-judge evaluation have limits. The leaderboard’s current protocol is distinct from the original paper’s protocol. IFScale’s artificial keyword-inclusion task is not a persistent guide or multi-step agent task. CELLO is not a tool-use benchmark. *(Collector a, same source entries.)*

### 3. Repository context can help or hurt depending on quality, task, and available documentation

- **Source position:** CTXbench compares no file, LLM-generated files, and developer-written files across SWE-bench and 138 tasks in 12 Python repositories. Generated files did not significantly improve average success and raised steps and cost by about 20–23%; developer-written files showed a small, not statistically significant average success improvement over no file and beat generated files. Agents followed context-file instructions, doing more tests, searches and reads. The study found no correlation between context-file length and success or cost in its tested range. When other documentation was removed, generated files improved performance, suggesting context usefulness depends on what else is available. *(Collector a, “Evaluating AGENTS.md,” lines 3–23, 110–133, 150–176, 356–380; collector b, source 1, pp. 3–7.)*
- **Source position:** A separate paired study of Codex on 124 small PR tasks and 10 repositories reports 28.64% lower median runtime and 16.58% fewer output tokens with a root `AGENTS.md`, with comparable task-completion behavior. Correctness was manually sanity-checked on a sample of 50 outputs. *(Collector a, “On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents,” abstract/method lines 3–5, 28; collector b, source 2, pp. 0–4.)*
- **Source position:** The REALM project’s small ablation reports no detectable correctness effect for no file, full always-on file, or retrieval-style selective context. It is explicitly power-limited (15–17 tasks per agent; effects below 30 percentage points not detectable under its stated setup). In one task niche, a warning about slow tests reduced wall-clock time. *(Collector b, source 3, README lines 216–236.)*
- **Synthesis:** Context can change agent behavior and may improve efficiency; correctness effects are mixed, small, or undetected in these studies. Quality and documentation availability matter. CTXbench is the only collected source that analyzes file length directly, and it found no length relationship over its tested range. None isolates principle-based versus prescriptive wording.
- **Limits:** These are repository-context studies, not research-guide experiments. The CTXbench study includes GPT-5.1 Mini and Qwen3-30B-Coder but not the cheapest 1–4B local models. The efficiency study tests one Codex configuration and small PRs. The REALM sample cannot establish equivalence or a true null.

### 4. Multi-step outcomes depend on the agent and evaluation setup, so local task testing matters

- **Source position:** IBM’s Open Agent Leaderboard reports different success/cost outcomes for the same underlying model wrapped in different agents. SWE-bench-Live archives trajectories for model-agent combinations but provides no instruction-length intervention. *(Collector a, “Open Agent Leaderboard,” lines 65–120; “SWE-bench-Live,” lines 15–52.)*
- **Source position:** Erfi’s local benchmark reports Qwen3.5-4B at 87% on its research-agent cases versus 94.4% for 9B and 12B models; all tested models failed a chained-tool case and stalled on a write-new-tests coding task. The author emphasizes evaluation against the actual protocol and counting failure costs. *(Collector a, “Erfi’s Lexicanum,” lines 215–219, 233–257, 291–305.)*
- **Source position:** Community reports and an OpenAI Codex issue describe instruction drift or missed rules in long sessions, but are self-selected reports without controls. SmallCode’s developer claim attributes a 4B agent result to tooling and feedback among other components, without isolating instruction effects. *(Collector a, local-model community entries; collector b, source 6, issue lines 129–225, 258–335.)*
- **Synthesis:** Agent benchmarks and local reports reinforce task/harness dependence, not a particular guide length. For the priority model class, local multi-step evaluation is a better basis for deciding whether a targeted rule earns its context and adherence cost than transferring an aggregate result from frontier models or another harness. This is a synthesis, not a directly tested prescription.

## Divergences and reconciliation

| Apparent tension | What each side reports | Reconciliation and remaining uncertainty |
|---|---|---|
| “More context is costly” versus “repository instructions improve efficiency.” | CTXbench finds generated files can increase steps and cost without average success gains; the separate Codex study reports lower runtime and output tokens with `AGENTS.md`. | These studies differ in agents, files, repositories, tasks and method. The Codex study tests presence and selected guidance, not length; CTXbench finds effects depend on file quality and whether other docs exist. Together they rule out a blanket claim that repository context is always overhead or always beneficial. |
| “Longer instructions hurt” versus “file length has no clear effect.” | AGENTIF and IFScale report worse joint compliance as length/constraint density rises. CTXbench finds no correlation between repository-file length and success/cost in its tested range. | These are different interventions and outcomes. Constraint-dense task instructions are not the same as repository context files whose useful content may vary. The CTXbench null is bounded to its length range, agents and coding tasks; it does not negate constraint-following results. |
| “Keep guidance short” versus “specific instructions are needed.” | Vendor guidance favors concise, relevant context but also warns against vagueness and recommends concrete requirements/examples for observed failures or agentic execution. | The positions are compatible if concision means removing low-value or duplicated material, not removing task-critical detail. Evidence does not determine the optimal balance for small local agents. |
| Small models may be more vulnerable, but some perform well on subsets. | AGENTIF’s 1.5–4B models have low all-constraints rates and lower aggregate adherence; CELLO and Lexicanum show smaller models can perform well on particular criteria/tasks. | These results use different tasks, models, and metrics. They support model- and task-specific performance, not a universal size rule or a causal guide-length effect. |

## Weak points and evidence gaps

- **Central gap:** No collected source directly randomizes small, cheap multi-step agents between short principle-based persistent guides and longer prescriptive guides while holding content and task constant. The collection therefore cannot resolve the requested binary choice or quantify an optimal length.
- **Transfer gap:** Direct small-model instruction adherence evidence is strongest in AGENTIF’s 1.5–4B leaderboard, but it measures instruction compliance in constructed scenarios rather than repository task success. Repository-file studies mostly test larger or proprietary configurations; CTXbench’s Qwen3 model is 30B.
- **Causal ambiguity:** More words can mean more constraints, examples, irrelevant context, or useful details. The studies do not consistently separate these factors. AGENTIF’s bucket comparisons are confounded by task/constraint content; context-file studies mostly compare file presence or source/quality.
- **Outcome mismatch:** Adherence, correctness, completion, runtime, token use, number of tool steps, and cost are not interchangeable. A rule may improve one and worsen another. Some correctness checks are sampled or low-powered.
- **Scope:** Findings concern agent prompts, repository files, or context windows. They do not directly establish what the repo’s research guides and briefs should contain. The role of framework/tool design is outside this digest’s focus.
- **What would materially change the map:** A powered ablation on representative 1–4B multi-step tasks, comparing matched short principle-based and longer prescriptive guide variants, with success, instruction violations, retries/steps, latency and token cost measured. Until then, small-model transfer remains an open question.
- **Collector-reported outside-focus line:** Collector A notes that tool design and task decomposition frequently appear in sources but a full survey is outside scope. Collector B reports none investigated. No other outside-focus item was reported.

## Sources not consulted

The following were listed by collectors as not consulted; they are not evidence in this digest:

- Google Gemini Enterprise Agent Platform system-instructions introduction beyond the opened Gemini API prompting page.
- AGENTIF current run configurations and source repository; leaderboard and paper were consulted, but detailed per-model configs/task records were not.
- Open Agent Leaderboard methodology paper and Exgentic repository.
- SWE-bench-Live submission trajectories and benchmark repository.
- SmallCode repository and its 100 task records.
- Other surfaced Reddit threads and third-party explainers.
- Anthropic “Claude Code Best Practices,” which could not be opened.
- Raw code, task, or result files for the REALM and agenteval projects; their claims here come from opened README/guide pages.

## Annex material not used as position evidence

- Google Cloud’s “Use system instructions” and OpenAI’s “Agent definitions” describe instruction roles and configuration, but do not evaluate length or specificity effects. *(Collector a, vendor sources.)*
- “Lost in the Middle” studies long-context retrieval and information position, including models such as LongChat-13B and MPT-30B-Instruct; it is related context-window evidence, not a persistent-guide or agent-task comparison. *(Collector a, academic source.)*
- Practitioner benchmark platforms and reports (Open Agent Leaderboard, SWE-bench-Live, local community discussions, and the 4B system claim) provide evaluation context or anecdotal examples, but no controlled guide-length result. *(Collector a.)*
- The agenteval project README and getting-started guide propose linting and task-based evaluation of instruction changes, but supply no performance result. *(Collector b, source 7.)*

## Provenance and saturation

Repeated pages from one origin were counted together: AGENTIF paper and live leaderboard form one benchmark origin; Anthropic’s several pages form one institutional guidance position; the REALM README and its underlying project are one origin; community threads and issue comments are anecdotal rather than independent controlled studies. The empirical strands that matter for the map come from distinct origins: AGENTIF, IFScale, CELLO, CTXbench, the AGENTS.md efficiency study, and REALM.

The collectors report that their final sources repeated the existing conditional pattern: instruction/constraint accumulation can impair joint adherence; repository context can affect cost and sometimes efficiency or behavior; outcome depends on task, source quality, and harness. These independent origins are sufficient to map the positions. Saturation applies to this map of positions, not to the unresolved direct comparison for small-model persistent guides. Further generic context-length studies or repeated practitioner advice are unlikely to change it; a direct, adequately powered small-model guide ablation would.

# Brief: collection (collector a)

## Objective

- Use: decide whether the research guides and briefs in this repo should stay short and principle-based, or need more rules.
- What is sought: what the evidence says about long, prescriptive instructions versus short, principle-based ones, in agent performance. Delivery: a map of the positions.
- Priority: small, cheap models running multi-step tasks.
- Mode: focused.
- Out of scope: how to write conversational prompts, and agent frameworks.
- Enough when: the last sources, from independent origins, only repeat what is already there.

## Where to look
These are your niches. Another collector covers the rest, so stay inside these. "Counterweight" means look here for evidence against the common view; "(agent)" only says who suggested the niche and does not change what you do.

1. **Vendor docs and engineering posts on agent instructions.** Anthropic (Claude Code best practices, building effective agents, context engineering), OpenAI (agent guides, AGENTS.md), Google.
2. **Academic work on following many instructions or constraints, and on how instruction or context length affects performance.** arXiv, ACL/NeurIPS venues.
5. **Independent agent benchmark builders and evaluation platforms.** AgentIF (agentif.github.io), Open Agent Leaderboard (Hugging Face), SWE-bench-Live (swe-bench-live.github.io). They compare multi-step task performance across models and agent configurations, including instruction adherence and cost; useful for checking whether instruction-length effects generalize beyond a single provider. Counterweight: benchmark maintainers’ own task suites can reflect their design choices, so compare independent suites and inspect original task/evaluation repositories. (agent)
7. **Open-model and local-agent user evaluation communities.** Hugging Face model cards, leaderboard datasets and Community Evals; Reddit’s r/LocalLLaMA; independent local-model evaluation write-ups such as Erfi’s Lexicanum. Users publish model-size-aware runs of tool use and multi-step tasks under local cost and hardware constraints, providing a practitioner counterweight to provider claims. Counterweight. Treat anecdotal or self-selected runs as leads and prioritize linked datasets, harnesses, and original run records. (agent)

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf/new-research/research-collection.md (read-only). It says how to collect, what to record and when to stop. The objective above is the filter for what is relevant.

## Rules
- You need web access to open sources. If you cannot open web pages at all, stop and say so in your output; do not fill in from memory.
- Do not run git commands that change state, and do not edit any file other than your output file.

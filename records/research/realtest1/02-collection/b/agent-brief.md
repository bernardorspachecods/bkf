# Brief: collection (collector b)

## Objective

- Use: decide whether the research guides and briefs in this repo should stay short and principle-based, or need more rules.
- What is sought: what the evidence says about long, prescriptive instructions versus short, principle-based ones, in agent performance. Delivery: a map of the positions.
- Priority: small, cheap models running multi-step tasks.
- Mode: focused.
- Out of scope: how to write conversational prompts, and agent frameworks.
- Enough when: the last sources, from independent origins, only repeat what is already there.

## Where to look
These are your niches. Another collector covers the rest, so stay inside these. "Counterweight" means look here for evidence against the common view; "(agent)" only says who suggested the niche and does not change what you do.

3. **Practitioner write-ups on AGENTS.md / CLAUDE.md / system prompts for coding agents.**
4. **Issue trackers and discussions of agent tools,** where people report how the agent behaves with long instructions.
6. **Reproducible ablation projects on repository instruction files.** GitHub projects such as `codeprakhar25/context-files-coding-agents` and `lukasmetzler/agenteval`. These test whether adding, removing, or changing standing context instructions affects correctness and efficiency on real coding tasks, directly addressing prescriptive repository guidance. Counterweight: small task sets and a few tested agents may limit generalization, especially to small models. (agent)

## Role
Open and follow the role guide: /Users/bernardopacheco/bkf/new-research/research-collection.md (read-only). It says how to collect, what to record and when to stop. The objective above is the filter for what is relevant.

## Rules
- You need web access to open sources. If you cannot open web pages at all, stop and say so in your output; do not fill in from memory.
- Do not run git commands that change state, and do not edit any file other than your output file.

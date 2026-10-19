# Sources: collection (collector b)

Scope: niches 3, 4 and 6 in the brief. Access checked 2026-10-19. Findings below report what the opened sources establish; repository instructions vs principle-based guides are not directly compared in a controlled test among these sources.

## Sources opened

### 1. Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?

- **Location:** [arXiv:2602.11988](https://arxiv.org/abs/2602.11988) (paper PDF opened via [mirror](https://readwise-assets.s3.amazonaws.com/media/wisereads/articles/evaluating-agents-md-are-repos/1152.pdf)); sections 3–6, especially pp. 3–7 (PDF lines 292–325, 401–408, 433–485, 515–564, 613–653).
- **Niche:** 6, reproducible ablation; also relevant to 3 as empirical context-file evidence.
- **Origin/provenance:** Research-paper authors; AGENTBENCH tasks drawn from 5,694 PRs across 12 Python repositories. Separate origin from the other evaluations here.
- **Access:** Full text, PDF, 18 pages.
- **Finding:** Compares no context file, LLM-generated files, and developer-written files. Four agent/model configurations include GPT-5.1 Mini and Qwen3-30B-Coder. LLM-generated context reduced mean task success by 0.5 percentage points on SWE-Bench Lite and 2 points on AGENTBENCH, while increasing steps by 2.45 and 3.92 and average cost by 20% and 23%. Developer-written files increased success compared with no file for three of four agents on AGENTBENCH and outperformed generated files for all four agents there, but increased steps and cost (up to 19%). The sample of developer files was 12; the benchmark had 138 instances. The paper says context files generally changed behavior: instructions were usually followed and agents did more testing and repository exploration; overviews did not make discovery of relevant files meaningfully faster. Removing other documentation changed the comparison: generated files then improved success by 2.7% on average and beat developer-written files.
- **Establishes / does not establish:** Context-file presence and quality can affect process, cost, and correctness, but effects vary by task set, agent, and documentation availability. GPT-5.1 Mini is directly represented. This is not a length or prescriptiveness ablation: no short-principle vs long-rule comparison, and the authors note Python's prominence may reduce the need for repository context. It does not justify a general claim that more rules help or hurt.

### 2. On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents

- **Location:** [PDF, ICSE JAWs 2026](https://assets.empirical-software.engineering/pdf/jaws26-agents.md-efficiency.pdf); abstract pp. 0–1, method pp. 1–3, results pp. 3–4, lines 31–40, 139–213, 238–247, 273–358.
- **Niche:** 6, paired ablation of presence/absence of repository instruction files.
- **Origin/provenance:** Lulla et al., independent empirical study of Codex using gpt-5.2-codex; 10 repositories and 124 small merged PR tasks. Not the same study or dataset as source 1.
- **Access:** Full text, PDF, 5 pages.
- **Finding:** With vs without a root AGENTS.md, paired on the same task and repository snapshot, the study reports lower median wall-clock time (28.64%) and median output tokens (16.58%) with AGENTS.md, with comparable task-completion behavior. The paper's correctness evaluation is explicitly a manual sanity check of 50 sampled outputs, not a full correctness measure. It filtered for files covering conventions, architecture/structure, and project description; PRs were limited to at most 100 changed lines and five files.
- **Establishes / does not establish:** Selected repository guidance may reduce time and output tokens for this Codex setup and these small tasks. It does not isolate length or prescriptiveness; cannot determine whether short/principle-based or long/rule-heavy text caused the effect. One model/agent configuration and small-scope tasks limit generalization, especially to small models. Authors call for replication across models and study of specificity and workflow guidance.

### 3. Do Context Files Help Coding Agents? A Two-Agent Ablation Study on Real Repositories (code and data release)

- **Location:** [GitHub repository](https://github.com/codeprakhar25/context-files-coding-agents), README rendered at lines 216–236 and repository file listing at 179–208.
- **Niche:** 6, reproducible ablation project.
- **Origin/provenance:** Project/paper accepted at REALM Workshop @ EMNLP 2026 (as the README states); separate project origin from sources 1–2. Measures Claude Code and Codex CLI on real merged PR tasks from three Python repositories.
- **Access:** README full text; code/data files listed, not individually opened or executed in this collection.
- **Finding:** README reports three conditions (no file, full always-on file, retrieval-style selective split). Correctness rates were 53.3%, 55.6%, 55.6% for Claude Code on 15 tasks and 58.8%, 56.9%, 52.9% for Codex on 17 tasks. Within-task omnibus permutation tests found no detectable effect. The authors explicitly call the study power-limited: at roughly 15–17 tasks × 3 repeats, minimum detectable effect exceeded 30 percentage points; detecting 10 points at 80% power would require about 120 tasks. For OpShin tasks, Claude's slow full-suite runs decreased from 3.67 to 2.44 to 1.67 across conditions, with about 24% lower wall-clock time, attributed to a warning about slow tests in AGENTS.md.
- **Establishes / does not establish:** A small, transparent two-agent ablation reports no detectable correctness change, with a process-efficiency effect in one repository/task niche. The low sample size cannot establish equivalence or a true null. It compares context delivery strategies, not short versus long instructions. Small task set and only two agent products constrain transfer to small models.

### 4. Anthropic, “Give Claude context: CLAUDE.md and better prompts”

- **Location:** [Claude Help Center](https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts), “What actually belongs in it” and “How often to update it,” lines 65–105.
- **Niche:** 3, practitioner guidance on CLAUDE.md.
- **Origin/provenance:** Anthropic support documentation; independent of the empirical papers, but product guidance rather than an experiment.
- **Access:** Full page text.
- **Finding:** Recommends a short, signal-dense file (roughly under 200 lines), including commands, conventions, architecture summary, hard constraints, and known gotchas; excludes material discoverable in code, changelogs, and aspirational rules. Advises adding a rule after Claude makes the same mistake twice and periodically removing stale instructions. Notes prompt caching reduces repeated token billing but says file length still uses context space and affects signal-to-noise.
- **Establishes / does not establish:** Documents Anthropic's practitioner recommendation and its stated rationale. Does not provide measured performance evidence or address small models directly.

### 5. Anthropic, “Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents”

- **Location:** [Anthropic article](https://claude.com/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more), lines 157–167.
- **Niche:** 3, practitioner guidance on persistent coding-agent instructions.
- **Origin/provenance:** Anthropic staff-authored article (author disclosure at line 173); distinct page from source 4 but same organizational origin, so count as one institutional position when synthesizing.
- **Access:** Full page text.
- **Finding:** Says appended system instructions have diminishing returns and that increasing their number tends to reduce strict adherence, especially when they conflict. Recommends moving procedures to skills, narrowly applicable rules to path-scoped files, and reliable mandatory behavior to deterministic hooks/permissions; explains that CLAUDE.md rules can fail under long sessions, ambiguity, or prompt injection.
- **Establishes / does not establish:** A product practitioner's design advice and stated failure modes. No experiment or quantitative length threshold; not evidence that fewer rules always improve task success.

### 6. OpenAI Codex issue #25884: “AGENTS.md instructions can be read correctly but then applied inconsistently later in the same session”

- **Location:** [GitHub issue](https://github.com/openai/codex/issues/25884), issue description and reports at lines 129–225 and comments at 258–335.
- **Niche:** 4, issue-tracker report on behavior with repository instructions.
- **Origin/provenance:** One user report and subsequent commenters in the OpenAI Codex issue tracker; not a controlled evaluation. Reports include Codex CLI 0.136.0, GPT-5 family (exact model unspecified), and nested instruction files.
- **Access:** Full issue and discussion text.
- **Finding:** Reporter describes the model restating small, explicit mandatory rules early in a session but later missing them in multi-turn work. A commenter describes stale instructions after resuming a session with an edited AGENTS.md. Others propose reloading, tracking file hashes, or requiring active checklists; these are user comments/workarounds, not validated fixes.
- **Establishes / does not establish:** A documented practitioner complaint consistent with instruction retention/application being imperfect over long sessions. It does not test whether long files are worse than short files, establish prevalence, or isolate model capability from harness/context handling.

### 7. agenteval: project README and getting-started documentation

- **Location:** [GitHub project](https://github.com/lukasmetzler/agenteval) and [getting-started guide](https://github.com/lukasmetzler/agenteval/blob/main/docs/getting-started.md), especially lines 196–203 of the guide and README lines 239–259.
- **Niche:** 6, reproducible evaluation tooling; also a practitioner account of instruction-file bloat.
- **Origin/provenance:** Independent open-source tooling project by Lukas Metzler; its descriptions are project claims, not independent empirical findings. Same origin as its own lint documentation, if consulted.
- **Access:** Full README and guide text; source code was not run.
- **Finding:** Project frames instructions as accumulating bloat, overlap, contradictions, and stale references, and offers static checks plus a workflow to change instructions and re-run task evaluations. This documents an actionable test approach, not results demonstrating that long instructions lower performance.
- **Establishes / does not establish:** Researchers/practitioners can evaluate instruction changes against task outcomes instead of assuming benefit. The README/guide alone provides no effect estimate and no head-to-head short/long instruction result.

## Not consulted

- Anthropic “Claude Code Best Practices” search result: web open redirected to code.claude.com and returned an inaccessible fetch error; no finding taken from it.
- Other search-result Reddit threads and blogs: not opened because opened sources above provided primary practitioner guidance, a direct issue report, and stronger empirical evidence. Search snippets were not used as evidence.
- The two named GitHub projects' code, tasks, and raw result files were not downloaded or executed. Findings for source 3 derive from its opened README summary; source 7's project claims likewise are not independent experimental evidence.

## Stopping note

The last sources checked were the REALM project README and agenteval README/getting-started guide. The REALM README added a counterweight on correctness (no detectable effect, but severely power-limited) and a specific efficiency mechanism; agenteval added an evaluation workflow but no new performance result. Together with the two independent empirical papers, Anthropic's practitioner recommendations, and an issue-tracker report, later material encountered in these niches was repeating the same positions: context can guide behavior and sometimes improve efficiency, effects on correctness are mixed or small, and rules can be missed. I stopped without claiming saturation on the exact question of long prescriptive versus short principle-based guides: the opened sources do not directly test that comparison, and the small-model evidence remains limited to GPT-5.1 Mini/Qwen3-30B in one paper and the low-powered two-agent project.

## Outside the focus

- None investigated.

## Handoff

Implemented `run_review` and `ReviewResult` in [review.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/review.py), with fake-`codex` coverage in [test_engine_review.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_engine_review.py). Added tests in [test_engine_agentstep.py](/Users/bernardopacheco/bkf-engine/agent-skills/dispatch-codex/harness/tests/test_engine_agentstep.py) for exit-code substitution and trailing newline removal from quota text. `agentstep.py` already contained both fixes.

The brief puts prompt construction in `build_prompt(attempt)` and supplies `min_checked` explicitly; the bash builds the prompt itself and reads `min_checked` from a global. The module leaves prompt contents to the workflow, as requested.

**Verification**

- `python3 -m unittest discover -s tests` — 85 tests passed.
- `bkf skills` — valid; zero issues.
- In a throwaway copy, allowing a fourth review attempt made the attempt-cap test fail with `[1, 2, 3, 4]` instead of `[1, 2, 3]`.
- In throwaway copies, removing exit substitution and quota newline trimming each made its regression test fail.

**Outside the focus**

The checkout also contains unrelated modified and untracked files from other work. I left them untouched.
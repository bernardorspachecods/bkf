**Verification**

- `python3 -m unittest discover -s tests` — passed, 24 tests.
- `bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh` — passed.
- `bkf skills` — passed; status valid, 0 issues.
- The throwaway parity check failed as intended after I changed the Bash end marker to `<!-- intentionally wrong marker -->`. That change was temporary and is not in the diff; it is not reviewer-visible there.

**Left ready**

- [`inject.py`](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/inject.py) provides `inject_rules(prompt_path)` and preserves the Bash output bytes.
- [`cli.py`](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/harness/cli.py) supports `python3 -m harness inject PROMPT_FILE` with the requested exit codes.
- [`test_inject.py`](/Users/bernardopacheco/bkf-agents/agent-skills/skills/dispatch-codex/harness/tests/test_inject.py) covers the specified cases and parity with the three real guides.
- The Gate harness paragraph in the skill links to the new module and tests.

No differences from the brief; nothing outside the focus. Python syntax is kept to 3.9-compatible features; the checks ran under Python 3.15.
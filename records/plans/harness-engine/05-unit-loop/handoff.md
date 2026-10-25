## Verification

- `python3 -m unittest discover -s tests` — 98 tests passed.
- `bkf skills` — valid; 0 issues.
- `git diff --check` — passed.
- In a throwaway copy, I changed the gate cap to use `max_rounds`. The two caps test failed as expected: it escalated after 1 gate failure instead of 2. **Not checked by the reviewer:** this temporary failure demonstration is outside the diff.

## Left ready

- Added [loop.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/harness/engine/loop.py) and [test_engine_loop.py](/Users/bernardopacheco/bkf-engine/agent-skills/skills/dispatch-codex/harness/tests/test_engine_loop.py), covering implementation, gate, review, escalation, resume, and handoff behavior.
- Added links to both files in the dispatch-codex `Shared code` list.
- The loop follows the brief’s `base_from` behavior; the bash instead derives the base from the plan step, as the brief directs.

## Outside focus

- Other existing working-tree changes were left untouched.
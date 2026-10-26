## What I checked

- Result and ready contract: the new module, CLI route, and tests in `diff.patch`; compared injection behavior with `lib-inject.sh` and `test-inject.sh`.
- Scope: all files in `diff.patch`; changes are limited to the harness and the required `SKILL.md` links.
- Criteria: `inject.py` and `test_inject.py` against the brief; the supplied gate is accepted as passed and was not rerun.
- Leaves ready: `inject_rules(prompt_path)` and `harness inject PROMPT_FILE` are present in the diff. The throwaway-copy failure demonstration is not checked, as the brief directs.
- Review guidance: `plan-review.md`; root and area maps: `MAP.md` and `agent-skills/MAP.md`.

## Problems

1. **Criteria — shell parity differs for an absolute directive path.** In `inject.py`, `_requested_files` joins the guide directory and directive with `os.path.join(directory, relative)`. If `relative` begins with `/`, Python discards `directory` and may read that absolute file. The shell implementation uses `$dir/$rel`, which keeps the guide directory prefix and will fail if that nested path is missing. For example, with an existing `/tmp/rule.md` and a guide containing `<!-- inject: /tmp/rule.md -->`, Python may inject it while Bash looks under the guide directory. Add a parity test for this input and match the shell behavior.

VERDICT: back
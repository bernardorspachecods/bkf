# Gate

The harness ran these commands in /Users/bernardopacheco/bkf-agents, outside any agent.

Result: all green (3 commands).

### `cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests`

exit code: 0

~~~~
.........................
----------------------------------------------------------------------
Ran 25 tests in 9.786s

OK
~~~~

### `bash agent-skills/skills/dispatch-codex/scripts/test-inject.sh`

exit code: 0

~~~~
PASS no directive: the brief is unchanged
PASS no guide in the brief: unchanged
PASS one directive: succeeds
PASS one directive: the original text stays first
PASS one directive: the rule text is in the brief
PASS one directive: the frontmatter is not
PASS one directive: the brief says where the text came from
PASS second run: the brief is unchanged
PASS two directives: both texts, in order
PASS missing file: fails
PASS missing file: the message names the file
PASS missing file: the brief is unchanged
PASS not a .md file: fails
PASS codex_run: the agent receives the rule text
PASS codex_run: the recorded brief is what the agent read
PASS codex_run: a failed injection stops the agent from starting
PASS real guides: every directive resolves
PASS real guides: plan/plan-implementation.md brings determinism into the brief
PASS real guides: plan/plan-review.md brings determinism into the brief
PASS real guides: code-review/code-review-axis.md brings determinism into the brief
~~~~

### `bkf skills`

exit code: 0

~~~~
== . ==
all BKF map inventories are up to date
== workflow-types/code-review ==
all BKF map inventories are up to date
== workflow-types/council ==
all BKF map inventories are up to date
== workflow-types/plan ==
all BKF map inventories are up to date
== workflow-types/research ==
all BKF map inventories are up to date
status: valid
packages: 15
issues: 0
catalog: valid
~~~~

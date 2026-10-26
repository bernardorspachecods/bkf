# Gate

The harness ran these commands in /Users/bernardopacheco/bkf-agents, outside any agent.

Result: all green (10 commands).

### `cd agent-skills/skills/dispatch-codex/harness && python3 -m unittest discover -s tests`

exit code: 0

~~~~
...........................................
----------------------------------------------------------------------
Ran 43 tests in 11.209s

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

### `bash agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh`

exit code: 0

~~~~
PASS current briefs: only the unit that changed gets that section
PASS current briefs: the integration logs the difference once
PASS current briefs: the final review reads the same, and logs nothing
PASS same briefs: no received-brief section and no note
PASS changed gate: the integration notes that the unit passed against another gate
PASS changed gate: the integration runs the current gate
PASS missing brief: the run stops and says which brief is missing
PASS missing brief: no reviewer saw an integration
PASS final review: a plain unit shows the current brief and the received one
PASS lock: while the run works, .lock holds a pid
PASS lock: a second resume is refused and says who holds it
PASS lock: finish is refused while the run works, and the run folder is still there
PASS lock: the refused commands did not disturb the run
PASS lock: the lock is gone when the script ends
PASS lock: a lock with a dead pid is replaced
agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh: line 10: 90525 Terminated: 15          sleep 30
PASS lock: a live pid that is not a plan-run.sh does not hold the run
PASS rebase 1: the integration review escalated and the run stopped there
PASS rebase 1: succeeds, the base moved and the old one is kept
PASS rebase 1: status.log says what was subtracted and at which HEAD
PASS rebase 1: after resume the integration passes
PASS rebase 1: the integration diff holds the units and not the owner's files
PASS rebase 1: refused once the integration is closed
PASS rebase 1 control: without the command the owner's files are in the integration diff
PASS rebase 1: a file of a unit's diff edited in the checkout is refused, and the git message names it
agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh: line 387: 93344 Terminated: 15          bash -c 'exec -a plan-run.sh sleep 30'
PASS rebase: refused while a plan-run.sh holds the run
PASS rebase: a step that does not exist is refused
PASS rebase: a step that is not a group is refused
PASS rebase 1: the integrator ran in the stopped attempt
PASS rebase 1: refused after the integrator ran, and the message names --paths
PASS rebase 1: the integrator's rounds are now in an earlier attempt
PASS rebase 1: still refused when the integrator's rounds are in an earlier attempt
PASS paths: the integration stopped at its round cap after two integrator rounds
PASS paths: a file of a unit's diff is refused, naming the unit
PASS paths: absolute and .. paths are refused as bad paths, an unchanged path as nothing to do
PASS paths: accepted, the files that leave the diff are listed
PASS paths: status.log has the exact list
PASS paths: after resume the integration passes
PASS paths: the owner's plans/ and tests/ left the diff; the units' and the integrator's files stay
PASS goal: the integration brief holds the goal as it is when the integration starts
PASS goal: it says the goal adds no criteria to the briefs
PASS goal: the integration review prompt has it
PASS goal: the integrator prompt has it
PASS goal: the unit implementer and reviewer do not see it
PASS goal: a gate block in the goal is not run as a gate of the integration
PASS goal: missing goal stops the integration and says which file
PASS accept: the reason is required
PASS accept: an empty reason is refused
PASS accept: a step that does not exist is refused
PASS accept: a unit whose diff was never applied is refused, naming it
agent-skills/skills/dispatch-codex/scripts/test-plan-run-gate.sh: line 470: 98499 Terminated: 15          bash -c 'exec -a plan-run.sh sleep 30'
PASS accept: refused while a plan-run.sh holds the run
PASS accept: the group's worktrees are still there before it succeeds
PASS accept: closes the integration: marker and status written, worktrees removed
PASS accept: status.log says who, at which HEAD, why, and that nothing was reviewed
PASS accept: refused once the integration is closed
PASS accept: resume goes on to the final review
PASS accept: a unit that did not pass is refused, naming it
PASS accept: a step that is not a group is refused
PASS quota (implement): the run stops and status.log has the text after 'try again at', unparsed
PASS quota (implement): the reason says usage limit, not a bare exit code
PASS quota (review): the run stops and status.log has the text after 'try again at', unparsed
PASS quota (review): the reason says usage limit, not a bare exit code
PASS quota (report): the run stops and status.log has the text after 'try again at', unparsed
PASS quota (report): the reason says usage limit, not a bare exit code
PASS quota (integrate): named too
PASS quota: a message with no 'try again at' is kept whole, not guessed
PASS quota: another failure keeps its exit message and no QUOTA line
PASS disk: room for the rest (125000 KB needed, 200000 free): the group runs
PASS disk: status.log says what was measured and projected
PASS disk: 100000 KB per worktree, 110000 free: the margin makes 125000 needed, so the step is refused
PASS disk: the refusal says what the estimate leaves out
PASS disk: the refusal removes the worktrees it made and leaves no ready marker
PASS disk: after the space is back, resume runs the group
PASS disk: a measure that shows no consumption (noise) never refuses, and is reported as 0 MB, not a negative number
PASS progress green: all expected lines appear in order
PASS progress redfix: gate FAIL precedes round 2 implementation
PASS progress backs: the final back is followed by escalation
PASS progress group: names both units and reports each implementation
PASS progress group: integration stages are in order
PASS progress stdout: start keeps its exact output and progress does not leak to it
PASS progress gate cap: failure is followed by escalation and step stop
PASS progress pause: the completed step is followed by pause
PASS progress final stop: review and stop are reported without READY
PASS board sequential: start prints the initial board before the first step
PASS board sequential: finished units and final review are passed on stdout
Board sample from the finished sequential plan:
Plano r · 2 unidades · início 00:05 → agora 00:05

Passo 1
  ✓ 01-unit        passou · 1 ronda

Passo 2
  ✓ 02-unit2       passou · 1 ronda

  ✓ Revisão final  passou
PASS board parallel: both units and integration appear under the parallel step
PASS board gate back: round 2 shows the gate failure on stderr
PASS board stdout: start and resume preserve their exact stdout
~~~~

### `bash agent-skills/skills/dispatch-codex/scripts/test-review-run-gate.sh`

exit code: 0

~~~~
PASS green: the run is ready
PASS green: the command, its output and exit code 0 are recorded
PASS green: the reviewer and the checker folders hold gate.md
PASS green: the briefs point to gate.md
PASS green: the report shows the gate before the first axis
PASS green: the report says all green
PASS red: the run still finishes
PASS red: the exit code of the failing command is recorded
PASS red: the report names the red command
PASS red: a later green command is still run and recorded
PASS none: the run is ready
PASS none: the report says nothing was run and calls it a gap
PASS none: the report does not say all green
PASS cwd: the command ran in the repository
PASS cwd: the reviewer already had gate.md when it started
PASS hang: the run finishes quickly instead of waiting
PASS hang: the timeout is recorded as red
PASS resume: the gate ran once in all
PASS resume: the report is rebuilt with the gate
~~~~

### `bash agent-skills/skills/dispatch-codex/scripts/test-council-run-board.sh`

exit code: 0

~~~~
PASS finished: all steps and agents are checked
PASS board command: the board is printed on stdout
PASS start stdout: READY output is unchanged
PASS check stdout: verdict output is unchanged
Sample council board from the finished run:
Conselho finished · início 00:05 → agora 00:05

✓ Conselheiros
    ✓ contrarian
    ✓ first-principles
    ✓ expansionist
    ✓ outsider
    ✓ executor
✓ Pacote anónimo
✓ Revisores
    ✓ 1
    ✓ 2
    ✓ 3
    ✓ 4
    ✓ 5
PASS stopped review: the stderr board marks Revisores with ✗
PASS resume stdout: READY output is unchanged
PASS running: stderr shows an in-progress step
~~~~

### `bash agent-skills/skills/dispatch-codex/scripts/test-research-run-board.sh`

exit code: 0

~~~~
PASS finished: every step and collector is checked
PASS finished: renderer errors do not change the run exit code
PASS finished: the collector output file is present
PASS collector parsing: comments and blank lines are skipped
PASS board command: renderer errors do not change its exit code
PASS board command: the board is printed on stdout
PASS start stdout: READY output is unchanged
PASS start: the initial board precedes progress
PASS progress: the line is followed by a blank line and board
PASS running: stderr shows an in-progress step
Sample research board from the finished run:
Pesquisa finished · início 00:05 → agora 00:05

✓ Mapa
✓ Recolha
    ✓ primary
✓ Digest
PASS stopped collection: the stderr board has an in-progress line
PASS stopped collection: the step is crossed and the collector has no output marker
~~~~

### `bash agent-skills/skills/dispatch-codex/scripts/test-review-run-board.sh`

exit code: 0

~~~~
PASS finished: every step and axis agent is checked
PASS finished: renderer errors do not change the run exit code
PASS finished: both checkers are checked
PASS board command: renderer errors do not change its exit code
PASS board command: the board is printed on stdout
PASS start stdout: READY output is unchanged
PASS start: the initial board precedes progress
PASS progress: the line is followed by a blank line and board
PASS running: stderr shows an in-progress step
Sample review board from the finished run:
Revisão finished · início 00:05 → agora 00:05

✓ Revisores
    ✓ standards
    ✓ standards-2
    ✓ spec
    ✓ spec-2
✓ Verificação
    ✓ standards
    ✓ spec
PASS stopped check: the stderr board has an in-progress line
PASS stopped check: review passed and check is crossed
~~~~

### `test ! -e agent-skills/skills/dispatch-codex/scripts/lib-inject.sh`

exit code: 0

~~~~
~~~~

### `! grep -rn "lib-inject" agent-skills/skills/dispatch-codex/scripts`

exit code: 0

~~~~
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

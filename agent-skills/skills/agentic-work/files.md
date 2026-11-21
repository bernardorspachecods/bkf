# Agentic work: package files

For maintainers of this skill; a run does not need this page.

- Run commands shared by the scripts: [run-commands.md](run-commands.md).
- Role guides: [implementation](roles/agentic-work-implementation.md), [review](roles/agentic-work-review.md), [integration](roles/agentic-work-integration.md).
- Script driver (not mentioned in SKILL.md; read only when the user asks for a script run): [plan-run.sh](scripts/plan-run.sh), workflow definition [plan.py](scripts/plan.py), with [inputs and prompts](scripts/plan_inputs.py), [brief lint](scripts/plan_lint.py), [rehearsal](scripts/plan_rehearse.py), [integration recovery](scripts/plan_integration.py), [board and record](scripts/plan_board.py) and [task cards](scripts/plan_cards.py).
- Conversation driver: [plan-unit.sh](scripts/plan-unit.sh) with [plan_unit.py](scripts/plan_unit.py), and the launcher [delegate-run.sh](scripts/delegate-run.sh).
- Python tests, run with `PYTHONPATH=agent-skills/harness python3 -m unittest discover -s agent-skills/skills/agentic-work/tests`: [test_plan.py](tests/test_plan.py), [test_plan_inputs.py](tests/test_plan_inputs.py), [test_plan_lint.py](tests/test_plan_lint.py), [test_plan_rehearse.py](tests/test_plan_rehearse.py), [test_plan_board.py](tests/test_plan_board.py), [test_plan_layout.py](tests/test_plan_layout.py), [test_plan_isolation.py](tests/test_plan_isolation.py), [test_plan_integration.py](tests/test_plan_integration.py), [test_plan_group_integration.py](tests/test_plan_group_integration.py), [test_plan_unit.py](tests/test_plan_unit.py), [test_plan_cards.py](tests/test_plan_cards.py), with [shared support](tests/plan_test_support.py). Shell tests: [test-plan-run-gate.sh](tests/test-plan-run-gate.sh), [test-delegate-run.sh](tests/test-delegate-run.sh).
- Unit size: each script run records its implementation rounds in `<run>/metrics.tsv`; use it to correct the size ceiling in [plan.md](plan.md#1-the-goal-and-the-units).
- Invocation and display metadata: [agents/openai.yaml](agents/openai.yaml).

# Unit size measurements

First measurement of how long a plan's implementation rounds take, moved here from `agent-skills/skills/plan/run-reference.md`. It is one plan (17 units), one repository and one model, measured on 2026-10-20: a starting point, not a law. Correct these numbers after a plan.

The run records, for each implementation round, the minutes, the agent's steps, the files in the diff and the input tokens (`<run>/metrics.tsv`, and a table in `status.md` after `finish`).

- Rounds of 14 to 60 agent steps took 1 to 5 minutes.
- Rounds of 100 or more steps took 12 to 16 minutes. The slowest carried about 156 thousand input tokens per step, against 30 to 60 thousand usual.
- A unit that repeated a known pattern across nine files took 32 steps.

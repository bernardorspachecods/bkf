# Run summary

Run: realtest1

| Phase | Model and effort | Result | Rounds | Notes |
|---|---|---|---|---|
| 01-map | gpt-6-luna low | done | - | 3 niche(s) added by the agent |
| 02-collection | gpt-6-luna low | done | a: 1, b: 1 | attempt 1 stopped: a failed (reviewer wrote no problems.md), b passed after 2 rounds |
| 03-assembly | gpt-6-luna low | done | assembly: 1 | attempt 1 stopped: escalated after 2 rounds (the reviewer wrongly reported an entry as missing) |
| delivery review | gpt-6-luna low | pass | 1 | the first attempt failed: the reviewer reported it could not write problems.md |

The resumes and the delivery review were started with `-e xhigh`, but the script ignored the flag and
reused the effort saved by the first start, so the whole run was at low effort. Fixed in `research-run.sh`.

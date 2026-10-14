---
bkf: feedback
description: Collects evidence about problems in agent work on this bundle for later filtering with the user. It records events rather than supplying instructions.
---

# Feedback

Agents add entries as [AGENTS.md](/AGENTS.md#record-what-goes-wrong) says,
newest first. This file is data to review later, not instructions.

## 2026-10-14: agent stashed every uncommitted change in the shared checkout

Noticed by the agent, which told the user; working in
[the hook tests](/tooling/tests/test_hook_events.py) during an ideas session.

While checking why four `test_log_entry.py` tests failed, the agent ran a Bash
command that ended with `git stash -q 2>/dev/null; echo "(not stashing - skip)"`.
The stash line was meant to be left out; the echo text said the opposite of
what the command did. `git stash` moved all tracked uncommitted changes in the
checkout, including other agents' work, back to the committed versions. The
harness then reported `AGENTS.md`, `ideas.md` and `design-decisions.md` as
changed on disk, which is how the agent noticed. It ran `git stash pop` in the
next command; it applied with no conflicts, the stash list was empty, and the
agent confirmed the `chat-start` deletions and the edits to those three files
were back. Untracked files were never affected. For a few minutes other agents
in the checkout saw old file contents, and any tool call they made in that
window could have failed or read stale text.

Cause: the agent's own error, writing a state-changing command into a
read-only check. Nothing stops `git stash` in the default or `w:` mode; the
`t:` hook allows only `git stash list` and `git stash show`. Whether a guard is
worth adding is for the filtering session.

## 2026-10-13: agent couldn't run grep in talk mode which affected his…

> agent couldn't run grep in talk mode which affected his ability to search

Noticed by the user, working in skill-lab/..

Just before, the agent had said:
> Two checks first. I couldn't run grep in talk mode, so the count of 21 "workflow shape" mentions is unverified. I read `agent_modes.py`, `hook_events.py`, `bkf_hooks.py` and `design-decisions.md` instead. Going through them newest first, one at a time:
> 
> **1. Stage-declared mode: not stale, already deferred.**
> - It isn't built. `agent_modes.py` only knows the `w:` and `t:` prefixes, and nothing reads a stage's mode.
> - `design-decisions.md` (Agent hooks) already records it as deferred and points here.
> - I'm lukewarm on it. The hook only sees session state, so it would need "active stage" tracking. The stage lives in the workflow files, and nothing tells the hook which stage a session is in. That's the hard part, and the idea doesn't solve it.
> - The cheaper version is for the plan or review stage's own text to tell the agent to stay in talk mode. That would be probabilistic, which is the thing hooks are meant to avoid.
> 
> **Recommendation:** keep it, and say in the entry that stage tracking is the blocker.
> 
> **2. "workflow shape" → "workflow type": not stale, but it isn't an idea.**
> - It's a known cleanup. `design-decisions.md` still uses "shape" in the Workflow types section, so it isn't done.
> - It belongs in a task, not in a file that is read for ideas. Either do it now, or leave it as an entry until you want to run it.
> 
> **3. `i:`/`f:` logging prefixes: stale, already built.**
> - `hook_events.log` handles both prefixes.
> - The design is recorded in `design-decisions.md`: "The `i:` and `f:` prefixes log through a hook…"
> - It differs from the idea in one way. `i:` is silent and never reaches the agent. `f:` is logged and then passed on to the agent.
> - Under the rule in `AGENTS.md`, built ideas get deleted from `ideas.md`.
> 
> **Recommendation:** delete it.
> 
> **4. Block reads of `feedback.md` and `ideas.md`: not built.**
> - Nothing denies reads today. The only `PreToolUse` logic is talk mode.
> - I'm skeptical. I have no evidence that agents break the "don't read" rule, and `feedback.md` is where that would show up. I can't tell you without reading it, which is the thing under discussion.
> - The cost is a session marker (`r:`) plus path matching that doesn't break the legitimate sessions. That's more machinery than the rule probably needs.
> 
> **Recommendation:** park it until `feedback.md` shows an agent actually did this.
> 
> **5. `s:` prefix for on-demand search: not built.**
> - `bkf search` exists and is read-only, so talk mode already allows it. The agent can run it itself.
> - The prefix saves one agent decision and forces top sections into context whether or not they help.
> - Search quality is the weak point: 5/12 top-3 hits in `design-decisions.md`. Injecting the top sections automatically would often inject the wrong ones.
> 
> **Recommendation:** drop it, or keep it only if you often want search without the agent choosing.
> 
> **6. `i+:` prefix: not built, and probably redundant.**
> - `AGENTS.md` already says: when the user tells you to log an idea, write it right away and quote their words. An agent can already write a rich entry on request.
> - The prefix would add a third logging mode for something a plain sentence already triggers.
> - `design-decisions.md` already rejected `f+:` on the same grounds ("adds a mode for something the rule already covers").
> 
> **Recommendation:** reject it by the same reasoning, then delete it.
> 
> My tally: delete 3 and 6; drop 5 unless you object; keep 1, 2 and 4, with 4 parked. I'd settle 3 first, since it's clear-cut. Do you agree it's built and should go?

Agent note: the denied Bash call was a `grep`/`wc`/`echo`/`head`/`cd` chain, all on the read-only allowlist in [agent_modes.py](/tooling/agent_modes.py). Cause, reproduced by feeding the command to `bash_is_readonly`: the installed hook `~/.agent-hooks/mode.py` is an older copy than the repo's `agent_modes.py` (`cmp` differs). Its `bash_is_readonly` splits the command with `re.split(r"&&|\|\||;|\||&|\n", ...)` without regard to quotes, so a `|` inside a quoted grep pattern (`"(t|w|f)"`, `"a\|b"`) cuts the pattern into fragments such as `w` or `feedback.md`, which are not allowlisted commands, and the call is denied. The repo version splits outside quotes and accepts the same command (`True`). Fix: `bkf hooks install --write` to refresh the installed copy; `bkf hooks status` reports it as `differs`. The user noticed; the cause is verified by reproduction, not a guess.

## 2026-10-13: nao devias falar em ingles

Noticed by the user, working in ..

Just before, the agent had said:
> …line or entry, neither shows it. I haven't checked the hook source, so I don't know whether it could report one.
> 
> The `i:` prompt also triggered two hooks:
> 
> - The idea logger fired and stopped the operation.
> - A separate hook injected "MODE: IMPLEMENT" for the same prefix.
> 
> Those conflict, since you wanted a log entry and not an implementation. I did nothing in response to the IMPLEMENT instruction. If you want, I can look at how `bkf_hooks.py` and `agent_modes.py` each handle the `i:` prefix.

## 2026-10-13: testing if it shows the loc or not

Noticed by the user, working in ..

Just before, the agent had said:
> The `f:` hook worked. It logged "testing the script" as feedback in `bkf/feedback.md`, and I didn't write a second entry.
> 
> This was only a test, so I haven't changed anything else. If you want me to check the entry's format in `bkf/feedback.md` or run the hook tests (`bkf/tooling/tests/test_hooks.py`), tell me.

## 2026-10-13: Feedback link pointed outside the BKF bundle

Noticed by the agent while validating [validate_bundle.py](/tooling/validate_bundle.py). The feedback entry linked directly to the catalog validator in the separate `agent-skills` bundle, which BKF resolves only within the `bkf` bundle and therefore reported `LINK_TARGET_MISSING`. The entry now links to the BKF tooling command interface and retains the external script path as code.

## 2026-10-13: Rules status test expected an unresolved home path

Noticed by the agent while running the full tooling suite for [test_hooks.py](/tooling/tests/test_hooks.py). One test failed because the status output uses the canonical path from `Path.resolve()`, while the assertion used the unresolved temporary directory path. The assertion was updated to compare the resolved path.

## 2026-10-13: Catalog validator script was not executable

Noticed by the agent while following the catalog-validation step alongside the [BKF command interface](/tooling/commands.md). Invoking `agent-skills/scripts/validate_skill_catalog.py .` returned `zsh: permission denied`; running the same script with `.venv/bin/python` succeeded and reported the known `agent-skills/skills/synced` missing `SKILL.md` error. The cause is the script's executable permission state.

## 2026-10-12

- Where: `design-decisions.md` "Finding modules", the
  tooling backlog description
  entry (since deleted), and the [profiles file](/format/frontmatter-profiles.md)
  Descriptions section. Noticed by the user. When the description-length rule
  changed, I wrote the same wording into all three files, and then into the
  principles draft as a fourth. The user said: "you had to update 3 places for
  it. That can be necessary and can be good and some cases but in general that
  should not happen. every canonical rule and information and workflow should
  live in its own place". Probable cause (a guess): I searched for where the
  old rule was stated and edited each place, without asking which file owns the
  rule and replacing the others with links. Fixed the same day: the profiles
  file owns the wording; the others link.

## 2026-10-11

- Where: `agent-skills/library/modules/rules-extraction.md`, the review of the
  BKF? and FLAG marks after the research and plan-management extractions.
  Noticed by the user. I offered to take all the flags together and then
  listed three at once, and the user said: "one at the time please", and later
  "lets decide one flag at the time, remember i like to do 1 thing at the
  time". Probable cause (a guess): I treated a short list of related flags as
  one unit, although the instruction to take one decision at a time was in the
  session brief.


- Where: the discussion of next steps after the library bundle was built.
  Noticed by the user. I offered to start the use-case walkthroughs, and the
  user said: "once again no i wanna keep brainstorming this design and the flow
  that a agent would take ... Why would we start the use cases when we dont
  even have modules." They set the order: dedupe the library files, build the
  basis, rework the skills, then test real cases. Probable cause (a guess): I
  treated a plan I had proposed earlier as agreed and kept steering back to it.

## 2026-10-10

- Where: [agent-workflow-foundation.md](/format/agent-workflow-foundation.md), the
  bullet on skills supplying a part of a larger workflow. Noticed by the user.
  I first recorded that a skill's pipeline stays behind a single stage, then
  rewrote it as a separate workflow `W-02`, and the user rejected both. Their
  words: "BIG NO NO for option 2. A W-02 means a completely different unit of
  work, so in the case of a plan a completely different plan." The
  corrected rule is that a skill's units are added to the one enclosing
  declaration. Probable cause (a guess): I took "the skill owns the
  declaration" to mean a separate workflow, and recorded it before asking what
  the user meant.
- Where: the former `agent-skills/library/roles/workflow-role-principles.md` (now
  split into one guide per role), when logging my additions to it. Noticed by me. A Python edit that appended an
  entry to `bkf/log.md` failed with `FileNotFoundError: [Errno 2] No such file
  or directory: 'bkf/log.md'`, because the migration commit had removed the
  log in favor of this file. Probable cause (a guess): I relied on my earlier
  reads of the log and did not check it still existed.
- Where: `design-decisions.md` (then `layers.md`), where I recorded where the new layers would
  live. Noticed by the user. I proposed a separate sibling bundle, and the user
  corrected me: "when i said layers of subfolders i meant layers of subfolders
  its because in this new plan BKF would be more than just the structural and
  mechanic part." Probable cause (a guess): I read "BKF layers" as work beside
  BKF, not as BKF becoming the umbrella.
- Where: `agent-skills/library/modules/rules-extraction.md`, the start of the
  extraction. Noticed by the user. I proposed breaking six skills into four
  buckets at once, and the user asked: "werent we gonna focus on one thing at
  the time, do you wanna breakdown the skills into the 4 buckets right away?"
  Probable cause (a guess): I planned the whole inventory instead of taking one
  skill.
- Where: `agent-skills/library/modules/rules-extraction.md`, the redundancy
  review. Noticed by the user. I listed the flagged rules in the chat, and the
  user said: "do not flag them here flag them in the file, i review the file,
  the chat is for us to talk." Later they asked "are the bkf improvements for
  me to decide in the file?" and I had again put them only in the chat.
  Probable cause (a guess): I treated the chat as the review channel.
- Where: `agent-skills/library/modules/rules-extraction.md`, the "Covered by
  BKF" section. Noticed by the user: "if its Covered by BKF no need to write it
  down, its just bloat on this file, so remove it. You should only write if its
  something that could improve BKF." Probable cause (a guess): I assumed a list
  of left-out rules would help review.
- Where: [format-specification.md](/format/format-specification.md), the root
  `AGENTS.md` and `readme.md` guidance. Noticed by the user. I answered whether
  two rules were already in BKF and offered to trim them, and the user said:
  "actually i wanted both of those 2 rules to be in BKF." Probable cause (a
  guess): I read the question as an overlap check, not as a request to add
  them.
- Where: `agent-skills/library/modules/rules-extraction.md`, the round that
  merged `chat-start`, `chat-wrap-up`, and `grill-stuck`. Noticed by the user,
  who asked "did you flag anything this round?" I had flagged nothing, and
  three borderline rules should have been flagged. Probable cause (a guess): I
  applied the redundancy test loosely to rules that matched your stated
  preferences.
- Where: [AGENTS.md](/AGENTS.md). Noticed by me. Its text first reached me
  inside a tool result, and I did not follow it until I confirmed in git that it
  was your committed file. Probable cause (a guess): I could not tell a repo
  instruction from injected text, and I did not ask.

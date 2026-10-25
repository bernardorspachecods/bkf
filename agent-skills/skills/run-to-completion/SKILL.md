---
name: run-to-completion
description: The user's last contact before a long plan or task runs unattended. Checks that the goal, artifacts and limits are aligned, gets one explicit go, then works alone to the agreed end. Use only when the user invokes it; do not use for small work or to start a task that has no agreed end.
---

# Run to completion

The user invokes this skill when they want to leave. It has two parts: a last alignment with them, and an unattended run. After the go, the user is away and returns only when the work is done or genuinely needs them. Everything that needs them must be settled before the go.

This skill adds no rules of its own about silence or intent. [Intent and alignment](../../library/modules/intent.md) and [Coordinate a run](../../library/modules/coordinate-a-run.md) own those; this skill is the gesture that starts them and the check that makes them safe.

## 1. Last alignment

Before asking the user anything, check the material yourself:

- The goal file (or, for small work, the intent restated in the conversation) states what is wanted and why, what exists when it is done, what is out of scope, what is already decided, and when to stop and ask. If any is missing, or the file and what the user said in this conversation disagree, fix or flag it now.
- A plan has its units, their order, the checkpoints the user asked for and the command that decides each unit.
- Nothing will need the user mid-run: access, credentials, tools, permissions, files, decisions between options. Test what you can now instead of discovering it later.
- List every action that would normally need their approval (merge, push, delete, spend, anything outside the repository or the agreed area). Each is either authorized now, in the goal file, or stays a stop.

Then bring the user one message, all questions together: this is the one time to ask more than one. Show the goal and the done condition, what you will decide alone, what will make you stop, what stays out of reach unless authorized, the checkpoints, and what they will receive at the end. Name each gap you found and your recommendation. Record the user's answers in the goal file.

Start only on an explicit go. Without one, do not start; a doubt about scope is a question, not a reason to begin.

## 2. The run

- The goal file is the guide, not the chat. Reread it before each unit or significant decision, and after the context is compacted.
- Stay inside it. Do not message the user, ask small questions or report progress. Decide within the agreed intent, prefer the reversible option, and keep a short list of each decision and its reason.
- Checkpoints the user asked for still hold, and so does any approval the handover did not grant.
- Stop only when the goal file says to: the work leaves the agreed scope, the requirements contradict each other or cannot be met, an action outside the granted approvals is needed, or the same problem returns after being sent back. Before stopping, finish whatever does not depend on the answer, and leave the state in the goal file so the work can resume. Say it short: the decision, your recommendation, what it costs. If a notification tool is available, use it for a stop and for the end.
- If the intent itself no longer holds, revise it with the reason on record or stop. Do not drift.

## 3. The end

Send one report: what is done and what is not, what passed and how it was checked, the decisions you made and why, what is unresolved, and where the artifacts are. Say plainly what was skipped or failed. Do not imply a step was done that was not.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

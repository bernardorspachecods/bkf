---
name: run-to-completion
description: The user's last contact before a long plan or task runs unattended. Checks that the goal, artifacts and limits are aligned, gets one explicit go, then works alone to the agreed end. Use only when the user invokes it; do not use for small work or to start a task that has no agreed end.
---

# Run to completion

The user invokes this skill when they want to leave. It has two parts: a last alignment with them, and an unattended run. After the go, the user is away and returns only when the work is done or genuinely needs them. Everything that needs them must be settled before the go.

This skill adds no rules of its own about silence or intent. [Intent and alignment](../../library/modules/intent.md) and [Coordinate a run](../../library/modules/coordinate-a-run.md) own those; this skill is the gesture that starts them and the check that makes them safe.

## 1. Last alignment

Before asking the user anything, check the material yourself against what the workflows in use require. The intent is complete by the standard of [Intent and alignment](../../library/modules/intent.md); a plan or run is complete by the standard of its own guide, and its settings, checkpoints and stop conditions are read from there, not assumed. Check also that the artifacts agree with each other and with what the user said in this conversation, and fix or flag any gap now.

Then check what could still need the user: access, credentials, tools, permissions, files, decisions between options. Test what you can now instead of discovering it mid-run. Find every action that would normally need their approval and decide for each whether it is authorized now, in the artifacts, or stays a stop.

Bring the user one message, all questions together: this is the one time to ask more than one. Show what will be done and when it is done, what you will decide alone, what will make you stop, what stays out of reach unless authorized, and what they will receive at the end. Name each gap you found with your recommendation. Record the answers in the artifacts the work follows.

Start only on an explicit go. Without one, do not start; a doubt about scope is a question, not a reason to begin.

## 2. The run

- The agreed artifacts guide the work, not the chat. Reread them before each significant decision and after the context is compacted.
- Silence, checkpoints, verification and escalation follow [Coordinate a run](../../library/modules/coordinate-a-run.md) and the workflow's own guide. This skill changes one thing: the user has already given their last answer, so there is nobody to ask.
- Decide within the agreed intent and prefer the reversible option. Keep a short list of each decision and its reason.
- Stop only where the artifacts say to stop, or where an action needs an approval the handover did not grant. Before stopping, finish what does not depend on the answer and leave the state written down so the work can resume. Say it short: the decision, your recommendation, what it costs. If a notification tool is available, use it for a stop and for the end.
- If the intent itself no longer holds, revise it with the reason on record or stop. Do not drift.

## 3. The end

Send one report: what is done and what is not, what passed and how it was checked, the decisions you made and why, what is unresolved, and where the artifacts are. Say plainly what was skipped or failed. Do not imply a step was done that was not.

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

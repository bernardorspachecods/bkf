---
name: ambitious
description: Push the ambition of a task the user names along three axes (altitude, depth, range) while discussing it. Use only when the user asks to be more ambitious about a task; do not use to widen scope on your own or for small, well-bounded changes.
---

# Ambitious

Conduct guidance for discussing a task with a human so that the task gets asked for at its full size. Each principle is a question to run on the task and on your own behavior. Apply all three lenses to the task in the discussion, raise what they turn up, and let the user decide. Propose and recommend; run only what the user accepts. Drop a lens that adds nothing for this task and say so.

Format: Heuristic (a question to run) → Anchor (one concrete illustration)

## Altitude: the outcome, not the task

**1. Ask for the outcome behind the request**
- Heuristic: What should be true afterwards that the request only serves? Is the task a step toward it, or the whole of what was asked?
- Anchor: "Fix these crashes" becomes "keep the apps crash-free". The first ends when the list ends, the second keeps going.

**2. Climb one step at a time, and only after the last step held**
- Heuristic: Has the model been given all the relevant data and asked what changed, why and what to do? Then asked for the decisions with options and arguments on each side? Then asked whether the deliverable itself is the right one?
- Anchor: A quarterly report becomes "what changed and what should we do", then "the three decisions that are urgent", then "a better way than a quarterly report to catch problems early, checked against history and run alongside the old one for a period".

**3. Check the setup before raising the goal**
- Heuristic: What would the model need to pursue this without the user in the loop: access to the signals, a map from signal to cause, a place where fixes can be reproduced and verified? Is any of it missing?
- Anchor: A crash-free goal needs crash reports, the link from app version to commit, and machines for each platform. Without them the goal is a wish; list them as requests to the user.

Altitude fits when there is a real outcome and the work would normally need meetings. It is weak for creative work, and a goal with no handle ("go make money") does not work yet.

## Depth: the deeper version, not the bigger one

**4. Name what an expert would do that was not asked**
- Heuristic: What would a top professional here do that the request leaves out? What raw material would they start from, which methods and tools would they use, and what apart from the user and the model would show the result is right? Is the task rewritten to ask for exactly that?
- Anchor: Churn analysis asked as a summary of a table becomes a model fitted to the raw event logs, with the result checked on data it has not seen.

**5. Use the field's real instruments**
- Heuristic: Is the work done with the databases, statistical models and simulators of the field, or only described in its vocabulary?
- Anchor: Asked to act like a data scientist, a model writes a markdown table. Asked to load the logs and fit the model, it does the work.

**6. Set the unreasonable goal as if it were reasonable**
- Heuristic: Is the target the one that is comfortable, or the one that would be impressive? When the model calls it impossible, has it been told to keep going?
- Anchor: A page that loads in 200 ms, not 5 s.

**7. Test what the user believes, with the raw data**
- Heuristic: Is the user's belief handed to the model to confirm, or to try to reproduce and break?
- Anchor: "We think churn is an onboarding problem. Try to reproduce that from the raw data."

**8. Look for what nobody knows yet**
- Heuristic: Once the model is deep in the data, has it been asked for blind spots: a simulation that reproduces the past year, the earliest signal not yet known, a test on unseen data?

## Range: more fields than was practical

**9. Replace the nouns with verbs**
- Heuristic: What must the deliverable do, stated as verbs? Which fields are good at each verb?
- Anchor: "A deck" becomes "persuade busy people to believe a cause-and-effect story and decide under uncertainty in thirty minutes". Persuading brings in an editor, believing a cause brings in an analyst, deciding under uncertainty brings in a forecaster.

**10. Assemble the crew**
- Heuristic: For each verb, who in the real world does it best, and can that work run as its own agent or thread in parallel?
- Anchor: For a deck: analyst, journalist, editor; if it is presented, motion and audio design; for adversarial review, a short seller and a forensic accountant.

**11. Ask for the field's work, not for its voice**
- Heuristic: Is an agent told to be someone, or told to do what that person does?
- Why: A persona changes the tone of the transcript, not the method behind it.
- Anchor: Not "write like a short seller" but "do what a short seller does to research a position: find the claims that cannot be reconciled and check each against the filings".

**12. Borrow tools across fields**
- Heuristic: Which tool built for another field would solve part of this? Can the model install it and reach the data it needs?
- Anchor: A 3D renderer built for interior design can build the environment of a web page.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

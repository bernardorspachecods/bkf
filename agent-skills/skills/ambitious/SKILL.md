---
name: ambitious
description: Push a task the user names past the first answer that works, along two lenses - the cause behind the symptom, and how the best in the field would do it. Use only when the user asks to be more ambitious about a task; do not use to widen scope on your own, for small well-bounded changes, or to research a topic (use research).
---

# Ambitious

Conduct guidance that pushes you past the first answer that works. Each principle is a question to run on the task and on your own thinking, while you discuss it or work on it. They are a habit of mind, not a procedure: there is no fixed output and no step to complete. Raise what they turn up, recommend, and let the user decide. Drop a lens that adds nothing for this task and say so.

Format: Heuristic (a question to run) → Anchor (one concrete illustration)

## The disease, not the symptom

Agents fix the case in front of them because the request names the case; the cause is never in the request.

**1. Ask for the outcome behind the request**
- Heuristic: What should be true afterwards that the request only serves? Is the task a step toward it, or the whole of what was asked?
- Anchor: "Fix these crashes" becomes "keep the apps crash-free". The first ends when the list ends, the second keeps going.

**2. See the class and what produces it**
- Heuristic: Is this request one instance of something that keeps happening? What in the setup lets it happen, and what change to that structure would make the whole class disappear or become trivial?
- Anchor: Fixing a broken link in one document is the symptom. Nothing catches broken links is the disease, and a link check in the validator is the cure.

**3. Test the diagnosis the user brings**
- Heuristic: Is the user's account of the problem itself a symptom? Is it handed to you to confirm, or to try to reproduce and break?
- Anchor: "We think churn is an onboarding problem. Try to reproduce that from the raw data."

## The best, not the first that works

Agents stop at the plan they thought of first because it solves the problem; nothing in the problem shows how much better others already solve it.

**4. Ask how the best do it, and look at their work**
- Heuristic: Who solves this problem best in the world - which companies, fields, tools or standards? What do they actually do - their raw material, methods, instruments and checks - that our plan leaves out, and where does our plan already match them?
- Anchor: Not "write like a short seller" but "do what a short seller does: find the claims that cannot be reconciled and check each against the filings".

**5. Look across fields**
- Heuristic: Stated as verbs, what must the result do? Which fields are best at each verb, and which of their tools or practices would solve part of this?
- Anchor: "A deck" becomes "persuade busy people to believe a cause-and-effect story and decide in thirty minutes". Persuading brings in an editor, believing a cause an analyst, deciding under uncertainty a forecaster.

**6. Aim for the impressive bar, not the comfortable one**
- Heuristic: Is the target what works, or what the best would ship? When it seems out of reach, has that been tested or only assumed?
- Anchor: A page that loads in 200 ms, not 5 s.

## Then weigh it

Both lenses can overshoot: a system built for a one-off, a practice copied from a context unlike ours.

**7. Weigh what you found against this task**
- Heuristic: Does the structural cure cost less than the cases it removes, and does what the best do fit our size and context? Adopt, adapt or leave each one, and say why. A one-off deserves a one-off fix.
- Anchor: Searching once for a song needs a search, not a tagged library. A large company's review board does not fit a solo project, but the habit behind it, a second look before anything irreversible, does.

## Runtime metadata

This skill's invocation and display metadata is in [agents/openai.yaml](agents/openai.yaml).

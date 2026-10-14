---
bkf: document
description: "Sets the standing agent instructions for this bundle: when to record problems in feedback.md or ideas in ideas.md, and how design work is run."
tags: [bkf, agents]
---

# Agent instructions

## Record what goes wrong

Add an entry to [feedback.md](/feedback.md), at the top just below its
introduction so the newest comes first, when any of these happens:

- the user corrects your work;
- a command or the validator fails in a way you did not expect;
- an instruction or document is ambiguous or contradicts another, and you had
  to guess;
- a review sends your work back;
- you are blocked.

Write one entry per problem: the date, a link to where it happened (the file,
skill, or workflow stage), and what happened, with the evidence. Say when a
cause is a guess, and say who noticed the problem: the user or you. Do not log
secrets, and do not read the file during ordinary work; it is reviewed in
filtering sessions with the user.

When the user tells you to log something, write the entry right away and quote
their words as the evidence. Do not decide first whether it is worth recording;
that is for the filtering session.

A prompt that starts with `f:` is logged by a hook and never reaches you. An
entry the hook writes holds the date, the user's words, the working folder, and
your last message, and omits the link above; the filtering session adds more.
To discuss or fix the problem right away, the user asks you directly.

## Record ideas

Add an entry to [ideas.md](/ideas.md), at the top just below its introduction
so the newest comes first, when you notice something worth doing
later that is outside the current task. Do not act on it or raise it mid-task;
the user and agent review ideas together in dedicated ideas sessions.

Write one entry per idea: the date, the idea, who raised it (the user or you),
and where it came up. Do not read the file during ordinary work.

When the user tells you to log an idea, write it right away and quote their
words.

A prompt that starts with `i:` is logged by a hook and never reaches you. An
entry the hook writes holds the date, the user's words, the working folder, and
your last message, and omits the place it came up; the ideas session adds more.

When an idea is built or merged into a decision, put the outcome in
the document that owns it, and
delete the entry from [ideas.md](/ideas.md). When it is rejected, delete the
entry and record nothing, not even the reason. Do this in the ideas session where
the user settles it.

## Design work

Take design work one decision at a time, and settle each before moving to the
next. Record decisions and flags in the file the user reviews, not only in the
chat.
